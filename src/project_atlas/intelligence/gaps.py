"""AS-2.0-INTEL-005 — evidence gap detection.

Identifies missing evidence that would materially improve a conclusion.
A gap is not a command to invent evidence and not a falsehood.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_GAPS
from project_atlas.intelligence.contradictions import (
    ContradictionContext,
    find_contradiction_candidates,
)
from project_atlas.intelligence.evidence import assess_evidence_many
from project_atlas.intelligence.query import IntelligenceQuery, SlotStatus
from project_atlas.intelligence.types import (
    AssessableClaim,
    AssessmentContext,
    LimitingFactor,
    SourceObservation,
    ValidityWindowInput,
)


class GapClass(StrEnum):
    NO_EVIDENCE = "no-evidence"
    MISSING_PROVENANCE = "missing-provenance"
    MISSING_SOURCE = "missing-source"
    MISSING_VALIDITY_WINDOW = "missing-validity-window"
    MISSING_CORROBORATION = "missing-corroboration"
    MISSING_AUTHORITY = "missing-authority"
    IDENTITY_UNRESOLVED = "identity-unresolved"
    WOULD_CHANGE_CONCLUSION = "would-change-conclusion"


class GapCurrentStatus(StrEnum):
    UNKNOWN_FROM_NO_EVIDENCE = "unknown-from-no-evidence"
    CONTESTED = "contested"
    STALE = "stale"
    LIMITED = "limited"


class EvidenceGap(BaseModel):
    """One missing-evidence signal. Not a write request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-INTEL-005"] = "AS-2.0-INTEL-005"
    gap_id: str
    gap_class: GapClass
    project_id: str
    subject: str | None = None
    field: str | None = None
    current_status: GapCurrentStatus
    why_material: str
    evidence_that_would_improve: str
    related_claim_ids: tuple[str, ...]
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["gap-not-authority"] = "gap-not-authority"


