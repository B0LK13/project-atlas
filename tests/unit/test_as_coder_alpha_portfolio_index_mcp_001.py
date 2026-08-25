"""AS-CODER-ALPHA-PORTFOLIO-INDEX-001 — zero-arg vault-scoped portfolio MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    PORTFOLIO_PACKAGE_ID,
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


def _row(claim_id: str, value: str, source_id: str, project_id: str) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "project_id": project_id,
        "subject": "datastore",
        "field": "engine",
        "value": value,
        "lifecycle": "new",
        "provenance": [
            {
                "source_id": source_id,
                "resource": f"docs/{project_id}.md",
                "sha256": "a" * 64,
            }
        ],
    }


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "dark-factory-02ee94d0").mkdir(parents=True)
    (vault / "projects" / "harbor-portal").mkdir(parents=True)
    _write(
        vault / "state" / "claims" / "dark-factory-02ee94d0.json",
        {
            "schema_version": 1,
            "project_id": "dark-factory-02ee94d0",
            "claims": [
                _row("claim-factory", "Factory compile", "src-factory", "dark-factory-02ee94d0")
            ],
        },
    )
    _write(
        vault / "state" / "claims" / "harbor-portal.json",
        {
            "schema_version": 1,
            "project_id": "harbor-portal",
            "claims": [
                _row("claim-portal", "SECRET-PORTAL-VALUE", "src-portal", "harbor-portal")
            ],
        },
    )
    return vault


def test_portfolio_tool_is_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.portfolio.state.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_portfolio(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.portfolio.state.read")
    result = report["result"]
    assert result["package_id"] == PORTFOLIO_PACKAGE_ID
    assert result["project_count"] == 0
    assert result["project_ids"] == []
    assert result["portfolio"] is None
    assert result["available"] is False
    assert result["honesty"]["unknown_is_valid"] is True
    assert result["honesty"]["mcp_is_authority"] is False
    assert result["honesty"]["portfolio_implicit_all"] is False
    assert result["honesty"]["empty_arg_portfolio_state"] is False
    assert result["honesty"]["request_contains_project"] is False
    assert result["honesty"]["owner_capability_granted"] is False


def test_missing_claims_is_unknown_not_invented(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.portfolio.state.read")
    result = report["result"]
    assert result["project_ids"] == ["sparse-proj"]
    assert result["available"] is True
    portfolio = result["portfolio"]
    assert portfolio is not None
    assert portfolio["numeric_priority_score"] is None
    assert portfolio["authority_note"] == "portfolio-not-authority"
    dumped = json.dumps(portfolio).lower()
    assert "healthy" not in dumped


def test_invalid_project_token_is_skipped(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "Not-Valid_ID").mkdir(parents=True)
    (vault / "projects" / "ok-project").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.portfolio.state.read")
    result = report["result"]
    assert result["project_ids"] == ["ok-project"]
    assert "Not-Valid_ID" in result["skipped_invalid_ids"]


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    report = invoke_mcp_tool(vault, "atlas.portfolio.state.read")
    result = report["result"]
    assert result["project_ids"] == ["dark-factory-02ee94d0", "harbor-portal"]
    entries = result["portfolio"]["state"]["entries"]
    by_id = {entry["project_id"]: json.dumps(entry, sort_keys=True) for entry in entries}
    assert "SECRET-PORTAL-VALUE" not in by_id["dark-factory-02ee94d0"]
    assert "SECRET-PORTAL-VALUE" in by_id["harbor-portal"]
    assert "Factory compile" not in by_id["harbor-portal"]


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    line = json.dumps({"tool": "atlas.portfolio.state.read"}, sort_keys=True)
    first = handle_mcp_request_line(vault, line)
    second = handle_mcp_request_line(vault, line)
    assert first == second
    assert _snapshot(vault) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            vault,
            json.dumps(
                {"tool": "atlas.portfolio.state.read", "args": {"project": "harbor-portal"}}
            ),
        )
    with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
        handle_mcp_request_line(
            vault,
            json.dumps({"tool": "atlas.portfolio.state.read", "project": "harbor-portal"}),
        )


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.portfolio.state.read", operator=bare)


def test_determinism(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    a = invoke_mcp_tool(vault, "atlas.portfolio.state.read")
    b = invoke_mcp_tool(vault, "atlas.portfolio.state.read")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["result"]["project_ids"] == sorted(a["result"]["project_ids"])
