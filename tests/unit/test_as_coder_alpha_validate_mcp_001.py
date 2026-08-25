"""AS-CODER-ALPHA-VALIDATE-MCP-001 — vault-scoped read-only validate."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from project_atlas.api_server import serve_api, session_credentials
from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    VALIDATE_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _start(vault: Path) -> tuple[Any, str, int]:
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, str(host), int(port)


def _get(host: str, port: int, path: str, auth: dict[str, str]) -> tuple[int, dict[str, Any]]:
    req = Request(f"http://{host}:{port}{path}", headers=auth)
    try:
        with urlopen(req, timeout=2) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        return int(exc.code), json.loads(exc.read().decode("utf-8"))


def test_validate_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.validate.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_is_honest_failure_not_invented_ok(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.validate.read")
    result = report["result"]
    assert result["package_id"] == VALIDATE_PACKAGE_ID
    assert result["ok"] is False
    assert result["error_count"] > 0
    assert result["authority"] == "derived"
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["ok_is_authority"] is False
    assert result["honesty"]["ok_is_healthy"] is False
    assert result["honesty"]["ok_is_release"] is False
    assert result["honesty"]["authentic_pilot"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["portfolio_implicit_all"] is False
    dump = json.dumps(result, sort_keys=True)
    assert "missing required generated file" in dump
    assert '"owner_capability_granted": true' not in dump


def test_scaffold_errors_are_deterministic_and_sorted(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    a = invoke_mcp_tool(vault, "atlas.validate.read")
    b = invoke_mcp_tool(vault, "atlas.validate.read")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    errors = a["result"]["errors"]
    assert errors == sorted(errors)


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "projects").mkdir()
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.validate.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.validate.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.validate.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.validate.read", operator=bare)


def test_passing_report_is_not_authority_or_pilot(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.validate.read")
    honesty = report["result"]["honesty"]
    assert honesty["ok_is_authority"] is False
    assert honesty["ok_is_healthy"] is False
    assert honesty["ok_is_release"] is False
    assert honesty["authentic_pilot"] is False
    assert honesty["owner_capability_granted"] is False
    assert honesty["canonical_write"] is False


def test_live_api_validate_matches_mcp_and_is_read_only(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    mcp = invoke_mcp_tool(vault, "atlas.validate.read")["result"]
    server, host, port = _start(vault)
    try:
        auth = session_credentials(server).auth_headers()
        after_bind = _snapshot(vault)
        status, body = _get(host, port, "/v1/validate", auth)
        meta_status, meta = _get(host, port, "/v1/meta", auth)
        after_read = _snapshot(vault)
    finally:
        server.shutdown()
        server.server_close()
    assert status == 200
    assert meta_status == 200
    assert meta.get("validate_live") is True
    assert body["package_id"] == VALIDATE_PACKAGE_ID
    assert body["ok"] is False
    assert body["errors"] == mcp["errors"]
    assert body["honesty"]["mcp_is_authority"] is False
    assert body["honesty"]["owner_capability_granted"] is False
    assert after_read == after_bind


def test_web_surfaces_are_wired() -> None:
    root = Path(__file__).resolve().parents[2]
    app = (root / "apps" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    nav = (root / "apps" / "web" / "src" / "components" / "ProdNav.tsx").read_text(
        encoding="utf-8"
    )
    page = (
        root / "apps" / "web" / "src" / "pages" / "production" / "ValidatePage.tsx"
    ).read_text(encoding="utf-8")
    hook = (root / "apps" / "web" / "src" / "hooks" / "useLiveValidate.ts").read_text(
        encoding="utf-8"
    )
    home = (root / "apps" / "web" / "src" / "pages" / "HomePage.tsx").read_text(
        encoding="utf-8"
    )
    assert 'path="/validate"' in app
    assert 'to: "/validate"' in nav
    assert "useLiveValidate" in page
    assert "ok≠healthy" in page
    assert 'liveApiFetch("/v1/validate")' in hook
    assert 'to: "/validate"' in home
    docs = (root / "docs" / "AS-CODER-ALPHA-VALIDATE-MCP-001.md").read_text(
        encoding="utf-8"
    )
    assert "atlas.validate.read" in docs
    assert "PILOT" in docs
