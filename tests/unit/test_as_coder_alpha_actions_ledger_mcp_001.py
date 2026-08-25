"""AS-CODER-ALPHA-ACTIONS-LEDGER-MCP-001 — vault-scoped action ledger read."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile, elevated_operator
from project_atlas.mcp_server import (
    ACTIONS_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)
from project_atlas.web_actions import submit_web_action


def _snapshot(vault: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(vault.rglob("*")):
        if path.is_file():
            out[path.relative_to(vault).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return out


def test_actions_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.actions.ledger.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_ledger_is_valid_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, "atlas.actions.ledger.read")
    result = report["result"]
    assert result["package_id"] == ACTIONS_PACKAGE_ID
    assert result["transaction_count"] == 0
    assert result["transactions"] == []
    assert result["honesty"]["empty_is_healthy"] is False
    assert result["honesty"]["get_is_post"] is False
    assert result["honesty"]["ledger_is_truth_core"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["authentic_pilot"] is False
    assert _snapshot(vault) == before


def test_existing_ledger_is_read_not_posted(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    submit_web_action(
        vault,
        action_id="act-refresh-1",
        action_type="refresh-status",
        payload={"lens": "ops"},
        operator=elevated_operator("ledger-seed", extra={"web.action"}),
    )
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, "atlas.actions.ledger.read")
    result = report["result"]
    assert result["transaction_count"] == 1
    assert result["transactions"][0]["action_id"] == "act-refresh-1"
    assert result["honesty"]["canonical_write"] is False
    assert _snapshot(vault) == before


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.actions.ledger.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.actions.ledger.read", "args": {"action_id": "x"}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.actions.ledger.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.actions.ledger.read", operator=bare)


def test_web_surfaces_are_wired() -> None:
    root = Path(__file__).resolve().parents[2]
    app = (root / "apps" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    nav = (root / "apps" / "web" / "src" / "components" / "ProdNav.tsx").read_text(
        encoding="utf-8"
    )
    page = (
        root / "apps" / "web" / "src" / "pages" / "production" / "ActionsPage.tsx"
    ).read_text(encoding="utf-8")
    hook = (root / "apps" / "web" / "src" / "hooks" / "useLiveActions.ts").read_text(
        encoding="utf-8"
    )
    assert 'path="/actions"' in app
    assert 'to: "/actions"' in nav
    assert "useLiveActions" in page
    assert "get≠post" in page
    assert 'liveApiFetch("/v1/actions")' in hook
    docs = (root / "docs" / "AS-CODER-ALPHA-ACTIONS-LEDGER-MCP-001.md").read_text(
        encoding="utf-8"
    )
    assert "atlas.actions.ledger.read" in docs
    assert "POST" in docs
