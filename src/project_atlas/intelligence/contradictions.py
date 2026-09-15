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
from dataclasses import field as dc_field
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

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
_GENERATED = {"by": GENERATED_BY}
_EMPTY: tuple[str, ...] = ()
_UNCERTAINTY_TEMPORAL: tuple[str, ...] = ("temporal-relationship-unknown",)
_UNCERTAINTY_TEMPORAL_LINEAGE: tuple[str, ...] = (
    "source-lineage-unknown",
    "temporal-relationship-unknown",
)
_SOURCE_SAME = "same-lineage"
_SOURCE_DISTINCT = "distinct-or-unknown-lineage"


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


@dataclass(frozen=True, slots=True)
class ContradictionCandidate:
    """Explainable contradiction candidate. Not a resolution.

    Compact frozen record. Same fields and ids as the pydantic form; not
    authority and not a proven falsehood.
    """

    candidate_id: str
    candidate_class: ContradictionClass
    claim_a_id: str
    claim_b_id: str
    project_id: str | None
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
    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-INTEL-002"] = "AS-2.0-INTEL-002"
    truth_boundary: str = TRUTH_BOUNDARY_CONTRADICTION
    generated: dict[str, str] = dc_field(default_factory=lambda: _GENERATED)
    authority_note: Literal["candidate-not-resolution"] = "candidate-not-resolution"

    def model_dump(self) -> dict[str, object]:
        """Pydantic-compatible dump. Nested evidence becomes dicts."""
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "candidate_id": self.candidate_id,
            "candidate_class": self.candidate_class,
            "claim_a_id": self.claim_a_id,
            "claim_b_id": self.claim_b_id,
            "project_id": self.project_id,
            "subject": self.subject,
            "field": self.field,
            "temporal_relationship": self.temporal_relationship,
            "authority_relationship": self.authority_relationship,
            "source_relationship": self.source_relationship,
            "severity_class": self.severity_class,
            "reason": self.reason,
            "supporting_evidence": tuple(item.model_dump() for item in self.supporting_evidence),
            "uncertainty": self.uncertainty,
            "recommended_human_review_reason": self.recommended_human_review_reason,
            "truth_boundary": self.truth_boundary,
            "generated": self.generated,
            "authority_note": self.authority_note,
        }

    def model_dump_json(self) -> str:
        """JSON dump using enum values. Not an authority document."""
        import json

        payload = self.model_dump()
        payload["candidate_class"] = self.candidate_class.value
        payload["temporal_relationship"] = self.temporal_relationship.value
        payload["severity_class"] = self.severity_class.value
        return json.dumps(payload, sort_keys=True)


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
    claim_id: str
    project_id: str | None
    subject: str
    field: str
    norm: str
    unknown: bool
    lineage: str
    lineage_unknown: bool
    evidence: tuple[EvidenceRef, ...]
    evidence_key: tuple[str, str, str]
    authority: AuthorityLevel | None
    authority_level: str
    authority_strong: bool
    authority_conflicting: bool
    claim_type: str | None
    authority_domain: str | None
    window_from: str | None
    window_to: str | None
    missing_source: bool


def find_contradiction_candidates(
    claims: Sequence[Claim | AssessableClaim],
    context: ContradictionContext | None = None,
) -> tuple[ContradictionCandidate, ...]:
    """Detect explainable candidates. Input order does not change semantics."""
    candidates, _stats = find_contradiction_candidates_report(claims, context)
    return candidates


_REVIEW_BY_CLASS = {
    item: (
        f"human-review-required:{item.value};"
        "auto-resolve-forbidden;candidate-is-not-falsehood"
    )
    for item in ContradictionClass
}


