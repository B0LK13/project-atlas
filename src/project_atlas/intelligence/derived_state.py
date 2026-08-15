"""AS-2.0-STATE-001 — derived project state synthesizer.

Read-only. Not Roadmap. Not canonical project truth. Not a write-back
engine. Prefer OBSERVED / DERIVED / UNKNOWN / CONTESTED / STALE over
speculative health language.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim, ClaimLifecycle
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_STATE
from project_atlas.intelligence.contradictions import (
    ContradictionCandidate,
    ContradictionClass,
    ContradictionContext,
    find_contradiction_candidates,
)
from project_atlas.intelligence.evidence import assess_evidence_many
from project_atlas.intelligence.normalize import group_key, normalize_value
from project_atlas.intelligence.timewin import windows_relation
from project_atlas.intelligence.types import (
    AssessableClaim,
    AssessmentContext,
    ConfidenceClass,
    EvidenceAssessment,
    EvidenceRef,
    LimitingFactor,
    SourceObservation,
    ValidityWindowInput,
    coerce_claims,
)

_FORBIDDEN_STATUS_INFERENCE = frozenset({"healthy", "on track", "failed", "blocked"})


class FactStatus(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    UNKNOWN = "unknown"
    CONTESTED = "contested"
    STALE = "stale"


class AttentionKind(StrEnum):
    CONTRADICTION = "contradiction"
    STALE = "stale"
    EVIDENCE_GAP = "evidence-gap"
    SOURCE_HEALTH = "source-health"
    IDENTITY_AMBIGUITY = "identity-ambiguity"
    UNKNOWN = "unknown"


class StateContext(BaseModel):
    """Read-only synthesis context. Never supplies wall-clock now."""

    model_config = ConfigDict(extra="forbid")

    as_of_valid_time: str | None = None
    sources: tuple[SourceObservation, ...] | None = None
    validity_windows: tuple[ValidityWindowInput, ...] = ()
    identity_ambiguous_claim_ids: tuple[str, ...] = ()


class DerivedFact(BaseModel):
    """One explainable derived fact slot. Always traceable to evidence."""

    model_config = ConfigDict(extra="forbid")

    fact_id: str
    project_id: str
    subject: str
    field: str
    status: FactStatus
    value: str | None = None
    confidence_class: ConfidenceClass
    claim_ids: tuple[str, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    limiting_factors: tuple[str, ...]
    why: str
    as_of_valid_time: str | None = None


class AttentionCandidate(BaseModel):
    """Attention signal with an explicit why. Not a health score."""

    model_config = ConfigDict(extra="forbid")

    attention_id: str
    kind: AttentionKind
    reason: str
    related_fact_ids: tuple[str, ...]
    related_candidate_ids: tuple[str, ...]


class DerivedProjectState(BaseModel):
    """Current derived project state. Not canonical. Not Roadmap."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-STATE-001"] = "AS-2.0-STATE-001"
    project_id: str
    as_of_valid_time: str | None = None
    evaluation_context: Literal["as-of-valid-time", "unspecified-valid-time"]
    known_facts: tuple[DerivedFact, ...]
    unknown_facts: tuple[DerivedFact, ...]
    stale_facts: tuple[DerivedFact, ...]
    contested_facts: tuple[DerivedFact, ...]
    recently_changed_facts: tuple[DerivedFact, ...]
    high_confidence_facts: tuple[str, ...]
    low_confidence_facts: tuple[str, ...]
    open_contradictions: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    source_health_concerns: tuple[str, ...]
    attention_candidates: tuple[AttentionCandidate, ...]
    temporal_changes: tuple[str, ...]
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["derived-state-not-canonical"] = "derived-state-not-canonical"


