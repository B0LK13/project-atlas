"""AS-2.1 Host/CORS ADV matrix deepen (release-hardening)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import CORS_ORIGIN, serve_api


def test_adv_options_cors_headers(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = Request(
            f"http://{host}:{port}/v1/meta",
            method="OPTIONS",
            headers={"Origin": CORS_ORIGIN},
        )
        with urlopen(req, timeout=2) as resp:
            assert resp.status == 204
            assert resp.headers.get("Access-Control-Allow-Origin") == CORS_ORIGIN
            methods = resp.headers.get("Access-Control-Allow-Methods", "")
            assert "GET" in methods
            assert "POST" in methods
    finally:
        server.shutdown()


def test_adv_get_rejects_evil_host(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = Request(
            f"http://{host}:{port}/v1/health",
            headers={"Host": "attacker.example"},
        )
        with pytest.raises(HTTPError) as excinfo:
            urlopen(req, timeout=2)
        assert excinfo.value.code == 403
        body = json.loads(excinfo.value.read().decode("utf-8"))
        assert body["error"] == "host-non-local-forbidden"
    finally:
        server.shutdown()


def test_adv_local_host_with_port_allowed(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = Request(
            f"http://{host}:{port}/v1/meta",
            headers={"Host": f"127.0.0.1:{port}"},
        )
        with urlopen(req, timeout=2) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
        assert meta["live_api"] is True
    finally:
        server.shutdown()
