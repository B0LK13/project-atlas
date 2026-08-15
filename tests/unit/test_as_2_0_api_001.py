"""AS-2.0-API-001 - read-only intelligence LIVE_API projections."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.web_api.intelligence import (
    WebIntelligenceError,
    read_intelligence_conflicts,
    read_intelligence_evidence,
    read_intelligence_explain,
    read_portfolio_state,
    read_project_attention,
    read_project_state,
)

HASH_A = "a" * 64


def _write_claims(vault: Path, project_id: str, claims: list[dict[str, object]]) -> None:
    root = vault / "state" / "claims"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{project_id}.json").write_text(
        json.dumps({"schema_version": 1, "project_id": project_id, "claims": claims}),
        encoding="utf-8",
    )


def _row(claim_id: str, value: str, source_id: str = "src-a") -> dict[str, object]:
    return {
        "claim_id": claim_id,
        "project_id": "harbor-api",
        "subject": "project:harbor-api",
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


def test_evidence_and_state_are_not_authority(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_claims(
        vault,
        "harbor-api",
        [_row("claim-a", "PostgreSQL 16"), _row("claim-b", "PostgreSQL 16", "src-b")],
    )
    evidence = read_intelligence_evidence(vault, "harbor-api")
    state = read_project_state(vault, "harbor-api")
    assert evidence["derived_intelligence_is_authority"] == "NO"
    assert evidence["canonical_write"] is False
    assert evidence["assessments"]
    assert state["authority_note"] == "derived-state-not-canonical"
    assert "healthy" not in json.dumps(state).lower()


def test_conflicts_do_not_replace_v1_conflicts(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_claims(
        vault,
        "harbor-api",
        [_row("claim-a", "PostgreSQL 15"), _row("claim-b", "PostgreSQL 16", "src-b")],
    )
    payload = read_intelligence_conflicts(vault, "harbor-api")
    assert payload["candidates"]
    assert payload["replaces_v1_conflicts"] is False
    assert payload["authority_note"] == "candidate-not-resolution"


def test_explain_attention_and_portfolio(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_claims(
        vault,
        "harbor-api",
        [_row("claim-a", "PostgreSQL 15"), _row("claim-b", "PostgreSQL 16", "src-b")],
    )
    explain = read_intelligence_explain(vault, "harbor-api", field="datastore")
    attention = read_project_attention(vault, "harbor-api")
    portfolio = read_portfolio_state(vault, ("harbor-api",))
    assert explain["explanation"]
    assert attention["authority_note"] == "risk-is-not-fact"
    assert portfolio["numeric_priority_score"] is None
    assert portfolio["state"]["authority_note"] == "portfolio-not-authority"


def test_empty_project_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    state = read_project_state(vault, "harbor-api")
    dumped = json.dumps(state).lower()
    assert "healthy" not in dumped
    assert any(item["status"] == "unknown" for item in state["unknown_facts"])


def test_wall_clock_as_of_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(WebIntelligenceError):
        read_project_state(vault, "harbor-api", as_of_valid_time="now")


def test_path_traversal_project_id_fails_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    with pytest.raises(WebIntelligenceError):
        read_intelligence_evidence(vault, "../etc")


def test_api_server_registers_get_only_intelligence_routes() -> None:
    text = Path("src/project_atlas/api_server.py").read_text(encoding="utf-8")
    for route in (
        "/v1/intelligence/evidence",
        "/v1/intelligence/conflicts",
        "/v1/intelligence/explain",
        "/v1/project-state",
        "/v1/project-attention",
        "/v1/portfolio-state",
    ):
        assert f'"{route}"' in text
    assert 'if path == "/v1/conflicts":' in text
    assert "replaces_v1_conflicts" not in text.split("if path == \"/v1/conflicts\":")[1][:400]
    assert 'path not in {"/v1/actions", "/v1/captures/conversation"}' in text
