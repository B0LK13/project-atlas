"""AS-CODER-ALPHA-CONFLICTS-MCP-001 — zero-arg vault-scoped conflicts MCP."""

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


def test_conflicts_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.conflicts.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_conflicts(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    result = invoke_mcp_tool(vault, "atlas.conflicts.read")["result"]
    assert result["package_id"] == CONFLICTS_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["reports"] == []
    assert result["honesty"]["resolved"] is False
    assert result["honesty"]["mcp_is_authority"] is False


def test_absent_conflict_file_is_empty_not_resolved(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    result = invoke_mcp_tool(vault, "atlas.conflicts.read")["result"]
    row = result["reports"][0]
    assert row["project_id"] == "harbor-api"
    payload = row["conflicts"]
    assert payload["project_id"] == "harbor-api"
    assert payload["conflict_count"] == 0
    assert payload["conflicts"] == []
    assert payload["authority"] == "derived"


def test_cross_project_isolation_and_secret_redaction(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    (vault / "projects" / "portal-app").mkdir(parents=True)
    fake_access_key = "AKIA" + ("0" * 16)
    _write(
        vault / "review" / "conflicts" / "harbor-api.json",
        {
            "entries": [
                {
                    "conflict_id": "c-harbor",
                    "subject": "datastore",
                    "field": "engine",
                    "conflict_type": "value",
                    "claims": [
                        {"claim": "postgresql-15", "source_id": "src-a"},
                        {"claim": fake_access_key, "source_id": "src-b"},
                    ],
                }
            ]
        },
    )
    _write(
        vault / "review" / "conflicts" / "portal-app.json",
        {
            "entries": [
                {
                    "conflict_id": "c-portal",
                    "subject": "ui",
                    "field": "theme",
                    "conflict_type": "value",
                    "claims": [{"claim": "portal-only-theme", "source_id": "src-p"}],
                }
            ]
        },
    )
    result = invoke_mcp_tool(vault, "atlas.conflicts.read")["result"]
    rows = {row["project_id"]: row["conflicts"] for row in result["reports"]}
    harbor = json.dumps(rows["harbor-api"], sort_keys=True)
    portal = json.dumps(rows["portal-app"], sort_keys=True)
    assert "c-harbor" in harbor
    assert "c-portal" not in harbor
    assert "portal-only-theme" not in harbor
    assert "postgresql-15" not in portal
    assert fake_access_key not in harbor
    assert "[redacted: secret-shaped value]" in harbor
    assert result["honesty"]["secrets_echoed"] is False


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.conflicts.read"}, sort_keys=True)
    assert handle_mcp_request_line(vault, line) == handle_mcp_request_line(vault, line)
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.conflicts.read", "args": {"project": "harbor-api"}}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.conflicts.read", operator=bare)
