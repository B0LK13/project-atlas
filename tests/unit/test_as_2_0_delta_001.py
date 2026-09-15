"""AS-2.0-DELTA-001 — delta polarity classification."""

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
from project_atlas.intelligence.delta import DeltaPolarity, classify_deltas
from project_atlas.intelligence.types import ValidityWindowInput

HASH_A = "a" * 64


def _claim(claim_id: str, *, value: str, predecessor: str | None = None) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id="harbor-api",
        subject="project:harbor-api",
        claim_type=ClaimType.TEST_RESULT,
        field="result",
        value=value,
        provenance=[
            ProvenanceReference(source_id="src-a", resource="docs/src-a.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
        predecessor_claim_id=predecessor,
    )


def test_explicit_fail_to_pass_is_positive() -> None:
    found = classify_deltas(
        [
            _claim("claim-old", value="fail"),
            _claim("claim-new", value="pass", predecessor="claim-old"),
        ]
    )
    assert found[0].polarity is DeltaPolarity.POSITIVE
    assert found[0].authority_note == "delta-not-score"


def test_postgres_succession_is_not_improvement() -> None:
    found = classify_deltas(
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16"),
        ],
        validity_windows=(
            ValidityWindowInput(claim_id="claim-a", valid_from="2024-01-01", valid_to="2024-03-31"),
            ValidityWindowInput(claim_id="claim-b", valid_from="2024-04-01", valid_to="2024-12-31"),
        ),
    )
    assert found
    assert all(item.polarity is not DeltaPolarity.POSITIVE for item in found)
    assert any(item.polarity is DeltaPolarity.INCOMPARABLE for item in found)
