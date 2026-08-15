"""AS-2.0-CTX-001 — derived agent context composer.

Composes read-only derived intelligence for an agent. Distinct from the
historical fixture context-pack package in ``project_atlas.context_pack``.
Not authority. Not a command. No canonical writes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_CTX
from project_atlas.intelligence.change import SemanticChange, detect_semantic_changes
from project_atlas.intelligence.contradictions import (
    ContradictionCandidate,
    ContradictionContext,
    find_contradiction_candidates,
)
from project_atlas.intelligence.derived_state import (
    DerivedFact,
    DerivedProjectState,
    StateContext,
    synthesize_project_state,
)
from project_atlas.intelligence.explain import EvidenceTrace, explain_why
from project_atlas.intelligence.gaps import EvidenceGap, detect_evidence_gaps
from project_atlas.intelligence.query import IntelligenceQuery, IntelligenceQueryKind
from project_atlas.intelligence.risk import RiskSignal, detect_risk_signals
from project_atlas.intelligence.timewin import parse_instant
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
    coerce_claims,
)

_CONSTRAINTS = (
    "DERIVED_INTELLIGENCE_IS_AUTHORITY=NO",
    "DERIVED_STATE_WRITES_TRUTH=NO",
    "AUTO_RESOLVE_TRUTH=NO",
    "UNKNOWN_IS_VALID=YES",
    "CANONICAL_WRITE=NO",
    "NEXT_ACTION_CANDIDATE_IS_COMMAND=NO",
)


class DerivedAgentContext(BaseModel):
    """Project-scoped derived context. Not a fixture pack and not authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-CTX-001"] = "AS-2.0-CTX-001"
    context_id: str
    project_id: str
    as_of_valid_time: str | None = None
    state: DerivedProjectState
    known_facts: tuple[DerivedFact, ...]
    unknown_facts: tuple[DerivedFact, ...]
    contested_facts: tuple[DerivedFact, ...]
    stale_facts: tuple[DerivedFact, ...]
    contradictions: tuple[ContradictionCandidate, ...]
    gaps: tuple[EvidenceGap, ...]
    risk_signals: tuple[RiskSignal, ...]
    changes: tuple[SemanticChange, ...]
    traces: tuple[EvidenceTrace, ...]
    constraints: tuple[str, ...]
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["context-not-authority"] = "context-not-authority"


def compose_agent_context(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
    as_of_valid_time: str | None = None,
) -> DerivedAgentContext:
    """Compose derived intelligence for one project. Never writes."""
    if not project_id.strip():
        raise ValueError("project_id is required")
    if as_of_valid_time is not None:
        parse_instant(as_of_valid_time, field="as-of")
    scoped = tuple(item for item in coerce_claims(claims) if item.project_id == project_id)
    state = synthesize_project_state(
        project_id,
        scoped,
        StateContext(
            as_of_valid_time=as_of_valid_time,
            sources=sources,
            validity_windows=validity_windows,
            identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        ),
    )
    contradictions = find_contradiction_candidates(
        scoped,
        ContradictionContext(
            as_of_valid_time=as_of_valid_time,
            validity_windows=validity_windows,
            sources=sources,
            identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        ),
    )
    gaps = detect_evidence_gaps(
        IntelligenceQuery(
            project_id=project_id,
            kind=IntelligenceQueryKind.GAPS,
            as_of_valid_time=as_of_valid_time,
        ),
        scoped,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
    )
    risks = detect_risk_signals(
        project_id,
        scoped,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        as_of_valid_time=as_of_valid_time,
    )
    changes = detect_semantic_changes(scoped, validity_windows=validity_windows)
    traces = _traces(
        project_id,
        scoped,
        state,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        as_of_valid_time=as_of_valid_time,
    )
    material = "|".join(
        (
            project_id,
            as_of_valid_time or "",
            state.package_id,
            ",".join(item.fact_id for item in state.known_facts),
            ",".join(item.candidate_id for item in contradictions),
        )
    )
    return DerivedAgentContext(
        context_id="ctx-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        project_id=project_id,
        as_of_valid_time=as_of_valid_time,
        state=state,
        known_facts=state.known_facts,
        unknown_facts=state.unknown_facts,
        contested_facts=state.contested_facts,
        stale_facts=state.stale_facts,
        contradictions=contradictions,
        gaps=gaps,
        risk_signals=risks,
        changes=changes,
        traces=traces,
        constraints=_CONSTRAINTS,
        truth_boundary=TRUTH_BOUNDARY_CTX,
    )


def _traces(
    project_id: str,
    claims: tuple[AssessableClaim, ...],
    state: DerivedProjectState,
    *,
    sources: tuple[SourceObservation, ...] | None,
    validity_windows: tuple[ValidityWindowInput, ...],
    identity_ambiguous_claim_ids: tuple[str, ...],
    as_of_valid_time: str | None,
) -> tuple[EvidenceTrace, ...]:
    slots: list[tuple[str | None, str | None]] = []
    seen: set[tuple[str | None, str | None]] = set()
    for fact in (*state.contested_facts, *state.unknown_facts, *state.stale_facts):
        key = (fact.subject, fact.field)
        if key in seen:
            continue
        seen.add(key)
        slots.append(key)
    if not slots:
        slots.append((None, None))
    found: list[EvidenceTrace] = []
    for subject, field in slots:
        found.append(
            explain_why(
                IntelligenceQuery(
                    project_id=project_id,
                    kind=IntelligenceQueryKind.EXPLAIN,
                    subject=subject,
                    field=field,
                    as_of_valid_time=as_of_valid_time,
                ),
                claims,
                sources=sources,
                validity_windows=validity_windows,
                identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
            )
        )
    found.sort(key=lambda item: item.trace_id)
    return tuple(found)
