"""D-INTEGRATE-007A §11/§12 resource-exhaustion hardening.

§11: LIVE_API slowloris — a partial request (no header terminator) must not
pin a worker thread forever; the per-connection read timeout closes it and the
server keeps serving other clients (loopback + Bearer + guards intact).

§12: ChatGPT bridge read — an oversized on-disk export must fail closed before
memory exhaustion, mirroring the sibling openai_import_real.py ceiling, while
normal-size exports still bridge (read-only, bounded, project-scoped).
"""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.chatgpt_bridge import (
    MAX_EXPORT_BYTES,
    ChatgptBridgeError,
    bridge_chatgpt_export,
)

# --- §11 SLOWLORIS ----------------------------------------------------------


def test_slowloris_partial_request_times_out_and_server_survives(
    tmp_path: Path,
) -> None:
    """A partial request must be closed by the read timeout; server survives."""
    vault = tmp_path / "v"
    vault.mkdir()
    # Short read timeout keeps the test fast; production default is 10s.
    server = serve_api(vault, host="127.0.0.1", port=0, read_timeout=0.5)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    slow = socket.create_connection((host, int(port)), timeout=5)
    try:
        # Slowloris: full request line + one header, then NO terminating blank
        # line — the server blocks parsing headers until the read timeout fires.
        slow.sendall(b"GET /v1/meta HTTP/1.1\r\nHost: 127.0.0.1\r\n")

        # The server must keep serving other clients while the slow socket is
        # held (ThreadingHTTPServer + bounded per-connection read timeout).
        auth = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/meta", headers=auth)
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["live_api"] is True

        # The partial connection must be closed by the server-side read timeout
        # (recv() returns b"" on a clean close). Without the timeout this socket
        # would be held indefinitely and recv() would block until client-side
        # timeout raised socket.timeout instead.
        slow.settimeout(5)
        assert slow.recv(1024) == b""
    finally:
        slow.close()
        server.shutdown()


def test_slowloris_send_nothing_still_recovers(tmp_path: Path) -> None:
    """Opening a socket and sending nothing must also time out, not wedge."""
    vault = tmp_path / "v"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0, read_timeout=0.5)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    idle = socket.create_connection((host, int(port)), timeout=5)
    try:
        idle.settimeout(5)
        # No bytes sent at all: the first request-line read must time out and
        # the server must close the connection rather than block forever.
        assert idle.recv(1024) == b""
        # A subsequent normal client is still served.
        auth = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/health", headers=auth)
        with urlopen(req, timeout=5) as resp:
            assert resp.status == 200
    finally:
        idle.close()
        server.shutdown()


# --- §12 CHATGPT BRIDGE READ ------------------------------------------------


def test_chatgpt_bridge_rejects_oversized_export(tmp_path: Path) -> None:
    """Oversized export fails closed before read_text (no receipt written)."""
    vault = tmp_path / "v"
    vault.mkdir()
    export = tmp_path / "huge.md"
    export.write_bytes(b"User: x\n" + (b"a" * (MAX_EXPORT_BYTES + 100)))
    with pytest.raises(ChatgptBridgeError, match="size-out-of-range"):
        bridge_chatgpt_export(vault, export, bridge_id="big-1")
    # Fail-closed: nothing quarantined or emitted.
    assert not (vault / "generated" / "ops" / "chatgpt" / "big-1-bridge.json").exists()


def test_chatgpt_bridge_rejects_empty_export(tmp_path: Path) -> None:
    """Zero-byte export is out of range (mirrors openai_import_real)."""
    vault = tmp_path / "v"
    vault.mkdir()
    export = tmp_path / "empty.md"
    export.write_bytes(b"")
    with pytest.raises(ChatgptBridgeError, match="size-out-of-range"):
        bridge_chatgpt_export(vault, export, bridge_id="empty-1")


def test_chatgpt_bridge_normal_size_still_bridges(tmp_path: Path) -> None:
    """Normal-size export still bridges into quarantine + receipt."""
    vault = tmp_path / "v"
    vault.mkdir()
    export = tmp_path / "conv.md"
    export.write_text("User: hi\nAssistant: hello\n", encoding="utf-8")
    report = bridge_chatgpt_export(vault, export, bridge_id="ok-1")
    assert report["chatgpt_bridge"] is True
    assert report["llm_authority"] is False
    assert report["turn_count"] == 2
    assert (vault / "generated" / "ops" / "chatgpt" / "ok-1-bridge.json").is_file()
