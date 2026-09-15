"""AS-2.0-RISK-001 — project attention / risk signals.

Risk is not a fact. Attention is not failure. Every signal has evidence
and a reason. No opaque score.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_RISK
from project_atlas.intelligence.derived_state import (
    AttentionKind,
    StateContext,
    synthesize_project_state,
)
from project_atlas.intelligence.gaps import GapCurrentStatus, detect_evidence_gaps
from project_atlas.intelligence.query import IntelligenceQuery, IntelligenceQueryKind
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
    coerce_claims,
)


class RiskClass(StrEnum):
    ATTENTION = "attention"
    EVIDENCE = "evidence"
    IDENTITY = "identity"
    TEMPORAL = "temporal"
    UNKNOWN = "unknown"


class RiskSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-RISK-001"] = "AS-2.0-RISK-001"
    signal_id: str
    project_id: str
    risk_class: RiskClass
    reason: str
    evidence_refs: tuple[str, ...]
    related_fact_ids: tuple[str, ...]
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["risk-not-fact"] = "risk-not-fact"


def detect_risk_signals(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
    as_of_valid_time: str | None = None,
) -> tuple[RiskSignal, ...]:
    scoped = [item for item in coerce_claims(claims) if item.project_id == project_id]
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
    gaps = detect_evidence_gaps(
        IntelligenceQuery(project_id=project_id, kind=IntelligenceQueryKind.GAPS),
        scoped,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
    )
    signals: list[RiskSignal] = []
    for item in state.attention_candidates:
        risk_class = {
            AttentionKind.CONTRADICTION: RiskClass.ATTENTION,
            AttentionKind.STALE: RiskClass.TEMPORAL,
            AttentionKind.EVIDENCE_GAP: RiskClass.EVIDENCE,
            AttentionKind.SOURCE_HEALTH: RiskClass.EVIDENCE,
            AttentionKind.IDENTITY_AMBIGUITY: RiskClass.IDENTITY,
            AttentionKind.UNKNOWN: RiskClass.UNKNOWN,
        }[item.kind]
        signals.append(
            _signal(
                project_id,
                risk_class,
                item.reason,
                item.related_candidate_ids + item.related_fact_ids,
                item.related_fact_ids,
            )
        )
    for gap in gaps:
        if gap.current_status is GapCurrentStatus.UNKNOWN_FROM_NO_EVIDENCE:
            signals.append(
                _signal(
                    project_id,
                    RiskClass.UNKNOWN,
                    "unknown-from-no-evidence-is-not-safe",
                    gap.related_claim_ids,
                    (),
                )
            )
    signals.sort(key=lambda item: item.signal_id)
    return tuple(signals)


def _signal(
    project_id: str,
    risk_class: RiskClass,
    reason: str,
    evidence_refs: tuple[str, ...],
    fact_ids: tuple[str, ...],
) -> RiskSignal:
    material = "|".join((project_id, risk_class.value, reason, ",".join(evidence_refs)))
    return RiskSignal(
        signal_id="rsk-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        project_id=project_id,
        risk_class=risk_class,
        reason=reason,
        evidence_refs=evidence_refs,
        related_fact_ids=fact_ids,
        truth_boundary=TRUTH_BOUNDARY_RISK,
    )
