"""AS-CODER-ALPHA-HANDOFF-MCP-001 — vault-scoped read-only handoff inventory."""

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
from project_atlas.cli import EXIT_OK, main
from project_atlas.mcp_server import (
    HANDOFF_MCP_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_api.handoffs import WebHandoffError, list_handoffs


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def _pack(
    *,
    handoff_id: str,
    project_id: str,
    purpose: str,
    note: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "handoff_id": handoff_id,
        "project_id": project_id,
        "operator_note": note,
        "context": {"purpose": purpose, "project_id": project_id},
        "honesty": {"lens_is_authority": False},
    }


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    factory = _pack(
        handoff_id="handoff-factory-aaaa",
        project_id="dark-factory-02ee94d0",
        purpose="Factory compile",
        note="resume factory",
    )
    portal = _pack(
        handoff_id="handoff-portal-bbbb",
        project_id="harbor-portal",
        purpose="Portal UI",
        note="SECRET-PORTAL-HANDOFF",
    )
    _write(vault / "generated" / "ops" / "handoffs" / "handoff-factory-aaaa.json", factory)
    _write(vault / "generated" / "ops" / "handoffs" / "handoff-portal-bbbb.json", portal)
    _write(
        vault / "generated" / "ops" / "handoffs" / "latest.json",
        {
            "handoff_id": "handoff-portal-bbbb",
            "path": "generated/ops/handoffs/handoff-portal-bbbb.json",
            "project_id": "harbor-portal",
        },
    )
    return vault


def test_handoff_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.handoff.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_handoffs(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.handoff.read")
    result = report["result"]
    assert result["package_id"] == HANDOFF_MCP_PACKAGE_ID
    assert result["handoff_count"] == 0
    assert result["handoffs"] == []
    assert result["available"] is False
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["create_or_resume"] is False
    assert result["honesty"]["portfolio_implicit_all"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    scoped = list_handoffs(vault, project_id="dark-factory-02ee94d0")
    assert scoped["handoff_count"] == 1
    row = scoped["handoffs"][0]
    assert row["project_id"] == "dark-factory-02ee94d0"
    blob = json.dumps(scoped, sort_keys=True)
    assert "SECRET-PORTAL-HANDOFF" not in blob
    assert "Portal UI" not in blob
    assert scoped["latest"] is None


def test_malformed_and_escape_paths_are_ignored(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    outside = tmp_path / "outside.json"
    _write(outside, _pack(handoff_id="handoff-escape", project_id="evil", purpose="leak"))
    handoffs = vault / "generated" / "ops" / "handoffs"
    handoffs.mkdir(parents=True)
    _write(
        handoffs / "not-a-handoff.json",
        _pack(handoff_id="handoff-nope", project_id="x", purpose="nope"),
    )
    _write(handoffs / "handoff-bad.json", ["not", "an", "object"])
    (handoffs / "handoff-link.json").symlink_to(outside)
    report = list_handoffs(vault)
    assert report["handoff_count"] == 0
    assert report["handoffs"] == []


def test_malicious_latest_pointer_is_not_echoed(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    handoffs = vault / "generated" / "ops" / "handoffs"
    handoffs.mkdir(parents=True)
    _write(
        handoffs / "latest.json",
        {
            "handoff_id": "handoff-escape",
            "path": "../../etc/passwd",
            "project_id": "harbor-portal",
        },
    )
    report = list_handoffs(vault)
    assert report["latest"] is None
    assert "../../etc/passwd" not in json.dumps(report)
    assert "/etc/passwd" not in json.dumps(report)


def test_invalid_project_filter_fail_closed(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    with pytest.raises(WebHandoffError):
        list_handoffs(vault, project_id="../etc")


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.handoff.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    payload = json.loads(first)
    assert payload["result"]["handoff_count"] == 2
    ids = [row["handoff_id"] for row in payload["result"]["handoffs"]]
    assert ids == sorted(ids)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.handoff.read", "args": {"project": "harbor-portal"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.handoff.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.handoff.read", operator=bare)


def test_live_api_list_and_filter(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    server = serve_api(vault, host="127.0.0.1", port=0)
    host, port = server.server_address[:2]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        hdrs = session_credentials(server).auth_headers()
        req = Request(f"http://{host}:{port}/v1/handoffs", headers=hdrs)
        with urlopen(req, timeout=2) as resp:
            all_rows = json.loads(resp.read().decode("utf-8"))
        assert all_rows["handoff_count"] == 2
        assert all_rows["honesty"]["create_or_resume"] is False
        req = Request(
            f"http://{host}:{port}/v1/handoffs?project=dark-factory-02ee94d0",
            headers=hdrs,
        )
        with urlopen(req, timeout=2) as resp:
            scoped = json.loads(resp.read().decode("utf-8"))
        assert scoped["handoff_count"] == 1
        assert scoped["handoffs"][0]["project_id"] == "dark-factory-02ee94d0"
        assert "SECRET-PORTAL-HANDOFF" not in json.dumps(scoped)
        req = Request(
            f"http://{host}:{port}/v1/handoffs?project=../etc",
            headers=hdrs,
        )
        with pytest.raises(HTTPError) as exc:
            urlopen(req, timeout=2)
        assert exc.value.code == 400
    finally:
        server.shutdown()


def test_cli_handoff_list_is_read_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    assert main(["handoff", "list", "--vault", str(vault), "--json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["handoff_count"] == 2
    assert payload["honesty"]["create_or_resume"] is False
    assert _snapshot(vault) == before


def test_repeated_list_is_idempotent(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    first = list_handoffs(vault)
    second = list_handoffs(vault)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