def synthesize_project_state(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
    context: StateContext | None = None,
) -> DerivedProjectState:
    """Derive explainable current state for one project. Never writes."""
    if not project_id:
        raise ValueError("project_id is required")
    ctx = context if context is not None else StateContext()
    scoped = tuple(
        item for item in coerce_claims(claims) if item.project_id == project_id
    )
    assessment_ctx = AssessmentContext(
        as_of_valid_time=ctx.as_of_valid_time,
        sources=ctx.sources,
        peer_claims=scoped,
        validity_windows=ctx.validity_windows,
        identity_ambiguous=bool(ctx.identity_ambiguous_claim_ids),
    )
    assessments = assess_evidence_many(scoped, assessment_ctx)
    by_claim = {item.claim_id: item for item in assessments}
    candidates = find_contradiction_candidates(
        scoped,
        ContradictionContext(
            as_of_valid_time=ctx.as_of_valid_time,
            validity_windows=ctx.validity_windows,
            sources=ctx.sources,
            identity_ambiguous_claim_ids=ctx.identity_ambiguous_claim_ids,
            assessments=assessments,
        ),
    )
    facts, temporal_changes = _facts_for_project(
        project_id, scoped, by_claim, candidates, ctx
    )
    attention = _attention(facts, candidates, ctx)
    known = tuple(item for item in facts if item.status in {FactStatus.OBSERVED, FactStatus.DERIVED})
    unknown = tuple(item for item in facts if item.status is FactStatus.UNKNOWN)
    stale = tuple(item for item in facts if item.status is FactStatus.STALE)
    contested = tuple(item for item in facts if item.status is FactStatus.CONTESTED)
    recent = tuple(item for item in facts if "recently-changed" in item.why)
    high = tuple(
        item.fact_id for item in facts if item.confidence_class is ConfidenceClass.HIGH
    )
    low = tuple(
        item.fact_id
        for item in facts
        if item.confidence_class in {ConfidenceClass.LOW, ConfidenceClass.UNKNOWN}
    )
    gaps = tuple(
        item.fact_id
        for item in facts
        if any(
            token in item.limiting_factors
            for token in (
                LimitingFactor.MISSING_PROVENANCE.value,
                LimitingFactor.MISSING_EVIDENCE.value,
                LimitingFactor.UNSUPPORTED_CLAIM.value,
            )
        )
    )
    source_health = tuple(
        item.fact_id
        for item in facts
        if LimitingFactor.MISSING_SOURCE.value in item.limiting_factors
        or LimitingFactor.LINEAGE_INTEGRITY_BROKEN.value in item.limiting_factors
    )
    evaluation_context: Literal["as-of-valid-time", "unspecified-valid-time"] = (
        "as-of-valid-time" if ctx.as_of_valid_time is not None else "unspecified-valid-time"
    )
    state = DerivedProjectState(
        project_id=project_id,
        as_of_valid_time=ctx.as_of_valid_time,
        evaluation_context=evaluation_context,
        known_facts=known,
        unknown_facts=unknown,
        stale_facts=stale,
        contested_facts=contested,
        recently_changed_facts=recent,
        high_confidence_facts=high,
        low_confidence_facts=low,
        open_contradictions=tuple(item.candidate_id for item in candidates),
        evidence_gaps=gaps,
        source_health_concerns=source_health,
        attention_candidates=attention,
        temporal_changes=temporal_changes,
        truth_boundary=TRUTH_BOUNDARY_STATE,
    )
    _reject_unsupported_status_inference(state)
    return state


