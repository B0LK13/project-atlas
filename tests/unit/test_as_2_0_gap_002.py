"""AS-2.0-GAP-002 — evidence gap prioritization."""

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
from project_atlas.intelligence import GAP_PRIORITY_IS_FACT
from project_atlas.intelligence.gap_priority import GapPriorityClass, prioritize_evidence_gaps

HASH_A = "a" * 64


def _claim(claim_id: str, *, value: str) -> Claim:
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
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_priority_is_not_a_score_or_fact() -> None:
    assert GAP_PRIORITY_IS_FACT == "NO"
    found = prioritize_evidence_gaps(
        "harbor-api",
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16"),
        ],
    )
    assert found
    assert all(item.numeric_score is None for item in found)
    assert all(item.authority_note == "priority-not-fact" for item in found)
    assert any(item.priority_class is GapPriorityClass.CONTESTED_CORE_FACT for item in found)


def test_empty_project_is_blocking_unknown() -> None:
    found = prioritize_evidence_gaps("harbor-api", [])
    assert any(item.priority_class is GapPriorityClass.BLOCKING_UNKNOWN for item in found)
    assert "healthy" not in "".join(item.model_dump_json() for item in found)
