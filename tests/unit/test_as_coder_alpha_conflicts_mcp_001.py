"""AS-CODER-ALPHA-CONFLICTS-MCP-001 — zero-arg vault-scoped conflict MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    CONFLICTS_PACKAGE_ID,
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
    _write(
        vault / "review" / "conflicts" / "dark-factory-02ee94d0.json",
        {
            "entries": [
                {
                    "conflict_id": "cf-factory",
                    "subject": "datastore",
                    "field": "engine",
                    "conflict_type": "value",
                    "claims": [{"claim": "Factory Postgres 15", "source_id": "src-a"}],
                }
            ]
        },
    )
    _write(
        vault / "review" / "conflicts" / "harbor-portal.json",
        {
            "entries": [
                {
                    "conflict_id": "cf-portal",
                    "subject": "ui",
                    "field": "theme",
                    "conflict_type": "value",
                    "claims": [{"claim": "PORTAL-ONLY-CLAIM", "source_id": "src-b"}],
                }
            ]
        },
    )
    return vault


def test_conflicts_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.conflicts.read" in listing["tools"]
    assert "atlas.context.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_conflicts(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    result = report["result"]
    assert result["package_id"] == CONFLICTS_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["projects"] == []
    assert result["honesty"]["resolution_selected"] is False
    assert result["honesty"]["mcp_is_authority"] is False


def test_missing_conflict_file_is_empty_not_resolved(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    rows = report["result"]["projects"]
    assert len(rows) == 1
    payload = rows[0]["conflicts"]
    assert payload["conflict_count"] == 0
    assert payload["conflicts"] == []
    assert payload["honesty"]["resolution_selected"] is False
    assert payload["honesty"]["unknown_is_valid"] is True


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    rows = {row["project_id"]: row["conflicts"] for row in report["result"]["projects"]}
    factory = json.dumps(rows["dark-factory-02ee94d0"], sort_keys=True)
    assert "PORTAL-ONLY-CLAIM" not in factory
    assert rows["dark-factory-02ee94d0"]["conflict_count"] == 1
    assert rows["harbor-portal"]["conflicts"][0]["claims"][0]["claim"] == "PORTAL-ONLY-CLAIM"
    assert "Factory Postgres 15" not in json.dumps(rows["harbor-portal"])


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.conflicts.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.conflicts.read", "write": True}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.conflicts.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.conflicts.read", operator=bare)


def test_does_not_touch_d149_owner_gates() -> None:
    source = Path(__file__).resolve().parents[2] / "src" / "project_atlas" / "mcp_server.py"
    text = source.read_text(encoding="utf-8")
    assert "refresh_authentic_o2_node_states" not in text
    assert "OWNER_GATE" not in text
