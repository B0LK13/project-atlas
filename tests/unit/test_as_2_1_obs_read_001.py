"""AS-2.1-OBS-READ-001 — read-only observability compute + MCP."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.obs_live import (
    PACKAGE_ID,
    build_live_observability_receipt,
    compute_live_observability_receipt,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def test_compute_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    before = _snapshot(vault)
    receipt = compute_live_observability_receipt(vault, receipt_id="no-write")
    assert receipt["package_id"] == PACKAGE_ID
    assert receipt["rollup"] == "unknown"
    assert receipt["authority_plane"] == "none"
    assert receipt["truth_boundary"]
    assert not (vault / "generated" / "ops" / "obs").exists()
    assert _snapshot(vault) == before


def test_build_still_persists_explicit_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    receipt = build_live_observability_receipt(vault, receipt_id="persist")
    path = vault / "generated" / "ops" / "obs" / "persist-live.json"
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["receipt_id"] == "persist"
    computed = compute_live_observability_receipt(vault, receipt_id="persist")
    assert computed["receipt_id"] == receipt["receipt_id"]
    assert computed["surfaces"] == receipt["surfaces"]


def test_mcp_obs_is_allow_listed_and_read_only(tmp_path: Path) -> None:
    listing = list_mcp_tools()
    assert "atlas.obs.read" in listing["tools"]
    assert listing["write_tools"] == []
    vault = tmp_path / "v"
    vault.mkdir()
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, "atlas.obs.read")
    result = report["result"]
    assert result["package_id"] == PACKAGE_ID
    assert result["rollup"] == "unknown"
    assert result["authority_plane"] == "none"
    assert _snapshot(vault) == before
    line = json.dumps({"tool": "atlas.obs.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.obs.read", "args": {"receipt_id": "x"}}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.obs.read", operator=bare)


def test_http_obs_get_does_not_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/obs", headers=hdrs)
        with urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["authority_plane"] == "none"
        assert payload["rollup"] == "unknown"
        assert not (vault / "generated" / "ops" / "obs").exists()
        post = Request(
            f"http://{host}:{port}/v1/obs",
            data=b"{}",
            headers={**hdrs, "Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(post, timeout=3)
        assert exc.value.code == 405
    finally:
        server.shutdown()
