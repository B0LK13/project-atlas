"""AS-CODER-ALPHA-MISSION-WORKSPACE-MCP-001 — read-only mission/workspace MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile, elevated_operator
from project_atlas.mcp_server import (
    MISSION_WS_PACKAGE_ID,
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


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    (vault / "generated" / "ops" / "pilot").mkdir(parents=True)
    (vault / "generated" / "ops" / "obs").mkdir(parents=True)
    (vault / "generated" / "ops" / "pilot" / "marker.txt").write_text(
        "not-an-authentic-pilot\n", encoding="utf-8"
    )
    return vault


def test_mission_and_workspace_tools_are_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.mission.read" in listing["tools"]
    assert "atlas.workspace.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.vault.write" not in listing["tools"]


@pytest.mark.parametrize("tool", ("atlas.mission.read", "atlas.workspace.read"))
def test_empty_vault_does_not_invent_pilot(tmp_path: Path, tool: str) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, tool)
    result = report["result"]
    assert result["package_id"] == MISSION_WS_PACKAGE_ID
    view = result["view"]
    assert view["project_count"] == 0
    assert view["empty_projects"] is True
    assert view["pilot_estate_rows"] == []
    assert view["authentic_pilot"] is False
    assert view["ui_canonical"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["pilot_invented"] is False


def test_ops_pilot_dir_does_not_become_authentic_pilot(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    mission = invoke_mcp_tool(vault, "atlas.mission.read")["result"]
    workspace = invoke_mcp_tool(vault, "atlas.workspace.read")["result"]
    assert mission["view"]["project_count"] == 1
    assert mission["view"]["surfaces"]["obs"] is True
    assert mission["view"]["surfaces"]["pilot"] is True
    assert mission["view"]["pilot_estate_rows"] == []
    assert mission["view"]["authentic_pilot"] is False
    assert workspace["view"]["pilot_estate_rows"] == []
    assert workspace["view"]["authentic_pilot"] is False
    dumped = json.dumps({"mission": mission, "workspace": workspace}, sort_keys=True)
    assert '"owner_capability_granted": false' in dumped
    assert '"owner_capability_granted": true' not in dumped
    assert '"authentic_pilot": true' not in dumped


@pytest.mark.parametrize("tool", ("atlas.mission.read", "atlas.workspace.read"))
def test_zero_arg_protocol_and_no_write(tmp_path: Path, tool: str) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": tool}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": tool, "args": {"estate": "/tmp/fake"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": tool, "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.mission.read", operator=bare)


def test_write_tools_remain_denied(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    elev = elevated_operator("mission-mcp-elev", extra={"vault.write"})
    for tool in ("atlas.vault.write", "atlas.estate.scan", "atlas.provider.generate"):
        with pytest.raises(McpServerError, match="mcp-tool-denied"):
            invoke_mcp_tool(vault, tool, operator=elev)
