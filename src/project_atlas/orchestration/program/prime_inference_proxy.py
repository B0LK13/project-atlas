"""Mission-scoped, inference-only relay for a local Ollama endpoint.

The worker never receives the Ollama management socket.  This host-side
component accepts only the two OpenAI-compatible paths Prime needs for a text
session and forwards bytes to one fixed loopback address.  It is deliberately
not a general HTTP proxy and does not accept a configurable upstream.
"""

from __future__ import annotations

import json
import os
import socket
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

MAX_HEADER_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 8 * 1024 * 1024
ALLOWED_PATHS = frozenset({"/v1/models", "/v1/chat/completions"})


def stored_tool_offer(request: dict[str, Any] | None, name: str) -> bool | None:
    """Inspect an explicitly supplied stored request, never a relay audit.

    AS-PRIME-TOOLCALL-DIAGNOSTICS-001: absence of request evidence is unknown;
    a complete OpenAI request omitting tools did not offer one.
    """
    if request is None:
        return None
    tools = request.get("tools", [])
    if not isinstance(tools, list):
        return None
    names = []
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("function"), dict):
            return None
        function = tool["function"]
        if tool.get("type") != "function" or not isinstance(function.get("name"), str):
            return None
        names.append(function["name"])
    return name in names


class InferenceProxyError(RuntimeError):
    """A request was rejected or the fixed local upstream failed."""


class InferenceOnlyUnixProxy:
    """Forward a bounded inference request over a mission-owned Unix socket."""

    def __init__(
        self,
        socket_path: Path,
        *,
        upstream_host: str = "127.0.0.1",
        upstream_port: int = 11434,
        audit_path: Path | None = None,
        max_requests: int = 40,
        max_total_output_tokens: int = 16_000,
    ) -> None:
        if upstream_host != "127.0.0.1" or upstream_port != 11434:
            raise ValueError("the Ollama upstream is intentionally fixed")
        self.socket_path = socket_path
        self._upstream = (upstream_host, upstream_port)
        self._audit_path = audit_path
        self._max_requests = max_requests
        self._max_total_output_tokens = max_total_output_tokens
        self._request_count = 0
        self._reserved_output_tokens = 0
        self._accounting_lock = threading.Lock()
        self._inference_slot = threading.BoundedSemaphore(1)
        self._server: socket.socket | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("proxy already started")
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        with suppress(FileNotFoundError):
            self.socket_path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        server.listen(8)
        server.settimeout(0.2)
        self._server = server
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        with suppress(FileNotFoundError):
            self.socket_path.unlink()

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                connection, _ = self._server.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            threading.Thread(
                target=self._handle,
                args=(connection,),
                daemon=True,
            ).start()

    def _handle(self, client: socket.socket) -> None:
        method = "unknown"
        target = "unknown"
        with client:
            try:
                request = _read_request(client)
                method, target, headers, body = request
                path = target.split("?", 1)[0]
                if path not in ALLOWED_PATHS or (
                    method != "GET" and path == "/v1/models"
                ) or (method != "POST" and path == "/v1/chat/completions"):
                    raise InferenceProxyError("management or unsupported path denied")
                if method == "GET" and path == "/v1/models":
                    if body:
                        raise InferenceProxyError(
                            "model catalog GET does not accept a request body"
                        )
                    output_budget = 0
                else:
                    body, output_budget = _bound_model_request(
                        body, self._max_total_output_tokens
                    )
                if not self._reserve_request(output_budget):
                    raise InferenceProxyError(
                        "pilot inference request or output budget exhausted"
                    )
                if not self._inference_slot.acquire(timeout=1):
                    raise InferenceProxyError("pilot allows one inference at a time")
                upstream_request = _build_upstream_request(method, target, headers, body)
                try:
                    with socket.create_connection(self._upstream, timeout=10) as upstream:
                        # The 10-second bound applies only to connecting to
                        # the fixed local service. CPU-only model generation
                        # may stream for longer; the Atlas deadline is outer.
                        upstream.settimeout(None)
                        upstream.sendall(upstream_request)
                        _relay(upstream, client)
                finally:
                    self._inference_slot.release()
                self._audit("forwarded", method, target)
            except (InferenceProxyError, OSError, ValueError) as exc:
                self._audit(type(exc).__name__, method, target)
                # The client sees a deterministic denial, never an upstream
                # error that could be mistaken for a successful model result.
                with suppress(OSError):
                    client.sendall(
                        b"HTTP/1.1 403 Forbidden\r\n"
                        b"Content-Length: 0\r\n"
                        b"Connection: close\r\n\r\n"
                    )

    def _reserve_request(self, output_budget: int) -> bool:
        with self._accounting_lock:
            if self._request_count >= self._max_requests:
                return False
            if self._reserved_output_tokens + output_budget > self._max_total_output_tokens:
                return False
            self._request_count += 1
            self._reserved_output_tokens += output_budget
            return True

    def _audit(self, event: str, method: str, target: str) -> None:
        if self._audit_path is None:
            return
        record = {"event": event, "method": method, "target": target.split("?", 1)[0]}
        try:
            with self._audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        except OSError:
            pass


