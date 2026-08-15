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


def find_contradiction_candidates(
    claims: Sequence[Claim | AssessableClaim],
    context: ContradictionContext | None = None,
) -> tuple[ContradictionCandidate, ...]:
    """Detect explainable candidates. Input order does not change semantics."""
    ctx = context if context is not None else ContradictionContext()
    items = coerce_claims(claims)
    windows = {item.claim_id: item for item in ctx.validity_windows}
    groups: dict[str, list[AssessableClaim]] = defaultdict(list)
    for item in items:
        groups[group_key(item.project_id, item.subject, item.field)].append(item)

    candidates: list[ContradictionCandidate] = []
    for bucket in groups.values():
        bucket.sort(key=lambda item: item.claim_id)
        for index, left in enumerate(bucket):
            for right in bucket[index + 1 :]:
                found = _pair_candidate(left, right, ctx, windows)
                if found is not None:
                    candidates.append(found)
    candidates.sort(key=lambda item: item.candidate_id)
    return tuple(candidates)


def _pair_candidate(
    left: AssessableClaim,
    right: AssessableClaim,
    ctx: ContradictionContext,
    windows: dict[str, ValidityWindowInput],
) -> ContradictionCandidate | None:
    if left.project_id != right.project_id:
        return None
    if is_unknown_value(left.value, left.normalized_text) or is_unknown_value(
        right.value, right.normalized_text
    ):
        return None
    if left.confidence is ConfidenceState.UNKNOWN or right.confidence is ConfidenceState.UNKNOWN:
        return None
    if normalize_value(left.value, left.normalized_text) == normalize_value(
        right.value, right.normalized_text
    ):
        return None
    if (
        left.authority_domain
        and right.authority_domain
        and left.authority_domain != right.authority_domain
    ):
        return None

    left_window = windows.get(left.claim_id)
    right_window = windows.get(right.claim_id)
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
        return None

    left_lineage = _claim_lineage(left)
    right_lineage = _claim_lineage(right)
    same_lineage = (
        left_lineage != "unknown-identity"
        and left_lineage == right_lineage
    )
    source_relationship = "same-lineage" if same_lineage else "distinct-or-unknown-lineage"
    authority_relationship = _authority_relationship(left, right)
    missing_source = _missing_source(left, right, ctx.sources)
    identity_ambiguous = (
        left.claim_id in ctx.identity_ambiguous_claim_ids
        or right.claim_id in ctx.identity_ambiguous_claim_ids
    )

    uncertainty: list[str] = []
    if temporal is TemporalRelationship.UNKNOWN:
        uncertainty.append("temporal-relationship-unknown")
    if not same_lineage and (
        left_lineage == "unknown-identity" or right_lineage == "unknown-identity"
    ):
        uncertainty.append("source-lineage-unknown")
    if missing_source:
        uncertainty.append("source-record-missing-or-deleted")
    if left.authority is None or right.authority is None:
        uncertainty.append("authority-incomplete")

    candidate_class, reason = _classify_pair(
        temporal=temporal,
        same_lineage=same_lineage,
        identity_ambiguous=identity_ambiguous,
        left=left,
        right=right,
        authority_relationship=authority_relationship,
    )
    severity = _severity(candidate_class, temporal, left, right)
    evidence = _pair_evidence(left, right)
    first, second = sorted((left.claim_id, right.claim_id))
    material = "|".join(
        (
            left.project_id or "",
            left.subject,
            left.field,
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
    return ContradictionCandidate(
        candidate_id=candidate_id,
        candidate_class=candidate_class,
        claim_a_id=first,
        claim_b_id=second,
        project_id=left.project_id,
        subject=left.subject,
        field=left.field,
        temporal_relationship=temporal,
        authority_relationship=authority_relationship,
        source_relationship=source_relationship,
        severity_class=severity,
        reason=reason,
        supporting_evidence=evidence,
        uncertainty=tuple(sorted(set(uncertainty))),
        recommended_human_review_reason=review,
        truth_boundary=TRUTH_BOUNDARY_CONTRADICTION,
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


def _missing_source(
    left: AssessableClaim,
    right: AssessableClaim,
    sources: tuple[SourceObservation, ...] | None,
) -> bool:
    if sources is None:
        return False
    index = {item.source_id: item for item in sources}
    for claim in (left, right):
        if not claim.provenance:
            return True
        for ref in claim.provenance:
            observed = index.get(ref.source_id)
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


def _pair_evidence(left: AssessableClaim, right: AssessableClaim) -> tuple[EvidenceRef, ...]:
    refs: list[EvidenceRef] = []
    for claim in (left, right):
        if claim.provenance:
            for item in claim.provenance:
                refs.append(
                    EvidenceRef(
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
                EvidenceRef(
                    source_id=None,
                    source_lineage_id=claim.source_lineage_id,
                    resource=None,
                    sha256=None,
                    claim_id=claim.claim_id,
                    role=EvidenceRole.UNKNOWN,
                )
            )
    refs.sort(key=lambda item: (item.claim_id or "", item.source_id or "", item.resource or ""))
    return tuple(refs)