def detect_evidence_gaps(
    query: IntelligenceQuery,
    claims: Sequence[AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
) -> tuple[EvidenceGap, ...]:
    """Detect material evidence gaps for a query scope."""
    assessments = assess_evidence_many(
        claims,
        AssessmentContext(
            as_of_valid_time=query.as_of_valid_time,
            sources=sources,
            peer_claims=tuple(claims),
            validity_windows=validity_windows,
            identity_ambiguous=bool(identity_ambiguous_claim_ids),
        ),
    )
    candidates = find_contradiction_candidates(
        claims,
        ContradictionContext(
            as_of_valid_time=query.as_of_valid_time,
            validity_windows=validity_windows,
            sources=sources,
            identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        ),
    )
    windows = {item.claim_id for item in validity_windows}
    gaps: list[EvidenceGap] = []
    claim_ids = tuple(item.claim_id for item in claims)
    if not claims:
        gaps.append(
            _gap(
                query,
                GapClass.NO_EVIDENCE,
                GapCurrentStatus.UNKNOWN_FROM_NO_EVIDENCE,
                "no-claims-in-scope",
                "at-least-one-provenance-backed-claim-for-the-requested-slot",
                (),
            )
        )
        return tuple(gaps)
    if candidates:
        gaps.append(
            _gap(
                query,
                GapClass.WOULD_CHANGE_CONCLUSION,
                GapCurrentStatus.CONTESTED,
                "open-contradiction-candidates-block-a-single-value",
                "human-review-or-temporally-disjoint-windows-or-authority-disposition",
                claim_ids,
            )
        )
    factors = {factor for item in assessments for factor in item.limiting_factors}
    if LimitingFactor.MISSING_PROVENANCE in factors:
        gaps.append(
            _gap(
                query,
                GapClass.MISSING_PROVENANCE,
                GapCurrentStatus.LIMITED,
                "one-or-more-claims-lack-provenance",
                "provenance-reference-with-source-id-and-resource",
                claim_ids,
            )
        )
    if LimitingFactor.MISSING_SOURCE in factors:
        gaps.append(
            _gap(
                query,
                GapClass.MISSING_SOURCE,
                GapCurrentStatus.LIMITED,
                "declared-source-missing-or-deleted",
                "present-source-record-for-the-cited-source-id",
                claim_ids,
            )
        )
    if LimitingFactor.AUTHORITY_WEAK in factors or LimitingFactor.AUTHORITY_MISMATCH in factors:
        gaps.append(
            _gap(
                query,
                GapClass.MISSING_AUTHORITY,
                GapCurrentStatus.LIMITED,
                "authority-is-weak-or-mismatched",
                "applicable-domain-authority-evidence",
                claim_ids,
            )
        )
    if LimitingFactor.SINGLE_SOURCE in factors or LimitingFactor.SAME_LINEAGE_ONLY in factors:
        gaps.append(
            _gap(
                query,
                GapClass.MISSING_CORROBORATION,
                GapCurrentStatus.LIMITED,
                "only-one-lineage-supports-the-value",
                "independent-lineage-cannot-be-fabricated-from-path",
                claim_ids,
            )
        )
    if LimitingFactor.TEMPORAL_STALE in factors:
        gaps.append(
            _gap(
                query,
                GapClass.MISSING_VALIDITY_WINDOW,
                GapCurrentStatus.STALE,
                "evidence-is-stale-not-invalid",
                "current-valid-time-window-or-successor-claim",
                claim_ids,
            )
        )
    elif query.as_of_valid_time is not None and any(
        item.claim_id not in windows for item in claims
    ):
        gaps.append(
            _gap(
                query,
                GapClass.MISSING_VALIDITY_WINDOW,
                GapCurrentStatus.LIMITED,
                "as-of-supplied-but-window-missing",
                "document-declared-valid-from-and-valid-to",
                claim_ids,
            )
        )
    if identity_ambiguous_claim_ids or LimitingFactor.IDENTITY_AMBIGUOUS in factors:
        gaps.append(
            _gap(
                query,
                GapClass.IDENTITY_UNRESOLVED,
                GapCurrentStatus.LIMITED,
                "subject-or-lineage-identity-is-ambiguous",
                "durable-identity-resolution-not-a-guess",
                claim_ids,
            )
        )
    gaps.sort(key=lambda item: item.gap_id)
    return tuple(gaps)


def gaps_for_query(
    query: IntelligenceQuery,
    claims: Sequence[AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
) -> tuple[tuple[EvidenceGap, ...], SlotStatus, str]:
    gaps = detect_evidence_gaps(
        query,
        claims,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
    )
    if not claims:
        return gaps, SlotStatus.NO_EVIDENCE, "unknown-from-no-evidence"
    statuses = {item.current_status for item in gaps}
    if GapCurrentStatus.CONTESTED in statuses:
        return gaps, SlotStatus.CONTESTED, "gaps-include-contested-slot"
    if GapCurrentStatus.STALE in statuses:
        return gaps, SlotStatus.STALE, "gaps-include-stale-slot"
    if GapCurrentStatus.UNKNOWN_FROM_NO_EVIDENCE in statuses:
        return gaps, SlotStatus.NO_EVIDENCE, "unknown-from-no-evidence"
    return gaps, SlotStatus.UNKNOWN, "gaps-limit-confidence"


def _gap(
    query: IntelligenceQuery,
    gap_class: GapClass,
    current_status: GapCurrentStatus,
    why_material: str,
    evidence_that_would_improve: str,
    claim_ids: tuple[str, ...],
) -> EvidenceGap:
    material = "|".join(
        (
            query.project_id,
            query.subject or "",
            query.field or "",
            gap_class.value,
            current_status.value,
            why_material,
        )
    )
    return EvidenceGap(
        gap_id="gap-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        gap_class=gap_class,
        project_id=query.project_id,
        subject=query.subject,
        field=query.field,
        current_status=current_status,
        why_material=why_material,
        evidence_that_would_improve=evidence_that_would_improve,
        related_claim_ids=claim_ids,
        truth_boundary=TRUTH_BOUNDARY_GAPS,
    )
