"""AS-CODER-ALPHA-MCP-STATE-ATTENTION-001 — vault-scoped state/attention MCP."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.authz import AuthzError, OperatorProfile
from project_atlas.mcp_server import (
    ROADMAP_PACKAGE_ID,
    STATE_ATTENTION_PACKAGE_ID,
    McpServerError,
    handle_mcp_request_line,
    invoke_mcp_tool,
    list_mcp_tools,
)

HASH_A = "a" * 64


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


def _claim_row(project_id: str, claim_id: str, value: str, source_id: str) -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "project_id": project_id,
        "subject": f"project:{project_id}",
        "field": "datastore",
        "value": value,
        "claim_type": "architecture-statement",
        "authority": "primary",
        "confidence": "high",
        "lifecycle": "new",
        "provenance": [
            {
                "source_id": source_id,
                "resource": f"docs/{source_id}.md",
                "sha256": HASH_A,
            }
        ],
    }


def _seed_vault(root: Path) -> Path:
    vault = root / "vault"
    (vault / "projects" / "alpha-state").mkdir(parents=True)
    (vault / "projects" / "beta-attention").mkdir(parents=True)
    _write(
        vault / "state" / "claims" / "alpha-state.json",
        {
            "schema_version": 1,
            "project_id": "alpha-state",
            "claims": [_claim_row("alpha-state", "claim-alpha", "PostgreSQL 16", "src-alpha")],
        },
    )
    _write(
        vault / "state" / "claims" / "beta-attention.json",
        {
            "schema_version": 1,
            "project_id": "beta-attention",
            "claims": [
                _claim_row("beta-attention", "claim-b15", "PostgreSQL 15", "src-b15"),
                _claim_row("beta-attention", "claim-b16", "PostgreSQL 16", "src-b16"),
            ],
        },
    )
    return vault


def test_state_and_attention_tools_are_allow_listed() -> None:
    listing = list_mcp_tools()
    assert "atlas.project-state.read" in listing["tools"]
    assert "atlas.project-attention.read" in listing["tools"]
    assert "atlas.roadmap.read" in listing["tools"]
    assert listing["write_tools"] == []


def test_empty_vault_does_not_invent_lenses(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    state = invoke_mcp_tool(vault, "atlas.project-state.read")["result"]
    attention = invoke_mcp_tool(vault, "atlas.project-attention.read")["result"]
    assert state["package_id"] == STATE_ATTENTION_PACKAGE_ID
    assert state["project_count"] == 0
    assert state["states"] == []
    assert attention["attentions"] == []
    assert state["honesty"]["mcp_is_authority"] is False
    assert state["honesty"]["portfolio_implicit_all"] is False
    dumped = json.dumps(state).lower()
    assert '"honesty": "healthy"' not in dumped
    assert state["honesty"]["empty_is_not_health_grade"] is True


def test_missing_claims_file_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    (vault / "projects" / "sparse-proj").mkdir(parents=True)
    report = invoke_mcp_tool(vault, "atlas.project-state.read")
    rows = report["result"]["states"]
    assert len(rows) == 1
    assert rows[0]["project_id"] == "sparse-proj"
    dumped = json.dumps(rows[0]["state"]).lower()
    assert "healthy" not in dumped
    assert rows[0]["state"]["honesty"] in {"NO_DATA", "UNKNOWN", "VALID_EMPTY"}


def test_cross_project_isolation(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    states = {
        row["project_id"]: row["state"]
        for row in invoke_mcp_tool(vault, "atlas.project-state.read")["result"]["states"]
    }
    attentions = {
        row["project_id"]: row["attention"]
        for row in invoke_mcp_tool(vault, "atlas.project-attention.read")["result"]["attentions"]
    }
    assert set(states) == {"alpha-state", "beta-attention"}
    alpha_dump = json.dumps(states["alpha-state"], sort_keys=True)
    assert "PostgreSQL 16" in alpha_dump
    assert "src-b15" not in alpha_dump
    assert "src-b16" not in alpha_dump
    beta_dump = json.dumps(attentions["beta-attention"], sort_keys=True)
    assert "src-alpha" not in beta_dump
    assert attentions["beta-attention"]["attention_rank_is_score"] == "NO"
    assert attentions["beta-attention"]["numeric_priority_score"] is None


def test_zero_arg_protocol_and_no_write(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    before = _snapshot(vault)
    for tool in ("atlas.project-state.read", "atlas.project-attention.read"):
        line = json.dumps({"tool": tool}, sort_keys=True)
        first = handle_mcp_request_line(vault, line)
        second = handle_mcp_request_line(vault, line)
        assert first == second
        with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
            handle_mcp_request_line(
                vault,
                json.dumps({"tool": tool, "args": {"project": "alpha-state"}}),
            )
        with pytest.raises(McpServerError, match="mcp-request-unexpected-key"):
            handle_mcp_request_line(
                vault,
                json.dumps({"tool": tool, "project": "alpha-state"}),
            )
    assert _snapshot(vault) == before


def test_mcp_read_required(tmp_path: Path) -> None:
    vault = tmp_path / "v"
    vault.mkdir()
    bare = OperatorProfile(operator_id="no-mcp", capabilities=frozenset({"api.read"}))
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.project-state.read", operator=bare)
    with pytest.raises(AuthzError, match=r"authz-denied:mcp\.read"):
        invoke_mcp_tool(vault, "atlas.project-attention.read", operator=bare)


def test_determinism(tmp_path: Path) -> None:
    vault = _seed_vault(tmp_path)
    for tool in ("atlas.project-state.read", "atlas.project-attention.read"):
        a = invoke_mcp_tool(vault, tool)
        b = invoke_mcp_tool(vault, tool)
        assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    ids = [
        row["project_id"]
        for row in a["result"]["attentions"]
    ]
    assert ids == sorted(ids)


def test_roadmap_tool_empty_and_zero_arg(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = invoke_mcp_tool(vault, "atlas.roadmap.read")
    result = report["result"]
    assert result["package_id"] == ROADMAP_PACKAGE_ID
    assert result["roadmaps"] == []
    assert result["honesty"]["roadmap_is_canonical"] is False
    assert result["honesty"]["mcp_is_authority"] is False
    seeded = _seed_vault(tmp_path / "seeded")
    before = _snapshot(seeded)
    line = json.dumps({"tool": "atlas.roadmap.read"}, sort_keys=True)
    first = handle_mcp_request_line(seeded, line)
    second = handle_mcp_request_line(seeded, line)
    assert first == second
    assert _snapshot(seeded) == before
    with pytest.raises(McpServerError, match="mcp-request-forbidden-key"):
        handle_mcp_request_line(
            seeded,
            json.dumps({"tool": "atlas.roadmap.read", "args": {"project": "alpha-state"}}),
        )
