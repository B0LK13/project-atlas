"""AS-2.0-PORTFOLIO-003 — portfolio attention ranking.

Discrete attention classes with reasons and evidence.
Ordering is a deterministic classification sort, not a priority score.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_PORTFOLIO
from project_atlas.intelligence.derived_state import (
    AttentionKind,
    DerivedProjectState,
    FactStatus,
)
from project_atlas.intelligence.portfolio import aggregate_portfolio_state
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
)

# Classification sort only. Not a numeric priority score.
_CLASS_ORDER = {
    "contested": 0,
    "unknown": 1,
    "stale": 2,
    "evidence": 3,
    "none": 4,
}


class AttentionRankClass(StrEnum):
    CONTESTED = "contested"
    UNKNOWN = "unknown"
    STALE = "stale"
    EVIDENCE = "evidence"
    NONE = "none"


class PortfolioAttentionEntry(BaseModel):
    """One project's attention class. No opaque score."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-PORTFOLIO-003"] = "AS-2.0-PORTFOLIO-003"
    entry_id: str
    project_id: str
    rank_class: AttentionRankClass
    reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    numeric_score: None = None
    sort_is_score: Literal[False] = False
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["rank-not-score"] = "rank-not-score"


def rank_portfolio_attention(
    projects: Mapping[str, Sequence[Claim | AssessableClaim]],
    *,
    sources_by_project: Mapping[str, tuple[SourceObservation, ...]] | None = None,
    validity_windows_by_project: Mapping[str, tuple[ValidityWindowInput, ...]] | None = None,
    identity_ambiguous_by_project: Mapping[str, tuple[str, ...]] | None = None,
    as_of_valid_time: str | None = None,
) -> tuple[PortfolioAttentionEntry, ...]:
    """Classify portfolio attention. Never assigns a numeric priority."""
    portfolio = aggregate_portfolio_state(
        projects,
        sources_by_project=sources_by_project,
        validity_windows_by_project=validity_windows_by_project,
        identity_ambiguous_by_project=identity_ambiguous_by_project,
        as_of_valid_time=as_of_valid_time,
    )
    found: list[PortfolioAttentionEntry] = []
    for item in portfolio.entries:
        rank, reasons, refs = _classify(item.project_id, item.state, portfolio.unknown_projects)
        material = "|".join((item.project_id, rank.value, ",".join(reasons)))
        found.append(
            PortfolioAttentionEntry(
                entry_id="att-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
                project_id=item.project_id,
                rank_class=rank,
                reasons=reasons,
                evidence_refs=refs,
                truth_boundary=TRUTH_BOUNDARY_PORTFOLIO,
            )
        )
    found.sort(key=lambda item: (_CLASS_ORDER[item.rank_class.value], item.project_id))
    return tuple(found)


def _classify(
    project_id: str,
    state: DerivedProjectState,
    unknown_projects: tuple[str, ...],
) -> tuple[AttentionRankClass, tuple[str, ...], tuple[str, ...]]:
    reasons: list[str] = []
    refs: list[str] = []
    if project_id in unknown_projects or state.unknown_facts:
        reasons.append("unknown-is-not-safe")
        refs.extend(item.fact_id for item in state.unknown_facts)
    if state.contested_facts or state.open_contradictions:
        reasons.append("contested-attention-is-not-failure")
        refs.extend(item.fact_id for item in state.contested_facts)
        refs.extend(state.open_contradictions)
    if state.stale_facts:
        reasons.append("stale-is-not-invalid")
        refs.extend(item.fact_id for item in state.stale_facts)
    evidence_kinds = {
        AttentionKind.EVIDENCE_GAP,
        AttentionKind.SOURCE_HEALTH,
        AttentionKind.IDENTITY_AMBIGUITY,
    }
    if any(item.kind in evidence_kinds for item in state.attention_candidates):
        reasons.append("evidence-attention-is-not-a-score")
        refs.extend(item.attention_id for item in state.attention_candidates)
    if state.contested_facts or state.open_contradictions:
        return AttentionRankClass.CONTESTED, tuple(reasons), tuple(refs)
    if project_id in unknown_projects or any(
        item.status is FactStatus.UNKNOWN for item in state.unknown_facts
    ):
        return AttentionRankClass.UNKNOWN, tuple(reasons) or ("unknown-from-no-evidence",), tuple(
            refs
        )
    if state.stale_facts:
        return AttentionRankClass.STALE, tuple(reasons), tuple(refs)
    if reasons:
        return AttentionRankClass.EVIDENCE, tuple(reasons), tuple(refs)
    return AttentionRankClass.NONE, ("no-attention-class-assigned",), ()
