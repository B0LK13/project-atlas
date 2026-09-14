"""Narrow adapter for the pinned Prime Agent RPC runtime.

This module owns only Prime's process and wire framing. Atlas still owns task
admission, leases, budgets, acceptance, verification, and continuation. The
adapter deliberately does not claim that an RPC response means the task ran:
the ``prompt`` response is an ACK for acceptance/queueing, while ``agent_end``
is the runtime's terminal execution event.
"""

from __future__ import annotations

import hashlib
import json
import os
import select
import selectors
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Final
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from project_atlas.orchestration.program.adapters.base import (
    AdapterCapabilities,
    AdapterOutcome,
    AdapterRequest,
    AdapterUnavailableError,
    build_child_env,
    process_start_identity,
)
from project_atlas.orchestration.program.models import ExecutionConfidence, FailureClass
from project_atlas.orchestration.program.profiles import (
    AdapterKind,
    AgentProfile,
    CredentialMechanism,
)

ADAPTER_ID: Final[str] = AdapterKind.PRIME_AGENT.value
ADAPTER_VERSION: Final[str] = "prime-agent-atlas-adapter-v1"
PRIME_UPSTREAM_SHA: Final[str] = (
    "5d25a44bd22e1c1fe8321e141cd6c3932563d14c"
)
DEFAULT_EXECUTABLE: Final[str] = "prime-agent"
DEFAULT_MAX_FRAME_BYTES: Final[int] = 512 * 1024
LOCAL_ONLY_MODES: Final[frozenset[str]] = frozenset({"local-only"})
SUPPORTED_SANDBOX_LAUNCHER: Final[str] = "/usr/bin/bwrap"
REQUIRED_BWRAP_OPTIONS: Final[frozenset[str]] = frozenset(
    {
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--proc",
        "--dev",
        "--tmpfs",
        "--ro-bind",
        "--chdir",
    }
)
SENSITIVE_BWRAP_BIND_SOURCES: Final[tuple[Path, ...]] = (
    Path("/"),
    Path("/home"),
    Path("/root"),
)
CHILD_ADMISSION_PATCH_ID: Final[str] = (
    "prime-agent-5d25a44-atlas-child-admission-v1"
)
CHILD_ADMISSION_PATCH_SHA256: Final[str] = (
    "226405200865db6f677e846da420d2fa7c04e8b42d5bef8b77c1ffffb7416dba"
)
PILOT_MEMORY_MAX_BYTES: Final[int] = 6 * 1024**3
PILOT_CPU_QUOTA_PERCENT: Final[int] = 400
PILOT_MIN_AVAILABLE_BYTES: Final[int] = 2 * 1024**3


class PrimeFrameError(ValueError):
    """A malformed or unsafe Prime JSONL record."""


