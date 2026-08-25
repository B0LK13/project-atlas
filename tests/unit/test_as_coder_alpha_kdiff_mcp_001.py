"""AS-CODER-ALPHA-KDIFF-MCP-001 — zero-arg validity-catalog inventory MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    KDIFF_PACKAGE_ID,
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


def test_kdiff_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.kdiff.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_missing_catalog_is_empty_not_invented_as_of(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.kdiff.read")
    result = report["result"]
    assert result["package_id"] == KDIFF_PACKAGE_ID
    assert result["catalog_count"] == 0
    assert result["catalogs"] == []
    assert result["honesty"]["as_of_invented"] is False
    assert result["honesty"]["kdiff_is_authority"] is False
    assert result["honesty"]["wall_clock_now"] is False
    assert result["honesty"]["request_contains_time"] is False


def test_catalog_inventory_no_as_of_evaluation(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    _write(
        vault / "generated" / "ops" / "bitemporal" / "harbor-validity-catalog.json",
        {"catalog_id": "harbor", "window_count": 2, "windows": [{}, {}]},
    )
    report = invoke_mcp_tool(vault, "atlas.kdiff.read")
    catalogs = report["result"]["catalogs"]
    assert len(catalogs) == 1
    assert catalogs[0]["catalog_id"] == "harbor"
    assert catalogs[0]["available"] is True
    assert catalogs[0]["window_count"] == 2
    assert catalogs[0]["honesty"]["as_of_invented"] is False
    dumped = json.dumps(report, sort_keys=True)
    assert '"as_of"' not in dumped
    assert report["result"]["honesty"]["as_of_invented"] is False


def test_unreadable_catalog_stays_unknown(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    path = vault / "generated" / "ops" / "bitemporal" / "broken-validity-catalog.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")
    report = invoke_mcp_tool(vault, "atlas.kdiff.read")
    row = report["result"]["catalogs"][0]
    assert row["available"] is False
    assert row["honesty"]["catalog_unreadable"] is True
    assert row["honesty"]["as_of_invented"] is False


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.kdiff.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.kdiff.read", "args": {"as_of": "now"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.kdiff.read", "from": "2024-01-01"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.kdiff.read", operator=bare)
