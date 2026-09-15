"""AS-2.0-INTEL-OBS-001 — derived-intelligence run observability.

Records pairing cost and duration. Not a quality score and not authority.
Does not write catalogs. Duration is a measurement, not generated.at.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import GENERATED_BY
from project_atlas.intelligence.contradictions import (
    ContradictionContext,
    PairingStats,
    find_contradiction_candidates_report,
)
from project_atlas.intelligence.types import AssessableClaim, coerce_claims

TRUTH_BOUNDARY_OBS = "OBSERVABILITY ≠ QUALITY SCORE / ≠ AUTHORITY / ≠ CANONICAL WRITE"


class IntelligenceRunReport(BaseModel):
    """Explainable run cost. Not a health or confidence score."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-INTEL-OBS-001"] = "AS-2.0-INTEL-OBS-001"
    report_id: str
    project_id: str | None
    claim_count: int
    pairing: PairingStats
    duration_ms: int
    materialized: bool
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["obs-not-score"] = "obs-not-score"


def observe_intelligence_run(
    claims: Sequence[Claim | AssessableClaim],
    *,
    project_id: str | None = None,
    context: ContradictionContext | None = None,
    materialize: bool = False,
) -> IntelligenceRunReport:
    """Measure one read-only intelligence pairing run. Never writes."""
    scoped = coerce_claims(claims)
    if project_id:
        scoped = tuple(item for item in scoped if item.project_id == project_id)
    started = time.perf_counter()
    _candidates, stats = find_contradiction_candidates_report(
        scoped, context, materialize=materialize
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    material = "|".join(
        (
            project_id or "",
            str(stats.claim_count),
            str(stats.pair_evaluations),
            str(stats.candidate_count),
            "materialize" if materialize else "count-only",
        )
    )
    return IntelligenceRunReport(
        report_id="obs-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        project_id=project_id,
        claim_count=stats.claim_count,
        pairing=stats,
        duration_ms=duration_ms,
        materialized=materialize,
        truth_boundary=TRUTH_BOUNDARY_OBS,
    )