def _read_request(
    client: socket.socket,
) -> tuple[str, str, list[tuple[str, str]], bytes]:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        if len(data) >= MAX_HEADER_BYTES:
            raise InferenceProxyError("request headers exceed limit")
        chunk = client.recv(min(4096, MAX_HEADER_BYTES - len(data)))
        if not chunk:
            raise InferenceProxyError("request ended before headers")
        data.extend(chunk)
    header_bytes, body = bytes(data).split(b"\r\n\r\n", 1)
    lines = header_bytes.decode("iso-8859-1").split("\r\n")
    try:
        method, target, version = lines[0].split(" ", 2)
    except ValueError as exc:
        raise InferenceProxyError("invalid HTTP request line") from exc
    if version != "HTTP/1.1":
        raise InferenceProxyError("only HTTP/1.1 is supported")
    headers: list[tuple[str, str]] = []
    content_length: int | None = None
    chunked = False
    expect_continue = False
    for line in lines[1:]:
        if ":" not in line:
            raise InferenceProxyError("invalid HTTP header")
        name, value = line.split(":", 1)
        name = name.strip()
        value = value.strip()
        if name.lower() == "transfer-encoding":
            if value.lower() != "chunked":
                raise InferenceProxyError("unsupported transfer encoding")
            chunked = True
        if name.lower() == "content-length":
            content_length = int(value)
        if name.lower() == "expect" and value.lower() == "100-continue":
            expect_continue = True
        if name.lower() not in {
            "connection",
            "host",
            "transfer-encoding",
            "expect",
            "content-length",
        }:
            headers.append((name, value))
    if chunked and content_length is not None:
        raise InferenceProxyError("ambiguous request body framing")
    if expect_continue:
        client.sendall(b"HTTP/1.1 100 Continue\r\n\r\n")
    if chunked:
        body = _read_chunked_body(client, body)
        content_length = len(body)
    if content_length is None:
        content_length = 0
    if content_length < 0 or content_length > MAX_REQUEST_BYTES:
        raise InferenceProxyError("request body exceeds limit")
    while len(body) < content_length:
        chunk = client.recv(min(65536, content_length - len(body)))
        if not chunk:
            raise InferenceProxyError("request ended before body")
        body += chunk
    if len(body) != content_length:
        raise InferenceProxyError("request body framing is invalid")
    return method, target, headers, body


def _bound_model_request(body: bytes, total_output_limit: int) -> tuple[bytes, int]:
    """Set or reject the model output cap without exposing prompt contents."""
    try:
        document = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InferenceProxyError("inference request must be JSON") from exc
    if not isinstance(document, dict):
        raise InferenceProxyError("inference request must be a JSON object")
    field = "max_completion_tokens" if "max_completion_tokens" in document else "max_tokens"
    requested = document.get(field, 512)
    if not isinstance(requested, int) or isinstance(requested, bool) or requested < 1:
        raise InferenceProxyError("inference output limit is invalid")
    bounded = min(requested, total_output_limit)
    document[field] = bounded
    # Ollama enables Qwen3 thinking by default.  The OpenAI-compatible API
    # supports the documented `reasoning_effort: none` control; make the
    # selected low-resource pilot profile explicit while preserving a caller's
    # deliberate setting.
    document.setdefault("reasoning_effort", "none")
    return (
        json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        bounded,
    )


def _read_chunked_body(client: socket.socket, initial: bytes) -> bytes:
    """Decode bounded HTTP chunks; the upstream request is never chunked."""
    data = bytearray(initial)
    output = bytearray()
    while True:
        while b"\r\n" not in data:
            if len(data) > MAX_REQUEST_BYTES:
                raise InferenceProxyError("chunked request exceeds limit")
            chunk = client.recv(4096)
            if not chunk:
                raise InferenceProxyError("chunked request ended before size")
            data.extend(chunk)
        size_line, remainder = bytes(data).split(b"\r\n", 1)
        try:
            size = int(size_line.split(b";", 1)[0], 16)
        except ValueError as exc:
            raise InferenceProxyError("invalid chunk size") from exc
        if size < 0 or len(output) + size > MAX_REQUEST_BYTES:
            raise InferenceProxyError("chunked request exceeds limit")
        data = bytearray(remainder)
        while len(data) < size + 2:
            chunk = client.recv(65536)
            if not chunk:
                raise InferenceProxyError("chunked request ended before data")
            data.extend(chunk)
        if data[size : size + 2] != b"\r\n":
            raise InferenceProxyError("invalid chunk terminator")
        output.extend(data[:size])
        data = data[size + 2 :]
        if size == 0:
            return bytes(output)


def _build_upstream_request(
    method: str,
    target: str,
    headers: list[tuple[str, str]],
    body: bytes,
) -> bytes:
    lines = [f"{method} {target} HTTP/1.1", "Host: 127.0.0.1:11434"]
    # Framing is owned by this serializer after the body has been rewritten.
    # Keep this invariant at the final boundary too: callers/tests may provide
    # headers that did not come directly from _read_request.
    lines.extend(
        f"{name}: {value}"
        for name, value in headers
        if name.lower() not in {"content-length", "transfer-encoding", "connection"}
    )
    lines.append(f"Content-Length: {len(body)}")
    lines.append("Connection: close")
    return ("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1") + body


def _relay(source: socket.socket, destination: socket.socket) -> None:
    while True:
        chunk = source.recv(65536)
        if not chunk:
            return
        destination.sendall(chunk)
