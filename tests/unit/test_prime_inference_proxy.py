from __future__ import annotations

import socket
import threading
from pathlib import Path

import pytest

from project_atlas.orchestration.program.prime_inference_proxy import (
    InferenceOnlyUnixProxy,
    InferenceProxyError,
    _bound_model_request,
    stored_tool_offer,
    _build_upstream_request,
)


@pytest.mark.parametrize(("request_body", "expected"), [
    (None, None), ({}, False), ({"tools": []}, False),
    ({"tools": [{"type": "function", "function": {"name": "ipython"}}]}, True),
    ({"tools": [{"type": "function", "function": {"name": "other"}}]}, False),
    ({"tools": "ipython"}, None), ({"tools": [{}]}, None),
])
def test_stored_request_tool_offer_is_not_a_catalog_claim(request_body, expected) -> None:
    assert stored_tool_offer(request_body, "ipython") is expected


def _ollama_fixture(listener: socket.socket, ready: threading.Event) -> None:
    ready.set()
    connection, _ = listener.accept()
    with connection:
        request = connection.recv(8192)
        assert b"POST /v1/chat/completions HTTP/1.1" in request
        connection.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
        )


def test_proxy_forwards_inference_only_and_denies_management(tmp_path: Path) -> None:
    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    upstream.bind(("127.0.0.1", 0))
    upstream.listen(1)
    # The production proxy is fixed to Ollama's port; replace only the
    # connection primitive in this in-process fixture.
    import project_atlas.orchestration.program.prime_inference_proxy as module

    original = module.socket.create_connection
    module.socket.create_connection = lambda _address, timeout: original(
        upstream.getsockname(), timeout=timeout
    )
    ready = threading.Event()
    thread = threading.Thread(target=_ollama_fixture, args=(upstream, ready), daemon=True)
    thread.start()
    proxy = InferenceOnlyUnixProxy(tmp_path / "proxy.sock")
    proxy.start()
    ready.wait(timeout=1)
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with client:
            client.connect(str(proxy.socket_path))
            client.sendall(
                b"POST /v1/chat/completions HTTP/1.1\r\n"
                b"Host: ignored\r\nTransfer-Encoding: chunked\r\n\r\n"
                b"2\r\n{}\r\n0\r\n\r\n"
            )
            assert b"200 OK" in client.recv(4096)

        denied = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with denied:
            denied.connect(str(proxy.socket_path))
            denied.sendall(b"POST /api/pull HTTP/1.1\r\nContent-Length: 0\r\n\r\n")
            assert b"403 Forbidden" in denied.recv(4096)
    finally:
        proxy.close()
        module.socket.create_connection = original
        upstream.close()


def test_model_request_is_explicitly_bounded() -> None:
    body, budget = _bound_model_request(b'{"model":"qwen3:4b"}', 16_000)
    assert budget == 512
    assert b'"max_tokens":512' in body
    assert b'"reasoning_effort":"none"' in body

    try:
        _bound_model_request(b'{"model":"qwen3:4b","max_tokens":0}', 16_000)
    except InferenceProxyError as exc:
        assert "output limit" in str(exc)
    else:
        raise AssertionError("invalid output limit was accepted")


def test_rewritten_request_has_one_utf8_content_length() -> None:
    request = _build_upstream_request(
        "POST",
        "/v1/chat/completions",
        [("content-length", "3"), ("X-Test", "ok")],
        "π".encode("utf-8"),
    )
    header, body = request.split(b"\r\n\r\n", 1)
    assert header.lower().count(b"content-length:") == 1
    assert b"Content-Length: 2" in header
    assert body == "π".encode("utf-8")


def test_bodyless_models_get_skips_json_validation_and_forwards_empty_body() -> None:
    request = _build_upstream_request("GET", "/v1/models", [("Content-Length", "0")], b"")
    header, body = request.split(b"\r\n\r\n", 1)
    assert b"GET /v1/models HTTP/1.1" in header
    assert header.lower().count(b"content-length:") == 1
    assert b"Content-Length: 0" in header
    assert body == b""


def test_proxy_forwards_models_get_without_json_body(tmp_path: Path) -> None:
    upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    upstream.bind(("127.0.0.1", 0))
    upstream.listen(1)
    import project_atlas.orchestration.program.prime_inference_proxy as module

    original = module.socket.create_connection
    module.socket.create_connection = lambda _address, timeout: original(
        upstream.getsockname(), timeout=timeout
    )

    def serve() -> None:
        connection, _ = upstream.accept()
        with connection:
            request = connection.recv(8192)
            assert b"GET /v1/models HTTP/1.1" in request
            assert request.split(b"\r\n\r\n", 1)[1] == b""
            connection.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
            )

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    proxy = InferenceOnlyUnixProxy(tmp_path / "models.sock")
    proxy.start()
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with client:
            client.connect(str(proxy.socket_path))
            client.sendall(b"GET /v1/models HTTP/1.1\r\nHost: ignored\r\n\r\n")
            assert b"200 OK" in client.recv(4096)
    finally:
        proxy.close()
        module.socket.create_connection = original
        upstream.close()