def find_contradiction_candidates_report(
    claims: Sequence[Claim | AssessableClaim],
    context: ContradictionContext | None = None,
    *,
    materialize: bool = True,
) -> tuple[tuple[ContradictionCandidate, ...], PairingStats]:
    """Same candidates as :func:`find_contradiction_candidates`, plus pairing stats.

    ``materialize=False`` still evaluates every qualifying pair for counts
    but does not allocate candidate objects. Semantics of which pairs
    qualify do not change.
    """
    ctx = context if context is not None else ContradictionContext()
    items = coerce_claims(claims)
    windows = {item.claim_id: item for item in ctx.validity_windows}
    source_index = (
        {item.source_id: item for item in ctx.sources} if ctx.sources is not None else None
    )
    ambiguous = set(ctx.identity_ambiguous_claim_ids)
    prepared = [_prepare(item, windows, source_index) for item in items]
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
    counted = 0
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
                        found, temporal_skip, qualifies = _pair_prepared(
                            left,
                            right,
                            ambiguous,
                            materialize=materialize,
                        )
                        if temporal_skip:
                            skipped_temporal += 1
                        elif qualifies and found is not None:
                            candidates.append(found)
                        elif qualifies:
                            counted += 1
    candidates.sort(key=lambda item: item.candidate_id)
    stats = PairingStats(
        claim_count=len(items),
        group_count=len(groups),
        pair_evaluations=pair_evaluations,
        candidate_count=len(candidates) + counted,
        skipped_same_value=skipped_same_value,
        skipped_unknown=skipped_unknown,
        skipped_temporal=skipped_temporal,
    )
    return tuple(candidates), stats


def _prepare(
    claim: AssessableClaim,
    windows: dict[str, ValidityWindowInput],
    source_index: dict[str, SourceObservation] | None,
) -> _PreparedClaim:
    unknown = is_unknown_value(claim.value, claim.normalized_text) or (
        claim.confidence is ConfidenceState.UNKNOWN
    )
    lineage = _claim_lineage(claim)
    evidence = _claim_evidence(claim)
    window = windows.get(claim.claim_id)
    authority = claim.authority
    return _PreparedClaim(
        claim=claim,
        claim_id=claim.claim_id,
        project_id=claim.project_id,
        subject=claim.subject,
        field=claim.field,
        norm=normalize_value(claim.value, claim.normalized_text),
        unknown=unknown,
        lineage=lineage,
        lineage_unknown=lineage == "unknown-identity",
        evidence=evidence,
        evidence_key=_evidence_sort(evidence[0]) if evidence else ("", "", ""),
        authority=authority,
        authority_level=authority.value if authority is not None else "unknown",
        authority_strong=authority in _STRONG_AUTHORITY,
        authority_conflicting=authority is AuthorityLevel.CONFLICTING,
        claim_type=claim.claim_type,
        authority_domain=claim.authority_domain,
        window_from=window.valid_from if window else None,
        window_to=window.valid_to if window else None,
        missing_source=_claim_missing_source(claim, source_index),
    )


def _pair_prepared(
    left: _PreparedClaim,
    right: _PreparedClaim,
    ambiguous: set[str],
    *,
    materialize: bool = True,
) -> tuple[ContradictionCandidate | None, bool, bool]:
    if left.project_id != right.project_id:
        return None, False, False
    if (
        left.authority_domain
        and right.authority_domain
        and left.authority_domain != right.authority_domain
    ):
        return None, False, False

    if left.window_from is None or right.window_from is None:
        temporal = TemporalRelationship.UNKNOWN
    else:
        try:
            temporal = TemporalRelationship(
                windows_relation(
                    left.window_from,
                    left.window_to,
                    right.window_from,
                    right.window_to,
                )
            )
        except IntelligenceTimeError:
            temporal = TemporalRelationship.UNKNOWN
    if temporal in {TemporalRelationship.SUCCESSION, TemporalRelationship.NON_OVERLAPPING}:
        return None, True, False
    if not materialize:
        return None, False, True

    same_lineage = not left.lineage_unknown and left.lineage == right.lineage
    source_relationship = _SOURCE_SAME if same_lineage else _SOURCE_DISTINCT
    authority_relationship = _authority_rel(left.authority_level, right.authority_level)
    missing_source = left.missing_source or right.missing_source
    identity_ambiguous = left.claim_id in ambiguous or right.claim_id in ambiguous
    uncertainty = _uncertainty(
        temporal is TemporalRelationship.UNKNOWN,
        (not same_lineage) and (left.lineage_unknown or right.lineage_unknown),
        missing_source,
        left.authority is None or right.authority is None,
    )
    candidate_class, reason = _classify_prepared(
        temporal=temporal,
        same_lineage=same_lineage,
        identity_ambiguous=identity_ambiguous,
        left=left,
        right=right,
        authority_relationship=authority_relationship,
    )
    severity = _severity_prepared(candidate_class, temporal, left, right)
    evidence = _merge_evidence(left, right)
    first, second = (left.claim_id, right.claim_id)
    if second < first:
        first, second = second, first
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
    candidate_id = "cc-" + hashlib.sha256(
        material.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:20]
    return (
        ContradictionCandidate(
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
            uncertainty=uncertainty,
            recommended_human_review_reason=_REVIEW_BY_CLASS[candidate_class],
        ),
        False,
        True,
    )


