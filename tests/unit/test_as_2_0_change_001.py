"""AS-2.0-CHANGE-001 — semantic change intelligence."""

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
from project_atlas.intelligence.change import ChangeClass, detect_semantic_changes
from project_atlas.intelligence.types import ValidityWindowInput

HASH_A = "a" * 64


def _claim(
    claim_id: str,
    *,
    value: str,
    predecessor: str | None = None,
    lifecycle: ClaimLifecycle = ClaimLifecycle.NEW,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id="harbor-api",
        subject="project:harbor-api",
        claim_type=ClaimType.ARCHITECTURE,
        field="datastore",
        value=value,
        provenance=[
            ProvenanceReference(source_id="src-a", resource="docs/src-a.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=lifecycle,
        verification=ReviewState.UNREVIEWED,
        predecessor_claim_id=predecessor,
    )


def test_predecessor_is_change_not_regression() -> None:
    found = detect_semantic_changes(
        [
            _claim("claim-old", value="PostgreSQL 15"),
            _claim("claim-new", value="PostgreSQL 16", predecessor="claim-old"),
        ]
    )
    assert len(found) == 1
    assert found[0].change_class is ChangeClass.PREDECESSOR
    assert found[0].authority_note == "change-not-regression"
    assert "regression" not in found[0].reason


def test_succession_is_change() -> None:
    found = detect_semantic_changes(
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16"),
        ],
        validity_windows=(
            ValidityWindowInput(claim_id="claim-a", valid_from="2024-01-01", valid_to="2024-03-31"),
            ValidityWindowInput(claim_id="claim-b", valid_from="2024-04-01", valid_to="2024-12-31"),
        ),
    )
    assert any(item.change_class is ChangeClass.SUCCESSION for item in found)


def test_order_independent() -> None:
    claims = [
        _claim("claim-old", value="PostgreSQL 15"),
        _claim("claim-new", value="PostgreSQL 16", predecessor="claim-old"),
    ]
    assert [item.change_id for item in detect_semantic_changes(claims)] == [
        item.change_id for item in detect_semantic_changes(list(reversed(claims)))
    ]
