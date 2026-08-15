"""AS-2.0-HANDOFF-001 — evidence-aware handoff intelligence.

Read-only handoff view for a receiving agent. Does not write vault
handoff packs and does not call ``project_atlas.agent_handoff``.
Not a command. Not auto-resolution.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.agent_context import (
    DerivedAgentContext,
    compose_agent_context,
)
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_HANDOFF
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
)

_DO_NOT = (
    "do-not-auto-resolve-contradictions",
    "do-not-write-canonical-truth",
    "do-not-treat-unknown-as-safe",
    "do-not-treat-derived-context-as-authority",
    "do-not-execute-next-action-candidates",
    "do-not-mutate-coder-alpha-handoff-packs",
)


class EvidenceHandoff(BaseModel):
    """Evidence-aware handoff. Not a write and not a command."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-HANDOFF-001"] = "AS-2.0-HANDOFF-001"
    handoff_id: str
    project_id: str
    context_id: str
    what_is_known: tuple[str, ...]
    what_is_unknown: tuple[str, ...]
    what_is_contested: tuple[str, ...]
    what_is_stale: tuple[str, ...]
    open_contradictions: tuple[str, ...]
    material_gaps: tuple[str, ...]
    risk_signal_ids: tuple[str, ...]
    evidence_trace_ids: tuple[str, ...]
    do_not: tuple[str, ...]
    context: DerivedAgentContext
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["handoff-not-command"] = "handoff-not-command"


def compose_evidence_handoff(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
    as_of_valid_time: str | None = None,
) -> EvidenceHandoff:
    """Compose a read-only evidence handoff. Never writes packs."""
    context = compose_agent_context(
        project_id,
        claims,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        as_of_valid_time=as_of_valid_time,
    )
    known = tuple(item.fact_id for item in context.known_facts)
    unknown = tuple(item.fact_id for item in context.unknown_facts)
    contested = tuple(item.fact_id for item in context.contested_facts)
    stale = tuple(item.fact_id for item in context.stale_facts)
    contradictions = tuple(item.candidate_id for item in context.contradictions)
    gaps = tuple(item.gap_id for item in context.gaps)
    risks = tuple(item.signal_id for item in context.risk_signals)
    traces = tuple(item.trace_id for item in context.traces)
    material = "|".join((project_id, context.context_id, ",".join(contested), ",".join(gaps)))
    return EvidenceHandoff(
        handoff_id="hnd-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        project_id=project_id,
        context_id=context.context_id,
        what_is_known=known,
        what_is_unknown=unknown,
        what_is_contested=contested,
        what_is_stale=stale,
        open_contradictions=contradictions,
        material_gaps=gaps,
        risk_signal_ids=risks,
        evidence_trace_ids=traces,
        do_not=_DO_NOT,
        context=context,
        truth_boundary=TRUTH_BOUNDARY_HANDOFF,
    )
