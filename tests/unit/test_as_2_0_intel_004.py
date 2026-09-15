"""AS-2.0-INTEL-004 — explain-why / evidence trace."""

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
    IntelligenceQuery,
    IntelligenceQueryKind,
    QueryOutcome,
    explain_why,
    query_intelligence,
)

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


def test_explain_lists_why_exists_and_why_limited() -> None:
    from project_atlas.intelligence.types import AssessableClaim

    claims = [AssessableClaim.from_claim(_claim("claim-a", value="PostgreSQL 16"))]
    query = IntelligenceQuery(
        project_id="harbor-api",
        kind=IntelligenceQueryKind.EXPLAIN,
        field="datastore",
    )
    trace = explain_why(query, claims)
    assert trace.why_exists
    assert "single-source" in trace.why_confidence_limited
    assert trace.supporting_provenance
    assert trace.authority_note == "trace-not-authoritative"
    assert "EXPLAIN-WHY ≠ AUTHORITY" in trace.truth_boundary


def test_explain_query_binding_returns_trace() -> None:
    answer = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.EXPLAIN),
        [_claim("claim-a", value="PostgreSQL 16")],
    )
    assert answer.outcome is QueryOutcome.ANSWER
    assert answer.explanation is not None
    assert answer.explanation["conclusion_kind"] == "assessment"


def test_explain_contradiction_does_not_resolve() -> None:
    from project_atlas.intelligence.types import AssessableClaim

    claims = [
        AssessableClaim.from_claim(_claim("claim-a", value="PostgreSQL 15")),
        AssessableClaim.from_claim(_claim("claim-b", value="PostgreSQL 16", source_id="src-b")),
    ]
    trace = explain_why(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.EXPLAIN),
        claims,
    )
    assert trace.conclusion_kind == "contradiction"
    assert "open-contradiction-candidates" in trace.why_confidence_limited


def test_explain_empty_is_no_evidence() -> None:
    answer = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.EXPLAIN),
        [],
    )
    assert answer.outcome is QueryOutcome.NONANSWER
    assert answer.reason == "no-matching-claims"
