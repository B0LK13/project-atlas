"""AS-CODER-ALPHA-UNKNOWN-MCP-001 / CHANGED-MCP-001 — zero-arg vault lenses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    CHANGED_MCP_PACKAGE_ID,
    UNKNOWN_MCP_PACKAGE_ID,
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


def test_unknown_and_changed_tools_are_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.unknown.read" in listing["tools"]
    assert "atlas.changed.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_lenses(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    unknown = invoke_mcp_tool(vault, "atlas.unknown.read")["result"]
    assert unknown["package_id"] == UNKNOWN_MCP_PACKAGE_ID
    assert unknown["project_count"] == 0
    assert unknown["unknowns"] == []
    assert unknown["honesty"]["unknown_is_healthy"] is False
    assert unknown["honesty"]["portfolio_implicit_all"] is False
    changed = invoke_mcp_tool(vault, "atlas.changed.read")["result"]
    assert changed["package_id"] == CHANGED_MCP_PACKAGE_ID
    assert changed["project_count"] == 0
    assert changed["changed"] == []
    assert changed["honesty"]["changed_is_kdiff"] is False


def test_missing_evidence_stays_unknown_not_healthy_or_unchanged(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    unknown = invoke_mcp_tool(vault, "atlas.unknown.read")["result"]["unknowns"]
    assert len(unknown) == 1
    lens = unknown[0]["unknown"]
    assert unknown[0]["project_id"] == "sparse-proj"
    assert lens["rollup"] == "unknown"
    assert lens["honesty"]["unknown_is_healthy"] is False
    changed = invoke_mcp_tool(vault, "atlas.changed.read")["result"]["changed"]
    assert len(changed) == 1
    clens = changed[0]["changed"]
    assert clens["status"] == "unknown"
    assert clens["rollup"] == "baseline"
    assert clens["honesty"]["changed_is_kdiff"] is False


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    before = _snapshot(vault)
    for tool in ("atlas.unknown.read", "atlas.changed.read"):
        line = json.dumps({"tool": tool}, sort_keys=True)
        first = handle_mcp_request_line(vault, line)
        second = handle_mcp_request_line(vault, line)
        assert first == second
        with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
            handle_mcp_request_line(
                vault,
                json.dumps({"tool": tool, "args": {"project": "harbor-api"}}),
            )
        with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
            handle_mcp_request_line(
                vault,
                json.dumps({"tool": tool, "project": "harbor-api"}),
            )
    assert _snapshot(vault) == before
    assert not (vault / "generated").exists()


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.unknown.read", operator=bare)
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.changed.read", operator=bare)
