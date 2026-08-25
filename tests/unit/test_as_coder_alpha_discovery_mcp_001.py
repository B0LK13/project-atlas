"""AS-CODER-ALPHA-DISCOVERY-MCP-001 — vault-scoped estate discovery MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.estate_discovery import REPORT_RELATIVE
from project_atlas.mcp_server import (
    DISCOVERY_PACKAGE_ID,
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


def test_discovery_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.discovery.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_absent_report_does_not_invent_roots(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.discovery.read")
    result = report["result"]
    assert result["package_id"] == DISCOVERY_PACKAGE_ID
    assert result["present"] is False
    assert result["authorized_root"] is None
    assert result["volume_root_authorized"] is False
    assert result["counts"]["projects"] == 0
    assert result["categories"]["DISCOVERED_PROJECTS"] == []
    assert result["honesty"]["invented_pilot_roots"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["ingest"] is False
    assert result["honesty"]["authentic_pilot"] is False


def test_present_report_is_projected_not_ingested(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    _write(
        vault / REPORT_RELATIVE,
        {
            "authorized_root": "/tmp/authorized-root",
            "volume_root_authorized": False,
            "volume_root_kind": "NONE",
            "counts": {"projects": 1, "knowledge": 0},
            "categories": {
                "DISCOVERED_PROJECTS": [{"project_id": "harbor-portal"}],
                "NEW_KNOWLEDGE": [],
                "AMBIGUOUS_MATCHES": [],
                "UNMATCHED_KNOWLEDGE": [],
                "IGNORED": [],
                "CONNECTED": [],
            },
            "scan": {"scan_complete": True},
        },
    )
    report = invoke_mcp_tool(vault, "atlas.discovery.read")
    result = report["result"]
    assert result["present"] is True
    assert result["counts"]["projects"] == 1
    assert result["categories"]["DISCOVERED_PROJECTS"][0]["project_id"] == "harbor-portal"
    assert result["honesty"]["ingest"] is False
    assert result["honesty"]["mcp_is_authority"] is False


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.discovery.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.discovery.read", "args": {"root": "/tmp"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.discovery.read", "root": "/tmp"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.discovery.read", operator=bare)


def test_malformed_report_does_not_invent_roots(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    path = vault / REPORT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    report = invoke_mcp_tool(vault, "atlas.discovery.read")
    result = report["result"]
    assert result["present"] is False
    assert result["volume_root_authorized"] is False
    assert result["categories"]["DISCOVERED_PROJECTS"] == []
    assert result["honesty"]["invented_pilot_roots"] is False
