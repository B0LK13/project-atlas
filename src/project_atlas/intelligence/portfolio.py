"""AS-2.0-PORTFOLIO-001 — cross-project state aggregator.

Aggregates per-project derived state. Prevents cross-project leakage
and identity collapse. Not portfolio truth and not a priority score.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_PORTFOLIO
from project_atlas.intelligence.derived_state import (
    DerivedProjectState,
    StateContext,
    synthesize_project_state,
)
from project_atlas.intelligence.timewin import parse_instant
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
    coerce_claims,
)


class LeakageRejection(BaseModel):
    """A claim excluded because it declared a different project identity."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    declared_project_id: str | None
    bundle_project_id: str
    reason: Literal["cross-project-claim-excluded"] = "cross-project-claim-excluded"


class PortfolioProjectEntry(BaseModel):
    """One project's derived state inside a portfolio aggregate."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    state: DerivedProjectState
    leakage_rejections: tuple[LeakageRejection, ...]


class PortfolioState(BaseModel):
    """Cross-project aggregate. Not authority and not a ranking score."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-PORTFOLIO-001"] = "AS-2.0-PORTFOLIO-001"
    portfolio_id: str
    entries: tuple[PortfolioProjectEntry, ...]
    rejected_leakage: tuple[LeakageRejection, ...]
    unknown_projects: tuple[str, ...]
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["portfolio-not-authority"] = "portfolio-not-authority"


def aggregate_portfolio_state(
    projects: Mapping[str, Sequence[Claim | AssessableClaim]],
    *,
    sources_by_project: Mapping[str, tuple[SourceObservation, ...]] | None = None,
    validity_windows_by_project: Mapping[str, tuple[ValidityWindowInput, ...]] | None = None,
    identity_ambiguous_by_project: Mapping[str, tuple[str, ...]] | None = None,
    as_of_valid_time: str | None = None,
) -> PortfolioState:
    """Aggregate independently synthesized project states. Never writes."""
    if as_of_valid_time is not None:
        parse_instant(as_of_valid_time, field="as-of")
    keys = sorted(project_id.strip() for project_id in projects)
    if any(not project_id for project_id in keys):
        raise ValueError("portfolio-project-id-required")
    if len(keys) != len(set(keys)):
        raise ValueError("portfolio-identity-collapse")
    entries: list[PortfolioProjectEntry] = []
    leakage: list[LeakageRejection] = []
    unknown: list[str] = []
    for project_id in keys:
        scoped, rejected = _scope(project_id, projects[project_id])
        leakage.extend(rejected)
        if not scoped:
            unknown.append(project_id)
        sources = None if sources_by_project is None else sources_by_project.get(project_id)
        windows = (
            ()
            if validity_windows_by_project is None
            else validity_windows_by_project.get(project_id, ())
        )
        ambiguous = (
            ()
            if identity_ambiguous_by_project is None
            else identity_ambiguous_by_project.get(project_id, ())
        )
        state = synthesize_project_state(
            project_id,
            scoped,
            StateContext(
                as_of_valid_time=as_of_valid_time,
                sources=sources,
                validity_windows=windows,
                identity_ambiguous_claim_ids=ambiguous,
            ),
        )
        entries.append(
            PortfolioProjectEntry(
                project_id=project_id,
                state=state,
                leakage_rejections=tuple(rejected),
            )
        )
    material = "|".join(keys + [item.claim_id for item in leakage])
    return PortfolioState(
        portfolio_id="pfo-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        entries=tuple(entries),
        rejected_leakage=tuple(leakage),
        unknown_projects=tuple(unknown),
        truth_boundary=TRUTH_BOUNDARY_PORTFOLIO,
    )


def _scope(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
) -> tuple[tuple[AssessableClaim, ...], tuple[LeakageRejection, ...]]:
    kept: list[AssessableClaim] = []
    rejected: list[LeakageRejection] = []
    for item in coerce_claims(claims):
        if item.project_id == project_id:
            kept.append(item)
            continue
        rejected.append(
            LeakageRejection(
                claim_id=item.claim_id,
                declared_project_id=item.project_id,
                bundle_project_id=project_id,
            )
        )
    return tuple(kept), tuple(rejected)
