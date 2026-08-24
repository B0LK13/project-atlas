"""AS-CODER-ALPHA-PROJECT-STATE-MCP-001 / ROADMAP-MCP-001 — vault-scoped MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    PROJECT_STATE_PACKAGE_ID,
    ROADMAP_PACKAGE_ID,
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


def test_tools_are_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.project-state.read" in listing["tools"]
    assert "atlas.roadmap.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_state_or_roadmap(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    state = invoke_mcp_tool(vault, "atlas.project-state.read")["result"]
    roadmap = invoke_mcp_tool(vault, "atlas.roadmap.read")["result"]
    assert state["package_id"] == PROJECT_STATE_PACKAGE_ID
    assert roadmap["package_id"] == ROADMAP_PACKAGE_ID
    assert state["project_count"] == 0
    assert roadmap["project_count"] == 0
    assert state["states"] == []
    assert roadmap["roadmaps"] == []
    assert state["honesty"]["mcp_is_authority"] is False
    assert roadmap["honesty"]["roadmap_is_canonical"] is False
    assert state["honesty"]["request_contains_as_of"] is False


def test_missing_artifacts_stay_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    state = invoke_mcp_tool(vault, "atlas.project-state.read")["result"]["states"]
    roadmap = invoke_mcp_tool(vault, "atlas.roadmap.read")["result"]["roadmaps"]
    assert len(state) == 1
    assert state[0]["project_id"] == "sparse-proj"
    assert roadmap[0]["project_id"] == "sparse-proj"
    state_body = json.dumps(state[0]["project_state"], sort_keys=True).upper()
    roadmap_body = json.dumps(roadmap[0]["roadmap"], sort_keys=True).upper()
    assert "UNKNOWN" in state_body or '"AVAILABLE": FALSE' in state_body
    assert "UNKNOWN" in roadmap_body or roadmap[0]["roadmap"].get("items") == []
    state_row = state[0]["project_state"]
    assert state_row.get("status") == "unknown"
    assert state_row.get("honesty") in {"NO_DATA", "UNKNOWN"} or (
        isinstance(state_row.get("honesty"), dict)
        and state_row["honesty"].get("lens_is_authority") is not True
    )
    assert state_row.get("authority", {}).get("derived_intelligence_is_authority") == "NO"
    roadmap_row = roadmap[0]["roadmap"]
    assert roadmap_row.get("status") == "unknown"
    assert roadmap_row.get("authority") == "derived-lens"


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    before = _snapshot(vault)
    for tool in ("atlas.project-state.read", "atlas.roadmap.read"):
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
                json.dumps({"tool": tool, "as_of": "2026-01-01T00:00:00Z"}),
            )
    assert _snapshot(vault) == before


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    for tool in ("atlas.project-state.read", "atlas.roadmap.read"):
        with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
            invoke_mcp_tool(vault, tool, operator=bare)


def test_determinism_and_sorted_ids(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "zeta-app").mkdir(parents=True)
    (vault / "projects" / "alpha-app").mkdir(parents=True)
    state = invoke_mcp_tool(vault, "atlas.project-state.read")
    again = invoke_mcp_tool(vault, "atlas.project-state.read")
    assert json.dumps(state, sort_keys=True) == json.dumps(again, sort_keys=True)
    ids = [row["project_id"] for row in state["result"]["states"]]
    assert ids == sorted(ids)
    road = invoke_mcp_tool(vault, "atlas.roadmap.read")
    rids = [row["project_id"] for row in road["result"]["roadmaps"]]
    assert rids == sorted(rids)
