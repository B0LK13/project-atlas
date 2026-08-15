"""AS-2.0-INTEL-002 — contradiction candidate intelligence.

Read-only. A candidate is not proof that either claim is false.
Never auto-resolves, deletes, or writes canonical truth.

Pair comparison is grouped by project + subject + field so the engine
does not do whole-vault O(N²) comparison.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import AuthorityLevel, Claim, ConfidenceState
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_CONTRADICTION
from project_atlas.intelligence.normalize import (
    group_key,
    is_unknown_value,
    lineage_key,
    normalize_value,
)
from project_atlas.intelligence.timewin import IntelligenceTimeError, windows_relation
from project_atlas.intelligence.types import (
    AssessableClaim,
    EvidenceAssessment,
    EvidenceRef,
    EvidenceRole,
    SourceObservation,
    ValidityWindowInput,
    coerce_claims,
)

_STRONG_AUTHORITY = frozenset(
    {
        AuthorityLevel.PRIMARY,
        AuthorityLevel.MAINTAINED,
        AuthorityLevel.VALIDATED_EXECUTION,
    }
)


class ContradictionClass(StrEnum):
    VALUE_CONFLICT = "value-conflict"
    TEMPORAL_CONFLICT = "temporal-conflict"
    AUTHORITY_CONFLICT = "authority-conflict"
    SOURCE_DIVERGENCE = "source-divergence"
    SCOPE_CONFLICT = "scope-conflict"
    IDENTITY_AMBIGUITY = "identity-ambiguity"
    UNKNOWN_CONFLICT = "unknown-conflict"


class TemporalRelationship(StrEnum):
    OVERLAPPING = "overlapping"
    NON_OVERLAPPING = "non-overlapping"
    SUCCESSION = "succession"
    UNKNOWN = "unknown"


class SeverityClass(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ContradictionContext(BaseModel):
    """Read-only pairing context. Missing windows stay temporally unknown."""

    model_config = ConfigDict(extra="forbid")

    as_of_valid_time: str | None = None
    validity_windows: tuple[ValidityWindowInput, ...] = ()
    sources: tuple[SourceObservation, ...] | None = None
    identity_ambiguous_claim_ids: tuple[str, ...] = ()
    assessments: tuple[EvidenceAssessment, ...] = ()


class ContradictionCandidate(BaseModel):
    """Explainable contradiction candidate. Not a resolution."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-INTEL-002"] = "AS-2.0-INTEL-002"
    candidate_id: str
    candidate_class: ContradictionClass
    claim_a_id: str
    claim_b_id: str
    project_id: str | None = None
    subject: str
    field: str
    temporal_relationship: TemporalRelationship
    authority_relationship: str
    source_relationship: str
    severity_class: SeverityClass
    reason: str
    supporting_evidence: tuple[EvidenceRef, ...]
    uncertainty: tuple[str, ...]
    recommended_human_review_reason: str
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["candidate-not-resolution"] = "candidate-not-resolution"


@dataclass(frozen=True, slots=True)
class PairingStats:
    """Explainable pairing cost. Not a quality score."""

    claim_count: int
    group_count: int
    pair_evaluations: int
    candidate_count: int
    skipped_same_value: int
    skipped_unknown: int
    skipped_temporal: int


@dataclass(frozen=True, slots=True)
class _PreparedClaim:
    claim: AssessableClaim
    norm: str
    unknown: bool
    lineage: str
    evidence: tuple[EvidenceRef, ...]


def find_contradiction_candidates(
    claims: Sequence[Claim | AssessableClaim],
    context: ContradictionContext | None = None,
) -> tuple[ContradictionCandidate, ...]:
    """Detect explainable candidates. Input order does not change semantics."""
    candidates, _stats = find_contradiction_candidates_report(claims, context)
    return candidates


