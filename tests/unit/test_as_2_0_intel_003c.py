"""AS-2.0-INTEL-003C - query kinds for Waves 10-14 library packages."""

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


def _claim(
    claim_id: str,
    *,
    value: str,
    field: str = "datastore",
    claim_type: ClaimType = ClaimType.ARCHITECTURE,
    source_id: str = "src-a",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id="harbor-api",
        subject="project:harbor-api",
        claim_type=claim_type,
        field=field,
        value=value,
        provenance=[
            ProvenanceReference(source_id=source_id, resource=f"docs/{source_id}.md", sha256=HASH_A)
        ],
        authority=AuthorityLevel.PRIMARY,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        verification=ReviewState.UNREVIEWED,
    )


def test_explain_graph_and_gap_priority_queries() -> None:
    claims = [
        _claim("claim-a", value="PostgreSQL 15"),
        _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
    ]
    graph = query_intelligence(
        IntelligenceQuery(
            project_id="harbor-api",
            kind=IntelligenceQueryKind.EXPLAIN_GRAPH,
        ),
        claims,
    )
    priority = query_intelligence(
        IntelligenceQuery(
            project_id="harbor-api",
            kind=IntelligenceQueryKind.GAP_PRIORITY,
        ),
        claims,
    )
    assert graph.outcome is QueryOutcome.ANSWER
    assert graph.explain_graph is not None
    assert graph.explain_graph["authority_note"] == "graph-not-authority"
    assert priority.prioritized_gaps
    assert all(item["numeric_score"] is None for item in priority.prioritized_gaps)


def test_dependency_and_decision_queries_are_not_authority() -> None:
    claims = [
        _claim(
            "dep-1",
            value="lighthouse",
            field="depends_on",
            claim_type=ClaimType.RUNTIME_DEPENDENCY,
        ),
        _claim("claim-a", value="PostgreSQL 15"),
        _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
    ]
    deps = query_intelligence(
        IntelligenceQuery(
            project_id="harbor-api",
            kind=IntelligenceQueryKind.DEPENDENCIES,
        ),
        claims,
    )
    decision = query_intelligence(
        IntelligenceQuery(
            project_id="harbor-api",
            kind=IntelligenceQueryKind.DECISION,
        ),
        claims,
    )
    assert deps.dependencies
    assert all(item["inferred"] is False for item in deps.dependencies)
    assert decision.decision is not None
    assert decision.decision["selected"] is None
    assert decision.decision["is_command"] is False
    assert "healthy" not in decision.model_dump_json()
