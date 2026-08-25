"""AS-CODER-ALPHA-CONFLICTS-MCP-001 — zero-arg vault-scoped conflicts MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile, elevated_operator
from project_atlas.mcp_server import (
    CONFLICTS_PACKAGE_ID,
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


def _write_conflicts(vault: Path, project_id: str, entries: list[dict[str, object]]) -> None:
    (vault / "projects" / project_id).mkdir(parents=True, exist_ok=True)
    path = vault / "review" / "conflicts" / f"{project_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"entries": entries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_conflicts_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.conflicts.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.vault.write" not in listing["tools"]


def test_empty_vault_does_not_invent_conflicts(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    result = report["result"]
    assert result["package_id"] == CONFLICTS_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["projects"] == []
    assert result["honesty"]["resolved"] is False
    assert result["honesty"]["winner_selected"] is False
    assert result["honesty"]["owner_capability_granted"] is False


def test_missing_conflict_file_is_empty_not_resolved(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    rows = report["result"]["projects"]
    assert len(rows) == 1
    assert rows[0]["project_id"] == "sparse-proj"
    assert rows[0]["available"] is True
    assert rows[0]["conflict_count"] == 0
    assert rows[0]["conflicts"] == []
    assert rows[0]["honesty"]["resolved"] is False
    assert rows[0]["honesty"]["winner_selected"] is False


def test_cross_project_isolation_and_no_winner(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write_conflicts(
        vault,
        "dark-factory",
        [
            {
                "conflict_id": "c-factory",
                "subject": "datastore",
                "field": "engine",
                "conflict_type": "value",
                "claims": [
                    {"claim": "postgres-15", "source_id": "src-a"},
                    {"claim": "postgres-16", "source_id": "src-b"},
                ],
            }
        ],
    )
    _write_conflicts(
        vault,
        "harbor-portal",
        [
            {
                "conflict_id": "c-portal",
                "subject": "ui",
                "field": "theme",
                "conflict_type": "value",
                "claims": [{"claim": "SECRET-PORTAL-THEME", "source_id": "src-p"}],
            }
        ],
    )
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    rows = {row["project_id"]: row for row in report["result"]["projects"]}
    assert set(rows) == {"dark-factory", "harbor-portal"}
    factory = json.dumps(rows["dark-factory"], sort_keys=True)
    assert "SECRET-PORTAL-THEME" not in factory
    assert rows["dark-factory"]["conflict_count"] == 1
    assert rows["dark-factory"]["honesty"]["resolved"] is False
    assert rows["dark-factory"]["honesty"]["winner_selected"] is False
    assert "SECRET-PORTAL-THEME" in json.dumps(rows["harbor-portal"])
    dumped = json.dumps(report, sort_keys=True)
    assert '"owner_capability_granted": false' in dumped
    assert '"owner_capability_granted": true' not in dumped
    assert '"winner_selected": false' in dumped
    assert '"resolved": false' in dumped


def test_secret_shaped_claim_is_redacted(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    secret = "AKIA" + ("A" * 16)
    _write_conflicts(
        vault,
        "harbor-api",
        [
            {
                "conflict_id": "c-secret",
                "subject": "creds",
                "field": "key",
                "conflict_type": "value",
                "claims": [{"claim": secret, "source_id": "src-s"}],
            }
        ],
    )
    report = invoke_mcp_tool(vault, "atlas.conflicts.read")
    dumped = json.dumps(report, sort_keys=True)
    assert secret not in dumped
    assert "redacted: secret-shaped value" in dumped


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write_conflicts(
        vault,
        "harbor-api",
        [
            {
                "conflict_id": "c1",
                "subject": "x",
                "field": "y",
                "conflict_type": "value",
                "claims": [{"claim": "a", "source_id": "s1"}],
            }
        ],
    )
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.conflicts.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.conflicts.read", "args": {"resolve": True}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.conflicts.read", "project": "harbor-api"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.conflicts.read", operator=bare)


def test_write_tools_remain_denied(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    elev = elevated_operator("conflicts-mcp-elev", extra={"vault.write"})
    for tool in ("atlas.vault.write", "atlas.estate.scan", "atlas.provider.generate"):
        with pytest.raises(McpServerError, match="mcp-tool-denied"):
            invoke_mcp_tool(vault, tool, operator=elev)