def find_contradiction_candidates_report(
    claims: Sequence[Claim | AssessableClaim],
    context: ContradictionContext | None = None,
) -> tuple[tuple[ContradictionCandidate, ...], PairingStats]:
    """Same candidates as :func:`find_contradiction_candidates`, plus pairing stats."""
    ctx = context if context is not None else ContradictionContext()
    items = coerce_claims(claims)
    windows = {item.claim_id: item for item in ctx.validity_windows}
    source_index = (
        {item.source_id: item for item in ctx.sources} if ctx.sources is not None else None
    )
    ambiguous = set(ctx.identity_ambiguous_claim_ids)
    prepared = [_prepare(item) for item in items]
    groups: dict[str, list[_PreparedClaim]] = defaultdict(list)
    skipped_unknown = 0
    for item in prepared:
        if item.unknown:
            skipped_unknown += 1
            continue
        groups[group_key(item.claim.project_id, item.claim.subject, item.claim.field)].append(item)

    candidates: list[ContradictionCandidate] = []
    pair_evaluations = 0
    skipped_same_value = 0
    skipped_temporal = 0
    for bucket in groups.values():
        bucket.sort(key=lambda item: item.claim.claim_id)
        by_value: dict[str, list[_PreparedClaim]] = defaultdict(list)
        for item in bucket:
            by_value[item.norm].append(item)
        value_keys = sorted(by_value)
        skipped_same_value += sum(len(rows) * (len(rows) - 1) // 2 for rows in by_value.values())
        for left_index, left_key in enumerate(value_keys):
            for right_key in value_keys[left_index + 1 :]:
                left_rows = by_value[left_key]
                right_rows = by_value[right_key]
                for left in left_rows:
                    for right in right_rows:
                        pair_evaluations += 1
                        found, temporal_skip = _pair_prepared(
                            left,
                            right,
                            windows,
                            source_index,
                            ambiguous,
                        )
                        if temporal_skip:
                            skipped_temporal += 1
                        if found is not None:
                            candidates.append(found)
    candidates.sort(key=lambda item: item.candidate_id)
    stats = PairingStats(
        claim_count=len(items),
        group_count=len(groups),
        pair_evaluations=pair_evaluations,
        candidate_count=len(candidates),
        skipped_same_value=skipped_same_value,
        skipped_unknown=skipped_unknown,
        skipped_temporal=skipped_temporal,
    )
    return tuple(candidates), stats


def _prepare(claim: AssessableClaim) -> _PreparedClaim:
    unknown = is_unknown_value(claim.value, claim.normalized_text) or (
        claim.confidence is ConfidenceState.UNKNOWN
    )
    return _PreparedClaim(
        claim=claim,
        norm=normalize_value(claim.value, claim.normalized_text),
        unknown=unknown,
        lineage=_claim_lineage(claim),
        evidence=_claim_evidence(claim),
    )


def _pair_prepared(
    left: _PreparedClaim,
    right: _PreparedClaim,
    windows: dict[str, ValidityWindowInput],
    source_index: dict[str, SourceObservation] | None,
    ambiguous: set[str],
) -> tuple[ContradictionCandidate | None, bool]:
    left_claim = left.claim
    right_claim = right.claim
    if left_claim.project_id != right_claim.project_id:
        return None, False
    if (
        left_claim.authority_domain
        and right_claim.authority_domain
        and left_claim.authority_domain != right_claim.authority_domain
    ):
        return None, False

    left_window = windows.get(left_claim.claim_id)
    right_window = windows.get(right_claim.claim_id)
    try:
        relation_raw = windows_relation(
            left_window.valid_from if left_window else None,
            left_window.valid_to if left_window else None,
            right_window.valid_from if right_window else None,
            right_window.valid_to if right_window else None,
        )
    except IntelligenceTimeError:
        relation_raw = "unknown"
    temporal = TemporalRelationship(relation_raw)
    if temporal in {TemporalRelationship.SUCCESSION, TemporalRelationship.NON_OVERLAPPING}:
        return None, True

    same_lineage = (
        left.lineage != "unknown-identity" and left.lineage == right.lineage
    )
    source_relationship = "same-lineage" if same_lineage else "distinct-or-unknown-lineage"
    authority_relationship = _authority_relationship(left_claim, right_claim)
    missing_source = _missing_source_index(left_claim, right_claim, source_index)
    identity_ambiguous = left_claim.claim_id in ambiguous or right_claim.claim_id in ambiguous

    uncertainty: list[str] = []
    if temporal is TemporalRelationship.UNKNOWN:
        uncertainty.append("temporal-relationship-unknown")
    if not same_lineage and (
        left.lineage == "unknown-identity" or right.lineage == "unknown-identity"
    ):
        uncertainty.append("source-lineage-unknown")
    if missing_source:
        uncertainty.append("source-record-missing-or-deleted")
    if left_claim.authority is None or right_claim.authority is None:
        uncertainty.append("authority-incomplete")

    candidate_class, reason = _classify_pair(
        temporal=temporal,
        same_lineage=same_lineage,
        identity_ambiguous=identity_ambiguous,
        left=left_claim,
        right=right_claim,
        authority_relationship=authority_relationship,
    )
    severity = _severity(candidate_class, temporal, left_claim, right_claim)
    evidence = tuple(sorted(left.evidence + right.evidence, key=_evidence_sort))
    first, second = sorted((left_claim.claim_id, right_claim.claim_id))
    material = "|".join(
        (
            left_claim.project_id or "",
            left_claim.subject,
            left_claim.field,
            first,
            second,
            candidate_class.value,
        )
    )
    candidate_id = "cc-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]
    review = (
        f"human-review-required:{candidate_class.value};"
        "auto-resolve-forbidden;candidate-is-not-falsehood"
    )
    return (
        ContradictionCandidate.model_construct(
            schema_version=1,
            package_id="AS-2.0-INTEL-002",
            candidate_id=candidate_id,
            candidate_class=candidate_class,
            claim_a_id=first,
            claim_b_id=second,
            project_id=left_claim.project_id,
            subject=left_claim.subject,
            field=left_claim.field,
            temporal_relationship=temporal,
            authority_relationship=authority_relationship,
            source_relationship=source_relationship,
            severity_class=severity,
            reason=reason,
            supporting_evidence=evidence,
            uncertainty=tuple(sorted(set(uncertainty))),
            recommended_human_review_reason=review,
            truth_boundary=TRUTH_BOUNDARY_CONTRADICTION,
            generated={"by": GENERATED_BY},
            authority_note="candidate-not-resolution",
        ),
        False,
    )


def _claim_lineage(claim: AssessableClaim) -> str:
    if claim.source_lineage_id:
        return lineage_key(claim.source_lineage_id, None)
    if claim.provenance:
        first = claim.provenance[0]
        return lineage_key(first.source_lineage_id, first.source_id)
    return lineage_key(None, None)


def _authority_relationship(left: AssessableClaim, right: AssessableClaim) -> str:
    left_level = left.authority.value if left.authority is not None else "unknown"
    right_level = right.authority.value if right.authority is not None else "unknown"
    levels = tuple(sorted((left_level, right_level)))
    if left_level == right_level:
        return f"same:{left_level}"
    return f"divergent:{levels[0]}|{levels[1]}"


def _missing_source_index(
    left: AssessableClaim,
    right: AssessableClaim,
    source_index: dict[str, SourceObservation] | None,
) -> bool:
    if source_index is None:
        return False
    for claim in (left, right):
        if not claim.provenance:
            return True
        for ref in claim.provenance:
            observed = source_index.get(ref.source_id)
            if observed is None or observed.deleted or not observed.present:
                return True
    return False


def _classify_pair(
    *,
    temporal: TemporalRelationship,
    same_lineage: bool,
    identity_ambiguous: bool,
    left: AssessableClaim,
    right: AssessableClaim,
    authority_relationship: str,
) -> tuple[ContradictionClass, str]:
    if identity_ambiguous:
        return (
            ContradictionClass.IDENTITY_AMBIGUITY,
            "values-differ-and-subject-or-lineage-identity-is-ambiguous",
        )
    if same_lineage:
        return (
            ContradictionClass.SOURCE_DIVERGENCE,
            "same-source-lineage-asserts-incompatible-values",
        )
    if temporal is TemporalRelationship.OVERLAPPING:
        return (
            ContradictionClass.TEMPORAL_CONFLICT,
            "incompatible-values-with-overlapping-valid-time",
        )
    if left.claim_type and right.claim_type and left.claim_type != right.claim_type:
        return (
            ContradictionClass.SCOPE_CONFLICT,
            "incompatible-values-under-different-claim-types",
        )
    if authority_relationship.startswith("divergent:") and (
        left.authority in _STRONG_AUTHORITY or right.authority in _STRONG_AUTHORITY
    ):
        return (
            ContradictionClass.AUTHORITY_CONFLICT,
            "incompatible-values-with-divergent-authority",
        )
    if (
        left.authority is AuthorityLevel.CONFLICTING
        or right.authority is AuthorityLevel.CONFLICTING
    ):
        return (
            ContradictionClass.AUTHORITY_CONFLICT,
            "incompatible-values-with-conflicting-authority-mark",
        )
    if temporal is TemporalRelationship.UNKNOWN and (
        left.authority is None or right.authority is None
    ):
        return (
            ContradictionClass.UNKNOWN_CONFLICT,
            "values-differ-but-temporal-and-authority-evidence-are-incomplete",
        )
    return (
        ContradictionClass.VALUE_CONFLICT,
        "incompatible-values-for-same-subject-and-field",
    )


def _severity(
    candidate_class: ContradictionClass,
    temporal: TemporalRelationship,
    left: AssessableClaim,
    right: AssessableClaim,
) -> SeverityClass:
    if candidate_class in {
        ContradictionClass.IDENTITY_AMBIGUITY,
        ContradictionClass.UNKNOWN_CONFLICT,
    }:
        return SeverityClass.UNKNOWN
    both_strong = left.authority in _STRONG_AUTHORITY and right.authority in _STRONG_AUTHORITY
    one_strong = (left.authority in _STRONG_AUTHORITY) != (right.authority in _STRONG_AUTHORITY)
    if temporal is TemporalRelationship.OVERLAPPING and both_strong:
        return SeverityClass.HIGH
    if one_strong:
        return SeverityClass.LOW
    if both_strong:
        return SeverityClass.MEDIUM
    return SeverityClass.LOW


def _claim_evidence(claim: AssessableClaim) -> tuple[EvidenceRef, ...]:
    refs: list[EvidenceRef] = []
    if claim.provenance:
        for item in claim.provenance:
            refs.append(
                EvidenceRef.model_construct(
                    source_id=item.source_id,
                    source_lineage_id=item.source_lineage_id or claim.source_lineage_id,
                    resource=item.resource,
                    sha256=item.sha256,
                    claim_id=claim.claim_id,
                    role=EvidenceRole.CONTRADICTING,
                )
            )
    else:
        refs.append(
            EvidenceRef.model_construct(
                source_id=None,
                source_lineage_id=claim.source_lineage_id,
                resource=None,
                sha256=None,
                claim_id=claim.claim_id,
                role=EvidenceRole.UNKNOWN,
            )
        )
    refs.sort(key=_evidence_sort)
    return tuple(refs)


def _evidence_sort(item: EvidenceRef) -> tuple[str, str, str]:
    return (item.claim_id or "", item.source_id or "", item.resource or "")
