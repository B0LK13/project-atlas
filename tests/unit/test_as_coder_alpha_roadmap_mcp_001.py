"""AS-CODER-ALPHA-ROADMAP-MCP-001 — zero-arg vault-scoped roadmap MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile, elevated_operator
from project_atlas.mcp_server import (
    ROADMAP_PACKAGE_ID,
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


def _write_roadmap(vault: Path, project_id: str, record: dict[str, object]) -> None:
    note = vault / "projects" / project_id / "roadmap.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        "---\ntype: Roadmap\n---\n\n# Roadmap\n\n## Roadmap record\n\n```json\n"
        + json.dumps(record)
        + "\n```\n",
        encoding="utf-8",
    )
    (vault / "projects" / project_id / "project.md").write_text(
        f"---\ntype: Project\ntitle: {project_id}\n---\n\n# {project_id}\n",
        encoding="utf-8",
    )


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    _write_roadmap(
        vault,
        "dark-factory-02ee94d0",
        {
            "items": [
                {
                    "id": "pkg-factory",
                    "title": "Factory compile",
                    "status": "IN_PROGRESS",
                    "depends_on": [],
                    "evidence": [],
                }
            ]
        },
    )
    _write_roadmap(
        vault,
        "harbor-portal",
        {
            "items": [
                {
                    "id": "pkg-portal",
                    "title": "SECRET-PORTAL-ROADMAP",
                    "status": "BLOCKED",
                    "depends_on": [],
                    "evidence": [],
                    "blockers": [
                        {
                            "reason": "SECRET-PORTAL-BLOCKER",
                            "waiting_on": "owner",
                            "unlock_condition": "owner merge",
                        }
                    ],
                }
            ]
        },
    )
    return vault


def test_roadmap_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.roadmap.read" in listing["tools"]
    assert listing["write_tools"] == []
    assert "atlas.vault.write" not in listing["tools"]


def test_empty_vault_does_not_invent_roadmaps(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.roadmap.read")
    result = report["result"]
    assert result["package_id"] == ROADMAP_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["roadmaps"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["roadmap_is_canonical"] is False
    assert result["honesty"]["owner_capability_granted"] is False
    assert result["honesty"]["portfolio_implicit_all"] is False


def test_missing_roadmap_evidence_is_unknown_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.roadmap.read")
    rows = report["result"]["roadmaps"]
    assert len(rows) == 1
    assert rows[0]["project_id"] == "sparse-proj"
    lens = rows[0]["roadmap"]
    assert lens["available"] is False
    assert lens["status"] == "unknown"
    assert lens["items"] == []
    assert lens["honesty"]["unknown_is_valid"] is True
    assert lens["honesty"]["fabricated_fields"] is False
    assert lens["honesty"]["owner_capability_granted"] is False
    assert lens["honesty"]["roadmap_is_canonical"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.roadmap.read")
    rows = {row["project_id"]: row["roadmap"] for row in report["result"]["roadmaps"]}
    assert set(rows) == {"dark-factory-02ee94d0", "harbor-portal"}
    factory = json.dumps(rows["dark-factory-02ee94d0"], sort_keys=True)
    assert "SECRET-PORTAL-ROADMAP" not in factory
    assert "SECRET-PORTAL-BLOCKER" not in factory
    assert rows["harbor-portal"]["available"] is True
    assert "SECRET-PORTAL-ROADMAP" in json.dumps(rows["harbor-portal"])
    assert rows["dark-factory-02ee94d0"]["you_are_here"]["title"] == "Factory compile"


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.roadmap.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    after = _snapshot(vault)
    assert after == before
    assert not list((vault / "generated" / "answers").glob("ans-roadmap-*"))
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.roadmap.read", "args": {"project": "harbor-portal"}}),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.roadmap.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.roadmap.read", operator=bare)


def test_write_tools_remain_denied_even_with_vault_write(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    elev = elevated_operator("roadmap-mcp-elev", extra={"vault.write"})
    assert elev.allows("vault.write")
    for tool in ("atlas.vault.write", "atlas.estate.scan", "atlas.provider.generate"):
        with pytest.raises(McpServerError, match="mcp-tool-denied"):
            invoke_mcp_tool(vault, tool, operator=elev)


def test_determinism_and_owner_capability_never_granted(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    a = invoke_mcp_tool(vault, "atlas.roadmap.read")
    b = invoke_mcp_tool(vault, "atlas.roadmap.read")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    ids = [row["project_id"] for row in a["result"]["roadmaps"]]
    assert ids == sorted(ids)
    dumped = json.dumps(a, sort_keys=True)
    assert '"owner_capability_granted": false' in dumped
    assert '"owner_capability_granted": true' not in dumped
    assert a["result"]["honesty"]["canonical_write"] is False
    assert a["result"]["honesty"]["auto_execution"] is False
