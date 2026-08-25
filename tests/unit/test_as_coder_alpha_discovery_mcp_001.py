"""AS-CODER-ALPHA-DISCOVERY-MCP-001 — zero-arg discovery-report MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile, elevated_operator
from project_atlas.mcp_server import (
    DISCOVERY_PACKAGE_ID,
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


def _write_report(vault: Path, payload: dict[str, object]) -> None:
    path = vault / "generated" / "ops" / "estate-discovery-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_discovery_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.discovery.read" in listing["tools"]
    assert "atlas.estate.scan" not in listing["tools"]
    assert listing["write_tools"] == []


def test_absent_report_does_not_invent_roots(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.discovery.read")
    result = report["result"]
    assert result["package_id"] == DISCOVERY_PACKAGE_ID
    discovery = result["discovery"]
    assert discovery["present"] is False
    assert discovery["authorized_root"] is None
    assert discovery["volume_root_authorized"] is False
    assert discovery["categories"]["DISCOVERED_PROJECTS"] == []
    assert result["honesty"]["invented_roots"] is False
    assert result["honesty"]["estate_scan"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["authentic_pilot"] is False
    assert result["honesty"]["volume_root_is_owner_authority"] is False


def test_volume_root_flag_does_not_grant_owner(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write_report(
        vault,
        {
            "authorized_root": "/tmp/not-an-owner-grant",
            "authorized_root_mode": "explicit",
            "volume_root_authorized": True,
            "volume_root_kind": "POSIX",
            "counts": {
                "projects": 1,
                "knowledge": 0,
                "ignored": 0,
                "required_review": 0,
                "connected": 0,
            },
            "scan": {"scan_complete": True},
            "categories": {
                "DISCOVERED_PROJECTS": [{"path": "harbor-api"}],
                "NEW_KNOWLEDGE": [],
                "AMBIGUOUS_MATCHES": [],
                "UNMATCHED_KNOWLEDGE": [],
                "IGNORED": [],
                "CONNECTED": [],
            },
        },
    )
    result = invoke_mcp_tool(vault, "atlas.discovery.read")["result"]
    assert result["discovery"]["present"] is True
    assert result["discovery"]["volume_root_authorized"] is True
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["authentic_pilot"] is False
    assert result["honesty"]["volume_root_is_owner_authority"] is False
    dumped = json.dumps(result, sort_keys=True)
    assert '"owner_capability_granted": false' in dumped
    assert '"owner_capability_granted": true' not in dumped
    assert '"authentic_pilot": true' not in dumped


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write_report(vault, {"categories": {}})
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.discovery.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.discovery.read", "args": {"root": "/tmp/estate"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.discovery.read", "root": "/tmp/estate"}),
        )


def test_mcp_read_required_and_estate_scan_denied(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.discovery.read", operator=bare)
    elev = elevated_operator("discovery-mcp-elev", extra={"vault.write"})
    with pytest.raises(McpServerError, match="mcp-tool-denied"):
        invoke_mcp_tool(vault, "atlas.estate.scan", operator=elev)