def _facts_for_project(
    project_id: str,
    claims: tuple[AssessableClaim, ...],
    assessments: dict[str, EvidenceAssessment],
    candidates: tuple[ContradictionCandidate, ...],
    ctx: StateContext,
) -> tuple[tuple[DerivedFact, ...], tuple[str, ...]]:
    if not claims:
        empty = _empty_project_fact(project_id, ctx.as_of_valid_time)
        return (empty,), ()
    groups: dict[str, list[AssessableClaim]] = defaultdict(list)
    for item in claims:
        groups[group_key(item.project_id, item.subject, item.field)].append(item)
    windows = {item.claim_id: item for item in ctx.validity_windows}
    facts: list[DerivedFact] = []
    temporal_changes: list[str] = []
    for bucket in groups.values():
        bucket.sort(key=lambda item: item.claim_id)
        sample = bucket[0]
        fact_id = _fact_id(project_id, sample.subject, sample.field)
        group_candidates = [
            item
            for item in candidates
            if item.subject == sample.subject and item.field == sample.field
        ]
        group_assessments = [assessments[item.claim_id] for item in bucket]
        refs = _unique_refs(group_assessments)
        factors = tuple(
            sorted({factor.value for item in group_assessments for factor in item.limiting_factors})
        )
        claim_ids = tuple(item.claim_id for item in bucket)
        contested = bool(group_candidates)
        stale = any(
            LimitingFactor.TEMPORAL_STALE in item.limiting_factors
            or (
                next(
                    (claim.lifecycle for claim in bucket if claim.claim_id == item.claim_id),
                    None,
                )
                is ClaimLifecycle.STALE
            )
            for item in group_assessments
        )
        unknown = all(item.confidence_class is ConfidenceClass.UNKNOWN for item in group_assessments)
        values = {normalize_value(item.value, item.normalized_text) for item in bucket}
        recently = any(
            item.predecessor_claim_id or item.lifecycle is ClaimLifecycle.UPDATED for item in bucket
        )
        succession = _group_succession(bucket, windows)
        if succession:
            temporal_changes.append(f"{fact_id}:temporal-succession")
            recently = True
        applicable = [
            (claim, assessment)
            for claim, assessment in zip(bucket, group_assessments, strict=True)
            if assessment.dimensions.temporal_applicability == "applicable"
        ]
        if contested:
            status = FactStatus.CONTESTED
            value: str | None = None
            why = "open-contradiction-candidates-prevent-a-single-value"
            confidence = ConfidenceClass.LOW
        elif unknown:
            status = FactStatus.UNKNOWN
            value = None
            why = "all-participating-claims-are-unknown"
            confidence = ConfidenceClass.UNKNOWN
        elif applicable and len(
            {normalize_value(item[0].value, item[0].normalized_text) for item in applicable}
        ) == 1:
            chosen, chosen_assessment = applicable[0]
            stale_applicable = any(
                LimitingFactor.TEMPORAL_STALE in item[1].limiting_factors for item in applicable
            )
            status = FactStatus.STALE if stale_applicable else (
                FactStatus.OBSERVED if len(applicable) == 1 else FactStatus.DERIVED
            )
            value = chosen.value
            why = (
                "as-of-applicable-claim-is-stale-not-invalid"
                if stale_applicable
                else "as-of-selected-applicable-claim"
            )
            confidence = chosen_assessment.confidence_class
        elif stale:
            status = FactStatus.STALE
            value = bucket[-1].value if len(values) == 1 else None
            why = "evidence-is-stale-not-invalid"
            confidence = ConfidenceClass.LOW
        elif len(values) == 1 and len(bucket) == 1:
            status = FactStatus.OBSERVED
            value = bucket[0].value
            why = "single-observed-claim-value"
            confidence = group_assessments[0].confidence_class
        elif len(values) == 1:
            status = FactStatus.DERIVED
            value = bucket[0].value
            why = "corroborated-value-derived-from-agreeing-claims"
            confidence = _best_confidence(group_assessments)
        else:
            status = FactStatus.UNKNOWN
            value = None
            why = "values-differ-without-a-qualified-contradiction-candidate"
            confidence = ConfidenceClass.UNKNOWN
        if recently:
            why = f"{why};recently-changed"
        fact = DerivedFact(
            fact_id=fact_id,
            project_id=project_id,
            subject=sample.subject,
            field=sample.field,
            status=status,
            value=value,
            confidence_class=confidence,
            claim_ids=claim_ids,
            evidence_refs=refs,
            limiting_factors=factors,
            why=why,
            as_of_valid_time=ctx.as_of_valid_time,
        )
        facts.append(fact)
    facts.sort(key=lambda item: item.fact_id)
    return tuple(facts), tuple(sorted(set(temporal_changes)))


def _empty_project_fact(project_id: str, as_of: str | None) -> DerivedFact:
    subject = project_id if ":" in project_id else f"project:{project_id}"
    return DerivedFact(
        fact_id=_fact_id(project_id, subject, "observed-claims"),
        project_id=project_id,
        subject=subject,
        field="observed-claims",
        status=FactStatus.UNKNOWN,
        value=None,
        confidence_class=ConfidenceClass.UNKNOWN,
        claim_ids=(),
        evidence_refs=(),
        limiting_factors=(LimitingFactor.MISSING_EVIDENCE.value,),
        why="no-claims-present",
        as_of_valid_time=as_of,
    )


def _group_succession(
    bucket: Sequence[AssessableClaim],
    windows: dict[str, ValidityWindowInput],
) -> bool:
    if len(bucket) < 2:
        return False
    ordered = sorted(bucket, key=lambda item: item.claim_id)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            left_window = windows.get(left.claim_id)
            right_window = windows.get(right.claim_id)
            if left_window is None or right_window is None:
                continue
            if (
                windows_relation(
                    left_window.valid_from,
                    left_window.valid_to,
                    right_window.valid_from,
                    right_window.valid_to,
                )
                == "succession"
            ):
                return True
    return False


