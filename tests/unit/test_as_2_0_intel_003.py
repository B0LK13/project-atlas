"""AS-2.0-INTEL-003 — intelligence query contract."""

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
    SlotStatus,
    query_intelligence,
)

HASH_A = "a" * 64


def _claim(
    claim_id: str,
    *,
    value: str,
    source_id: str = "src-a",
    project_id: str | None = "harbor-api",
    field: str = "datastore",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id=project_id,
        subject="project:harbor-api",
        claim_type=ClaimType.ARCHITECTURE,
        field=field,
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


def test_evidence_query_is_deterministic_and_project_scoped() -> None:
    claims = [
        _claim("claim-a", value="PostgreSQL 16"),
        _claim("claim-other", value="secret", project_id="other-proj"),
    ]
    query = IntelligenceQuery(
        project_id="harbor-api",
        kind=IntelligenceQueryKind.EVIDENCE,
        subject="project:harbor-api",
        field="datastore",
    )
    left = query_intelligence(query, claims)
    right = query_intelligence(query, list(reversed(claims)))
    assert left.model_dump() == right.model_dump()
    assert left.outcome is QueryOutcome.ANSWER
    assert left.status is SlotStatus.OBSERVED
    assert all(item.project_id == "harbor-api" for item in left.assessments)
    assert "secret" not in left.model_dump_json()
    assert left.authority_note == "query-not-authoritative"


def test_conflict_query_marks_contested_without_resolving() -> None:
    answer = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.CONFLICTS),
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert answer.status is SlotStatus.CONTESTED
    assert answer.candidates
    assert "auto-resolve-forbidden" in answer.candidates[0].recommended_human_review_reason


def test_empty_query_is_no_evidence_not_healthy() -> None:
    answer = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.EVIDENCE),
        [],
    )
    assert answer.outcome is QueryOutcome.NONANSWER
    assert answer.status is SlotStatus.NO_EVIDENCE
    assert "healthy" not in answer.model_dump_json()


def test_wall_clock_as_of_is_invalid() -> None:
    answer = query_intelligence(
        IntelligenceQuery(
            project_id="harbor-api",
            kind=IntelligenceQueryKind.STATE,
            as_of_valid_time="now",
        ),
        [_claim("claim-a", value="PostgreSQL 16")],
    )
    assert answer.outcome is QueryOutcome.INVALID
    assert "wall-clock-forbidden" in answer.reason


def test_explain_and_gaps_are_unbound_until_later_packages() -> None:
    claims = [_claim("claim-a", value="PostgreSQL 16")]
    explain = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.EXPLAIN),
        claims,
    )
    gaps = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.GAPS),
        claims,
    )
    assert explain.outcome is QueryOutcome.NONANSWER
    assert explain.reason == "explain-package-not-bound"
    assert gaps.reason == "gaps-package-not-bound"


def test_replay_query_id_is_stable() -> None:
    query = IntelligenceQuery(
        project_id="harbor-api",
        kind=IntelligenceQueryKind.STATE,
        field="datastore",
    )
    first = query_intelligence(query, [_claim("claim-a", value="PostgreSQL 16")])
    second = query_intelligence(query, [_claim("claim-a", value="PostgreSQL 16")])
    assert first.query_id == second.query_id
    assert first.query_id.startswith("iq-")
