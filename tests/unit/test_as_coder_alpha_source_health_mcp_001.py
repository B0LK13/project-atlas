"""AS-CODER-ALPHA-SOURCE-HEALTH-MCP-001 — zero-arg vault-scoped source-health MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    SOURCE_HEALTH_PACKAGE_ID,
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
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    (vault / "projects" / "portal-app").mkdir(parents=True)
    sources = [
        {
            "source_id": "src-harbor",
            "path": "docs/harbor.md",
            "likely_project": "harbor-api",
        },
        {
            "source_id": "src-portal",
            "path": "docs/portal.md",
            "likely_project": "portal-app",
        },
    ]
    _write(vault / "generated" / "ops" / "connect-manifest.json", {"sources": sources})
    _write(vault / "sources" / "manifests" / "source-manifest.json", {"sources": sources})
    _write(
        vault / "generated" / "reports" / "secret-findings.json",
        {
            "findings": [
                {
                    "source_id": "src-harbor",
                    "path": "docs/harbor.md",
                    "reason_code": "SECRET_QUARANTINE",
                }
            ]
        },
    )
    return vault


def test_source_health_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.source-health.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_health(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.source-health.read")
    result = report["result"]
    assert result["package_id"] == SOURCE_HEALTH_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["reports"] == []
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["portfolio_implicit_all"] is False
    assert result["honesty"]["request_contains_project"] is False
    assert result["honesty"]["unreadable_as_healthy"] is False
    assert result["honesty"]["secrets_echoed"] is False


def test_missing_artifacts_are_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.source-health.read")
    rows = report["result"]["reports"]
    assert len(rows) == 1
    assert rows[0]["project_id"] == "sparse-proj"
    health = rows[0]["source_health"]
    assert health["project_id"] == "sparse-proj"
    assert health["health_state"] in {"UNKNOWN", "UNREADABLE"}
    assert health["honesty"]["lens_is_authority"] is False
    assert health["honesty"]["unreadable_as_healthy"] is False


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.source-health.read")
    rows = {
        row["project_id"]: row["source_health"] for row in report["result"]["reports"]
    }
    assert set(rows) == {"harbor-api", "portal-app"}
    harbor = rows["harbor-api"]
    portal = rows["portal-app"]
    assert harbor["project_id"] == "harbor-api"
    assert portal["project_id"] == "portal-app"
    harbor_dump = json.dumps(harbor, sort_keys=True)
    portal_dump = json.dumps(portal, sort_keys=True)
    assert "docs/portal.md" not in harbor_dump
    assert "docs/harbor.md" not in portal_dump
    assert harbor["honesty"]["secrets_echoed"] is False
    assert "SECRET" not in harbor_dump or "SECRET_QUARANTINE" in harbor_dump


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.source-health.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.source-health.read", "args": {"project": "harbor-api"}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.source-health.read", "project": "harbor-api"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.source-health.read", operator=bare)


def test_determinism(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    first = invoke_mcp_tool(vault, "atlas.source-health.read")
    second = invoke_mcp_tool(vault, "atlas.source-health.read")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    ids = [row["project_id"] for row in first["result"]["reports"]]
    assert ids == sorted(ids)


def test_demo_fixture_cannot_masquerade_as_authority(tmp_path: Path) -> None:
    vault = tmp_path / "fixture-vault"
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.source-health.read")
    result = report["result"]
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["lens_is_authority"] is False
    health = result["reports"][0]["source_health"]
    assert health.get("authority", "derived") in {"derived", None} or health.get(
        "authority"
    ) == "derived"
    assert health["honesty"]["lens_is_authority"] is False
