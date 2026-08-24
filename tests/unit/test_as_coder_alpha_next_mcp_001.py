"""AS-CODER-ALPHA-NEXT-MCP-001 — zero-arg vault-scoped What Next MCP tool."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    NEXT_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)


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


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    return vault


def test_next_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.next.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_next(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.next.read")
    result = report["result"]
    assert result["package_id"] == NEXT_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["lenses"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["next_is_command"] is False
    assert result["honesty"]["portfolio_implicit_all"] is False


def test_missing_project_evidence_is_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.next.read")
    rows = report["result"]["lenses"]
    assert len(rows) == 1
    assert rows[0]["project_id"] == "sparse-proj"
    lens = rows[0]["next"]
    assert lens["summary"] == "UNKNOWN"
    assert lens["honesty"]["unknown_is_valid"] is True
    assert lens["honesty"]["next_is_command"] is False
    assert lens["honesty"]["fabricated_fields"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    _write(
        vault / "projects" / "harbor-portal" / "project.md",
        "---\ntype: Project\ntitle: harbor-portal\n---\n\nSECRET-PORTAL-NEXT\n",
    )
    report = invoke_mcp_tool(vault, "atlas.next.read")
    rows = {row["project_id"]: row["next"] for row in report["result"]["lenses"]}
    assert set(rows) == {"dark-factory-02ee94d0", "harbor-portal"}
    factory = json.dumps(rows["dark-factory-02ee94d0"], sort_keys=True)
    assert "SECRET-PORTAL-NEXT" not in factory
    assert rows["harbor-portal"]["project_id"] == "harbor-portal"


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.next.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.next.read", "args": {"project": "harbor-portal"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.next.read", "project": "harbor-portal"}),
        )


def test_mcp_read_capability_required(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    bare = OperatorProfile(operator_id="bare", capabilities=frozenset())
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.next.read", operator=bare)
