"""AS-CODER-ALPHA-CAPTURES-MCP-001 — vault-scoped session-capture list MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    CAPTURES_PACKAGE_ID,
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
    (vault / "projects" / "alpha").mkdir(parents=True)
    (vault / "projects" / "beta").mkdir(parents=True)
    _write(
        vault / "generated" / "ops" / "session-captures" / "capture-aaa.json",
        {
            "capture_id": "capture-aaa",
            "project_id": "alpha",
            "kind": "note",
            "source": "explicit",
            "summary": "SECRET-ALPHA-CAP",
        },
    )
    _write(
        vault / "generated" / "ops" / "session-captures" / "capture-bbb.json",
        {
            "capture_id": "capture-bbb",
            "project_id": "beta",
            "kind": "note",
            "source": "explicit",
            "summary": "SECRET-BETA-CAP",
        },
    )
    return vault


def test_captures_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.captures.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_captures(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    result = invoke_mcp_tool(vault, "atlas.captures.read")["result"]
    assert result["package_id"] == CAPTURES_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["projects"] == []
    assert result["honesty"]["owner_capability_granted"] is False


def test_missing_captures_are_empty_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    row = invoke_mcp_tool(vault, "atlas.captures.read")["result"]["projects"][0][
        "captures"
    ]
    assert row["available"] is True
    assert row["count"] == 0
    assert row["items"] == []
    assert row["honesty"]["capture_is_authority"] is False


def test_cross_project_isolation_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    report = invoke_mcp_tool(vault, "atlas.captures.read")
    assert _snapshot(vault) == before
    rows = {row["project_id"]: row["captures"] for row in report["result"]["projects"]}
    alpha = json.dumps(rows["alpha"], sort_keys=True)
    assert "SECRET-ALPHA-CAP" in alpha
    assert "SECRET-BETA-CAP" not in alpha
    assert rows["alpha"]["count"] == 1
    assert "SECRET-BETA-CAP" in json.dumps(rows["beta"], sort_keys=True)


def test_zero_arg_and_mcp_read(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    line = json.dumps({"tool": "atlas.captures.read"}, sort_keys=True)
    assert handle_mcp_request_line(vault, line) == handle_mcp_request_line(vault, line)
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.captures.read", "args": {"project": "alpha"}}),
        )
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.captures.read", operator=bare)
