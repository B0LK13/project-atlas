"""AS-CODER-ALPHA-OPS-RECEIPTS-MCP-001 — vault-scoped ops receipt inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    RECEIPTS_PACKAGE_ID,
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


def test_receipts_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.ops.receipts.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_absent_ops_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.ops.receipts.read")
    result = report["result"]
    assert result["package_id"] == RECEIPTS_PACKAGE_ID
    assert result["available"] is False
    assert result["receipt_rows"] == 0
    assert result["receipts"] == []
    assert result["rollup"] == "unknown"
    assert result["health"] == "unknown"
    assert result["honesty"]["unknown_equals_healthy"] is False
    assert result["honesty"]["completion_claimed"] is False
    assert result["honesty"]["authentic_pilot"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["release_certified"] is False


def test_presence_does_not_upgrade_health(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write(
        vault / "generated" / "ops" / "obs" / "sample-live.json",
        {"package_id": "AS-2.1-OBS-LIVE-001", "rollup": "healthy"},
    )
    report = invoke_mcp_tool(vault, "atlas.ops.receipts.read")
    result = report["result"]
    assert result["available"] is True
    assert result["receipt_rows"] == 1
    assert result["rollup"] == "unknown"
    assert result["health"] == "unknown"
    row = result["receipts"][0]
    assert row["health"] == "unknown"
    assert row.get("embedded_rollup_promoted") is False
    assert result["honesty"]["completion_claimed"] is False


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.ops.receipts.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.ops.receipts.read", "args": {"limit": 1}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.ops.receipts.read", "limit": 1}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.ops.receipts.read", operator=bare)
