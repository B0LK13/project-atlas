"""AS-2.0-EXPLAIN-001 — library-only explanation graph.

Connects derived state, assessments, contradictions, changes, attention,
context, and next-action candidates. Not LLM authority.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.agent_context import compose_agent_context
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_EXPLAIN_GRAPH
from project_atlas.intelligence.next_action import propose_next_action_candidates
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
)


class ExplanationNodeKind(StrEnum):
    FACT = "derived-fact"
    ASSESSMENT = "evidence-assessment"
    CONTRADICTION = "contradiction-candidate"
    CHANGE = "semantic-change"
    RISK = "risk-signal"
    CONTEXT = "agent-context"
    NEXT_ACTION = "next-action-candidate"
    GAP = "evidence-gap"


class ExplanationEdgeKind(StrEnum):
    DERIVED_FROM = "derived-from"
    SUPPORTED_BY = "supported-by"
    CONTRADICTED_BY = "contradicted-by"
    LIMITED_BY = "limited-by"
    ATTENTION_FOR = "attention-for"
    COULD_CHANGE = "could-change"
    CONTEXT_INCLUDES = "context-includes"
    CANDIDATE_FOR = "candidate-for"


class ExplanationNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    kind: ExplanationNodeKind
    ref_id: str
    what: str
    why: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    uncertainty: tuple[str, ...]
    contradictions: tuple[str, ...]
    evidence_that_could_change: tuple[str, ...]


class ExplanationEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    kind: ExplanationEdgeKind
    source_id: str
    target_id: str
    reason: str


class ExplanationGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-EXPLAIN-001"] = "AS-2.0-EXPLAIN-001"
    graph_id: str
    project_id: str
    nodes: tuple[ExplanationNode, ...]
    edges: tuple[ExplanationEdge, ...]
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["graph-not-authority"] = "graph-not-authority"


def build_explanation_graph(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
    as_of_valid_time: str | None = None,
) -> ExplanationGraph:
    """Build a read-only explanation graph. Never writes and never invents."""
    if not project_id.strip():
        raise ValueError("project_id is required")
    context = compose_agent_context(
        project_id,
        claims,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        as_of_valid_time=as_of_valid_time,
    )
    actions = propose_next_action_candidates(
        project_id,
        claims,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        as_of_valid_time=as_of_valid_time,
    )
    nodes: list[ExplanationNode] = []
    edges: list[ExplanationEdge] = []
    contradiction_ids = tuple(item.candidate_id for item in context.contradictions)
    gap_improve = tuple(item.evidence_that_would_improve for item in context.gaps)

    nodes.append(
        _node(
            ExplanationNodeKind.CONTEXT,
            context.context_id,
            "derived-agent-context",
            context.constraints,
            (context.context_id,),
            ("derived-not-authority",),
            contradiction_ids,
            gap_improve,
        )
    )
    for fact in (
        *context.known_facts,
        *context.unknown_facts,
        *context.contested_facts,
        *context.stale_facts,
    ):
        node = _node(
            ExplanationNodeKind.FACT,
            fact.fact_id,
            f"fact:{fact.status.value}:{fact.field}",
            (fact.why,),
            fact.claim_ids,
            fact.limiting_factors,
            contradiction_ids if fact.status.value == "contested" else (),
            gap_improve,
        )
        nodes.append(node)
        edges.append(
            _edge(
                ExplanationEdgeKind.CONTEXT_INCLUDES,
                context.context_id,
                node.node_id,
                "context-includes-fact",
            )
        )
        if fact.claim_ids:
            edges.append(
                _edge(
                    ExplanationEdgeKind.DERIVED_FROM,
                    node.node_id,
                    context.context_id,
                    "fact-derived-from-scoped-claims",
                )
            )
        if fact.limiting_factors:
            edges.append(
                _edge(
                    ExplanationEdgeKind.LIMITED_BY,
                    node.node_id,
                    context.context_id,
                    "fact-confidence-is-limited",
                )
            )
    for item in context.contradictions:
        node = _node(
            ExplanationNodeKind.CONTRADICTION,
            item.candidate_id,
            f"contradiction:{item.candidate_class.value}",
            (item.reason,),
            (item.claim_a_id, item.claim_b_id),
            item.uncertainty,
            (item.candidate_id,),
            ("human-review-of-both-claims",),
        )
        nodes.append(node)
        edges.append(
            _edge(
                ExplanationEdgeKind.CONTRADICTED_BY,
                context.context_id,
                node.node_id,
                "context-has-contradiction-candidate",
            )
        )
    for gap in context.gaps:
        node = _node(
            ExplanationNodeKind.GAP,
            gap.gap_id,
            f"gap:{gap.gap_class.value}",
            (gap.why_material,),
            gap.related_claim_ids,
            (gap.current_status.value,),
            contradiction_ids if gap.current_status.value == "contested" else (),
            (gap.evidence_that_would_improve,),
        )
        nodes.append(node)
        edges.append(
            _edge(
                ExplanationEdgeKind.COULD_CHANGE,
                node.node_id,
                context.context_id,
                gap.evidence_that_would_improve,
            )
        )
    for risk in context.risk_signals:
        node = _node(
            ExplanationNodeKind.RISK,
            risk.signal_id,
            f"risk:{risk.risk_class.value}",
            (risk.reason,),
            risk.evidence_refs,
            ("risk-is-not-fact",),
            contradiction_ids,
            gap_improve,
        )
        nodes.append(node)
        edges.append(
            _edge(
                ExplanationEdgeKind.ATTENTION_FOR,
                node.node_id,
                context.context_id,
                risk.reason,
            )
        )
    for change in context.changes:
        node = _node(
            ExplanationNodeKind.CHANGE,
            change.change_id,
            f"change:{change.change_class.value}",
            (change.reason,),
            tuple(item for item in (change.from_claim_id, change.to_claim_id) if item),
            ("change-is-not-regression",),
            (),
            (),
        )
        nodes.append(node)
        edges.append(
            _edge(
                ExplanationEdgeKind.SUPPORTED_BY,
                node.node_id,
                context.context_id,
                change.reason,
            )
        )
    for action in actions:
        node = _node(
            ExplanationNodeKind.NEXT_ACTION,
            action.candidate_id,
            f"next:{action.kind.value}",
            (action.reason,),
            action.evidence_refs,
            ("candidate-is-not-command",),
            contradiction_ids if action.kind.value == "review-contradiction" else (),
            gap_improve,
        )
        nodes.append(node)
        edges.append(
            _edge(
                ExplanationEdgeKind.CANDIDATE_FOR,
                node.node_id,
                context.context_id,
                action.reason,
            )
        )

    nodes.sort(key=lambda item: item.node_id)
    edges.sort(key=lambda item: item.edge_id)
    material = "|".join((project_id, ",".join(item.node_id for item in nodes)))
    return ExplanationGraph(
        graph_id="xg-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        project_id=project_id,
        nodes=tuple(nodes),
        edges=tuple(edges),
        truth_boundary=TRUTH_BOUNDARY_EXPLAIN_GRAPH,
    )


def _node(
    kind: ExplanationNodeKind,
    ref_id: str,
    what: str,
    why: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    uncertainty: tuple[str, ...],
    contradictions: tuple[str, ...],
    evidence_that_could_change: tuple[str, ...],
) -> ExplanationNode:
    material = "|".join((kind.value, ref_id, what))
    return ExplanationNode(
        node_id="nd-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        kind=kind,
        ref_id=ref_id,
        what=what,
        why=why,
        evidence_refs=evidence_refs,
        uncertainty=uncertainty,
        contradictions=contradictions,
        evidence_that_could_change=evidence_that_could_change,
    )


def _edge(
    kind: ExplanationEdgeKind,
    source_id: str,
    target_id: str,
    reason: str,
) -> ExplanationEdge:
    material = "|".join((kind.value, source_id, target_id, reason))
    return ExplanationEdge(
        edge_id="eg-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        kind=kind,
        source_id=source_id,
        target_id=target_id,
        reason=reason,
    )
