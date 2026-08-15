"""AS-2.0-INTEL-001 — evidence quality and uncertainty core.

Read-only. Deterministic. Never mutates claims, sources, or Layer B.
Never presents a numeric score as objective probability.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from project_atlas.domain import AuthorityLevel, Claim, ClaimLifecycle, ConfidenceState
from project_atlas.intelligence.boundary import TRUTH_BOUNDARY_EVIDENCE
from project_atlas.intelligence.normalize import (
    group_key,
    is_unknown_value,
    lineage_key,
    normalize_value,
)
from project_atlas.intelligence.timewin import IntelligenceTimeError, window_applicability
from project_atlas.intelligence.types import (
    AssessableClaim,
    AssessmentContext,
    ConfidenceClass,
    EvidenceAssessment,
    EvidenceDimensions,
    EvidenceRef,
    EvidenceRole,
    LimitingFactor,
    LineageIntegrity,
    SourceObservation,
    ValidityWindowInput,
    coerce_claim,
    coerce_claims,
)

_STRONG_AUTHORITY = frozenset(
    {
        AuthorityLevel.PRIMARY,
        AuthorityLevel.MAINTAINED,
        AuthorityLevel.VALIDATED_EXECUTION,
    }
)
_WEAK_AUTHORITY = frozenset({AuthorityLevel.GENERATED, AuthorityLevel.INFERRED})
_MISMATCH_AUTHORITY = frozenset({AuthorityLevel.CONFLICTING, AuthorityLevel.REJECTED})
_UNSTABLE_LIFECYCLE = frozenset({ClaimLifecycle.REJECTED, ClaimLifecycle.REMOVED_SOURCE})

_UNKNOWN_FORCING = frozenset(
    {
        LimitingFactor.MISSING_PROVENANCE,
        LimitingFactor.UNKNOWN_CLAIM,
        LimitingFactor.UNSUPPORTED_CLAIM,
        LimitingFactor.TEMPORAL_NOT_YET_VALID,
        LimitingFactor.IDENTITY_AMBIGUOUS,
    }
)
_LOW_FORCING = frozenset(
    {
        LimitingFactor.CONTRADICTORY_EVIDENCE,
        LimitingFactor.TEMPORAL_STALE,
        LimitingFactor.AUTHORITY_MISMATCH,
        LimitingFactor.AUTHORITY_DISAGREEMENT,
        LimitingFactor.LINEAGE_INTEGRITY_BROKEN,
        LimitingFactor.MISSING_SOURCE,
        LimitingFactor.CLAIM_IDENTITY_UNSTABLE,
    }
)


def assess_evidence(
    claim: Claim | AssessableClaim,
    context: AssessmentContext | None = None,
) -> EvidenceAssessment:
    """Derive an explainable evidence assessment. Does not mutate ``claim``."""
    ctx = context if context is not None else AssessmentContext()
    target = coerce_claim(claim)
    peers = _same_group_peers(target, ctx.peer_claims)
    window = _window_for(target.claim_id, ctx.validity_windows)
    source_index = _source_index(ctx.sources)

    observations = _collect_observations(target, source_index)
    supporting, contradicting, contradicting_peers = _evidence_refs(target, peers)
    factors, reasons, unknown, dimensions = _analyze(
        target,
        ctx,
        window,
        observations,
        source_index,
        peers,
        contradicting_peers,
        supporting,
    )
    confidence = _classify(target, factors, dimensions)
    evaluation_context: Literal["as-of-valid-time", "unspecified-valid-time"] = (
        "as-of-valid-time" if ctx.as_of_valid_time is not None else "unspecified-valid-time"
    )
    links = tuple(
        sorted(
            {
                *(ref.resource for ref in supporting if ref.resource),
                *(ref.resource for ref in contradicting if ref.resource),
                *(item.resource for item in target.provenance if item.resource),
            }
        )
    )
    return EvidenceAssessment(
        claim_id=target.claim_id,
        project_id=target.project_id,
        subject=target.subject,
        field=target.field,
        confidence_class=confidence,
        confidence_reasons=tuple(sorted(set(reasons))),
        limiting_factors=tuple(sorted(set(factors), key=lambda item: item.value)),
        supporting_evidence=supporting,
        contradicting_evidence=contradicting,
        unknown_factors=tuple(sorted(set(unknown))),
        as_of_valid_time=ctx.as_of_valid_time,
        evaluation_context=evaluation_context,
        dimensions=dimensions,
        provenance_links=links,
        truth_boundary=TRUTH_BOUNDARY_EVIDENCE,
    )


def assess_evidence_many(
    claims: Sequence[Claim | AssessableClaim],
    context: AssessmentContext | None = None,
) -> tuple[EvidenceAssessment, ...]:
    """Assess many claims. Input order does not change per-claim semantics."""
    ctx = context if context is not None else AssessmentContext()
    coerced = coerce_claims(claims)
    merged_peers = tuple(ctx.peer_claims) + coerced
    inner = AssessmentContext(
        as_of_valid_time=ctx.as_of_valid_time,
        sources=ctx.sources,
        peer_claims=merged_peers,
        validity_windows=ctx.validity_windows,
        identity_ambiguous=ctx.identity_ambiguous,
    )
    assessments = [assess_evidence(item, inner) for item in coerced]
    assessments.sort(key=lambda item: (item.project_id or "", item.claim_id))
    return tuple(assessments)


def _same_group_peers(
    target: AssessableClaim, peers: Sequence[AssessableClaim]
) -> tuple[AssessableClaim, ...]:
    key = group_key(target.project_id, target.subject, target.field)
    return tuple(
        peer
        for peer in peers
        if peer.claim_id != target.claim_id
        and group_key(peer.project_id, peer.subject, peer.field) == key
    )


def _window_for(
    claim_id: str, windows: Sequence[ValidityWindowInput]
) -> ValidityWindowInput | None:
    matches = [item for item in windows if item.claim_id == claim_id]
    if not matches:
        return None
    matches.sort(key=lambda item: (item.valid_from or "", item.valid_to or ""))
    return matches[0]


def _source_index(
    sources: tuple[SourceObservation, ...] | None,
) -> dict[str, SourceObservation] | None:
    if sources is None:
        return None
    index: dict[str, SourceObservation] = {}
    for item in sources:
        index[item.source_id] = item
        if item.source_lineage_id:
            index[f"lineage:{item.source_lineage_id}"] = item
    return index


def _collect_observations(
    target: AssessableClaim,
    source_index: dict[str, SourceObservation] | None,
) -> tuple[SourceObservation, ...]:
    found: list[SourceObservation] = []
    seen: set[str] = set()
    for ref in target.provenance:
        key = ref.source_id
        if key in seen:
            continue
        seen.add(key)
        if source_index is None:
            found.append(
                SourceObservation(
                    source_id=ref.source_id,
                    source_lineage_id=ref.source_lineage_id or target.source_lineage_id,
                    present=True,
                    lineage_integrity=LineageIntegrity.UNKNOWN,
                )
            )
            continue
        observed = source_index.get(key)
        if observed is None and (ref.source_lineage_id or target.source_lineage_id):
            lineage = ref.source_lineage_id or target.source_lineage_id
            observed = source_index.get(f"lineage:{lineage}")
        if observed is not None:
            found.append(observed)
    return tuple(found)


def _evidence_refs(
    target: AssessableClaim,
    peers: Sequence[AssessableClaim],
) -> tuple[tuple[EvidenceRef, ...], tuple[EvidenceRef, ...], tuple[AssessableClaim, ...]]:
    own_value = normalize_value(target.value, target.normalized_text)
    supporting: list[EvidenceRef] = []
    for ref in target.provenance:
        supporting.append(
            EvidenceRef(
                source_id=ref.source_id,
                source_lineage_id=ref.source_lineage_id or target.source_lineage_id,
                resource=ref.resource,
                sha256=ref.sha256,
                claim_id=target.claim_id,
                role=EvidenceRole.SUPPORTING,
            )
        )
    contradicting: list[EvidenceRef] = []
    contradicting_peers: list[AssessableClaim] = []
    for peer in peers:
        if is_unknown_value(peer.value, peer.normalized_text):
            continue
        if normalize_value(peer.value, peer.normalized_text) == own_value:
            for ref in peer.provenance:
                supporting.append(
                    EvidenceRef(
                        source_id=ref.source_id,
                        source_lineage_id=ref.source_lineage_id or peer.source_lineage_id,
                        resource=ref.resource,
                        sha256=ref.sha256,
                        claim_id=peer.claim_id,
                        role=EvidenceRole.SUPPORTING,
                    )
                )
            continue
        contradicting_peers.append(peer)
        if peer.provenance:
            for ref in peer.provenance:
                contradicting.append(
                    EvidenceRef(
                        source_id=ref.source_id,
                        source_lineage_id=ref.source_lineage_id or peer.source_lineage_id,
                        resource=ref.resource,
                        sha256=ref.sha256,
                        claim_id=peer.claim_id,
                        role=EvidenceRole.CONTRADICTING,
                    )
                )
        else:
            contradicting.append(
                EvidenceRef(
                    source_id=None,
                    source_lineage_id=peer.source_lineage_id,
                    resource=None,
                    sha256=None,
                    claim_id=peer.claim_id,
                    role=EvidenceRole.CONTRADICTING,
                )
            )
    supporting.sort(
        key=lambda item: (item.claim_id or "", item.source_id or "", item.resource or "")
    )
    contradicting.sort(
        key=lambda item: (item.claim_id or "", item.source_id or "", item.resource or "")
    )
    return tuple(supporting), tuple(contradicting), tuple(contradicting_peers)


def _analyze(
    target: AssessableClaim,
    ctx: AssessmentContext,
    window: ValidityWindowInput | None,
    observations: tuple[SourceObservation, ...],
    source_index: dict[str, SourceObservation] | None,
    peers: Sequence[AssessableClaim],
    contradicting_peers: Sequence[AssessableClaim],
    supporting: Sequence[EvidenceRef],
) -> tuple[
    list[LimitingFactor],
    list[str],
    list[str],
    EvidenceDimensions,
]:
    factors: list[LimitingFactor] = []
    reasons: list[str] = []
    unknown: list[str] = []

    provenance_complete = bool(target.provenance) and all(
        bool(item.source_id) and bool(item.resource) for item in target.provenance
    )
    if not target.provenance:
        factors.append(LimitingFactor.MISSING_PROVENANCE)
        reasons.append("no-provenance-references")
    elif not provenance_complete or any(item.sha256 is None for item in target.provenance):
        factors.append(LimitingFactor.UNKNOWN_PROVENANCE)
        unknown.append("provenance-hash-or-resource-incomplete")

    if target.confidence is ConfidenceState.UNKNOWN or is_unknown_value(
        target.value, target.normalized_text
    ):
        factors.append(LimitingFactor.UNKNOWN_CLAIM)
        reasons.append("claim-marked-or-valued-unknown")

    if not target.provenance and not target.source_hashes:
        factors.append(LimitingFactor.UNSUPPORTED_CLAIM)
        reasons.append("no-supporting-evidence")
    elif not target.provenance and target.source_hashes:
        factors.append(LimitingFactor.MISSING_EVIDENCE)
        unknown.append("hashes-without-provenance")

    if not target.claim_id or not target.subject or not target.field:
        factors.append(LimitingFactor.CLAIM_IDENTITY_UNSTABLE)
        reasons.append("claim-identity-incomplete")
    claim_identity_stable = LimitingFactor.CLAIM_IDENTITY_UNSTABLE not in factors
    if ctx.identity_ambiguous:
        factors.append(LimitingFactor.IDENTITY_AMBIGUOUS)
        unknown.append("subject-or-lineage-identity-ambiguous")
        claim_identity_stable = False

    lineage_ids: set[str] = set()
    source_ids: set[str] = set()
    for evidence_ref in supporting:
        lineage_ids.add(lineage_key(evidence_ref.source_lineage_id, evidence_ref.source_id))
        if evidence_ref.source_id:
            source_ids.add(evidence_ref.source_id)
    if not lineage_ids and target.source_lineage_id:
        lineage_ids.add(lineage_key(target.source_lineage_id, None))
    if not source_ids:
        for provenance_ref in target.provenance:
            source_ids.add(provenance_ref.source_id)

    repeated_same_source = False
    if target.provenance:
        counted: dict[str, int] = {}
        for provenance_ref in target.provenance:
            key = lineage_key(
                provenance_ref.source_lineage_id or target.source_lineage_id,
                provenance_ref.source_id,
            )
            counted[key] = counted.get(key, 0) + 1
        repeated_same_source = any(count > 1 for count in counted.values())
    for source_row in observations:
        if source_row.observation_count > 1:
            repeated_same_source = True
    if repeated_same_source:
        factors.append(LimitingFactor.REPEATED_SAME_SOURCE)
        reasons.append("repeated-same-source-not-corroboration")

    distinct_lineage_count = len({key for key in lineage_ids if key != "unknown-identity"})
    distinct_source_count = len(source_ids)
    if distinct_lineage_count <= 1 and distinct_source_count <= 1 and target.provenance:
        factors.append(LimitingFactor.SINGLE_SOURCE)
        reasons.append("single-source-observation")
    if distinct_lineage_count == 1 and (
        len(target.provenance) > 1 or len(supporting) > 1 or repeated_same_source
    ):
        factors.append(LimitingFactor.SAME_LINEAGE_ONLY)
        reasons.append("same-lineage-copies-do-not-inflate-confidence")

    if distinct_lineage_count >= 2:
        factors.append(LimitingFactor.INDEPENDENCE_UNKNOWN)
        unknown.append("source-independence-not-knowable-from-path-or-id")
        reasons.append("multiple-lineages-recorded-independence-unknown")

    moved_preserved = any(
        item.path_moved
        and item.lineage_integrity is LineageIntegrity.OK
        and bool(item.source_lineage_id)
        for item in observations
    )
    if moved_preserved:
        reasons.append("durable-lineage-preserved-after-move")

    integrity = LineageIntegrity.UNKNOWN
    if observations:
        if any(item.lineage_integrity is LineageIntegrity.BROKEN for item in observations):
            integrity = LineageIntegrity.BROKEN
            factors.append(LimitingFactor.LINEAGE_INTEGRITY_BROKEN)
            reasons.append("lineage-integrity-broken")
        elif all(item.lineage_integrity is LineageIntegrity.OK for item in observations):
            integrity = LineageIntegrity.OK
        else:
            factors.append(LimitingFactor.LINEAGE_INTEGRITY_UNKNOWN)
            unknown.append("lineage-integrity-not-proven")
    else:
        unknown.append("lineage-integrity-not-observed")

    source_presence: Literal["present", "missing", "unknown"] = "unknown"
    if source_index is None:
        unknown.append("source-inventory-not-declared")
        if target.provenance:
            source_presence = "unknown"
    else:
        missing = False
        present = False
        for provenance_ref in target.provenance:
            observed = source_index.get(provenance_ref.source_id)
            lineage_id = provenance_ref.source_lineage_id or target.source_lineage_id
            if observed is None and lineage_id is not None:
                observed = source_index.get(f"lineage:{lineage_id}")
            if observed is None or observed.deleted or not observed.present:
                missing = True
            else:
                present = True
        if missing:
            factors.append(LimitingFactor.MISSING_SOURCE)
            reasons.append("declared-source-missing-or-deleted")
            source_presence = "present" if present else "missing"
        elif present:
            source_presence = "present"
        elif target.provenance:
            factors.append(LimitingFactor.MISSING_SOURCE)
            reasons.append("declared-source-missing-or-deleted")
            source_presence = "missing"

    authority = target.authority
    authority_class = authority.value if authority is not None else "unknown"
    if authority is None:
        unknown.append("claim-authority-absent")
        factors.append(LimitingFactor.AUTHORITY_WEAK)
    elif authority in _MISMATCH_AUTHORITY:
        factors.append(LimitingFactor.AUTHORITY_MISMATCH)
        reasons.append(f"authority-{authority.value}")
    elif authority is AuthorityLevel.PENDING:
        unknown.append("authority-pending")
        factors.append(LimitingFactor.AUTHORITY_WEAK)
    elif authority in _WEAK_AUTHORITY:
        factors.append(LimitingFactor.AUTHORITY_WEAK)
        reasons.append(f"authority-{authority.value}")
    elif authority in _STRONG_AUTHORITY:
        reasons.append(f"authority-{authority.value}")

    authority_disagreement = False
    if contradicting_peers:
        peer_levels = {peer.authority for peer in contradicting_peers if peer.authority is not None}
        if authority is not None and peer_levels and peer_levels != {authority}:
            authority_disagreement = True
            factors.append(LimitingFactor.AUTHORITY_DISAGREEMENT)
            reasons.append("peer-authority-disagreement")

    if contradicting_peers:
        factors.append(LimitingFactor.CONTRADICTORY_EVIDENCE)
        reasons.append("incompatible-peer-values")

    agreeing_lineages = {
        lineage_key(ref.source_lineage_id, ref.source_id)
        for ref in supporting
        if lineage_key(ref.source_lineage_id, ref.source_id) != "unknown-identity"
    }
    corroborating_lineage_count = len(agreeing_lineages)
    if corroborating_lineage_count >= 2 and not contradicting_peers:
        reasons.append("corroborating-distinct-lineages")

    temporal = "unspecified"
    try:
        temporal = window_applicability(
            as_of_valid_time=ctx.as_of_valid_time,
            valid_from=window.valid_from if window else None,
            valid_to=window.valid_to if window else None,
        )
    except IntelligenceTimeError as exc:
        factors.append(LimitingFactor.TEMPORAL_UNKNOWN)
        unknown.append(str(exc))
        temporal = "unknown"
    if target.lifecycle is ClaimLifecycle.STALE:
        factors.append(LimitingFactor.TEMPORAL_STALE)
        reasons.append("lifecycle-stale")
        if temporal == "unspecified":
            temporal = "stale"
    if temporal == "stale" and LimitingFactor.TEMPORAL_STALE not in factors:
        factors.append(LimitingFactor.TEMPORAL_STALE)
        reasons.append("valid-to-before-as-of")
    elif temporal == "not-yet-valid":
        factors.append(LimitingFactor.TEMPORAL_NOT_YET_VALID)
        reasons.append("valid-from-after-as-of")
    elif temporal == "unknown":
        factors.append(LimitingFactor.TEMPORAL_UNKNOWN)
        unknown.append("validity-window-missing-or-incomplete")
    elif temporal == "applicable":
        reasons.append("temporally-applicable")
    elif temporal == "unspecified":
        unknown.append("as-of-valid-time-not-supplied")

    recency_known = any(item.last_modified is not None for item in target.provenance)
    if not recency_known:
        unknown.append("observation-recency-not-declared")

    dimensions = EvidenceDimensions(
        source_presence=source_presence,
        distinct_lineage_count=distinct_lineage_count,
        distinct_source_count=distinct_source_count,
        repeated_same_source=repeated_same_source,
        durable_identity_preserved_after_move=moved_preserved,
        lineage_integrity=integrity,
        independence_known=False,
        authority_class=authority_class,
        authority_disagreement=authority_disagreement,
        temporal_applicability=temporal,
        claim_identity_stable=claim_identity_stable,
        corroborating_lineage_count=corroborating_lineage_count,
        contradicting_peer_count=len(contradicting_peers),
        provenance_complete=provenance_complete,
        observation_recency_known=recency_known,
    )
    return factors, reasons, unknown, dimensions


def _classify(
    target: AssessableClaim,
    factors: Sequence[LimitingFactor],
    dimensions: EvidenceDimensions,
) -> ConfidenceClass:
    factor_set = set(factors)
    if factor_set & _UNKNOWN_FORCING:
        return ConfidenceClass.UNKNOWN
    if target.lifecycle in _UNSTABLE_LIFECYCLE:
        return ConfidenceClass.LOW
    if factor_set & _LOW_FORCING:
        return ConfidenceClass.LOW
    strong = target.authority in _STRONG_AUTHORITY
    present = dimensions.source_presence in {"present", "unknown"} and (
        bool(target.provenance) or dimensions.durable_identity_preserved_after_move
    )
    if strong and present and dimensions.claim_identity_stable:
        return ConfidenceClass.HIGH
    if present and target.authority not in _MISMATCH_AUTHORITY:
        return ConfidenceClass.MEDIUM
    return ConfidenceClass.LOW
