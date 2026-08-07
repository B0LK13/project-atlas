"""Deterministic claims, authority, conflicts and review processing (AS-CORE-003)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from project_atlas.claim_identity import (
    _digest,
    _slug,
    canonical_identity_key,
    claim_id_from_key,
)
from project_atlas.compilation import CompilationCandidate, CompilationOutcome
from project_atlas.domain import (
    AuthorityLevel,
    AuthorityRecord,
    CanonicalImpact,
    Claim,
    ClaimLifecycle,
    ClaimLifecycleRecord,
    ClaimLifecycleTransition,
    ClaimType,
    ConceptLifecycle,
    ConceptRecord,
    ConceptType,
    ConfidenceState,
    ConflictingClaim,
    ConflictRecord,
    Diagnostic,
    DiagnosticCode,
    GeneratedMetadata,
    KnowledgeState,
    LifecycleStatus,
    ProvenanceReference,
    ReviewCategory,
    ReviewEntry,
    ReviewState,
    Severity,
    VerificationMetadata,
)
from project_atlas.evidence_compiler import SourceExtraction, extract_source
from project_atlas.okf_renderer import render_concept_note
from project_atlas.schema import validate_record
from project_atlas.secrets import scan_text
from project_atlas.subject_derivation import detect_duplicate_semantic_subjects

_ALLOWED_LIFECYCLE_TRANSITIONS: dict[ClaimLifecycle, frozenset[ClaimLifecycle]] = {
    ClaimLifecycle.NEW: frozenset(
        {ClaimLifecycle.UNCHANGED, ClaimLifecycle.UPDATED, ClaimLifecycle.CONTRADICTED,
         ClaimLifecycle.SUPERSEDED, ClaimLifecycle.REMOVED_SOURCE, ClaimLifecycle.REJECTED}
    ),
    ClaimLifecycle.UNCHANGED: frozenset(
        {ClaimLifecycle.UNCHANGED, ClaimLifecycle.UPDATED, ClaimLifecycle.CONTRADICTED,
         ClaimLifecycle.STALE, ClaimLifecycle.REMOVED_SOURCE, ClaimLifecycle.REJECTED}
    ),
    ClaimLifecycle.UPDATED: frozenset(
        {ClaimLifecycle.UNCHANGED, ClaimLifecycle.UPDATED, ClaimLifecycle.SUPERSEDED,
         ClaimLifecycle.CONTRADICTED, ClaimLifecycle.STALE, ClaimLifecycle.REMOVED_SOURCE,
         ClaimLifecycle.REJECTED}
    ),
    ClaimLifecycle.SUPERSEDED: frozenset({ClaimLifecycle.SUPERSEDED, ClaimLifecycle.REJECTED}),
    ClaimLifecycle.CONTRADICTED: frozenset(
        {ClaimLifecycle.UNCHANGED, ClaimLifecycle.UPDATED, ClaimLifecycle.SUPERSEDED,
         ClaimLifecycle.CONTRADICTED, ClaimLifecycle.STALE, ClaimLifecycle.REMOVED_SOURCE,
         ClaimLifecycle.REJECTED}
    ),
    ClaimLifecycle.STALE: frozenset(
        {ClaimLifecycle.UNCHANGED, ClaimLifecycle.UPDATED, ClaimLifecycle.SUPERSEDED,
         ClaimLifecycle.STALE, ClaimLifecycle.REMOVED_SOURCE, ClaimLifecycle.REJECTED}
    ),
    ClaimLifecycle.REMOVED_SOURCE: frozenset({ClaimLifecycle.RESTORED, ClaimLifecycle.REJECTED}),
    ClaimLifecycle.RESTORED: frozenset(
        {ClaimLifecycle.UNCHANGED, ClaimLifecycle.UPDATED, ClaimLifecycle.CONTRADICTED,
         ClaimLifecycle.REMOVED_SOURCE, ClaimLifecycle.REJECTED}
    ),
    ClaimLifecycle.REJECTED: frozenset({ClaimLifecycle.REJECTED}),
}

_AUTHORITY_PRECEDENCE = {
    AuthorityLevel.PRIMARY: 100,
    AuthorityLevel.VALIDATED_EXECUTION: 90,
    AuthorityLevel.MAINTAINED: 70,
    AuthorityLevel.GENERATED: 30,
    AuthorityLevel.INFERRED: 20,
    AuthorityLevel.PENDING: 0,
    AuthorityLevel.CONFLICTING: 0,
    AuthorityLevel.REJECTED: -1,
}


def authority_transition_allowed(
    previous: AuthorityLevel, current: AuthorityLevel
) -> bool:
    """Return whether an authority change is safe without explicit review."""
    if previous is AuthorityLevel.REJECTED and current is not AuthorityLevel.REJECTED:
        return False
    if previous is AuthorityLevel.PRIMARY and current in {
        AuthorityLevel.GENERATED,
        AuthorityLevel.INFERRED,
    }:
        return False
    if previous is AuthorityLevel.CONFLICTING and current not in {
        AuthorityLevel.CONFLICTING,
        AuthorityLevel.REJECTED,
    }:
        return False
    return _AUTHORITY_PRECEDENCE[current] >= _AUTHORITY_PRECEDENCE[previous]


def lifecycle_transition_allowed(
    previous: ClaimLifecycle, current: ClaimLifecycle
) -> bool:
    """Return whether a claim lifecycle transition is governed and versioned."""
    return current in _ALLOWED_LIFECYCLE_TRANSITIONS[previous]


def validate_lifecycle_transition(
    previous: ClaimLifecycle, current: ClaimLifecycle
) -> None:
    """Raise a governed validation failure for an invalid lifecycle edge."""
    _require_lifecycle_transition(previous, current)


def _require_lifecycle_transition(previous: ClaimLifecycle, current: ClaimLifecycle) -> None:
    if not lifecycle_transition_allowed(previous, current):
        raise ValueError(f"invalid claim lifecycle transition: {previous.value} -> {current.value}")


@dataclass(frozen=True)
class KnowledgeBundle:
    claims: tuple[Claim, ...]
    concepts: tuple[ConceptRecord, ...]
    authorities: tuple[AuthorityRecord, ...]
    conflicts: tuple[ConflictRecord, ...]
    reviews: tuple[ReviewEntry, ...]
    lifecycle: tuple[ClaimLifecycleRecord, ...]
    status: dict[str, int]
    writes: dict[str, str]
    preconditions: dict[str, bytes | None]
    # AS-EXT-001A: per-source outcomes and structured diagnostics (§7.8/§7.9).
    candidates: tuple[CompilationCandidate, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


def _quote_source_text(text: str) -> str:
    """Render untrusted source text as visibly inert Markdown.

    Inline literals are wrapped in code spans. Multi-line excerpts are placed
    inside a fenced code block labelled as a source excerpt. This prevents
    source instructions from being rendered as headings, titles, bare prose, or
    executable-looking directives in generated content.
    """
    lines = text.splitlines()
    if len(lines) > 1:
        # Find a fence backtick count that does not appear in the content.
        max_consecutive = 0
        for line in lines:
            run = 0
            for ch in line:
                if ch == "`":
                    run += 1
                    max_consecutive = max(max_consecutive, run)
                else:
                    run = 0
        fence = "`" * max(3, max_consecutive + 1)
        return f"{fence}source-excerpt\n{text.rstrip()}\n{fence}"
    # Inline literal. Choose delimiter length that does not collide with
    # internal backticks.
    inline = text.strip()
    if not inline:
        return "`_empty_`"
    max_run = 0
    run = 0
    for ch in inline:
        if ch == "`":
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    delimiter = "`" * (max_run + 1) if max_run else "`"
    # If the inline literal starts or ends with a backtick (or with spaces),
    # CommonMark requires padding so the delimiters are not swallowed.
    pad = inline.startswith(("`", " ")) or inline.endswith(("`", " "))
    if pad:
        return f"{delimiter} {inline} {delimiter}"
    return f"{delimiter}{inline}{delimiter}"


def _authority(path: str, classification: str) -> tuple[AuthorityLevel, int, str]:
    if path == ".atlas-project.yaml":
        return AuthorityLevel.PRIMARY, 100, "explicit project manifest"
    if classification in {"architecture", "requirements", "validation", "security"}:
        return AuthorityLevel.MAINTAINED, 70, "classified maintained source"
    if classification in {"roadmap", "work-package", "project-overview"}:
        return AuthorityLevel.MAINTAINED, 60, "classified project documentation"
    if "generated" in path.lower():
        return AuthorityLevel.GENERATED, 30, "generated source path"
    return AuthorityLevel.INFERRED, 20, "bounded deterministic extraction from source"


def _provenance(project: str, entry: dict[str, Any]) -> ProvenanceReference:
    resource = str(entry["source"]).replace("../../", "", 2)
    if resource.startswith(("/", "\\")) or ".." in Path(resource).parts:
        raise ValueError(f"unsafe provenance resource: {resource}")
    return ProvenanceReference(
        source_id=str(entry["source_id"]),
        source_lineage_id=(
            str(entry["source_lineage_id"]) if entry.get("source_lineage_id") else None
        ),
        project_id=project,
        resource=resource,
        sha256=str(entry["sha256"]) if entry.get("sha256") else None,
    )


def _claim(
    project: str,
    entry: dict[str, Any],
    claim_type: ClaimType,
    field: str,
    value: str,
    locator: str,
    *,
    subject: str | None = None,
) -> Claim:
    normalized = " ".join(value.split())
    source_id = str(entry["source_id"])
    source_lineage_id = entry.get("source_lineage_id")
    source_identity = str(source_lineage_id or source_id)
    project_identity = str(entry.get("project_uuid") or project)
    # AS-CORE-004: never silently fall back to project when subject is missing.
    if not subject:
        raise ValueError(
            f"refusing claim promotion without semantic subject "
            f"(source={source_id}, field={field}, locator={locator})"
        )

    identity_key = canonical_identity_key(
        project_identity, source_identity, claim_type.value, field, locator
    )
    claim_id = claim_id_from_key(identity_key)
    level, _precedence, _reason = _authority(str(entry["path"]), str(entry["classification"]))
    return Claim(
        claim_id=claim_id,
        project_id=project,
        source_lineage_id=(
            str(entry["source_lineage_id"]) if entry.get("source_lineage_id") else None
        ),
        subject=subject,
        claim_type=claim_type,
        field=field,
        value=normalized,
        normalized_text=normalized.lower(),
        provenance=[_provenance(project, entry)],
        source_hashes=[str(entry["sha256"])],
        authority=level,
        confidence=ConfidenceState.HIGH
        if level in {AuthorityLevel.PRIMARY, AuthorityLevel.MAINTAINED}
        else ConfidenceState.MEDIUM,
        lifecycle=ClaimLifecycle.NEW,
        extraction_method=f"semantic-locator:{locator}",
        verification=ReviewState.UNREVIEWED,
    )


def _extract(project: str, entry: dict[str, Any]) -> tuple[list[Claim], SourceExtraction]:
    """Extract claims for one source with per-source failure isolation.

    AS-EXT-001A (§7.8): extraction never aborts the batch. Parser failures
    become FAILED/PARTIAL candidates with structured diagnostics; only
    COMPLETE_CANDIDATE sources contribute canonical claims, preserving
    all-or-nothing promotion per source. Claim Identity v2 derivation via
    ``_claim`` is unchanged.
    """
    extraction = extract_source(project, entry)
    claims: list[Claim] = []
    if extraction.candidate.promotable:
        for record in extraction.records:
            if not record.subject:
                # Fail closed: incomplete subject derivation never promotes.
                continue
            claim = _claim(
                project,
                entry,
                ClaimType(record.claim_type),
                record.field,
                record.value,
                record.locator,
                subject=record.subject,
            )
            updates: dict[str, Any] = {"extraction_method": record.extraction_method}
            if record.predecessor_id:
                updates["predecessor_claim_id"] = record.predecessor_id
            claims.append(claim.model_copy(update=updates))
    return claims, extraction


def _event_claim(project: str, entry: dict[str, Any]) -> Claim:
    event_type = str(entry["event_type"])
    claim_type = {
        "validation": ClaimType.TEST_RESULT,
        "decision": ClaimType.DECISION,
        "blocker": ClaimType.RISK,
        "failure": ClaimType.RISK,
    }.get(event_type, ClaimType.WORK_PACKAGE_STATUS)
    value = " ".join(str(entry["summary"]).split())
    if scan_text(value):
        raise ValueError(f"secret-bearing agent event cannot become a claim: {entry['event_id']}")
    event_id = str(entry["event_id"])
    source_id = event_id
    source_lineage_id = entry.get("source_lineage_id")
    source_identity = str(source_lineage_id or source_id)

    event_locator = f"event:{event_id}"
    identity_key = canonical_identity_key(
        project, source_identity, claim_type.value, event_type, event_locator
    )
    claim_id = claim_id_from_key(identity_key)
    
    raw_event_hash = entry.get("sha256") or entry.get("component_sha256")
    if isinstance(raw_event_hash, dict):
        event_hash = _digest(json.dumps(raw_event_hash, sort_keys=True, separators=(",", ":")))
    else:
        event_hash = str(raw_event_hash or _digest(source_id))
    ref = ProvenanceReference(
        source_id=source_id,
        source_lineage_id=(
            str(entry["source_lineage_id"]) if entry.get("source_lineage_id") else None
        ),
        project_id=project,
        resource=str(entry["source"]).replace("../../", "", 2),
        sha256=event_hash,
        receipt_id=str(entry["receipt_id"]),
    )
    return Claim(
        claim_id=claim_id,
        project_id=project,
        source_lineage_id=(
            str(entry["source_lineage_id"]) if entry.get("source_lineage_id") else None
        ),
        subject=f"project:{project}",
        claim_type=claim_type,
        field=event_type,
        value=value,
        normalized_text=value.lower(),
        provenance=[ref],
        source_hashes=[event_hash],
        authority=AuthorityLevel.VALIDATED_EXECUTION,
        confidence=ConfidenceState.HIGH,
        lifecycle=ClaimLifecycle.NEW,
        extraction_method=f"agent-event:{event_type}",
        verification=ReviewState.VERIFIED,
    )


def _concept(project: str, claims: list[Claim], entries: list[dict[str, Any]]) -> ConceptRecord:
    sources = [_provenance(project, entry) for entry in entries]
    requested_type = next(
        (str(entry["concept_type"]) for entry in entries if entry.get("concept_type")),
        "Project",
    )
    try:
        concept_type = ConceptType(requested_type)
    except ValueError:
        # Unknown source classifications remain valid evidence and are emitted
        # as a generic Reference concept rather than rejected.
        concept_type = ConceptType.REFERENCE
    return ConceptRecord(
        project_id=project,
        concept_id=project,
        type=concept_type,
        title=project,
        description="Deterministically compiled project concept.",
        resource=f"projects/{project}/concepts.md",
        tags=[_slug(project)],
        lifecycle=ConceptLifecycle(status=LifecycleStatus.UNKNOWN),
        knowledge_state=KnowledgeState.EVIDENCE_BACKED
        if claims
        else KnowledgeState.IMPORTED_SOURCE,
        review_state=ReviewState.PENDING_HUMAN_REVIEW if claims else ReviewState.UNREVIEWED,
        sources=sources,
        generated_by="project-atlas:as-core-003",
        generated=GeneratedMetadata(by="agent:project-atlas"),
        verified=VerificationMetadata(),
    )


def _conflicts(project: str, claims: list[Claim]) -> list[ConflictRecord]:
    grouped: dict[str, list[Claim]] = {}
    for claim in claims:
        grouped.setdefault(f"{claim.subject}|{claim.field}", []).append(claim)
    results: list[ConflictRecord] = []
    for key, values in sorted(grouped.items()):
        distinct = {
            claim.normalized_text
            for claim in values
            if isinstance(claim.normalized_text, str)
        }
        if len(distinct) < 2:
            continue
        subject, field = key.split("|", 1)
        lineage_key = "|".join(
            sorted({claim.source_lineage_id or claim.provenance[0].source_id for claim in values})
        )
        conflict_key = project + "|" + key + "|" + lineage_key + "|" + "|".join(sorted(distinct))
        conflict_id = f"conflict-{_digest(conflict_key)[:20]}"
        results.append(
            ConflictRecord(
                project_id=project,
                conflict_id=conflict_id,
                subject=subject,
                field=field,
                claims=[
                    ConflictingClaim(
                        source_id=claim.provenance[0].source_id,
                        source_lineage_id=claim.source_lineage_id,
                        claim=claim.value,
                    )
                    for claim in sorted(values, key=lambda item: item.claim_id)
                ],
                claim_ids=sorted(claim.claim_id for claim in values),
                source_lineage_ids=sorted(
                    {
                        claim.source_lineage_id
                        for claim in values
                        if claim.source_lineage_id is not None
                    }
                ),
                provenance=[ref for claim in values for ref in claim.provenance],
            )
        )
    return results


def _review(
    project: str, claims: list[Claim], conflicts: list[ConflictRecord]
) -> list[ReviewEntry]:
    entries = [
        ReviewEntry(
            review_id=f"review-{_digest(f'{project}|pending|{claim.claim_id}')[:20]}",
            project_id=project,
            category=ReviewCategory.PENDING_CLAIM,
            subject_id=claim.claim_id,
            reason="claim requires human verification",
            source_ids=[ref.source_id for ref in claim.provenance],
            source_lineage_ids=[
                ref.source_lineage_id
                for ref in claim.provenance
                if ref.source_lineage_id is not None
            ],
        )
        for claim in claims
        if claim.verification is not ReviewState.VERIFIED
    ]
    entries.extend(
        ReviewEntry(
            review_id=f"review-{_digest(f'{project}|low-confidence|{claim.claim_id}')[:20]}",
            project_id=project,
            category=ReviewCategory.LOW_CONFIDENCE,
            subject_id=claim.claim_id,
            reason="claim has insufficient deterministic authority",
            source_ids=[item.source_id for item in claim.provenance],
            source_lineage_ids=[
                item.source_lineage_id
                for item in claim.provenance
                if item.source_lineage_id is not None
            ],
        )
        for claim in claims
        if claim.confidence is ConfidenceState.LOW
    )
    entries.extend(
        ReviewEntry(
            review_id=f"review-{_digest(f'{project}|lifecycle|{claim.claim_id}')[:20]}",
            project_id=project,
            category=ReviewCategory.STALE_OR_SUPERSEDED,
            subject_id=claim.claim_id,
            reason=f"claim lifecycle is {claim.lifecycle.value}",
            source_ids=[item.source_id for item in claim.provenance],
        )
        for claim in claims
        if claim.lifecycle in {ClaimLifecycle.STALE, ClaimLifecycle.SUPERSEDED}
    )
    entries.extend(
        ReviewEntry(
            review_id=f"review-{_digest(f'{project}|conflict|{conflict.conflict_id}')[:20]}",
            project_id=project,
            category=ReviewCategory.CONFLICT,
            subject_id=conflict.conflict_id,
            reason="materially incompatible source-backed claims",
            source_ids=[item.source_id for item in conflict.claims],
            source_lineage_ids=[
                item.source_lineage_id
                for item in conflict.claims
                if item.source_lineage_id is not None
            ],
        )
        for conflict in conflicts
    )
    return sorted(entries, key=lambda item: item.review_id)


def _apply_lifecycle(
    project: str,
    claims: list[Claim],
    vault: Path,
    conflict_ids: dict[str, str] | None = None,
    observed_at: str | None = None,
) -> tuple[list[Claim], list[ClaimLifecycleRecord], bytes | None]:
    state_path = vault / "state" / "claim-lifecycle" / f"{project}.json"
    previous: dict[str, dict[str, Any]] = {}
    original_bytes = None
    if state_path.is_file():
        original_bytes = state_path.read_bytes()
        try:
            raw = json.loads(original_bytes.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid claim lifecycle state: {state_path}") from exc
        if (
            not isinstance(raw, dict)
            or raw.get("schema_version") != 1
            or not isinstance(raw.get("claims"), list)
        ):
            raise ValueError(f"invalid claim lifecycle state: {state_path}")
        try:
            previous = {
                record.claim_id: record.model_dump(mode="json")
                for record in (
                    ClaimLifecycleRecord.model_validate(item) for item in raw["claims"]
                )
            }
        except (ValidationError, TypeError) as exc:
            raise ValueError(f"invalid claim lifecycle state: {state_path}") from exc
    current_ids = {claim.claim_id for claim in claims}
    conflict_ids = conflict_ids or {}
    policy = _lifecycle_policy(vault)
    output: list[Claim] = []
    lifecycle: list[ClaimLifecycleRecord] = []
    superseded: dict[str, str] = {
        claim.predecessor_claim_id: claim.claim_id
        for claim in claims
        if claim.predecessor_claim_id
    }
    for claim in sorted(claims, key=lambda item: item.claim_id):
        content_hash = _digest(claim.normalized_text or claim.value)
        prior = previous.get(claim.claim_id)
        state = ClaimLifecycle.NEW
        previous_hash = None
        prior_previous_hash: str | None = None
        prior_state = None
        reason = "first observation"
        transition_at = _parse_datetime(observed_at)
        prior_transitions = []
        observation_count = 1
        created_at = transition_at
        previous_source_ids: list[str] = []
        rejection_reason = None
        history_bridge: list[tuple[ClaimLifecycle, ClaimLifecycle, str]] = []
        if prior:
            previous_hash = str(prior.get("content_sha256"))
            prior_previous_hash = prior.get("previous_content_sha256")
            prior_state = ClaimLifecycle(prior.get("lifecycle", ClaimLifecycle.NEW.value))
            prior_transitions = list(prior.get("transitions", []))
            observation_count = int(prior.get("observation_count", 1))
            created_at = _parse_datetime(prior.get("created_at"))
            previous_source_ids = list(prior.get("source_ids", []))
            if prior_state is ClaimLifecycle.REJECTED:
                state = ClaimLifecycle.REJECTED
                rejection_reason = prior.get("rejection_reason") or "previously rejected"
                reason = rejection_reason
            elif previous_hash == content_hash and prior_state is ClaimLifecycle.NEW:
                state = ClaimLifecycle.UNCHANGED
                reason = "equivalent normalized content and matching provenance"
            elif previous_hash == content_hash:
                if prior_state is ClaimLifecycle.REMOVED_SOURCE:
                    state = ClaimLifecycle.RESTORED
                elif prior_state is ClaimLifecycle.RESTORED:
                    state = ClaimLifecycle.UNCHANGED
                else:
                    state = prior_state
                reason = "equivalent observation retained existing lifecycle"
            else:
                state = ClaimLifecycle.UPDATED
                reason = "material normalized content change"
            if prior_state is ClaimLifecycle.STALE and state is ClaimLifecycle.UNCHANGED:
                reason = "source observed again under stale policy"
            if claim.claim_id in conflict_ids:
                if prior_state is ClaimLifecycle.REMOVED_SOURCE:
                    state = ClaimLifecycle.CONTRADICTED
                    reason = "active unresolved material conflict after restoration"
                    history_bridge = [
                        (
                            ClaimLifecycle.REMOVED_SOURCE,
                            ClaimLifecycle.RESTORED,
                            "source returned with historical claim identity",
                        ),
                        (ClaimLifecycle.RESTORED, state, reason),
                    ]
                else:
                    state = ClaimLifecycle.CONTRADICTED
                    reason = "active unresolved material conflict"
            if prior_state is not None and not history_bridge:
                _require_lifecycle_transition(prior_state, state)
        if claim.claim_id in conflict_ids and state is ClaimLifecycle.NEW:
            state = ClaimLifecycle.CONTRADICTED
            reason = "active unresolved material conflict"
        if claim.claim_id in superseded:
            # This is the successor; the predecessor is transitioned below.
            reason = "explicit predecessor linkage"
        if prior and _is_stale(observed_at, policy) and state in {
            ClaimLifecycle.UNCHANGED,
            ClaimLifecycle.UPDATED,
        }:
            _require_lifecycle_transition(state, ClaimLifecycle.STALE)
            state = ClaimLifecycle.STALE
            reason = policy["reference"]
        if prior:
            observation_count += 1 if state is not prior_state else 0
        claim = claim.model_copy(update={"lifecycle": state})
        if state is not ClaimLifecycle.REJECTED:
            output.append(claim)
        transition_steps: list[tuple[ClaimLifecycle, ClaimLifecycle, str]] = list(history_bridge)
        if prior_state is None and state is not ClaimLifecycle.NEW:
            transition_steps.append((ClaimLifecycle.NEW, state, reason))
        elif prior_state is not None and state is not prior_state:
            if state is ClaimLifecycle.STALE and prior_state is ClaimLifecycle.NEW:
                transition_steps.extend(
                    [
                        (ClaimLifecycle.NEW, ClaimLifecycle.UNCHANGED, "equivalent observation"),
                        (ClaimLifecycle.UNCHANGED, state, reason),
                    ]
                )
            else:
                transition_steps.append((prior_state, state, reason))
        transitions = list(prior_transitions)
        for previous_transition, new_transition, transition_reason in transition_steps:
            transitions.append(
                ClaimLifecycleTransition(
                    previous_state=previous_transition,
                    new_state=new_transition,
                    reason=transition_reason,
                    reference_ids=[ref.source_id for ref in claim.provenance],
                    transition_at=transition_at,
                    previous_content_sha256=previous_hash,
                    new_content_sha256=content_hash,
                    related_conflict_id=conflict_ids.get(claim.claim_id),
                ).model_dump(mode="json")
            )
        lifecycle.append(
            ClaimLifecycleRecord(
                claim_id=claim.claim_id,
                project_id=project,
                lifecycle=state,
                content_sha256=content_hash,
                source_ids=[ref.source_id for ref in claim.provenance],
                source_lineage_ids=[
                    ref.source_lineage_id
                    for ref in claim.provenance
                    if ref.source_lineage_id is not None
                ],
                previous_content_sha256=(
                    prior_previous_hash
                    if prior and previous_hash == content_hash
                    else previous_hash
                ),
                previous_source_ids=previous_source_ids,
                predecessor_claim_id=claim.predecessor_claim_id,
                created_at=created_at,
                last_observed_at=transition_at,
                observation_count=observation_count,
                transitions=transitions,
                rejection_reason=rejection_reason,
            )
        )
    for predecessor_id, successor_id in sorted(superseded.items()):
        prior = previous.get(predecessor_id)
        if prior is None:
            raise ValueError(f"supersession predecessor is not retained: {predecessor_id}")
        prior_state = ClaimLifecycle(prior.get("lifecycle", ClaimLifecycle.NEW.value))
        _require_lifecycle_transition(prior_state, ClaimLifecycle.SUPERSEDED)
        lifecycle.append(
            ClaimLifecycleRecord(
                claim_id=predecessor_id,
                project_id=project,
                lifecycle=ClaimLifecycle.SUPERSEDED,
                content_sha256=str(prior["content_sha256"]),
                source_ids=list(prior.get("source_ids", [])),
                previous_source_ids=list(prior.get("previous_source_ids", [])),
                superseded_by_claim_id=successor_id,
                created_at=prior.get("created_at"),
                last_observed_at=_parse_datetime(prior.get("last_observed_at")),
                observation_count=int(prior.get("observation_count", 1)),
                transitions=[
                    *list(prior.get("transitions", [])),
                    ClaimLifecycleTransition(
                        previous_state=prior_state,
                        new_state=ClaimLifecycle.SUPERSEDED,
                        reason="explicit predecessor linkage",
                        reference_ids=list(prior.get("source_ids", [])),
                        superseded_by_claim_id=successor_id,
                    ),
                ],
            )
        )
    superseded_ids = set(superseded)
    for claim_id, prior in sorted(previous.items()):
        if claim_id not in current_ids and claim_id not in superseded_ids:
            lifecycle.append(
                ClaimLifecycleRecord(
                    claim_id=claim_id,
                    project_id=project,
                    lifecycle=ClaimLifecycle.REMOVED_SOURCE,
                    content_sha256=str(prior["content_sha256"]),
                    source_ids=list(prior.get("source_ids", [])),
                    previous_source_ids=list(prior.get("previous_source_ids", [])),
                    created_at=_parse_datetime(prior.get("created_at")),
                    last_observed_at=_parse_datetime(prior.get("last_observed_at")),
                    observation_count=int(prior.get("observation_count", 1)),
                    transitions=list(prior.get("transitions", [])),
                )
            )
    return output, lifecycle, original_bytes


def _lifecycle_policy(vault: Path) -> dict[str, Any]:
    path = vault / ".atlas" / "claim-lifecycle-policy.json"
    if not path.is_file():
        return {"stale_after_days": None, "reference": "no stale policy configured"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid claim lifecycle policy: {path}") from exc
    days = raw.get("stale_after_days") if isinstance(raw, dict) else None
    if days is not None and (not isinstance(days, int) or days < 0):
        raise ValueError(f"invalid stale_after_days policy: {path}")
    return {
        "stale_after_days": days,
        "reference": str(raw.get("reference", "configured stale policy")),
    }


def _is_stale(observed_at: str | None, policy: dict[str, Any]) -> bool:
    # A configured stale policy is intentionally the only source of staleness.
    # The current bounded compiler has no wall-clock default.
    days = policy.get("stale_after_days")
    if days is None or observed_at is None:
        return False
    try:
        observed = datetime.fromisoformat(observed_at)
    except ValueError as exc:
        raise ValueError("claim observation timestamp is invalid") from exc
    return bool((datetime.now(observed.tzinfo) - observed).days >= days)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("claim observation timestamp is invalid") from exc


def compile_knowledge(
    project: str,
    entries: list[dict[str, Any]],
    vault: Path,
    event_entries: list[dict[str, Any]] | None = None,
) -> KnowledgeBundle:
    claims: list[Claim] = []
    candidates: list[CompilationCandidate] = []
    diagnostics: list[Diagnostic] = []
    subject_assignments: list[tuple[str, str, str]] = []
    for entry in entries:
        extracted, extraction = _extract(project, entry)
        claims.extend(extracted)
        candidates.append(extraction.candidate)
        diagnostics.extend(extraction.diagnostics)
        source_id = str(entry.get("source_id") or "")
        path = str(entry.get("path") or "")
        for record in extraction.records:
            if record.subject:
                subject_assignments.append((source_id, path, record.subject))
    for collision in detect_duplicate_semantic_subjects(subject_assignments):
        # Illegitimate duplicate stable semantic IDs: fail closed for that
        # ambiguous subject. Withhold ALL claims whose subject depends on the
        # ambiguous identity (definitional owners and third-party references),
        # and account for every withheld claim/source in the diagnostic.
        serialized = collision.serialized
        withheld = [claim for claim in claims if claim.subject == serialized]
        withheld_ids = tuple(sorted({claim.claim_id for claim in withheld}))
        affected_source_ids = tuple(
            sorted(
                {
                    ref.source_id
                    for claim in withheld
                    for ref in claim.provenance
                    if ref.source_id
                }
            )
        )
        paths_text = ", ".join(collision.definitional_source_paths) or "(paths unavailable)"
        ids_text = ", ".join(collision.definitional_source_ids)
        withheld_ids_text = ", ".join(withheld_ids) if withheld_ids else "(none)"
        affected_text = ", ".join(affected_source_ids) if affected_source_ids else "(none)"
        diagnostics.append(
            Diagnostic(
                code=DiagnosticCode.AMBIGUOUS_IDENTITY,
                severity=Severity.ERROR,
                subject=serialized,
                reason=(
                    f"semantic subject {serialized} is ambiguous: duplicate "
                    f"definitional source_ids [{ids_text}] at paths "
                    f"[{paths_text}]; ALL claims depending on this subject "
                    f"are withheld from canonical state until ambiguity is "
                    f"resolved "
                    f"(total_claims_withheld={len(withheld)}, "
                    f"unique_claim_ids_withheld={len(withheld_ids)} "
                    f"[{withheld_ids_text}], "
                    f"affected_source_ids=[{affected_text}], "
                    f"canonical_impact=staging-only)"
                ),
                remediation=(
                    "resolve the duplicate stable semantic identifier so the "
                    "subject is unique; remove or rename one definitional "
                    "owner. Atlas does not pick a winner by path or parse "
                    "order. Independent unambiguous subjects continue. "
                    "Third-party receipts/reviews that reference the "
                    "ambiguous subject remain withheld because the referent "
                    "cannot be uniquely resolved."
                ),
                continued=True,
                canonical_impact=CanonicalImpact.STAGING_ONLY,
            )
        )
        claims = [claim for claim in claims if claim.subject != serialized]
    claims.extend(_event_claim(project, entry) for entry in (event_entries or []))
    by_id: dict[str, Claim] = {}
    for claim in claims:
        prior = by_id.get(claim.claim_id)
        if prior is not None:
            # Fail-closed guard (AS-CORE-003). Unreachable from per-source
            # extraction since AS-EXT-001A: intra-source locator collisions
            # are withheld upstream (§7.7), and cross-source claim ids are
            # namespaced by durable source identity.
            raise ValueError(
                "ambiguous identity boundary: duplicate explicit IDs or "
                f"colliding semantic anchors for {claim.claim_id}"
            )
        by_id[claim.claim_id] = claim
    preliminary_conflicts = _conflicts(project, claims)
    conflict_ids = {
        claim_id: conflict.conflict_id
        for conflict in preliminary_conflicts
        for claim_id in conflict.claim_ids
    }
    observed_values = [
        str(value)
        for item in [*entries, *(event_entries or [])]
        if (value := item.get("observed_at") or item.get("timestamp"))
    ]
    observed_at = max(observed_values) if observed_values else None
    claims, lifecycle, original_lifecycle_bytes = _apply_lifecycle(
        project, claims, vault, conflict_ids=conflict_ids, observed_at=observed_at
    )
    preconditions: dict[str, bytes | None] = {}
    preconditions[f"state/claim-lifecycle/{project}.json"] = original_lifecycle_bytes
    conflicts = _conflicts(project, claims)
    reviews = _review(project, claims, conflicts)
    reviews.extend(
        ReviewEntry(
            review_id=f"review-{_digest(f'{project}|lifecycle|{record.claim_id}')[:20]}",
            project_id=project,
            category=ReviewCategory(record.lifecycle.value),
            subject_id=record.claim_id,
            reason=record.rejection_reason or "historical lifecycle requires review",
            source_ids=record.source_ids,
        )
        for record in lifecycle
        if record.lifecycle
        in {
            ClaimLifecycle.SUPERSEDED,
            ClaimLifecycle.STALE,
            ClaimLifecycle.REJECTED,
        }
    )
    reviews = sorted(
        {item.review_id: item for item in reviews}.values(),
        key=lambda item: item.review_id,
    )
    concepts = [_concept(project, claims, entries)]
    authorities: list[AuthorityRecord] = []
    for entry in entries:
        level, precedence, reason = _authority(str(entry["path"]), str(entry["classification"]))
        authority_key = project + "|" + str(
            entry.get("source_lineage_id") or entry["source_id"]
        )
        authorities.append(
            AuthorityRecord(
                authority_id=f"authority-{_digest(authority_key)[:20]}",
                project_id=project,
                subject_id=project,
                level=level,
                precedence=precedence,
                reason=reason,
                source_ids=[str(entry["source_id"])],
                source_lineage_ids=(
                    [str(entry["source_lineage_id"])]
                    if entry.get("source_lineage_id")
                    else []
                ),
            )
        )
    for entry in event_entries or []:
        event_id = str(entry["event_id"])
        authorities.append(
            AuthorityRecord(
                authority_id=f"authority-{_digest(project + '|' + event_id)[:20]}",
                project_id=project,
                subject_id=project,
                level=AuthorityLevel.VALIDATED_EXECUTION,
                precedence=90,
                reason="validated agent-event package",
                source_ids=[event_id],
                source_lineage_ids=(
                    [str(entry["source_lineage_id"])]
                    if entry.get("source_lineage_id")
                    else []
                ),
            )
        )
    status = {
        "verified_claims": sum(claim.confidence is ConfidenceState.HIGH for claim in claims),
        "maintained_claims": sum(claim.authority is AuthorityLevel.MAINTAINED for claim in claims),
        "inferred_claims": sum(claim.authority is AuthorityLevel.INFERRED for claim in claims),
        "unresolved_conflicts": len(conflicts),
        "stale_claims": sum(claim.lifecycle is ClaimLifecycle.STALE for claim in claims),
        "claims_missing_provenance": sum(not claim.provenance for claim in claims),
        "claims_awaiting_review": len(reviews),
        "authority_coverage": len(authorities),
        "sources_complete": sum(
            candidate.outcome is CompilationOutcome.COMPLETE_CANDIDATE
            for candidate in candidates
        ),
        "sources_partial": sum(
            candidate.outcome is CompilationOutcome.PARTIAL_CANDIDATE
            for candidate in candidates
        ),
        "sources_failed": sum(
            candidate.outcome is CompilationOutcome.FAILED for candidate in candidates
        ),
        "claims_withheld": sum(candidate.claims_withheld for candidate in candidates),
        "diagnostics": len(diagnostics),
    }
    return KnowledgeBundle(
        claims=tuple(claims),
        concepts=tuple(concepts),
        authorities=tuple(authorities),
        conflicts=tuple(conflicts),
        reviews=tuple(reviews),
        lifecycle=tuple(lifecycle),
        status=status,
        writes={},
        preconditions=preconditions,
        candidates=tuple(candidates),
        diagnostics=tuple(diagnostics),
    )


def render_bundle(bundle: KnowledgeBundle, project: str) -> dict[str, str]:
    for record in (
        *bundle.claims,
        *bundle.concepts,
        *bundle.conflicts,
        *bundle.authorities,
        *bundle.reviews,
        *bundle.lifecycle,
    ):
        kind = {
            Claim: "claim",
            ConceptRecord: "concept-record",
            ConflictRecord: "conflict-record",
            AuthorityRecord: "authority-record",
            ReviewEntry: "review-entry",
            ClaimLifecycleRecord: "claim-lifecycle",
        }[type(record)]
        validate_record(record, kind)
    for diagnostic in bundle.diagnostics:
        validate_record(diagnostic, "diagnostic")
    claims = [claim.model_dump(mode="json") for claim in bundle.claims]
    concepts = [concept.model_dump(mode="json") for concept in bundle.concepts]
    conflicts = [conflict.model_dump(mode="json") for conflict in bundle.conflicts]
    authorities = [authority.model_dump(mode="json") for authority in bundle.authorities]
    reviews = [review.model_dump(mode="json") for review in bundle.reviews]
    lifecycle = [item.model_dump(mode="json") for item in bundle.lifecycle]
    state = {"schema_version": 1, "project_id": project, "claims": claims}
    concept_state = {"schema_version": 1, "project_id": project, "concepts": concepts}
    projections = {
        "claims.md": _render_claims(project, bundle.claims),
        "concepts.md": _render_concepts(project, bundle.concepts),
        "conflicts.md": _render_conflicts(project, bundle.conflicts),
        "decisions.md": _render_type(project, bundle.claims, ClaimType.DECISION, "Decisions"),
        "validations.md": _render_type(
            project, bundle.claims, ClaimType.TEST_RESULT, "Validations"
        ),
        "risks.md": _render_type(project, bundle.claims, ClaimType.RISK, "Risks"),
        "knowledge-status.md": _render_status(project, bundle.status),
    }
    result = {
        f"state/claims/{project}.json": json.dumps(state, indent=2, sort_keys=True) + "\n",
        f"state/concepts/{project}.json": json.dumps(concept_state, indent=2, sort_keys=True)
        + "\n",
        f"state/authority/{project}.json": json.dumps(
            {"schema_version": 1, "project_id": project, "authorities": authorities},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        f"state/claim-lifecycle/{project}.json": json.dumps(
            {"schema_version": 1, "project_id": project, "claims": lifecycle},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        f"state/diagnostics/{project}.json": json.dumps(
            {
                "schema_version": 1,
                "project_id": project,
                "diagnostics": [
                    diagnostic.model_dump(mode="json")
                    for diagnostic in sorted(
                        bundle.diagnostics,
                        key=lambda item: (
                            str(item.source_path),
                            item.code.value,
                            str(item.locator),
                            item.reason,
                        ),
                    )
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        f"state/compilation-outcomes/{project}.json": json.dumps(
            {
                "schema_version": 1,
                "project_id": project,
                "candidates": [
                    {
                        "source_path": candidate.source_path,
                        "outcome": candidate.outcome.value,
                        "claims_extracted": candidate.claims_extracted,
                        "claims_withheld": candidate.claims_withheld,
                        "diagnostics": sorted(candidate.diagnostics),
                        "classification": dict(candidate.classification),
                    }
                    for candidate in sorted(
                        bundle.candidates, key=lambda item: item.source_path
                    )
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        f"review/conflicts/{project}.json": json.dumps(
            {"schema_version": 1, "project_id": project, "entries": conflicts},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        f"review/pending/{project}.json": json.dumps(
            {"schema_version": 1, "project_id": project, "entries": reviews},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        f"generated/reports/knowledge-status-{project}.json": json.dumps(
            {"schema_version": 1, "project_id": project, **bundle.status}, indent=2, sort_keys=True
        )
        + "\n",
    }
    result.update({f"projects/{project}/{name}": content for name, content in projections.items()})
    receipt_hash = _digest("".join(result[key] for key in sorted(result)))
    result[f"receipts/claims/{project}-{receipt_hash[:24]}.json"] = (
        json.dumps(
            {
                "schema_version": 1,
                "receipt_type": "claims-compile",
                "project_id": project,
                "claims": len(claims),
                "conflicts": len(conflicts),
                "reviews": len(reviews),
                "state_sha256": receipt_hash,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    legacy_claims = [
        claim
        for claim in bundle.claims
        if claim.source_lineage_id is None
        and any(ref.source_lineage_id is None for ref in claim.provenance)
    ]
    if legacy_claims:
        legacy_payload = {
            "schema_version": 1,
            "receipt_type": "legacy-claim-generation-compatibility",
            "project_id": project,
            "reason": (
                "claim generation used compatibility source_id because durable "
                "source_lineage_id was absent; this covers unmigrated legacy "
                "sources and agent-event-derived claims, which never carry "
                "source_lineage_id by design"
            ),
            "claims": [
                {
                    "claim_id": claim.claim_id,
                    "source_ids": sorted({ref.source_id for ref in claim.provenance}),
                }
                for claim in sorted(legacy_claims, key=lambda item: item.claim_id)
            ],
        }
        legacy_hash = _digest(json.dumps(legacy_payload, sort_keys=True))[:24]
        result[f"receipts/claims/{project}-legacy-{legacy_hash}.json"] = (
            json.dumps(legacy_payload, indent=2, sort_keys=True) + "\n"
        )
    return result


def _render_claims(project: str, claims: tuple[Claim, ...]) -> str:
    lines = [
        f"# Claims — {project}",
        "",
        "Derived from source-backed claims; machine state is authoritative.",
        "",
    ]
    lines.extend(
        f"- `{claim.claim_id}` **{claim.claim_type}**: {_quote_source_text(claim.value)} "
        f"_(source: {claim.provenance[0].source_id})_"
        for claim in claims
    )
    return "\n".join(lines) + "\n"


def _render_concepts(project: str, concepts: tuple[ConceptRecord, ...]) -> str:
    if not concepts:
        return f"# Concepts — {project}\n\n_No concepts._\n"
    return "\n".join(
        render_concept_note(concept, f"projects/{project}/concepts.md").rstrip()
        for concept in concepts
    ) + "\n"


def _render_conflicts(project: str, conflicts: tuple[ConflictRecord, ...]) -> str:
    lines = [f"# Conflicts — {project}", ""]
    if conflicts:
        lines.extend(
            f"- `{conflict.conflict_id}` `{conflict.field}` — unresolved" for conflict in conflicts
        )
    else:
        lines.append("_No unresolved conflicts._")
    return "\n".join(lines) + "\n"


def _render_type(project: str, claims: tuple[Claim, ...], claim_type: ClaimType, title: str) -> str:
    selected = [claim for claim in claims if claim.claim_type == claim_type]
    lines = [f"# {title} — {project}", ""]
    lines.extend(
        f"- {_quote_source_text(claim.value)} _(source: {claim.provenance[0].source_id})_"
        for claim in selected
    )
    if not selected:
        lines.append("_No verified entries._")
    return "\n".join(lines) + "\n"


def _render_status(project: str, status: dict[str, int]) -> str:
    lines = [f"# Knowledge status — {project}", "", "| Signal | Count |", "|---|---:|"]
    lines.extend(f"| {key.replace('_', ' ')} | {value} |" for key, value in sorted(status.items()))
    return "\n".join(lines) + "\n"
