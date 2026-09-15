"""AS-2.0-INTEL-004 — explain-why / evidence trace.

Explains why a derived conclusion exists and why confidence is limited.
Does not create evidence, resolve contradictions, or write truth.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_EXPLAIN
from project_atlas.intelligence.contradictions import (
    ContradictionContext,
    find_contradiction_candidates,
)
from project_atlas.intelligence.evidence import assess_evidence_many
from project_atlas.intelligence.query import IntelligenceQuery, SlotStatus
from project_atlas.intelligence.types import (
    AssessableClaim,
    AssessmentContext,
    EvidenceAssessment,
    EvidenceRef,
    SourceObservation,
    ValidityWindowInput,
)


class EvidenceTrace(BaseModel):
    """Explainable trace. Not new evidence and not a resolution."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-INTEL-004"] = "AS-2.0-INTEL-004"
    trace_id: str
    conclusion_kind: Literal["assessment", "contradiction", "fact", "unknown"]
    why_exists: tuple[str, ...]
    why_confidence_limited: tuple[str, ...]
    supporting_provenance: tuple[EvidenceRef, ...]
    contradicting_provenance: tuple[EvidenceRef, ...]
    unknown_factors: tuple[str, ...]
    as_of_valid_time: str | None = None
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["trace-not-authoritative"] = "trace-not-authoritative"


def explain_why(
    query: IntelligenceQuery,
    claims: Sequence[AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
) -> EvidenceTrace:
    """Build an evidence trace for the query scope. Never mutates claims."""
    assessments = assess_evidence_many(
        claims,
        AssessmentContext(
            as_of_valid_time=query.as_of_valid_time,
            sources=sources,
            peer_claims=tuple(claims),
            validity_windows=validity_windows,
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
    why_exists: list[str] = []
    why_limited: list[str] = []
    supporting: list[EvidenceRef] = []
    contradicting: list[EvidenceRef] = []
    unknown: list[str] = []
    kind: Literal["assessment", "contradiction", "fact", "unknown"] = "unknown"
    if not claims:
        why_exists.append("no-matching-claims")
        unknown.append("no-evidence")
    elif candidates:
        kind = "contradiction"
        why_exists.append("incompatible-values-in-query-scope")
        why_limited.append("open-contradiction-candidates")
        for candidate in candidates:
            contradicting.extend(candidate.supporting_evidence)
            unknown.extend(candidate.uncertainty)
    else:
        kind = "assessment"
        why_exists.append("derived-from-scoped-claim-assessments")
        for assessment in assessments:
            why_limited.extend(factor.value for factor in assessment.limiting_factors)
            supporting.extend(assessment.supporting_evidence)
            contradicting.extend(assessment.contradicting_evidence)
            unknown.extend(assessment.unknown_factors)
    if query.as_of_valid_time is None:
        unknown.append("as-of-valid-time-not-supplied")
    material = "|".join(
        (
            query.project_id,
            query.subject or "",
            query.field or "",
            query.claim_id or "",
            kind,
        )
    )
    return EvidenceTrace(
        trace_id="ex-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        conclusion_kind=kind,
        why_exists=tuple(sorted(set(why_exists))),
        why_confidence_limited=tuple(sorted(set(why_limited))),
        supporting_provenance=_unique_refs(supporting),
        contradicting_provenance=_unique_refs(contradicting),
        unknown_factors=tuple(sorted(set(unknown))),
        as_of_valid_time=query.as_of_valid_time,
        truth_boundary=TRUTH_BOUNDARY_EXPLAIN,
    )


def explanation_for_query(
    query: IntelligenceQuery,
    claims: Sequence[AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
) -> tuple[EvidenceTrace, SlotStatus, str, tuple[EvidenceAssessment, ...]]:
    """Query-binding helper used by INTEL-003 after this package lands."""
    trace = explain_why(
        query,
        claims,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
    )
    assessments = assess_evidence_many(
        claims,
        AssessmentContext(
            as_of_valid_time=query.as_of_valid_time,
            sources=sources,
            peer_claims=tuple(claims),
            validity_windows=validity_windows,
        ),
    )
    if not claims:
        return trace, SlotStatus.NO_EVIDENCE, "no-matching-claims", ()
    if trace.conclusion_kind == "contradiction":
        return trace, SlotStatus.CONTESTED, "explained-open-contradiction", assessments
    if "temporal-stale" in trace.why_confidence_limited:
        return trace, SlotStatus.STALE, "explained-stale-evidence", assessments
    if assessments and all(item.confidence_class.value == "unknown" for item in assessments):
        return trace, SlotStatus.UNKNOWN, "explained-unknown-assessment", assessments
    return trace, SlotStatus.DERIVED, "explained-derived-assessment", assessments


def _unique_refs(items: Sequence[EvidenceRef]) -> tuple[EvidenceRef, ...]:
    seen: set[tuple[str, str, str, str]] = set()
    out: list[EvidenceRef] = []
    for item in items:
        key = (item.claim_id or "", item.source_id or "", item.resource or "", item.role.value)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.sort(key=lambda item: (item.claim_id or "", item.source_id or "", item.resource or ""))
    return tuple(out)