class PrimeFrameParser:
    """Strict LF JSONL parser for Prime RPC stdout.

    ``str.splitlines`` is intentionally not used: it treats U+2028 and U+2029
    as line boundaries even though Prime permits them inside JSON strings.
    """

    def __init__(self, *, max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> None:
        if max_frame_bytes < 2:
            raise ValueError("max_frame_bytes must be at least 2")
        self._max_frame_bytes = max_frame_bytes
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> list[dict[str, Any]]:
        self._buffer.extend(chunk)
        if len(self._buffer) > self._max_frame_bytes and b"\n" not in self._buffer:
            raise PrimeFrameError("frame exceeds configured maximum")
        records: list[dict[str, Any]] = []
        while True:
            try:
                end = self._buffer.index(0x0A)
            except ValueError:
                break
            raw = bytes(self._buffer[:end])
            del self._buffer[: end + 1]
            if raw.endswith(b"\r"):
                raw = raw[:-1]
            if len(raw) > self._max_frame_bytes:
                raise PrimeFrameError("frame exceeds configured maximum")
            if not raw:
                continue
            try:
                value = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise PrimeFrameError(f"invalid JSON frame: {exc}") from exc
            if not isinstance(value, dict):
                raise PrimeFrameError("RPC frame must be a JSON object")
            records.append(value)
        if len(self._buffer) > self._max_frame_bytes:
            raise PrimeFrameError("frame exceeds configured maximum")
        return records

    def finish(self) -> None:
        """Reject an unterminated partial record at stream end."""
        if self._buffer:
            raise PrimeFrameError("stream ended with an incomplete frame")


class PrimeChildAdmissionBroker:
    """Atlas-owned gate for native Prime child creation.

    The broker is deliberately a small local IPC boundary, not a scheduler.
    It reserves a bounded number of child slots for one already-admitted Atlas
    attempt and records the child lifecycle. The Prime compatibility patch
    calls it before creating a native child; a missing or invalid reply fails
    the spawn closed.
    """

    protocol_version = 1

    def __init__(
        self,
        socket_path: Path,
        *,
        mission_id: str,
        task_id: str,
        attempt_id: str,
        parent_session_id: str,
        max_children: int,
        role: str,
        scope_hash: str,
        max_child_seconds: int,
        max_child_tokens: int | None,
        max_budget_seconds: int,
        child_models: list[str],
        max_child_depth: int = 1,
        journal_path: Path | None = None,
        candidate_sha: str | None = None,
        tree_sha: str | None = None,
        workspace_identity: str | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> None:
        if max_children < 1 or max_child_seconds < 1 or max_budget_seconds < max_child_seconds:
            raise ValueError("child admission limits are invalid")
        if max_child_tokens is not None and max_child_tokens < 1:
            raise ValueError("max_child_tokens must be positive")
        if not role or len(scope_hash) != 64:
            raise ValueError("child admission role and scope are required")
        # Fail closed: admission without an explicit model allowlist or with a
        # non-positive recursion depth is a configuration error, not a default.
        if (
            not isinstance(child_models, list)
            or not child_models
            or any(not isinstance(model, str) or not model.strip() for model in child_models)
        ):
            raise ValueError("child_models must be a non-empty list of model names")
        if (
            not isinstance(max_child_depth, int)
            or isinstance(max_child_depth, bool)
            or max_child_depth < 1
        ):
            raise ValueError("max_child_depth must be an integer >= 1")
        self.socket_path = socket_path
        self.journal_path = journal_path or socket_path.with_suffix(".jsonl")
        self.candidate_sha = candidate_sha
        self.tree_sha = tree_sha
        self.workspace_identity = workspace_identity
        self.mission_id = mission_id
        self.task_id = task_id
        self.attempt_id = attempt_id
        self.parent_session_id = parent_session_id
        self.max_children = max_children
        self.role = role
        self.scope_hash = scope_hash
        self.max_child_seconds = max_child_seconds
        self.max_child_tokens = max_child_tokens
        self.max_budget_seconds = max_budget_seconds
        self.child_models = list(child_models)
        self.max_child_depth = max_child_depth
        self._fencing_token = 0
        self._reserved_budget_seconds = 0
        self.cancel_requested = cancel_requested
        self.records: list[dict[str, Any]] = []
        self._slots = threading.BoundedSemaphore(max_children)
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._server: socket.socket | None = None

    def bind_parent_session(self, session_id: str) -> None:
        if not session_id:
            raise ValueError("parent session id must not be empty")
        self.parent_session_id = session_id

    def start(self, *, timeout_seconds: float = 2.0) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.socket_path.unlink(missing_ok=True)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        self.journal_path.touch(mode=0o600, exist_ok=True)
        os.chmod(self.journal_path, 0o600)
        self._thread = threading.Thread(
            target=self._serve,
            name="atlas-prime-child-admission",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout_seconds):
            self.close()
            raise PrimeDaemonError("child admission broker did not become ready")

    def close(self) -> None:
        self._stop.set()
        server = self._server
        if server is not None:
            server.close()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self.socket_path.unlink(missing_ok=True)

    def wait_until_idle(self, timeout_seconds: float) -> bool:
        """Wait until every reserved child has sent a terminal release."""
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while time.monotonic() < deadline:
            if not self.records or all(record["phase"] == "released" for record in self.records):
                return True
            if self.cancel_requested is not None and self.cancel_requested():
                return False
            time.sleep(0.05)
        return not self.records or all(record["phase"] == "released" for record in self.records)

    def _journal(self, event: str, record: dict[str, Any]) -> None:
        payload = {
            "event": event,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "parent_session_id": self.parent_session_id,
            "candidate_sha": self.candidate_sha,
            "tree_sha": self.tree_sha,
            "workspace_identity": self.workspace_identity,
            "record": record,
        }
        with self.journal_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _deny(
        self, request: dict[str, Any], *, code: str, message: str
    ) -> dict[str, Any]:
        """Refuse a request after journaling the denial (fsync) for audit."""
        phase = request.get("phase")
        entry = {
            "phase": phase if isinstance(phase, str) else None,
            "denial": code,
            "reason": message,
            "request_digest": hashlib.sha256(
                json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()[:24],
        }
        # The wire denial below still fails closed even if the audit journal
        # itself cannot be written.
        with suppress(OSError):
            self._journal("denied", entry)
        return {"ok": False, "denial": code, "error": message}

    def _bind_parent_session(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Match or adopt the parent session binding; first-seen wins.

        While ``parent_session_id`` is unbound (the Atlas session id is only
        known after the daemon answers ``create``), the first request's value
        becomes the binding; later mismatches are refused.
        """
        incoming = request.get("parent_session_id")
        if self.parent_session_id:
            if incoming != self.parent_session_id:
                return self._deny(
                    request,
                    code="BINDING_REFUSAL",
                    message="child admission binding mismatch: parent_session_id",
                )
            return None
        if not isinstance(incoming, str) or not incoming:
            return self._deny(
                request,
                code="BINDING_REFUSAL",
                message="child admission requires a parent session binding",
            )
        self.parent_session_id = incoming
        try:
            self._journal("parent_bound", {"parent_session_id": incoming})
        except OSError:
            return self._deny(
                request,
                code="JOURNAL_REFUSAL",
                message="child admission parent binding could not be journaled",
            )
        return None

    def _serve(self) -> None:
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server = server
        try:
            server.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            server.listen(8)
            server.settimeout(0.2)
            self._ready.set()
            while not self._stop.is_set():
                try:
                    connection, _ = server.accept()
                except TimeoutError:
                    continue
                except OSError:
                    break
                with connection:
                    self._serve_connection(connection)
        finally:
            self._ready.set()
            server.close()
            self._server = None

    def _serve_connection(self, connection: socket.socket) -> None:
        connection.settimeout(2.0)
        parser = PrimeFrameParser(max_frame_bytes=64 * 1024)
        try:
            raw = bytearray()
            while b"\n" not in raw and len(raw) <= 64 * 1024:
                chunk = connection.recv(min(64 * 1024 - len(raw), 64 * 1024))
                if not chunk:
                    break
                raw.extend(chunk)
            records = parser.feed(bytes(raw))
            parser.finish()
            if len(records) != 1:
                raise PrimeFrameError("child admission requires one JSONL request")
            response = self._handle(records[0])
        except (OSError, PrimeFrameError, ValueError) as exc:
            response = {"ok": False, "error": str(exc)[:512]}
        # The client vanished before the reply; the decision is already
        # journaled, and the retry will be answered from the journal path.
        with suppress(OSError):
            connection.sendall(
                (json.dumps(response, ensure_ascii=False, sort_keys=True) + "\n").encode()
            )

    def _handle(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("protocol") != "atlas-prime-child-admission":
            return self._deny(
                request, code="PROTOCOL_REFUSAL", message="unsupported child admission protocol"
            )
        if request.get("version") != self.protocol_version:
            return self._deny(
                request, code="PROTOCOL_REFUSAL", message="unsupported child admission version"
            )
        for key, expected in (
            ("mission_id", self.mission_id),
            ("task_id", self.task_id),
            ("attempt_id", self.attempt_id),
            ("role", self.role),
            ("scope_hash", self.scope_hash),
        ):
            if expected and request.get(key) != expected:
                return self._deny(
                    request,
                    code="BINDING_REFUSAL",
                    message=f"child admission binding mismatch: {key}",
                )
        if self.cancel_requested is not None and self.cancel_requested():
            return self._deny(
                request, code="CANCELLED", message="child admission stopped by Atlas"
            )
        parent_denial = self._bind_parent_session(request)
        if parent_denial is not None:
            return parent_denial
        phase = request.get("phase")
        if phase == "reserve":
            name = request.get("name")
            prompt_digest = request.get("prompt_sha256")
            if not isinstance(name, str) or not name.strip():
                return self._deny(
                    request, code="NAME_REFUSAL", message="child name is required"
                )
            if not isinstance(prompt_digest, str) or len(prompt_digest) != 64:
                return self._deny(
                    request, code="PROMPT_REFUSAL", message="child prompt digest is required"
                )
            if request.get("max_child_seconds") != self.max_child_seconds:
                return self._deny(
                    request,
                    code="DEADLINE_REFUSAL",
                    message="child deadline does not match Atlas reservation",
                )
            if request.get("max_child_tokens") != self.max_child_tokens:
                return self._deny(
                    request,
                    code="TOKEN_REFUSAL",
                    message="child token limit does not match Atlas reservation",
                )
            # MODEL_REFUSAL / RECURSION_REFUSAL: children only run explicitly
            # admitted models and must stay below the admitted recursion depth.
            model = request.get("model")
            if not isinstance(model, str) or not model.strip() or model not in self.child_models:
                return self._deny(
                    request,
                    code="MODEL_REFUSAL",
                    message="child model is not admitted by Atlas",
                )
            depth = request.get("depth")
            if (
                not isinstance(depth, int)
                or isinstance(depth, bool)
                or not 0 <= depth < self.max_child_depth
            ):
                return self._deny(
                    request,
                    code="RECURSION_REFUSAL",
                    message="child depth exceeds the admitted recursion budget",
                )
            request_hash = hashlib.sha256(
                json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            admission_id = request_hash[:24]
            # Request dedup: an identical reserve for an still-active admission
            # re-answers with the existing identity instead of double-spending
            # a slot or budget; only a `reserve_retry` audit event is written.
            for record in self.records:
                if record["request_hash"] == request_hash and record["phase"] in {
                    "reserved",
                    "committed",
                }:
                    with suppress(OSError):
                        self._journal(
                            "reserve_retry",
                            {
                                "admission_id": admission_id,
                                "request_hash": request_hash,
                                "phase": record["phase"],
                            },
                        )
                    return {
                        "ok": True,
                        "admission_id": admission_id,
                        "fencing_token": record["fencing_token"],
                        "max_depth": self.max_child_depth,
                    }
            if not self._slots.acquire(blocking=False):
                return self._deny(
                    request,
                    code="CAPACITY_REFUSAL",
                    message="Atlas child capacity is exhausted",
                )
            if self._reserved_budget_seconds + self.max_child_seconds > self.max_budget_seconds:
                self._slots.release()
                return self._deny(
                    request,
                    code="BUDGET_REFUSAL",
                    message="Atlas child budget is exhausted",
                )
            self._reserved_budget_seconds += self.max_child_seconds
            self._fencing_token += 1
            record = {
                "admission_id": admission_id,
                "request_hash": request_hash,
                "fencing_token": self._fencing_token,
                "name": name,
                "model": model,
                "depth": depth,
                "prompt_sha256": prompt_digest,
                "phase": "reserved",
                "role": self.role,
                "scope_hash": self.scope_hash,
                "budget_reserved": {
                    "seconds": self.max_child_seconds,
                    "tokens": self.max_child_tokens,
                },
            }
            try:
                self._journal("reserved", record)
            except OSError:
                self._reserved_budget_seconds -= self.max_child_seconds
                self._fencing_token -= 1
                self._slots.release()
                return self._deny(
                    request,
                    code="JOURNAL_REFUSAL",
                    message="child admission could not be journaled",
                )
            self.records.append(record)
            return {
                "ok": True,
                "admission_id": admission_id,
                "fencing_token": self._fencing_token,
                "max_depth": self.max_child_depth,
            }
        if phase == "commit":
            raw_admission_id = request.get("admission_id")
            child_id = request.get("child_id")
            session_dir = request.get("session_dir")
            if not all(
                isinstance(item, str) and item
                for item in (raw_admission_id, child_id, session_dir)
            ):
                return self._deny(
                    request,
                    code="IDENTITY_REFUSAL",
                    message="child commit identity is incomplete",
                )
            fencing_token = request.get("fencing_token")
            if not isinstance(fencing_token, int) or isinstance(fencing_token, bool):
                return self._deny(
                    request,
                    code="FENCING_REFUSED",
                    message="child commit fencing token is missing or malformed",
                )
            admission_id = str(raw_admission_id)
            child_id = str(child_id)
            session_dir = str(session_dir)
            for record in self.records:
                if record["admission_id"] == admission_id:
                    if record["fencing_token"] != fencing_token:
                        return self._deny(
                            request,
                            code="FENCING_REFUSED",
                            message="child commit fencing token mismatch",
                        )
                    if record["phase"] == "committed":
                        # Idempotent retry: same child under the same fencing
                        # token re-acknowledges instead of erroring.
                        if record.get("child_id") == child_id:
                            return {"ok": True}
                        return self._deny(
                            request,
                            code="STATE_REFUSAL",
                            message="child admission is already committed to another child",
                        )
                    if record["phase"] != "reserved":
                        return self._deny(
                            request,
                            code="STATE_REFUSAL",
                            message="child admission is not reservable",
                        )
                    updated = {
                        **record,
                        "phase": "committed",
                        "child_id": child_id,
                        "session_dir": session_dir,
                    }
                    try:
                        self._journal("committed", updated)
                    except OSError:
                        return self._deny(
                            request,
                            code="JOURNAL_REFUSAL",
                            message="child commit could not be journaled",
                        )
                    record.update(updated)
                    return {"ok": True}
            return self._deny(
                request, code="IDENTITY_REFUSAL", message="unknown child admission"
            )
        if phase == "release":
            raw_admission_id = request.get("admission_id")
            status = request.get("status")
            if not isinstance(raw_admission_id, str) or status not in {
                "done",
                "error",
                "cancelled",
            }:
                return self._deny(
                    request, code="RELEASE_REFUSAL", message="child release is malformed"
                )
            fencing_token = request.get("fencing_token")
            if not isinstance(fencing_token, int) or isinstance(fencing_token, bool):
                return self._deny(
                    request,
                    code="FENCING_REFUSED",
                    message="child release fencing token is missing or malformed",
                )
            admission_id = raw_admission_id
            for record in self.records:
                if record["admission_id"] == admission_id:
                    if record["fencing_token"] != fencing_token:
                        return self._deny(
                            request,
                            code="FENCING_REFUSED",
                            message="child release fencing token mismatch",
                        )
                    if record["phase"] == "released":
                        # Idempotent retry: same terminal status under the same
                        # fencing token re-acknowledges; the slot stays freed.
                        if record.get("status") == status:
                            return {"ok": True}
                        return self._deny(
                            request,
                            code="STATE_REFUSAL",
                            message="child admission is already released with another status",
                        )
                    updated = {**record, "phase": "released", "status": status}
                    try:
                        self._journal("released", updated)
                    except OSError:
                        return self._deny(
                            request,
                            code="JOURNAL_REFUSAL",
                            message="child release could not be journaled",
                        )
                    record.update(updated)
                    self._slots.release()
                    return {"ok": True}
            return self._deny(
                request, code="IDENTITY_REFUSAL", message="unknown child admission"
            )
        return self._deny(
            request, code="PHASE_REFUSAL", message="unsupported child admission phase"
        )


def probe_local_model_endpoint(endpoint: str, *, timeout_seconds: float = 2.0) -> dict[str, Any]:
    """Inspect a loopback OpenAI-compatible model catalog without inference."""
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError("local model endpoint must use a loopback HTTP(S) host")
    url = endpoint.rstrip("/") + "/v1/models"
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            body = json.loads(response.read(DEFAULT_MAX_FRAME_BYTES).decode("utf-8"))
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"endpoint": endpoint, "reachable": False, "models": [], "error": str(exc)}
    rows = body.get("data") if isinstance(body, dict) else None
    models = sorted(
        item["id"]
        for item in rows
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ) if isinstance(rows, list) else []
    return {"endpoint": endpoint, "reachable": True, "models": models}


def _validate_autonomous_limits(config: Any, max_seconds: int) -> None:
    """Reject Prime's implicit-unlimited autonomous budget semantics."""
    if not isinstance(config, dict):
        raise AdapterUnavailableError(
            "Prime autonomous configuration must be an object",
            code="INVALID_AUTONOMOUS_CONFIGURATION",
        )
    required = ("maxContinuations", "maxTurns", "maxTokens", "timeoutMs")
    if any(
        key not in config
        or not isinstance(config[key], int)
        or isinstance(config[key], bool)
        or config[key] < 1
        for key in required
    ):
        raise AdapterUnavailableError(
            "Prime autonomous mode requires finite maxContinuations, maxTurns, "
            "maxTokens, and timeoutMs limits",
            code="UNBOUNDED_AUTONOMOUS_CONFIGURATION",
        )
    if config["timeoutMs"] > max_seconds * 1000:
        raise AdapterUnavailableError(
            "Prime autonomous timeoutMs exceeds the Atlas task deadline",
            code="AUTONOMOUS_DEADLINE_EXCEEDED",
        )
    keep_alive = config.get("subagentKeepAliveMs")
    if keep_alive is not None and (
        not isinstance(keep_alive, int)
        or isinstance(keep_alive, bool)
        or keep_alive < 0
        or keep_alive >= config["timeoutMs"]
    ):
        raise AdapterUnavailableError(
            "Prime subagentKeepAliveMs must be non-negative and below timeoutMs",
            code="INVALID_AUTONOMOUS_KEEPALIVE",
        )


def _validate_runtime_manifest(
    profile: AgentProfile, expected_sha: str, executable: str
) -> None:
    """Require an explicit, source-bound runtime identity before dispatch."""
    manifest_path = profile.adapter_options.get("runtime_manifest")
    if not isinstance(manifest_path, str) or not manifest_path:
        raise AdapterUnavailableError(
            "Prime execution requires a runtime_manifest bound to the pinned source",
            code="RUNTIME_MANIFEST_MISSING",
        )
    try:
        document = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdapterUnavailableError(
            "Prime runtime_manifest is unreadable",
            code="RUNTIME_MANIFEST_INVALID",
        ) from exc
    if not isinstance(document, dict):
        raise AdapterUnavailableError(
            "Prime runtime_manifest must contain an object",
            code="RUNTIME_MANIFEST_INVALID",
        )
    if (
        document.get("upstream_sha") != expected_sha
        or document.get("source_commit_verified") is not True
    ):
        raise AdapterUnavailableError(
            "Prime runtime_manifest does not verify the configured source pin",
            code="RUNTIME_PIN_MISMATCH",
        )
    executable_identity = document.get("executable")
    if not isinstance(executable_identity, dict):
        raise AdapterUnavailableError(
            "Prime runtime_manifest has no executable identity",
            code="RUNTIME_EXECUTABLE_UNBOUND",
        )
    expected_path = executable_identity.get("path")
    expected_hash = executable_identity.get("sha256")
    if (
        expected_path != executable
        or not isinstance(expected_hash, str)
        or len(expected_hash) != 64
        or any(character not in "0123456789abcdef" for character in expected_hash)
    ):
        raise AdapterUnavailableError(
            "Prime runtime_manifest executable identity does not match the runner",
            code="RUNTIME_EXECUTABLE_MISMATCH",
        )
    try:
        actual_hash = hashlib.sha256(Path(executable).read_bytes()).hexdigest()
    except OSError as exc:
        raise AdapterUnavailableError(
            "Prime executable cannot be hashed",
            code="RUNTIME_EXECUTABLE_UNREADABLE",
        ) from exc
    if actual_hash != expected_hash:
        raise AdapterUnavailableError(
            "Prime executable hash does not match runtime_manifest",
            code="RUNTIME_EXECUTABLE_MISMATCH",
        )


def _validate_sandbox_argv(sandbox_argv: list[str] | tuple[str, ...]) -> None:
    """Require a concrete Linux sandbox with the minimum isolation controls.

    Merely naming an executable is not an isolation boundary: ``/bin/true``
    and a shell wrapper both satisfy that check while leaving Prime with the
    supervisor's host authority. The supported unattended Linux profile is
    Bubblewrap with namespace, lifecycle, scoped-mount, and working-directory
    controls present in the actual argv. Deployment may add stricter mounts,
    but it cannot remove these controls.
    """
    launcher = Path(shutil.which(sandbox_argv[0]) or sandbox_argv[0]).resolve()
    if launcher != Path(SUPPORTED_SANDBOX_LAUNCHER):
        raise AdapterUnavailableError(
            "Prime unattended execution requires the approved Bubblewrap launcher",
            code="UNAPPROVED_ISOLATION_WRAPPER",
        )
    options = set(sandbox_argv[1:])
    missing = sorted(REQUIRED_BWRAP_OPTIONS - options)
    if missing:
        raise AdapterUnavailableError(
            "Prime Bubblewrap sandbox is missing required isolation options: "
            + ", ".join(missing),
            code="INCOMPLETE_ISOLATION_CONFIGURATION",
        )
    for index, option in enumerate(sandbox_argv[:-1]):
        source: str | None = None
        writable_bind = False
        if option in {"--bind", "--ro-bind", "--dev-bind"}:
            source = sandbox_argv[index + 1]
            writable_bind = option == "--bind"
        else:
            for bind_flag in ("--bind=", "--ro-bind=", "--dev-bind="):
                if option.startswith(bind_flag):
                    source = option[len(bind_flag) :]
                    writable_bind = bind_flag == "--bind="
                    break
        if source is None:
            continue
        if not source:
            raise AdapterUnavailableError(
                "Prime Bubblewrap bind option is missing a source path",
                code="UNSAFE_ISOLATION_MOUNT",
            )
        resolved_source = Path(source).resolve()
        if any(
            resolved_source == sensitive
            or (sensitive != Path("/") and resolved_source.is_relative_to(sensitive))
            for sensitive in SENSITIVE_BWRAP_BIND_SOURCES
        ) or (writable_bind and resolved_source == Path("/etc")):
            raise AdapterUnavailableError(
                f"Prime Bubblewrap {option} source {resolved_source} is outside the "
                "approved mission scope",
                code="UNSAFE_ISOLATION_MOUNT",
            )


class PrimeDaemonClient:
    """Small client for Prime's public daemon protocol.

    This intentionally speaks only the documented supervisor socket protocol;
    it does not depend on Prime's private supervisor-worker transport.
    """

    protocol_name = "prime-agent.daemon"
    protocol_version = 7

    def __init__(
        self,
        socket_path: Path,
        *,
        client_id: str,
        timeout_seconds: float = 30.0,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        resume_cursor: dict[str, Any] | None = None,
    ) -> None:
        self.socket_path = socket_path
        self.client_id = client_id
        self.timeout_seconds = timeout_seconds
        self._parser = PrimeFrameParser(max_frame_bytes=max_frame_bytes)
        self._socket: socket.socket | None = None
        self._reader: Any = None
        self.records: list[dict[str, Any]] = []
        self.commands: list[dict[str, Any]] = []
        self.snapshot: dict[str, Any] | None = None
        self.last_event_cursor: dict[str, Any] | None = None
        self.last_event_sequence: int | None = None
        self.resume_cursor = dict(resume_cursor) if resume_cursor is not None else None
        self.server_capabilities: tuple[str, ...] = ()
        self.schema_revision: int | None = None

    def connect(self) -> None:
        if self._socket is not None:
            raise PrimeDaemonError("daemon client is already connected")
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(self.timeout_seconds)
        try:
            connection.connect(str(self.socket_path))
            self._socket = connection
            self._reader = connection.makefile("rb")
            hello = self._read_record()
            protocol = hello.get("protocol")
            if hello.get("type") != "daemon_hello" or not isinstance(protocol, dict):
                raise PrimeDaemonError("Prime daemon handshake is invalid")
            if (
                protocol.get("name") != self.protocol_name
                or protocol.get("version") != self.protocol_version
            ):
                raise PrimeDaemonError("Prime daemon protocol version is unsupported")
            capabilities = hello.get("serverCapabilities")
            if isinstance(capabilities, list) and all(
                isinstance(item, str) and item for item in capabilities
            ):
                self.server_capabilities = tuple(capabilities)
            schema_revision = hello.get("schemaRevision")
            if isinstance(schema_revision, int) and not isinstance(schema_revision, bool):
                self.schema_revision = schema_revision
            self._remember_record(hello)
        except BaseException:
            connection.close()
            self._socket = None
            self._reader = None
            raise

    def close(self) -> None:
        reader = self._reader
        connection = self._socket
        self._reader = None
        self._socket = None
        if reader is not None:
            reader.close()
        if connection is not None:
            connection.close()

    def _read_record(self) -> dict[str, Any]:
        if self._reader is None:
            raise PrimeDaemonError("daemon client is not connected")
        raw = self._reader.readline()
        if not raw:
            raise PrimeDaemonError("Prime daemon closed the public socket")
        records = self._parser.feed(raw)
        if len(records) != 1:
            raise PrimeDaemonError("Prime daemon returned an invalid JSONL record")
        return records[0]

    def _remember_record(self, record: dict[str, Any]) -> None:
        """Record progress monotonically across reconnect/replay deliveries."""
        self.records.append(record)
        cursor = record.get("cursor")
        if not isinstance(cursor, dict):
            cursor = record.get("lastEventCursor")
        if isinstance(cursor, dict):
            generation = cursor.get("generation")
            sequence = cursor.get("sequence")
            if (
                isinstance(generation, str)
                and isinstance(sequence, int)
                and not isinstance(sequence, bool)
            ):
                current_generation = (
                    self.last_event_cursor.get("generation")
                    if self.last_event_cursor is not None
                    else None
                )
                current_sequence = self.last_event_sequence
                if (
                    current_generation != generation
                    or current_sequence is None
                    or sequence > current_sequence
                ):
                    self.last_event_cursor = {"generation": generation, "sequence": sequence}
                    self.last_event_sequence = sequence

    def _next_command_id(self, label: str, command: dict[str, Any]) -> str:
        canonical = json.dumps(command, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]
        return f"{self.client_id}:{label}:{digest}"

    def request(
        self,
        command: dict[str, Any],
        *,
        label: str,
        cancel_requested: Any = None,
        cancel_command: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._socket is None:
            raise PrimeDaemonError("daemon client is not connected")
        command_id = self._next_command_id(label, command)
        envelope = {
            "type": "command",
            "id": command_id,
            "protocol": {"name": self.protocol_name, "version": self.protocol_version},
            "clientId": self.client_id,
            "command": command,
        }
        payload = (json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        self._socket.sendall(payload)
        self.commands.append(envelope)
        cancel_sent = False
        abort_id: str | None = None
        while True:
            if cancel_requested is not None and not cancel_sent:
                readable, _, _ = select.select([self._socket], [], [], 0.2)
                if not readable:
                    if cancel_requested():
                        if cancel_command is None:
                            raise PrimeDaemonError(
                                "Prime daemon request cancelled without an abort command"
                            )
                        abort_id = self._next_command_id("abort", cancel_command)
                        abort_payload = {
                            "type": "command",
                            "id": abort_id,
                            "protocol": {
                                "name": self.protocol_name,
                                "version": self.protocol_version,
                            },
                            "clientId": self.client_id,
                            "command": cancel_command,
                        }
                        self._socket.sendall(
                            (json.dumps(abort_payload, separators=(",", ":")) + "\n").encode()
                        )
                        self.commands.append(abort_payload)
                        cancel_sent = True
                    continue
            record = self._read_record()
            self._remember_record(record)
            if cancel_sent and abort_id is not None and record.get("id") == abort_id:
                if record.get("success") is not True:
                    raise PrimeDaemonError("Prime daemon abort was not accepted")
                raise PrimeDaemonError("Prime daemon request cancelled")
            if record.get("type") != "response" or record.get("id") != command_id:
                continue
            if record.get("success") is not True:
                raise PrimeDaemonError(str(record.get("error", "Prime daemon command failed")))
            return record

    def create_resident(
        self,
        *,
        session_path: Path,
        cwd: Path,
        session_dir: Path,
        agent_dir: Path | None = None,
        provider: str | None = None,
        model: str | None = None,
        lifecycle: str = "resident",
        autonomous: dict[str, Any] | None = None,
    ) -> str:
        config: dict[str, Any] = {
            "cwd": str(cwd),
            "sessionDir": str(session_dir),
            "executionMode": "rpc",
        }
        if agent_dir is not None:
            config["agentDir"] = str(agent_dir)
        if provider:
            config["provider"] = provider
        if model:
            config["model"] = model
        if autonomous is not None:
            config["autonomous"] = dict(autonomous)
        response = self.request(
            {
                "type": "create",
                "sessionPath": str(session_path),
                "lifecycle": lifecycle,
                "config": config,
            },
            label="create",
        )
        data = response.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("activeSessionId"), str):
            raise PrimeDaemonError("Prime daemon create response has no active session id")
        active_session_id = data["activeSessionId"]
        assert isinstance(active_session_id, str)
        return active_session_id

    def attach(
        self,
        active_session_id: str,
        *,
        recovery_config: dict[str, Any] | None = None,
        launch_env: dict[str, str] | None = None,
    ) -> None:
        command: dict[str, Any] = {
            "type": "attach",
            "activeSessionId": active_session_id,
            "clientId": self.client_id,
            "capabilities": ["attach_snapshot", "event_sequence"],
        }
        if recovery_config is not None:
            if "owned_session_recovery_context" not in self.server_capabilities:
                raise PrimeDaemonError(
                    "Prime daemon does not advertise owned-session recovery context"
                )
            command["capabilities"].append("owned_session_recovery_context")
            command["recoveryConfig"] = dict(recovery_config)
        if launch_env is not None:
            command["launchEnv"] = dict(launch_env)
        if self.resume_cursor is not None:
            command["resumeCursor"] = {
                "activeSessionId": active_session_id,
                **self.resume_cursor,
            }
        response = self.request(
            command,
            label="attach",
        )
        data = response.get("data")
        if isinstance(data, dict):
            snapshot = data.get("snapshot")
            if isinstance(snapshot, dict):
                self.snapshot = snapshot
            cursor = data.get("lastEventCursor")
            if isinstance(cursor, dict):
                self._remember_record({"lastEventCursor": cursor})
            if self.last_event_cursor is not None:
                self.resume_cursor = dict(self.last_event_cursor)

    def set_rlm_max_depth(self, active_session_id: str, max_depth: int) -> None:
        self.request(
            {
                "type": "set_rlm_max_depth",
                "activeSessionId": active_session_id,
                "maxDepth": max_depth,
            },
            label="rlm-depth",
        )

    def prompt_and_wait(
        self,
        active_session_id: str,
        message: str,
        *,
        admission_id: str | None = None,
        cancel_requested: Any = None,
    ) -> None:
        command: dict[str, Any] = {
            "type": "prompt_and_wait",
            "activeSessionId": active_session_id,
            "message": message,
        }
        if admission_id is not None:
            command["admissionId"] = admission_id
        self.request(
            command,
            label="prompt",
            cancel_requested=cancel_requested,
            cancel_command={"type": "abort", "activeSessionId": active_session_id},
        )

    def abort(self, active_session_id: str) -> None:
        self.request(
            {"type": "abort", "activeSessionId": active_session_id},
            label="abort",
        )

    def last_assistant_text(self, active_session_id: str) -> str | None:
        response = self.request(
            {"type": "get_last_assistant_text", "activeSessionId": active_session_id},
            label="last-assistant",
        )
        data = response.get("data")
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            return None
        text = data["text"]
        assert isinstance(text, str)
        return text

    def session_stats(self, active_session_id: str) -> dict[str, Any] | None:
        """Return the public daemon's session usage snapshot, if valid."""
        response = self.request(
            {"type": "get_session_stats", "activeSessionId": active_session_id},
            label="session-stats",
        )
        data = response.get("data")
        return dict(data) if isinstance(data, dict) else None


class PrimeDaemonError(AdapterUnavailableError):
    """The public Prime daemon route could not be used safely."""


def _prime_failure_class(text: str) -> FailureClass:
    """Classify provider rejection without turning it into an infrastructure retry."""
    lowered = text.casefold()
    if any(
        marker in lowered
        for marker in (
            "api key",
            "apikey",
            "credential",
            "unauthorized",
            "authentication",
            "quota",
            "credit balance",
            "billing",
            "no provider",
            "provider is not configured",
        )
    ):
        return FailureClass.QUOTA_OR_CREDENTIAL
    return FailureClass.TRANSIENT_INFRASTRUCTURE


class PrimeExecutorAdapter:
    """Run one bounded Prime RPC attempt under an Atlas request."""

    def __init__(
        self,
        executable: str = DEFAULT_EXECUTABLE,
        *,
        upstream_sha: str = PRIME_UPSTREAM_SHA,
        max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
        daemon_socket: Path | None = None,
    ) -> None:
        self._executable = executable
        self.upstream_sha = upstream_sha
        self._max_frame_bytes = max_frame_bytes
        self._daemon_socket = daemon_socket

    @property
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            adapter_id=ADAPTER_ID,
            supports_resume=self._daemon_socket is not None,
            supports_session_probe=True,
            # RPC mints the session identity; a pre-assigned Atlas id is only a
            # binding until Prime returns its active session id.
            accepts_assigned_session=False,
            supports_cost_limit=False,
            reports_cost=False,
            supports_result_schema=False,
            version=ADAPTER_VERSION,
        )

    def _resolve(self) -> str:
        path = Path(self._executable)
        if path.is_absolute() or "/" in self._executable:
            if path.is_file() and os.access(path, os.X_OK):
                return str(path.resolve())
        else:
            found = shutil.which(self._executable)
            if found is not None:
                return str(Path(found).resolve())
        raise AdapterUnavailableError(
            f"Prime executable {self._executable!r} is not available",
            code="RUNTIME_NOT_INSTALLED",
        )

    @staticmethod
    def _has_child_admission_patch(profile: AgentProfile) -> bool:
        manifest_path = profile.adapter_options.get("runtime_manifest")
        if not isinstance(manifest_path, str) or not manifest_path:
            return False
        try:
            document = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        patches = document.get("compatibility_patches") if isinstance(document, dict) else None
        return isinstance(patches, list) and any(
            isinstance(item, dict)
            and item.get("id") == CHILD_ADMISSION_PATCH_ID
            and item.get("sha256") == CHILD_ADMISSION_PATCH_SHA256
            for item in patches
        )

    def preflight(self, profile: AgentProfile) -> None:
        if profile.adapter is not AdapterKind.PRIME_AGENT:
            raise AdapterUnavailableError(
                f"profile {profile.profile_id} does not use the Prime adapter",
                code="ADAPTER_MISMATCH",
            )
        autonomous = profile.adapter_options.get("autonomous")
        if autonomous is not None:
            _validate_autonomous_limits(autonomous, profile.limits.max_seconds)
        sandbox_argv = profile.adapter_options.get("sandbox_argv")
        if not isinstance(sandbox_argv, (list, tuple)) or not sandbox_argv:
            raise AdapterUnavailableError(
                "Prime execution requires an explicit external isolation "
                "wrapper in adapter_options.sandbox_argv",
                code="EXTERNAL_ISOLATION_UNAVAILABLE",
            )
        if not all(isinstance(item, str) and item for item in sandbox_argv):
            raise AdapterUnavailableError(
                "adapter_options.sandbox_argv must contain non-empty strings",
                code="INVALID_ISOLATION_CONFIGURATION",
            )
        if shutil.which(sandbox_argv[0]) is None and not Path(sandbox_argv[0]).is_file():
            raise AdapterUnavailableError(
                f"Prime isolation wrapper {sandbox_argv[0]!r} is unavailable",
                code="EXTERNAL_ISOLATION_UNAVAILABLE",
            )
        lifecycle = profile.adapter_options.get("daemon_lifecycle", "resident")
        if lifecycle not in {"resident", "client_owned"}:
            raise AdapterUnavailableError(
                "Prime daemon_lifecycle must be resident or client_owned",
                code="INVALID_DAEMON_LIFECYCLE",
            )
        if lifecycle == "client_owned" and (
            profile.credential is not CredentialMechanism.NOT_APPLICABLE
            or profile.env_allowlist
        ):
            raise AdapterUnavailableError(
                "client_owned Prime recovery requires no credential env; use the "
                "existing credential broker before enabling it",
                code="CLIENT_OWNED_CREDENTIAL_BOUNDARY",
            )
        if profile.adapter_options.get("allow_children") is True:
            child_admission = profile.adapter_options.get("child_admission")
            max_child_tokens = (
                child_admission.get("max_child_tokens")
                if isinstance(child_admission, dict)
                else None
            )
            if (
                self._daemon_socket is None
                or not isinstance(child_admission, dict)
                or child_admission.get("patch_id") != CHILD_ADMISSION_PATCH_ID
                or not self._has_child_admission_patch(profile)
                or not isinstance(child_admission.get("max_children"), int)
                or isinstance(child_admission.get("max_children"), bool)
                or not 1 <= child_admission["max_children"] <= 8
                or not isinstance(child_admission.get("max_child_seconds"), int)
                or isinstance(child_admission.get("max_child_seconds"), bool)
                or not 1 <= child_admission["max_child_seconds"] <= profile.limits.max_seconds
                or not isinstance(child_admission.get("max_budget_seconds"), int)
                or isinstance(child_admission.get("max_budget_seconds"), bool)
                or child_admission["max_budget_seconds"] < child_admission["max_child_seconds"]
                or (
                    max_child_tokens is not None
                    and (
                        not isinstance(max_child_tokens, int)
                        or isinstance(max_child_tokens, bool)
                        or max_child_tokens < 1
                    )
                )
            ):
                raise AdapterUnavailableError(
                    "Prime native children require the version-pinned Atlas "
                    "host-side admission hook and a daemon-backed session",
                    code="CHILD_ADMISSION_UNAVAILABLE",
                )
            child_models = child_admission.get("child_models")
            if (
                not isinstance(child_models, list)
                or not child_models
                or any(
                    not isinstance(model, str) or not model.strip() for model in child_models
                )
            ):
                raise AdapterUnavailableError(
                    "Prime native children require an explicit non-empty "
                    "child_models allowlist",
                    code="CHILD_MODELS_REQUIRED",
                )
            max_child_depth = child_admission.get("max_child_depth", 1)
            if (
                not isinstance(max_child_depth, int)
                or isinstance(max_child_depth, bool)
                or max_child_depth < 1
            ):
                raise AdapterUnavailableError(
                    "Prime child_admission max_child_depth must be an integer >= 1",
                    code="INVALID_CHILD_DEPTH",
                )
        resolved = self._resolve()
        _validate_runtime_manifest(profile, self.upstream_sha, resolved)
        _validate_sandbox_argv(sandbox_argv)
        provider = profile.adapter_options.get("provider")
        if not isinstance(provider, str) or not provider.strip() or not profile.model:
            raise AdapterUnavailableError(
                "Prime requires an explicit provider and model in the Atlas profile; "
                "implicit personal runtime configuration is refused",
                code="PROVIDER_SELECTION_REQUIRED",
            )
        inference_mode = profile.adapter_options.get("inference_mode")
        if inference_mode in LOCAL_ONLY_MODES:
            endpoint = profile.adapter_options.get("local_endpoint")
            if (
                not isinstance(endpoint, str)
                or not isinstance(provider, str)
                or not provider
                or not profile.model
                or profile.credential is not CredentialMechanism.NOT_APPLICABLE
                or profile.env_allowlist
            ):
                raise AdapterUnavailableError(
                    "local-only Prime requires loopback endpoint, provider/model, "
                    "and no credential environment",
                    code="INVALID_LOCAL_ONLY_PROFILE",
                )
            try:
                catalog = probe_local_model_endpoint(endpoint)
            except ValueError as exc:
                raise AdapterUnavailableError(str(exc), code="INVALID_LOCAL_ENDPOINT") from exc
            if not catalog["reachable"]:
                raise AdapterUnavailableError(
                    "local-only Prime endpoint is unreachable",
                    code="LOCAL_ENDPOINT_UNAVAILABLE",
                )
            if profile.model not in catalog["models"]:
                raise AdapterUnavailableError(
                    f"local-only Prime model {profile.model!r} is not advertised",
                    code="LOCAL_MODEL_UNAVAILABLE",
                )

    def probe_run_started(self, request: AdapterRequest) -> bool | None:
        markers = (
            request.evidence_dir / f"{request.attempt_id}.prime-rpc.jsonl",
            request.evidence_dir / f"{request.attempt_id}.prime-daemon.jsonl",
            request.evidence_dir / f"{request.attempt_id}.child-admission.jsonl",
        )
        for marker in markers:
            if not marker.is_file():
                continue
            try:
                lines = marker.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            if marker.name.endswith(".child-admission.jsonl"):
                if _valid_child_journal_lines(
                    lines,
                    mission_id=request.program_id,
                    task_id=request.task_id,
                    attempt_id=request.attempt_id,
                ):
                    return True
            elif any(line.strip() for line in lines):
                return True
        return None

    def _argv(self, request: AdapterRequest) -> list[str]:
        options = request.profile.adapter_options
        argv = [self._resolve(), "--mode", "rpc"]
        session_dir = options.get("session_dir")
        if isinstance(session_dir, str) and session_dir:
            argv += ["--session-dir", session_dir]
        provider = options.get("provider")
        if isinstance(provider, str) and provider:
            argv += ["--provider", provider]
        model = request.profile.model
        if model:
            argv += ["--model", model]
        sandbox_argv = options.get("sandbox_argv")
        if isinstance(sandbox_argv, (list, tuple)) and all(
            isinstance(item, str) for item in sandbox_argv
        ):
            return [*sandbox_argv, *argv]
        return argv

    def run(self, request: AdapterRequest) -> AdapterOutcome:
        if self._daemon_socket is not None:
            return self._run_resident(request)
        started = time.monotonic()
        request.evidence_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = request.evidence_dir / f"{request.attempt_id}.prime-rpc.jsonl"
        env = build_child_env(request.profile, extra=dict(request.extra_env))
        env.setdefault("PRIME_AGENT_CODING_AGENT_DIR", str(request.evidence_dir / "prime-config"))
        env.setdefault("PRIME_AGENT_SESSION_DIR", str(request.evidence_dir / "prime-sessions"))
        process = subprocess.Popen(
            self._argv(request),
            cwd=str(request.workspace),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=hasattr(os, "setsid"),
        )
        pid = process.pid
        if request.process_launched is not None:
            request.process_launched(pid)
        identity = process_start_identity(pid)
        if request.process_started is not None:
            request.process_started(pid, identity)

        parser = PrimeFrameParser(max_frame_bytes=self._max_frame_bytes)
        frames: list[dict[str, Any]] = []
        stderr_chunks: list[bytes] = []
        request_id = request.idempotency_key
        command = json.dumps(
            {"id": request_id, "type": "prompt", "message": request.instruction},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        assert process.stdin is not None
        process.stdin.write(command)
        process.stdin.flush()
        process.stdin.close()
        process.stdin = None

        deadline = started + request.timeout_seconds
        terminal = "completed"
        saw_agent_end = False
        selector = selectors.DefaultSelector()
        assert process.stdout is not None
        assert process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ)
        selector.register(process.stderr, selectors.EVENT_READ)
        while process.poll() is None and time.monotonic() < deadline:
            if request.cancel_requested is not None and request.cancel_requested():
                terminal = "cancelled"
                process.terminate()
                break
            ready = selector.select(timeout=min(0.1, max(0.0, deadline - time.monotonic())))
            if not ready:
                continue
            stream = ready[0][0].fileobj
            # Read descriptors directly. Buffered ``readline`` may read ahead
            # into the next JSONL record; a later ``communicate`` call cannot
            # see bytes hidden in that wrapper buffer.
            fd = stream if isinstance(stream, int) else stream.fileno()
            chunk = os.read(fd, 64 * 1024)
            if not chunk:
                selector.unregister(stream)
                continue
            if stream is process.stdout:
                parsed = parser.feed(chunk)
                frames.extend(parsed)
                if any(frame.get("type") == "agent_end" for frame in parsed):
                    saw_agent_end = True
                    break
            else:
                stderr_chunks.append(chunk)
        selector.close()
        if process.poll() is None and terminal == "completed" and not saw_agent_end:
            terminal = "timeout"
            process.terminate()
        try:
            stdout, stderr = process.communicate(
                timeout=max(1.0, deadline - time.monotonic())
            )
        except subprocess.TimeoutExpired:
            process.terminate()
            stdout, stderr = process.communicate()
        if stdout:
            frames.extend(parser.feed(stdout))
        parser.finish()
        stderr_text = b"".join(stderr_chunks) + stderr
        transcript_path.write_text(
            "".join(
                json.dumps(frame, ensure_ascii=False, sort_keys=True) + "\n"
                for frame in frames
            ),
            encoding="utf-8",
        )
        has_end = any(frame.get("type") == "agent_end" for frame in frames)
        if terminal in {"cancelled", "timeout"}:
            confidence = ExecutionConfidence.UNCERTAIN
            failure = FailureClass.UNCERTAIN_OUTCOME
        elif process.returncode == 0 and has_end:
            confidence = ExecutionConfidence.CONFIRMED
            failure = None
        else:
            confidence = ExecutionConfidence.FAILED
            failure = _prime_failure_class(
                _reported_text(frames)
                or b"".join(stderr_chunks).decode("utf-8", errors="replace")
            )
            terminal = "rpc_error"
        reported = _reported_text(frames)
        return AdapterOutcome(
            attempt_id=request.attempt_id,
            task_id=request.task_id,
            launched=True,
            confidence=confidence,
            terminal_state=terminal,
            exit_status=process.returncode,
            session_id=_session_id(frames),
            pid=pid,
            process_start_identity=identity,
            reported=reported or stderr_text.decode("utf-8", errors="replace")[-8192:] or None,
            structured=None,
            usage={"status": "not-reported-by-public-rpc"},
            estimated_cost_usd=None,
            evidence=(transcript_path.name,),
            failure_class=failure,
            duration_seconds=time.monotonic() - started,
            notes=(f"Prime Agent source pinned to {self.upstream_sha}",),
        )

    def _run_resident(self, request: AdapterRequest) -> AdapterOutcome:
        started = time.monotonic()
        request.evidence_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = request.evidence_dir / f"{request.attempt_id}.prime-daemon.jsonl"
        metadata_path = request.evidence_dir / f"{request.attempt_id}.prime-daemon.json"
        env = build_child_env(request.profile, extra=dict(request.extra_env))
        agent_dir = request.evidence_dir / "prime-config"
        session_dir = request.evidence_dir / "prime-sessions"
        env.setdefault("PRIME_AGENT_CODING_AGENT_DIR", str(agent_dir))
        env.setdefault("PRIME_AGENT_SESSION_DIR", str(session_dir))
        candidate_sha, tree_sha = _git_identity(request.workspace)
        broker: PrimeChildAdmissionBroker | None = None
        child_options = request.profile.adapter_options.get("child_admission")
        if request.profile.adapter_options.get("allow_children") is True:
            assert isinstance(child_options, dict)
            broker = PrimeChildAdmissionBroker(
                request.evidence_dir / f"{request.attempt_id}.child-admission.sock",
                mission_id=request.program_id,
                task_id=request.task_id,
                attempt_id=request.attempt_id,
                parent_session_id="",
                max_children=int(child_options["max_children"]),
                role=request.profile.agent_id,
                scope_hash=_prime_child_scope_hash(request),
                max_child_seconds=int(child_options["max_child_seconds"]),
                max_child_tokens=(
                    int(child_options["max_child_tokens"])
                    if child_options.get("max_child_tokens") is not None
                    else None
                ),
                max_budget_seconds=int(child_options["max_budget_seconds"]),
                child_models=[str(model) for model in child_options["child_models"]],
                max_child_depth=int(child_options.get("max_child_depth", 1)),
                journal_path=request.evidence_dir
                / f"{request.attempt_id}.child-admission.jsonl",
                candidate_sha=candidate_sha,
                tree_sha=tree_sha,
                workspace_identity=str(request.workspace.resolve()),
                cancel_requested=request.cancel_requested,
            )
            try:
                broker.start()
            except BaseException:
                broker.close()
                raise
            env.update(
                {
                    "ATLAS_PRIME_CHILD_ADMISSION_SOCKET": str(broker.socket_path),
                    "ATLAS_PRIME_MISSION_ID": request.program_id,
                    "ATLAS_PRIME_TASK_ID": request.task_id,
                    "ATLAS_PRIME_ATTEMPT_ID": request.attempt_id,
                    "ATLAS_PRIME_ROLE": request.profile.agent_id,
                    "ATLAS_PRIME_SCOPE_HASH": _prime_child_scope_hash(request),
                    "ATLAS_PRIME_MAX_CHILD_SECONDS": str(child_options["max_child_seconds"]),
                    "ATLAS_PRIME_MAX_CHILD_TOKENS": str(child_options.get("max_child_tokens", "")),
                }
            )
        daemon_pid: int | None = None
        daemon_process_start_identity: str | None = None
        daemon_available = False
        assert self._daemon_socket is not None
        client = PrimeDaemonClient(
            self._daemon_socket,
            client_id=(
                f"atlas:{request.program_id}:{request.task_id}:{request.attempt_id}"
            ),
            timeout_seconds=min(30.0, float(request.timeout_seconds)),
            max_frame_bytes=self._max_frame_bytes,
            resume_cursor=_resume_cursor_for_session(
                request.evidence_dir, request.resume_session_id
            ),
        )
        reported: str | None = None
        usage: dict[str, Any] = {"status": "not-reported-by-public-daemon"}
        estimated_cost_usd: float | None = None
        active_session_id: str | None = request.resume_session_id
        failure: FailureClass | None = None
        try:
            daemon_pid = self._ensure_daemon(
                request,
                env=env,
                session_dir=session_dir,
            )
            daemon_available = True
            if daemon_pid is not None:
                daemon_process_start_identity = process_start_identity(daemon_pid)
            if broker is not None and daemon_pid is None:
                raise PrimeDaemonError(
                    "child admission requires a newly started mission-owned daemon"
                )
            client.connect()
            lifecycle = request.profile.adapter_options.get("daemon_lifecycle", "resident")
            if request.resume_session_id:
                active_session_id = request.resume_session_id
                recovery_config: dict[str, Any] | None = None
                if lifecycle == "client_owned":
                    recovery_config = {
                        "cwd": str(request.workspace),
                        "agentDir": str(agent_dir),
                        "sessionDir": str(session_dir),
                        "executionMode": "rpc",
                        **(
                            {"provider": request.profile.adapter_options["provider"]}
                            if isinstance(request.profile.adapter_options.get("provider"), str)
                            else {}
                        ),
                        **(
                            {"model": request.profile.model}
                            if request.profile.model is not None
                            else {}
                        ),
                    }
                    autonomous = request.profile.adapter_options.get("autonomous")
                    if isinstance(autonomous, dict):
                        recovery_config["autonomous"] = dict(autonomous)
                client.attach(active_session_id, recovery_config=recovery_config, launch_env={})
            else:
                autonomous = request.profile.adapter_options.get("autonomous")
                active_session_id = client.create_resident(
                    session_path=session_dir / f"{request.attempt_id}.jsonl",
                    cwd=request.workspace,
                    session_dir=session_dir,
                    agent_dir=agent_dir,
                    provider=request.profile.adapter_options.get("provider"),
                    model=request.profile.model,
                    lifecycle=lifecycle,
                    autonomous=(dict(autonomous) if isinstance(autonomous, dict) else None),
                )
            if broker is not None:
                assert active_session_id is not None
                broker.bind_parent_session(active_session_id)
            client.set_rlm_max_depth(active_session_id, 0)
            if broker is not None:
                client.set_rlm_max_depth(active_session_id, 1)
            client.prompt_and_wait(
                active_session_id,
                request.instruction,
                admission_id=request.idempotency_key,
                cancel_requested=request.cancel_requested,
            )
            if broker is not None and not broker.wait_until_idle(
                max(0.0, request.timeout_seconds - (time.monotonic() - started))
            ):
                raise PrimeDaemonError("an admitted Prime child did not reach a terminal release")
            reported = client.last_assistant_text(active_session_id)
            try:
                stats = client.session_stats(active_session_id)
            except PrimeDaemonError:
                stats = None
            usage, estimated_cost_usd = _usage_from_session_stats(stats)
            confidence = ExecutionConfidence.CONFIRMED
            terminal = "completed"
            failure = None
            exit_status = 0
        except (OSError, PrimeDaemonError, TimeoutError) as exc:
            reported = str(exc)
            failure = _prime_failure_class(reported)
            confidence = (
                ExecutionConfidence.UNCERTAIN
                if daemon_available and failure is not FailureClass.QUOTA_OR_CREDENTIAL
                else ExecutionConfidence.FAILED
            )
            terminal = "daemon_error"
            exit_status = None
            active_session_id = request.resume_session_id
        finally:
            transcript = "".join(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
                for record in client.records
            )
            transcript_path.write_text(
                transcript,
                encoding="utf-8",
            )
            metadata_path.write_text(
                json.dumps(
                    {
                        "mission_id": request.program_id,
                        "task_id": request.task_id,
                        "attempt_id": request.attempt_id,
                        "parent_task_id": None,
                        "executor_kind": ADAPTER_ID,
                        "upstream_sha": self.upstream_sha,
                        "adapter_version": ADAPTER_VERSION,
                        "workspace_identity": str(request.workspace.resolve()),
                        "candidate_sha": candidate_sha,
                        "tree_sha": tree_sha,
                        "prime_session_id": request.resume_session_id,
                        "prime_active_session_id": active_session_id,
                        "client_id": client.client_id,
                        "server_capabilities": list(client.server_capabilities),
                        "schema_revision": client.schema_revision,
                        "command_ids": [item["id"] for item in client.commands],
                        "worker_generation": (
                            client.last_event_cursor.get("generation")
                            if client.last_event_cursor is not None
                            else None
                        ),
                        "daemon_process_start_identity": daemon_process_start_identity,
                        "last_event_cursor": client.last_event_cursor,
                        "lease_fencing_identity": None,
                        "policy_hash": None,
                        "deadline_seconds": request.timeout_seconds,
                        "budget_reserved": None,
                        "budget_consumed": None,
                        "usage": usage,
                        "estimated_cost_usd": estimated_cost_usd,
                        # Prime native children are fail-closed until the
                        # Atlas host-side admission hook is available. Keep
                        # the field explicit so an empty registry is not
                        # mistaken for an unrecorded one.
                        "child_registry": list(broker.records) if broker is not None else [],
                        "child_registry_journal": (
                            broker.journal_path.name if broker is not None else None
                        ),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            client.close()
            if broker is not None:
                broker.close()
        return AdapterOutcome(
            attempt_id=request.attempt_id,
            task_id=request.task_id,
            launched=daemon_available,
            confidence=confidence,
            terminal_state=terminal,
            exit_status=exit_status,
            session_id=active_session_id,
            pid=daemon_pid,
            process_start_identity=daemon_process_start_identity,
            reported=reported,
            structured=None,
            usage=usage,
            estimated_cost_usd=estimated_cost_usd,
            evidence=tuple(
                [transcript_path.name, metadata_path.name]
                + ([broker.journal_path.name] if broker is not None else [])
            ),
            failure_class=failure,
            duration_seconds=time.monotonic() - started,
            notes=(
                f"Prime Agent daemon protocol v7 pinned to {self.upstream_sha}",
                "resident lifecycle is daemon-owned; Atlas closes only its client socket",
            ),
        )

    def _ensure_daemon(
        self,
        request: AdapterRequest,
        *,
        env: dict[str, str],
        session_dir: Path,
    ) -> int | None:
        assert self._daemon_socket is not None
        deadline = time.monotonic() + request.timeout_seconds
        probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            probe.settimeout(0.2)
            probe.connect(str(self._daemon_socket))
            return None
        except OSError:
            pass
        finally:
            probe.close()
        self._daemon_socket.parent.mkdir(parents=True, exist_ok=True)
        session_dir.mkdir(parents=True, exist_ok=True)
        daemon_argv = [
            self._resolve(),
            "--mode",
            "daemon",
            "--daemon-socket",
            str(self._daemon_socket),
            "--cwd",
            str(request.workspace),
            "--session-dir",
            str(session_dir),
        ]
        sandbox_argv = request.profile.adapter_options.get("sandbox_argv")
        if isinstance(sandbox_argv, (list, tuple)) and all(
            isinstance(item, str) for item in sandbox_argv
        ):
            daemon_argv = [*sandbox_argv, *daemon_argv]
        process = subprocess.Popen(
            daemon_argv,
            cwd=str(request.workspace),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=hasattr(os, "setsid"),
        )
        if request.process_launched is not None:
            request.process_launched(process.pid)
        identity = process_start_identity(process.pid)
        if request.process_started is not None:
            request.process_started(process.pid, identity)
        while time.monotonic() < deadline:
            probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                probe.settimeout(0.2)
                probe.connect(str(self._daemon_socket))
                return process.pid
            except OSError as exc:
                if process.poll() is not None:
                    raise PrimeDaemonError(
                        "Prime daemon exited before its public socket became ready"
                    ) from exc
                time.sleep(0.05)
            finally:
                probe.close()
        process.terminate()
        raise PrimeDaemonError("timed out waiting for the Prime daemon socket")


def _session_id(frames: list[dict[str, Any]]) -> str | None:
    for frame in frames:
        data = frame.get("data")
        if isinstance(data, dict) and isinstance(data.get("sessionId"), str):
            return str(data["sessionId"])
    return None


def _git_identity(workspace: Path) -> tuple[str | None, str | None]:
    """Read the candidate and tree IDs without changing the workspace."""
    values: list[str | None] = []
    for revision in ("HEAD", "HEAD^{tree}"):
        try:
            result = subprocess.run(
                ["git", "rev-parse", revision],
                cwd=workspace,
                capture_output=True,
                check=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            values.append(None)
        else:
            value = result.stdout.strip()
            values.append(value if value else None)
    return values[0], values[1]


def _prime_child_scope_hash(request: AdapterRequest) -> str:
    """Bind child admission to the Atlas-resolved workspace/tool scope."""
    scope = {
        "workspace": str(request.workspace.resolve()),
        "allowed_mutation_prefixes": list(request.profile.allowed_mutation_prefixes),
        "allowed_tools": list(request.profile.allowed_tools),
        "disallowed_tools": list(request.profile.disallowed_tools),
        "permission_mode": request.profile.permission_mode,
    }
    return hashlib.sha256(
        json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _resume_cursor_for_session(
    evidence_dir: Path, active_session_id: str | None
) -> dict[str, Any] | None:
    """Read only a previously recorded cursor for an explicit session resume."""
    if active_session_id is None or not evidence_dir.is_dir():
        return None
    newest: tuple[float, dict[str, Any]] | None = None
    for path in evidence_dir.glob("*.prime-daemon.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if document.get("prime_active_session_id") != active_session_id:
            continue
        cursor = document.get("last_event_cursor")
        if not isinstance(cursor, dict):
            continue
        if not isinstance(cursor.get("generation"), str):
            continue
        if not isinstance(cursor.get("sequence"), int) or isinstance(cursor.get("sequence"), bool):
            continue
        stamp = path.stat().st_mtime
        if newest is None or stamp > newest[0]:
            newest = (stamp, {"generation": cursor["generation"], "sequence": cursor["sequence"]})
    return newest[1] if newest is not None else None


def _worker_generation(records: list[dict[str, Any]]) -> str | None:
    cursor = _last_event_cursor(records)
    generation = cursor.get("generation") if cursor else None
    return generation if isinstance(generation, str) else None


def _last_event_cursor(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for record in records:
        cursor = record.get("cursor")
        if not isinstance(cursor, dict):
            meta = record.get("meta")
            cursor = meta.get("cursor") if isinstance(meta, dict) else None
        if isinstance(cursor, dict) and isinstance(cursor.get("generation"), str):
            latest = {
                "generation": cursor["generation"],
                "sequence": cursor.get("sequence"),
            }
    return latest


def _reported_text(frames: list[dict[str, Any]]) -> str | None:
    values: list[str] = []
    for frame in frames:
        data = frame.get("data")
        if isinstance(data, dict):
            for key in ("text", "message", "content"):
                value = data.get(key)
                if isinstance(value, str):
                    values.append(value)
    return "\n".join(values)[-8192:] or None


def _usage_from_session_stats(stats: dict[str, Any] | None) -> tuple[dict[str, Any], float | None]:
    """Keep usage evidence separate from unknown provider billing."""
    if not isinstance(stats, dict):
        return {"status": "not-reported-by-public-daemon"}, None
    tokens = stats.get("tokens")
    cost = stats.get("cost")
    usage: dict[str, Any] = {"status": "reported"}
    if isinstance(tokens, dict):
        usage["tokens"] = dict(tokens)
    else:
        usage["tokens_status"] = "not-reported"
    estimated_cost = (
        float(cost)
        if isinstance(cost, (int, float)) and not isinstance(cost, bool)
        else None
    )
    if estimated_cost is None:
        usage["billing_status"] = "unknown"
    else:
        usage["client_estimated_cost_usd"] = estimated_cost
        usage["billing_status"] = "not-billed-amount"
    return usage, estimated_cost


def _valid_child_journal_lines(
    lines: list[str], *, mission_id: str, task_id: str, attempt_id: str
) -> bool:
    """Recognize only a non-empty journal bound to this Atlas attempt."""
    found = False
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return False
        if not isinstance(entry, dict) or any(
            entry.get(key) != expected
            for key, expected in (
                ("mission_id", mission_id),
                ("task_id", task_id),
                ("attempt_id", attempt_id),
            )
        ):
            return False
        if entry.get("event") not in {
            "reserved",
            "reserve_retry",
            "parent_bound",
            "committed",
            "released",
            "denied",
        }:
            return False
        found = True
    return found