def _merge_evidence(left: _PreparedClaim, right: _PreparedClaim) -> tuple[EvidenceRef, ...]:
    left_ev = left.evidence
    right_ev = right.evidence
    if not left_ev:
        return right_ev
    if not right_ev:
        return left_ev
    if len(left_ev) == 1 and len(right_ev) == 1:
        if left.evidence_key <= right.evidence_key:
            return (left_ev[0], right_ev[0])
        return (right_ev[0], left_ev[0])
    merged: list[EvidenceRef] = []
    left_index = 0
    right_index = 0
    while left_index < len(left_ev) and right_index < len(right_ev):
        left_key = _evidence_sort(left_ev[left_index])
        right_key = _evidence_sort(right_ev[right_index])
        if left_key <= right_key:
            merged.append(left_ev[left_index])
            left_index += 1
        else:
            merged.append(right_ev[right_index])
            right_index += 1
    if left_index < len(left_ev):
        merged.extend(left_ev[left_index:])
    if right_index < len(right_ev):
        merged.extend(right_ev[right_index:])
    return tuple(merged)


def _uncertainty(
    temporal_unknown: bool,
    lineage_unknown: bool,
    missing_source: bool,
    authority_incomplete: bool,
) -> tuple[str, ...]:
    if not missing_source and not authority_incomplete:
        if temporal_unknown and lineage_unknown:
            return _UNCERTAINTY_TEMPORAL_LINEAGE
        if temporal_unknown:
            return _UNCERTAINTY_TEMPORAL
        if lineage_unknown:
            return ("source-lineage-unknown",)
        return _EMPTY
    flags: list[str] = []
    if temporal_unknown:
        flags.append("temporal-relationship-unknown")
    if lineage_unknown:
        flags.append("source-lineage-unknown")
    if missing_source:
        flags.append("source-record-missing-or-deleted")
    if authority_incomplete:
        flags.append("authority-incomplete")
    flags.sort()
    return tuple(flags)


_AUTH_REL: dict[tuple[str, str], str] = {}


def _authority_rel(left_level: str, right_level: str) -> str:
    key = (left_level, right_level)
    cached = _AUTH_REL.get(key)
    if cached is not None:
        return cached
    if left_level == right_level:
        cached = f"same:{left_level}"
    else:
        levels = tuple(sorted((left_level, right_level)))
        cached = f"divergent:{levels[0]}|{levels[1]}"
    _AUTH_REL[key] = cached
    return cached


def _claim_missing_source(
    claim: AssessableClaim,
    source_index: dict[str, SourceObservation] | None,
) -> bool:
    if source_index is None:
        return False
    if not claim.provenance:
        return True
    for ref in claim.provenance:
        observed = source_index.get(ref.source_id)
        if observed is None or observed.deleted or not observed.present:
            return True
    return False


def _claim_lineage(claim: AssessableClaim) -> str:
    if claim.source_lineage_id:
        return lineage_key(claim.source_lineage_id, None)
    if claim.provenance:
        first = claim.provenance[0]
        return lineage_key(first.source_lineage_id, first.source_id)
    return lineage_key(None, None)


def _classify_prepared(
    *,
    temporal: TemporalRelationship,
    same_lineage: bool,
    identity_ambiguous: bool,
    left: _PreparedClaim,
    right: _PreparedClaim,
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
        left.authority_strong or right.authority_strong
    ):
        return (
            ContradictionClass.AUTHORITY_CONFLICT,
            "incompatible-values-with-divergent-authority",
        )
    if left.authority_conflicting or right.authority_conflicting:
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


def _severity_prepared(
    candidate_class: ContradictionClass,
    temporal: TemporalRelationship,
    left: _PreparedClaim,
    right: _PreparedClaim,
) -> SeverityClass:
    if candidate_class in {
        ContradictionClass.IDENTITY_AMBIGUITY,
        ContradictionClass.UNKNOWN_CONFLICT,
    }:
        return SeverityClass.UNKNOWN
    both_strong = left.authority_strong and right.authority_strong
    one_strong = left.authority_strong != right.authority_strong
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
