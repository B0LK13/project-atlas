"""AS-2.0-INTEL-005 — evidence gap detection."""

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
from project_atlas.intelligence import (
    GapClass,
    GapCurrentStatus,
    IntelligenceQuery,
    IntelligenceQueryKind,
    SlotStatus,
    detect_evidence_gaps,
    query_intelligence,
)
from project_atlas.intelligence.types import AssessableClaim, ValidityWindowInput

HASH_A = "a" * 64


def _claim(claim_id: str, *, value: str, source_id: str = "src-a") -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id="harbor-api",
        subject="project:harbor-api",
        claim_type=ClaimType.ARCHITECTURE,
        field="datastore",
        value=value,
        provenance=[
            ProvenanceReference(
                source_id=source_id,
                resource=f"docs/{source_id}.md",
                sha256=HASH_A,
            )
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_no_claims_is_unknown_from_no_evidence() -> None:
    gaps = detect_evidence_gaps(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.GAPS),
        [],
    )
    assert len(gaps) == 1
    assert gaps[0].gap_class is GapClass.NO_EVIDENCE
    assert gaps[0].current_status is GapCurrentStatus.UNKNOWN_FROM_NO_EVIDENCE


def test_contested_is_not_no_evidence() -> None:
    gaps = detect_evidence_gaps(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.GAPS),
        [
            AssessableClaim.from_claim(_claim("claim-a", value="PostgreSQL 15")),
            AssessableClaim.from_claim(_claim("claim-b", value="PostgreSQL 16", source_id="src-b")),
        ],
    )
    statuses = {item.current_status for item in gaps}
    assert GapCurrentStatus.CONTESTED in statuses
    assert GapCurrentStatus.UNKNOWN_FROM_NO_EVIDENCE not in statuses


def test_stale_is_not_invalid() -> None:
    gaps = detect_evidence_gaps(
        IntelligenceQuery(
            project_id="harbor-api",
            kind=IntelligenceQueryKind.GAPS,
            as_of_valid_time="2026-10-01",
        ),
        [AssessableClaim.from_claim(_claim("claim-a", value="PostgreSQL 15"))],
        validity_windows=(
            ValidityWindowInput(
                claim_id="claim-a",
                valid_from="2024-01-01",
                valid_to="2024-12-31",
            ),
        ),
    )
    stale = [item for item in gaps if item.current_status is GapCurrentStatus.STALE]
    assert stale
    assert "not-invalid" in stale[0].why_material


def test_gap_query_distinguishes_empty_from_contested() -> None:
    empty = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.GAPS),
        [],
    )
    contested = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.GAPS),
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert empty.status is SlotStatus.NO_EVIDENCE
    assert contested.status is SlotStatus.CONTESTED
