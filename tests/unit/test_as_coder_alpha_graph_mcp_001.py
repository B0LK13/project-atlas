"""AS-CODER-ALPHA-GRAPH-MCP-001 — zero-arg vault-scoped impact-graph MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile, elevated_operator
from project_atlas.mcp_server import (
    GRAPH_PACKAGE_ID,
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


def _write_graph(vault: Path, *, nodes: list[object], edges: list[object]) -> None:
    path = vault / "generated" / "indexes" / "impact-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "nodes": nodes,
                "edges": edges,
                "authority_plane": "derived",
                "note": "IMPACT GRAPH ≠ AUTOMATIC AUTHORITY",
                "truth_boundary": "Graph≠authority",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_graph_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.graph.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.vault.write" not in listing["tools"]


def test_absent_graph_is_unknown_not_fabricated(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.graph.read")
    result = report["result"]
    assert result["package_id"] == GRAPH_PACKAGE_ID
    graph = result["graph"]
    assert graph["available"] is False
    assert graph["node_count"] == 0
    assert graph["edge_count"] == 0
    assert graph["graph_authority"] is False
    assert result["honesty"]["graph_is_authority"] is False
    assert result["honesty"]["fabricated_edges"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["unknown_is_valid"] is True


def test_unreadable_and_elevated_authority_stay_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    bad = vault / "generated" / "indexes"
    bad.mkdir(parents=True)
    (bad / "impact-graph.json").write_text("{not-json", encoding="utf-8")
    unreadable = invoke_mcp_tool(vault, "atlas.graph.read")["result"]["graph"]
    assert unreadable["available"] is False
    (bad / "impact-graph.json").write_text(
        json.dumps({"nodes": [{"id": "x"}], "edges": [], "authority_plane": "canonical"}),
        encoding="utf-8",
    )
    elevated = invoke_mcp_tool(vault, "atlas.graph.read")["result"]["graph"]
    assert elevated["available"] is False
    assert elevated["node_count"] == 0
    assert elevated["edge_count"] == 0


def test_derived_graph_counts_without_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write_graph(
        vault,
        nodes=[{"id": "a"}, {"id": "b"}],
        edges=[{"from": "a", "to": "b"}],
    )
    result = invoke_mcp_tool(vault, "atlas.graph.read")["result"]
    assert result["graph"]["available"] is True
    assert result["graph"]["node_count"] == 2
    assert result["graph"]["edge_count"] == 1
    assert result["graph"]["graph_authority"] is False
    assert result["graph"]["authority"] == "derived"
    assert result["honesty"]["graph_is_authority"] is False
    dumped = json.dumps(result, sort_keys=True)
    assert '"owner_capability_granted": false' in dumped
    assert '"owner_capability_granted": true' not in dumped


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write_graph(vault, nodes=[{"id": "n1"}], edges=[])
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.graph.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.graph.read", "args": {"path": "generated/indexes"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.graph.read", "project": "harbor-api"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.graph.read", operator=bare)


def test_write_tools_remain_denied(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    elev = elevated_operator("graph-mcp-elev", extra={"vault.write"})
    for tool in ("atlas.vault.write", "atlas.estate.scan", "atlas.provider.generate"):
        with pytest.raises(McpServerError, match="mcp-tool-denied"):
            invoke_mcp_tool(vault, tool, operator=elev)
