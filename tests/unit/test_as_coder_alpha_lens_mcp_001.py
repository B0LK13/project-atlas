"""AS-CODER-ALPHA-*-MCP-001 — vault-scoped overview/unknown/state MCP tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.mcp_server import (
    OVERVIEW_PACKAGE_ID,
    STATE_PACKAGE_ID,
    UNKNOWN_PACKAGE_ID,
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


def _seed(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "alpha-one").mkdir(parents=True)
    (vault / "projects" / "beta-two").mkdir(parents=True)
    (vault / "projects" / "beta-two" / "project.md").write_text(
        "---\ntype: Project\ntitle: beta-two\n---\n\nSECRET-BETA-LENS\n",
        encoding="utf-8",
    )
    return vault


@pytest.mark.parametrize(
    ("tool_id", "package_id", "field"),
    [
        ("atlas.overview.read", OVERVIEW_PACKAGE_ID, "overview"),
        ("atlas.unknown.read", UNKNOWN_PACKAGE_ID, "unknown"),
        ("atlas.state.read", STATE_PACKAGE_ID, "state"),
    ],
)
def test_lens_tool_allow_listed_and_unknown_empty(
    tmp_path: Path, tool_id: str, package_id: str, field: str
) -> None:
    listing = list_mcp_tools()
    assert tool_id in listing["tools"]
    assert listing["write_tools"] == []
    empty = tmp_path / "empty"
    empty.mkdir()
    report = invoke_mcp_tool(empty, tool_id)
    result = report["result"]
    assert result["package_id"] == package_id
    assert result["project_count"] == 0
    assert result["lenses"] == []
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["portfolio_implicit_all"] is False


@pytest.mark.parametrize(
    ("tool_id", "field"),
    [
        ("atlas.overview.read", "overview"),
        ("atlas.unknown.read", "unknown"),
        ("atlas.state.read", "state"),
    ],
)
def test_lens_cross_project_and_no_write(
    tmp_path: Path, tool_id: str, field: str
) -> None:
    vault = _seed(tmp_path)
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, tool_id)
    assert _snapshot(vault) == before
    rows = {row["project_id"]: row[field] for row in report["result"]["lenses"]}
    assert set(rows) == {"alpha-one", "beta-two"}
    alpha = json.dumps(rows["alpha-one"], sort_keys=True)
    assert "SECRET-BETA-LENS" not in alpha
    assert rows["beta-two"]["project_id"] == "beta-two"
    line = json.dumps({"tool": tool_id}, sort_keys=True)
    assert handle_mcp_request_line(vault, line)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": tool_id, "args": {"project": "beta-two"}}),
        )