def _best_confidence(items: Sequence[EvidenceAssessment]) -> ConfidenceClass:
    order = {
        ConfidenceClass.HIGH: 3,
        ConfidenceClass.MEDIUM: 2,
        ConfidenceClass.LOW: 1,
        ConfidenceClass.UNKNOWN: 0,
    }
    return max(items, key=lambda item: order[item.confidence_class]).confidence_class


def _attention(
    facts: tuple[DerivedFact, ...],
    candidates: tuple[ContradictionCandidate, ...],
    ctx: StateContext,
) -> tuple[AttentionCandidate, ...]:
    rows: list[AttentionCandidate] = []
    for fact in facts:
        if fact.status is FactStatus.CONTESTED:
            related = tuple(
                item.candidate_id
                for item in candidates
                if item.subject == fact.subject and item.field == fact.field
            )
            rows.append(
                _attention_row(
                    AttentionKind.CONTRADICTION,
                    "open-contradiction-candidates-need-human-review",
                    (fact.fact_id,),
                    related,
                )
            )
        if fact.status is FactStatus.STALE:
            rows.append(
                _attention_row(
                    AttentionKind.STALE,
                    "stale-evidence-is-not-invalid",
                    (fact.fact_id,),
                    (),
                )
            )
        if fact.status is FactStatus.UNKNOWN:
            rows.append(
                _attention_row(
                    AttentionKind.UNKNOWN,
                    fact.why,
                    (fact.fact_id,),
                    (),
                )
            )
        if LimitingFactor.MISSING_SOURCE.value in fact.limiting_factors:
            rows.append(
                _attention_row(
                    AttentionKind.SOURCE_HEALTH,
                    "declared-source-missing-or-deleted",
                    (fact.fact_id,),
                    (),
                )
            )
        if LimitingFactor.MISSING_PROVENANCE.value in fact.limiting_factors:
            rows.append(
                _attention_row(
                    AttentionKind.EVIDENCE_GAP,
                    "missing-provenance",
                    (fact.fact_id,),
                    (),
                )
            )
    if ctx.identity_ambiguous_claim_ids:
        related_facts = tuple(
            item.fact_id
            for item in facts
            if any(claim_id in ctx.identity_ambiguous_claim_ids for claim_id in item.claim_ids)
        )
        related_candidates = tuple(
            item.candidate_id
            for item in candidates
            if item.candidate_class is ContradictionClass.IDENTITY_AMBIGUITY
        )
        rows.append(
            _attention_row(
                AttentionKind.IDENTITY_AMBIGUITY,
                "caller-marked-identity-ambiguity",
                related_facts,
                related_candidates,
            )
        )
    rows.sort(key=lambda item: item.attention_id)
    return tuple(rows)


def _attention_row(
    kind: AttentionKind,
    reason: str,
    fact_ids: tuple[str, ...],
    candidate_ids: tuple[str, ...],
) -> AttentionCandidate:
    material = "|".join((kind.value, reason, ",".join(fact_ids), ",".join(candidate_ids)))
    return AttentionCandidate(
        attention_id="attn-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        kind=kind,
        reason=reason,
        related_fact_ids=fact_ids,
        related_candidate_ids=candidate_ids,
    )


def _unique_refs(items: Sequence[EvidenceAssessment]) -> tuple[EvidenceRef, ...]:
    seen: set[tuple[str, str, str, str, str]] = set()
    refs: list[EvidenceRef] = []
    for assessment in items:
        for ref in assessment.supporting_evidence + assessment.contradicting_evidence:
            key = (
                ref.claim_id or "",
                ref.source_id or "",
                ref.resource or "",
                ref.sha256 or "",
                ref.role.value,
            )
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    refs.sort(key=lambda item: (item.claim_id or "", item.source_id or "", item.resource or ""))
    return tuple(refs)


def _fact_id(project_id: str, subject: str, field: str) -> str:
    material = "|".join((project_id, subject, field))
    return "fact-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _reject_unsupported_status_inference(state: DerivedProjectState) -> None:
    """Fail closed if synthesis invents health/roadmap language."""
    blobs = [state.truth_boundary, state.authority_note]
    for fact in (
        state.known_facts
        + state.unknown_facts
        + state.stale_facts
        + state.contested_facts
        + state.recently_changed_facts
    ):
        blobs.append(fact.why)
        blobs.append(fact.status.value)
    for item in state.attention_candidates:
        blobs.append(item.reason)
    text = " ".join(blobs).lower()
    for token in _FORBIDDEN_STATUS_INFERENCE:
        if token in text:
            raise ValueError(f"unsupported-status-inference:{token}")
