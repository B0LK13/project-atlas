"""AS-2.0-INTEL-003B — extended intelligence query kinds."""

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
            ProvenanceReference(source_id=source_id, resource=f"docs/{source_id}.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_attention_and_context_queries_are_not_authority() -> None:
    claims = [
        _claim("claim-a", value="PostgreSQL 15"),
        _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
    ]
    attention = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.ATTENTION),
        claims,
    )
    context = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.CONTEXT),
        claims,
    )
    assert attention.outcome is QueryOutcome.ANSWER
    assert attention.risks
    assert attention.authority_note == "query-not-authoritative"
    assert context.context is not None
    assert context.context["authority_note"] == "context-not-authority"


def test_change_query_empty_is_not_healthy() -> None:
    answer = query_intelligence(
        IntelligenceQuery(project_id="harbor-api", kind=IntelligenceQueryKind.CHANGE),
        [],
    )
    assert answer.outcome is QueryOutcome.NONANSWER
    assert "healthy" not in answer.model_dump_json()
