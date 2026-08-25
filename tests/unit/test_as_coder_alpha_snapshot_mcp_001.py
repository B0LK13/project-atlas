"""AS-CODER-ALPHA-SNAPSHOT-MCP-001 — vault-scoped LIVE_API facade snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    SNAPSHOT_PACKAGE_ID,
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


def test_snapshot_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.snapshot.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_snapshot(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.snapshot.read")
    result = report["result"]
    assert result["package_id"] == SNAPSHOT_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["knowledge_count"] == 0
    assert result["projects"] == []
    assert result["knowledge"] == []
    assert result["graph"]["available"] is False
    assert result["graph"]["graph_authority"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["backup_bundle"] is False
    assert result["honesty"]["atlas_snapshot_restore"] is False


def test_projects_are_listed_without_authority(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.snapshot.read")
    ids = {row["project_id"] for row in report["result"]["projects"]}
    assert ids == {"harbor-portal", "dark-factory-02ee94d0"}
    assert report["result"]["project_count"] == 2
    assert report["result"]["honesty"]["mcp_is_authority"] is False


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    (vault / "projects").mkdir()
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.snapshot.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.snapshot.read", "args": {"project": "x"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.snapshot.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.snapshot.read", operator=bare)


def test_no_owner_capability_and_not_backup(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.snapshot.read")
    dump = json.dumps(report, sort_keys=True)
    assert '"owner_capability_granted": true' not in dump
    assert report["result"]["honesty"]["backup_bundle"] is False
    assert report["result"]["honesty"]["authentic_pilot"] is False


def test_web_surfaces_are_wired() -> None:
    root = Path(__file__).resolve().parents[2]
    app = (root / "apps" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    nav = (root / "apps" / "web" / "src" / "components" / "ProdNav.tsx").read_text(
        encoding="utf-8"
    )
    page = (
        root / "apps" / "web" / "src" / "pages" / "production" / "SnapshotPage.tsx"
    ).read_text(encoding="utf-8")
    hook = (root / "apps" / "web" / "src" / "hooks" / "useLiveSnapshot.ts").read_text(
        encoding="utf-8"
    )
    assert 'path="/snapshot"' in app
    assert 'to: "/snapshot"' in nav
    assert "useLiveSnapshot" in page
    assert "facade≠backup" in page
    assert 'liveApiFetch("/v1/snapshot")' in hook
    docs = (root / "docs" / "AS-CODER-ALPHA-SNAPSHOT-MCP-001.md").read_text(
        encoding="utf-8"
    )
    assert "atlas.snapshot.read" in docs
    assert "backup" in docs
