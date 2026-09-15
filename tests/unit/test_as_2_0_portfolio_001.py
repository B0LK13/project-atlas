"""AS-2.0-PORTFOLIO-001 — cross-project state aggregator."""

from __future__ import annotations

import pytest

from project_atlas.domain import (
    AuthorityLevel,
    Claim,
    ClaimLifecycle,
    ClaimType,
    ConfidenceState,
    ProvenanceReference,
    ReviewState,
)
from project_atlas.intelligence.portfolio import aggregate_portfolio_state

HASH_A = "a" * 64


def _claim(claim_id: str, *, project_id: str, value: str) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id=project_id,
        subject=f"project:{project_id}",
        claim_type=ClaimType.ARCHITECTURE,
        field="datastore",
        value=value,
        provenance=[
            ProvenanceReference(source_id="src-a", resource="docs/src-a.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_aggregate_keeps_projects_isolated() -> None:
    state = aggregate_portfolio_state(
        {
            "harbor-api": [_claim("h1", project_id="harbor-api", value="PostgreSQL 16")],
            "lighthouse": [_claim("l1", project_id="lighthouse", value="Redis 7")],
        }
    )
    assert state.authority_note == "portfolio-not-authority"
    assert [item.project_id for item in state.entries] == ["harbor-api", "lighthouse"]
    harbor = next(item for item in state.entries if item.project_id == "harbor-api")
    light = next(item for item in state.entries if item.project_id == "lighthouse")
    harbor_values = {fact.value for fact in harbor.state.known_facts if fact.value}
    light_values = {fact.value for fact in light.state.known_facts if fact.value}
    assert "Redis 7" not in harbor_values
    assert "PostgreSQL 16" not in light_values


def test_cross_project_claim_is_rejected_not_mixed() -> None:
    state = aggregate_portfolio_state(
        {
            "harbor-api": [
                _claim("h1", project_id="harbor-api", value="PostgreSQL 16"),
                _claim("leak", project_id="lighthouse", value="should-not-mix"),
            ]
        }
    )
    assert state.rejected_leakage
    assert state.rejected_leakage[0].reason == "cross-project-claim-excluded"
    harbor = state.entries[0]
    values = {fact.value for fact in harbor.state.known_facts if fact.value}
    assert "should-not-mix" not in values


def test_identity_collapse_fails_closed() -> None:
    with pytest.raises(ValueError, match="identity-collapse"):
        aggregate_portfolio_state(
            {
                "harbor-api": [],
                " harbor-api": [],
            }
        )


def test_empty_bundle_is_unknown_not_healthy() -> None:
    state = aggregate_portfolio_state({"harbor-api": []})
    assert "harbor-api" in state.unknown_projects
    assert "healthy" not in state.model_dump_json()
