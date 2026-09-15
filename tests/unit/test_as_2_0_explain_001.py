"""AS-2.0-EXPLAIN-001 — explanation graph."""

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
from project_atlas.intelligence.explain_graph import (
    ExplanationNodeKind,
    build_explanation_graph,
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


def test_graph_answers_what_why_evidence_and_is_not_authority() -> None:
    graph = build_explanation_graph(
        "harbor-api",
        [
            _claim("claim-a", value="PostgreSQL 15"),
            _claim("claim-b", value="PostgreSQL 16", source_id="src-b"),
        ],
    )
    assert graph.authority_note == "graph-not-authority"
    assert graph.package_id == "AS-2.0-EXPLAIN-001"
    kinds = {item.kind for item in graph.nodes}
    assert ExplanationNodeKind.FACT in kinds
    assert ExplanationNodeKind.CONTRADICTION in kinds
    assert ExplanationNodeKind.NEXT_ACTION in kinds
    assert all(item.what and item.why for item in graph.nodes)
    contested = [item for item in graph.nodes if item.kind is ExplanationNodeKind.FACT]
    assert any(item.contradictions for item in contested)
    assert any(item.evidence_that_could_change for item in graph.nodes)
    assert "llm" not in graph.model_dump_json()
    assert graph.edges


def test_empty_project_graph_is_unknown_not_healthy() -> None:
    graph = build_explanation_graph("harbor-api", [])
    assert "healthy" not in graph.model_dump_json()
    assert graph.nodes
