"""AS-2.0-PORTFOLIO-003 — portfolio attention ranking."""

from __future__ import annotations

from project_atlas.domain import (
    AuthorityLevel,
    Claim,
    ClaimLifecycle,
    ClaimType,
    ConfidenceState,
    ProvenanceReference,
    ReviewState,
)
from project_atlas.intelligence.portfolio_attention import (
    AttentionRankClass,
    rank_portfolio_attention,
)

HASH_A = "a" * 64


def _claim(claim_id: str, *, project_id: str, value: str, source_id: str = "src-a") -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id=project_id,
        subject=f"project:{project_id}",
        claim_type=ClaimType.ARCHITECTURE,
        field="datastore",
        value=value,
        provenance=[
            ProvenanceReference(source_id=source_id, resource=f"docs/{source_id}.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_ranking_is_not_a_numeric_score() -> None:
    found = rank_portfolio_attention(
        {
            "harbor-api": [
                _claim("h1", project_id="harbor-api", value="PostgreSQL 15"),
                _claim("h2", project_id="harbor-api", value="PostgreSQL 16", source_id="src-b"),
            ],
            "lighthouse": [],
        }
    )
    assert found
    assert all(item.numeric_score is None for item in found)
    assert all(item.sort_is_score is False for item in found)
    assert all(item.authority_note == "rank-not-score" for item in found)
    harbor = next(item for item in found if item.project_id == "harbor-api")
    light = next(item for item in found if item.project_id == "lighthouse")
    assert harbor.rank_class is AttentionRankClass.CONTESTED
    assert light.rank_class is AttentionRankClass.UNKNOWN
    assert found[0].rank_class is AttentionRankClass.CONTESTED
    dumped = "".join(item.model_dump_json() for item in found)
    assert "priority" not in dumped
    assert "healthy" not in dumped


def test_empty_portfolio_unknown_is_not_safe() -> None:
    found = rank_portfolio_attention({"harbor-api": []})
    assert found[0].rank_class is AttentionRankClass.UNKNOWN
    assert any("unknown" in reason for reason in found[0].reasons)
