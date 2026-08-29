"""AS-ORIGIN-001 — Specification-backed work origination (Phase 2A-1, ADR-033).

Bridges two already-shipped, independent pipelines:

1. Deterministic claim extraction (``knowledge_compiler.py`` / ``ingest``),
   which produces typed, provenanced :class:`~project_atlas.domain.Claim`
   objects persisted at ``state/claims/<project_id>.json``.
2. The Living Project Roadmap lens (``project_roadmap.py``), which derives
   ``next_unlock`` from a structured ``## Roadmap record`` fenced-JSON block
   at ``projects/<project_id>/roadmap.md`` -- but never reads claims itself.

This module reads claims, applies a deterministic evidence-quorum policy
gate (no model call ever decides pass/fail), and -- only when the gate
passes -- writes a roadmap record in exactly the shape
``project_roadmap._load_roadmap_source``/``_parse_fenced_record`` expect.
``project_roadmap.py`` itself is never modified.

Truth boundaries (mirrors ``intelligence/next_action.py``'s discipline):
``ORIGINATION_PROPOSAL_IS_COMMAND = NO``. A proposal is never executable on
its own, never bypasses the owner merge gate, and never promotes itself to
``EXECUTION_READY`` when ``authority_class == OWNER_HELD``.

Phase 2A-1 scope only (ADR-033 "Phasing"): this module produces a roadmap
projection file. It does not touch the governor, lease/dispatch machinery,
or ``orchestration/autonomy/*`` -- those are explicitly out of scope until
a separate, later PR (Phase 2A-2).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from atlas_contracts.identity import safe_relative_component
from project_atlas.domain import (
    AuthorityLevel,
    Claim,
    ClaimLifecycle,
    ClaimType,
)

# Deliberate reuse of the existing deterministic machinery per ADR-033
# ("reuse... rather than inventing a second one"): the conflict detector,
# the status-normalization vocabulary, and the fenced-record parser.
from project_atlas.knowledge_compiler import _conflicts
from project_atlas.project_roadmap import _normalize_status, _parse_fenced_record

PACKAGE_ID = "AS-ORIGIN-001"
GENERATOR_ID = "atlas-origination-001"
ORIGINATION_PROPOSAL_IS_COMMAND = "NO"
TRUTH_BOUNDARY_ORIGIN = (
    "ORIGINATION PROPOSAL != COMMAND / != EXECUTION / != AUTHORITY / "
    "!= EXECUTION_READY WHEN OWNER_HELD"
)

_FORBIDDEN_VERBS = frozenset(
    {"execute", "write", "merge", "promote", "resolve", "delete", "deploy"}
)

# ADR-033 policy gate rule 1: an "authoritative intent" signal is a
# ROADMAP_STATUS/WORK_PACKAGE_STATUS claim whose normalized value (via
# project_roadmap._normalize_status, the *same* vocabulary the roadmap lens
# itself uses -- no second vocabulary is invented here) indicates the item
# has not yet started. Raw values of "ready"/"planned"/"entry_gate"/
# "not_started" all normalize to NOT_STARTED; that is the sole marker this
# module treats as "next/ready/planned" per ADR-033 rule 1. A raw value of
# "next" alone does not appear in _normalize_status's vocabulary and
# normalizes to UNKNOWN, so it is deliberately *not* treated as an intent
# signal -- fail-closed rather than guessing a second alias table.
_INTENT_STATUS = "NOT_STARTED"

# ADR-033 rule 4 (already-completed veto): the same _normalize_status
# vocabulary's two "done" states -- IMPLEMENTED and VERIFIED_COMPLETION --
# reused verbatim, never a second completion vocabulary.
_COMPLETION_STATUSES = frozenset({"IMPLEMENTED", "VERIFIED_COMPLETION"})

# Claim types eligible as an authoritative-intent signal (ADR-033 rule 1).
_INTENT_CLAIM_TYPES = frozenset({ClaimType.ROADMAP_STATUS, ClaimType.WORK_PACKAGE_STATUS})

# Claim types eligible as a corroborating-acceptance signal (ADR-033 rule 2):
# either a TEST_RESULT claim for a skipped/xfail/not-yet-passing test, or a
# second independent WORK_PACKAGE_STATUS/DECISION claim citing concrete
# acceptance criteria.
_ACCEPTANCE_STATUS_CLAIM_TYPES = frozenset({ClaimType.WORK_PACKAGE_STATUS, ClaimType.DECISION})

_SKIP_STATE_RE = re.compile(
    r"\b(?:skip(?:ped|s|ping)?|xfail|x-fail|expected failure|not yet passing|"
    r"not yet implemented|not implemented|not passing|pending)\b",
    re.IGNORECASE,
)
# A negation immediately before the matched marker (e.g. "no longer
# skipped", "not skipped") means the claim is reporting the *absence* of
# the skip state, not the state itself -- must never count as a signal.
# "unskipped" never reaches this check at all: "\bskip" cannot match
# mid-token, so it is excluded by the word-boundary alone.
_SKIP_NEGATION_PREFIX_RE = re.compile(r"\b(?:no longer|not|never)\s*$", re.IGNORECASE)

_ACCEPTANCE_CRITERIA_MARKERS = (
    "acceptance criteria",
    "acceptance test",
    "definition of done",
    "error code",
    "test matrix",
    "success criteria",
)

# Vague/TBD-shaped prose that mentions an acceptance-criteria *topic*
# (matches _ACCEPTANCE_CRITERIA_MARKERS above, enough to corroborate a
# quorum per ADR-033 rule 2) but names no concrete, verifiable criterion --
# never enough to promote a claim into success_criteria.
_VAGUE_CRITERION_MARKERS = (
    "will be defined",
    "to be defined",
    "to be determined",
    "not yet defined",
    "not yet determined",
    "will be determined",
    "tbd",
)

_NAMED_TEST_RESOURCE_RE = re.compile(
    r"(?:^|/)test_[^/]+\.py$|(?:^|/)[^/]+_test\.py$",
    re.IGNORECASE,
)

# ADR-033 rule 4: claims below this authority floor never qualify as an
# intent or acceptance signal (no INFERRED-only intent signal).
_AUTHORITY_FLOOR_EXCLUDED = frozenset(
    {AuthorityLevel.INFERRED, AuthorityLevel.PENDING, AuthorityLevel.REJECTED,
     AuthorityLevel.CONFLICTING}
)

# ADR-033 rule 4: superseded/contradicted/stale/removed/rejected claims are
# filtered before the quorum check, never proposed.
_LIFECYCLE_FLOOR_EXCLUDED = frozenset(
    {
        ClaimLifecycle.SUPERSEDED,
        ClaimLifecycle.CONTRADICTED,
        ClaimLifecycle.STALE,
        ClaimLifecycle.REMOVED_SOURCE,
        ClaimLifecycle.REJECTED,
    }
)

# directive §5 owner-gated surfaces: a static path classifier, never a
# model judgment call. Order does not matter; every category is checked.
_OWNER_HELD_WORKFLOW_RE = re.compile(r"(^|/)\.github/workflows/", re.IGNORECASE)
_OWNER_HELD_AUTH_SECURITY_RE = re.compile(
    r"(^|/)(auth|security)(/|_|-|\.|$)", re.IGNORECASE
)
_OWNER_HELD_DEPENDENCY_MANIFEST_RE = re.compile(
    r"(^|/)(pyproject\.toml|requirements[^/]*\.txt|package(-lock)?\.json"
    r"|poetry\.lock|uv\.lock|pipfile(\.lock)?|go\.(mod|sum)|cargo\.(toml|lock))$",
    re.IGNORECASE,
)
_OWNER_HELD_MIGRATION_RE = re.compile(r"(^|/)migrations?/", re.IGNORECASE)
_OWNER_HELD_DEPLOY_RE = re.compile(
    r"(^|/)(deploy|docker|k8s|kubernetes)(/|_|-|\.|$)|(^|/)dockerfile$",
    re.IGNORECASE,
)


class EvidenceSignal(BaseModel):
    """One claim used as intent or corroborating evidence."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_type: ClaimType
    signal_role: Literal["authoritative_intent", "corroborating_acceptance"]
    resource: str  # from Claim.provenance[0].resource
    locator: str | None
    value: str  # the claim's own value, for human review


class OriginationProposal(BaseModel):
    """Never a command, never executable on its own -- mirrors
    NextActionCandidate's authority discipline (intelligence/next_action.py).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORIGIN-001"] = "AS-ORIGIN-001"
    work_id: str  # deterministic hash of (project_id, subject, authoritative claim_id)
    project_id: str
    title: str
    why_this_work: str
    source_evidence: tuple[EvidenceSignal, ...]  # >= 2, >= 1 of each role
    source_locations: tuple[str, ...]
    proposed_scope: tuple[str, ...]  # paths/areas implied by evidence, not invented
    success_criteria: tuple[str, ...]  # from named tests/acceptance clauses only
    dependencies: tuple[str, ...]
    contradictions: tuple[str, ...]  # non-empty => BLOCKED
    risk_class: Literal["O1"] = "O1"  # Phase 2A only ever proposes O1
    authority_class: Literal["EXECUTION_READY", "OWNER_HELD"]
    confidence: Literal["EVIDENCE_COMPLETE", "EVIDENCE_PARTIAL"]
    status: Literal["VALID", "BLOCKED", "INSUFFICIENT_ACCEPTANCE_CONTRACT"]
    block_reason: str | None = None
    is_command: Literal[False] = False
    executable: Literal[False] = False


class CandidateFact(BaseModel):
    """One subject's claims within one project -- the unit correlation and
    policy operate over. Grouping is by (project_id, subject): the same
    interpretation ADR-033's "unrelated failing tests" negative requirement
    depends on -- an intent signal and an acceptance signal must describe
    the *same* subject, never merely the same project, or any unrelated
    skipped test anywhere in the project could corroborate any unrelated
    roadmap item.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str
    subject: str
    claims: tuple[Claim, ...]


def _safe_project_id(project_id: str) -> str:
    return safe_relative_component(project_id, label="project id")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _claim_resource(claim: Claim) -> str:
    return claim.provenance[0].resource if claim.provenance else ""


def _claim_locator(claim: Claim) -> str | None:
    return claim.provenance[0].locator if claim.provenance else None


def _claim_text(claim: Claim) -> str:
    return (claim.normalized_text or claim.value).lower()


def _sanitize_narrative(text: str) -> str:
    """Mirror next_action.py's forbidden-verb sanitization for narrative
    strings (title/why_this_work). Evidence *values* are left verbatim
    (EvidenceSignal.value is explicitly for human review of the raw claim);
    only the strings this module itself composes are sanitized, so
    instruction-like prose embedded in a claim's value can never make a
    generated proposal read like an executable command.
    """
    lowered = text.lower()
    tokens = set(re.split(r"[^a-z0-9]+", lowered))
    if tokens & _FORBIDDEN_VERBS:
        return "evidence-backed origination candidate (narrative withheld: forbidden verb token)"
    return text


def _eligible(claim: Claim) -> bool:
    if claim.authority in _AUTHORITY_FLOOR_EXCLUDED:
        return False
    return claim.lifecycle not in _LIFECYCLE_FLOOR_EXCLUDED


def _is_intent_claim(claim: Claim) -> bool:
    if claim.claim_type not in _INTENT_CLAIM_TYPES:
        return False
    if not _eligible(claim):
        return False
    status, _notes = _normalize_status(claim.normalized_text or claim.value)
    return status == _INTENT_STATUS


def _is_skip_marker_present(text: str) -> bool:
    """Match a real skip/xfail/not-yet-passing test state -- a bounded
    phrase pattern, never a raw substring -- so "unskipped and passing" or
    "no longer skipped" can never false-positive as a skip signal.
    """
    for match in _SKIP_STATE_RE.finditer(text):
        if _SKIP_NEGATION_PREFIX_RE.search(text[: match.start()]):
            continue
        return True
    return False


def _is_skipped_test_claim(claim: Claim) -> bool:
    if claim.claim_type is not ClaimType.TEST_RESULT:
        return False
    if not _eligible(claim):
        return False
    return _is_skip_marker_present(_claim_text(claim))


def _is_acceptance_criteria_claim(claim: Claim, *, exclude_claim_id: str) -> bool:
    if claim.claim_id == exclude_claim_id:
        return False  # never double-count the same claim (ADR-033 rule 2)
    if claim.claim_type not in _ACCEPTANCE_STATUS_CLAIM_TYPES:
        return False
    if not _eligible(claim):
        return False
    text = _claim_text(claim)
    return any(marker in text for marker in _ACCEPTANCE_CRITERIA_MARKERS)


def _looks_like_concrete_criterion(value: str) -> bool:
    """A structured, deterministic check for whether a claim's own value
    names an actual verifiable criterion -- not merely that the claim
    *mentions* the acceptance-criteria topic (that looser check is
    sufficient to corroborate a quorum per ADR-033 rule 2, but not to
    promote a claim into ``success_criteria``: a locator alone is not
    proof of concreteness, and vague/TBD prose like "acceptance criteria
    will be defined eventually" must never count).
    """
    text = value.lower()
    if any(marker in text for marker in _VAGUE_CRITERION_MARKERS):
        return False
    return any(marker in text for marker in _ACCEPTANCE_CRITERIA_MARKERS)


def _looks_like_named_test_resource(resource: str) -> bool:
    """A real test *file*, not merely a resource whose path happens to
    contain the substring "test" (e.g. ``docs/test_matrix.md``): a
    ``test_*.py``/``*_test.py`` filename, matched anywhere in the path so
    ``tests/test_sample.py`` and a bare ``test_sample.py`` both count.
    """
    posix = resource.replace("\\", "/").lower()
    return bool(_NAMED_TEST_RESOURCE_RE.search(posix))


def extract_candidate_facts(
    claims: list[Claim] | tuple[Claim, ...],
    project_id: str,
) -> tuple[CandidateFact, ...]:
    """Group claims by subject within one project. Deterministic, no model calls.

    Cross-project claims are dropped by construction -- a claim whose
    ``project_id`` does not match the requested project never enters any
    bucket, so cross-project evidence can never contaminate a candidate
    (ADR-033 "Cross-project evidence" fail-closed path).
    """
    safe_project_id = _safe_project_id(project_id)
    grouped: dict[str, list[Claim]] = {}
    for claim in claims:
        if claim.project_id != safe_project_id:
            continue
        grouped.setdefault(claim.subject, []).append(claim)
    facts = [
        CandidateFact(
            project_id=safe_project_id,
            subject=subject,
            claims=tuple(sorted(items, key=lambda item: item.claim_id)),
        )
        for subject, items in grouped.items()
    ]
    return tuple(sorted(facts, key=lambda fact: fact.subject))


def correlate_evidence(fact: CandidateFact) -> tuple[EvidenceSignal, ...] | None:
    """Apply the evidence-quorum rule (ADR-033 rules 1-2).

    Returns ``None`` when the quorum is not met (no candidate exists --
    silent-safe, not an error). Otherwise returns the ordered evidence
    signals: eligible authoritative-intent claims first (sorted by claim
    id), then eligible corroborating-acceptance claims (sorted by claim
    id), each claim contributing at most one signal.
    """
    intent_claims = sorted(
        (claim for claim in fact.claims if _is_intent_claim(claim)),
        key=lambda claim: claim.claim_id,
    )
    if not intent_claims:
        return None
    primary_intent = intent_claims[0]

    acceptance_claims: list[Claim] = []
    for claim in fact.claims:
        is_skip_signal = (
            _is_skipped_test_claim(claim) and claim.claim_id != primary_intent.claim_id
        )
        is_criteria_signal = _is_acceptance_criteria_claim(
            claim, exclude_claim_id=primary_intent.claim_id
        )
        if is_skip_signal or is_criteria_signal:
            acceptance_claims.append(claim)
    # never double-count: a claim already used as intent cannot also corroborate.
    used_intent_ids = {claim.claim_id for claim in intent_claims}
    acceptance_claims = [
        claim for claim in acceptance_claims if claim.claim_id not in used_intent_ids
    ]
    acceptance_claims = sorted(
        {claim.claim_id: claim for claim in acceptance_claims}.values(),
        key=lambda claim: claim.claim_id,
    )
    if not acceptance_claims:
        return None

    signals: list[EvidenceSignal] = [
        EvidenceSignal(
            claim_id=primary_intent.claim_id,
            claim_type=primary_intent.claim_type,
            signal_role="authoritative_intent",
            resource=_claim_resource(primary_intent),
            locator=_claim_locator(primary_intent),
            value=primary_intent.value,
        )
    ]
    for claim in acceptance_claims:
        signals.append(
            EvidenceSignal(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                signal_role="corroborating_acceptance",
                resource=_claim_resource(claim),
                locator=_claim_locator(claim),
                value=claim.value,
            )
        )
    return tuple(signals)


def _classify_authority(
    proposed_scope: tuple[str, ...],
    fact_claims: tuple[Claim, ...],
) -> Literal["EXECUTION_READY", "OWNER_HELD"]:
    # "unless the evidence itself specifies the dependency" (ADR-033 rule 7)
    # means any evidence for this subject, not only the quorum's two
    # selected intent/acceptance signals -- so this scans the fact's full
    # claim set, not just evidence_signals. The claim must still clear the
    # same _eligible() authority/lifecycle floor every other signal in this
    # module is held to -- an INFERRED/REJECTED/stale/superseded
    # RUNTIME_DEPENDENCY claim must never be able to flip a
    # pyproject.toml-touching proposal from OWNER_HELD to EXECUTION_READY.
    has_dependency_evidence = any(
        claim.claim_type is ClaimType.RUNTIME_DEPENDENCY and _eligible(claim)
        for claim in fact_claims
    )
    for path in proposed_scope:
        posix = path.replace("\\", "/")
        if _OWNER_HELD_WORKFLOW_RE.search(posix):
            return "OWNER_HELD"
        if _OWNER_HELD_AUTH_SECURITY_RE.search(posix):
            return "OWNER_HELD"
        if _OWNER_HELD_MIGRATION_RE.search(posix):
            return "OWNER_HELD"
        if _OWNER_HELD_DEPLOY_RE.search(posix):
            return "OWNER_HELD"
        if _OWNER_HELD_DEPENDENCY_MANIFEST_RE.search(posix) and not has_dependency_evidence:
            return "OWNER_HELD"
    return "EXECUTION_READY"


def _derive_success_criteria(evidence_signals: tuple[EvidenceSignal, ...]) -> tuple[str, ...]:
    """Derive success criteria only from a named test or an explicit
    acceptance clause with a concrete locator (ADR-033 rule 5/6): never
    invented beyond what the evidence itself cites.
    """
    criteria: list[str] = []
    for signal in evidence_signals:
        if signal.signal_role != "corroborating_acceptance":
            continue
        if signal.claim_type is ClaimType.TEST_RESULT and _looks_like_named_test_resource(
            signal.resource
        ):
            criteria.append(f"test result ({signal.resource}): {signal.value}")
        elif (
            signal.claim_type in _ACCEPTANCE_STATUS_CLAIM_TYPES
            and signal.locator
            and _looks_like_concrete_criterion(signal.value)
        ):
            location = f"{signal.resource}#{signal.locator}"
            criteria.append(f"acceptance criterion ({location}): {signal.value}")
    return tuple(criteria)


def validate_policy(
    project_id: str,
    fact: CandidateFact,
    evidence_signals: tuple[EvidenceSignal, ...],
    all_project_claims: list[Claim] | tuple[Claim, ...],
) -> OriginationProposal:
    """Full policy gate (ADR-033 rules 3, 5, 6, 7). Pure and deterministic.

    Called only once ``correlate_evidence`` has already found a quorum for
    ``fact``; this function decides VALID / BLOCKED / INSUFFICIENT_ACCEPTANCE_
    CONTRACT and packages the final :class:`OriginationProposal`.
    """
    safe_project_id = _safe_project_id(project_id)
    intent = next(s for s in evidence_signals if s.signal_role == "authoritative_intent")

    proposed_scope = tuple(
        sorted({signal.resource for signal in evidence_signals if signal.resource})
    )
    source_locations = tuple(
        sorted(
            {
                f"{signal.resource}#{signal.locator}" if signal.locator else signal.resource
                for signal in evidence_signals
                if signal.resource
            }
        )
    )
    authority_class = _classify_authority(proposed_scope, fact.claims)

    title = _sanitize_narrative(f"Advance {fact.subject}: {intent.value}"[:200])
    why_this_work = _sanitize_narrative(
        f"Evidence quorum met for {fact.subject}: authoritative intent claim "
        f"{intent.claim_id} ({intent.claim_type.value}) normalizes to "
        f"{_INTENT_STATUS}, corroborated by "
        f"{len(evidence_signals) - 1} acceptance signal(s)."
    )

    # ADR-033 rule 4: veto if any *eligible* claim on this subject -- in any
    # field, not only the field the intent/acceptance signals happen to use
    # -- already reports completion (IMPLEMENTED/VERIFIED_COMPLETION in
    # project_roadmap._normalize_status's own vocabulary; reused rather than
    # inventing a second one, same discipline as the intent-status check
    # above). _conflicts() groups by subject|field, so a completion claim
    # recorded under a *different* field from the intent/acceptance signals
    # (e.g. "lifecycle" vs "status") would never surface as a same-field
    # contradiction there -- this is a separate, explicit check.
    completion_claims = [
        claim
        for claim in fact.claims
        if claim.claim_type in _INTENT_CLAIM_TYPES
        and _eligible(claim)
        and _normalize_status(claim.normalized_text or claim.value)[0] in _COMPLETION_STATUSES
    ]
    if completion_claims:
        contradictions = tuple(
            sorted(
                f"{claim.field}: {claim.value} (claim {claim.claim_id})"
                for claim in completion_claims
            )
        )
        return OriginationProposal(
            work_id=_work_id(safe_project_id, fact.subject, intent.claim_id),
            project_id=safe_project_id,
            title=title,
            why_this_work=why_this_work,
            source_evidence=evidence_signals,
            source_locations=source_locations,
            proposed_scope=proposed_scope,
            success_criteria=(),
            dependencies=(),
            contradictions=contradictions,
            authority_class=authority_class,
            confidence="EVIDENCE_PARTIAL",
            status="BLOCKED",
            block_reason="ALREADY_COMPLETED_EVIDENCE",
        )

    # ADR-033 rule 3: reject if a contradicting claim exists for this subject.
    # Reuse the existing deterministic conflict detector; never a second one.
    # Scoped to this fact's own claims only -- already project+subject
    # scoped by extract_candidate_facts's construction -- never the raw
    # all_project_claims, which _conflicts() does not itself filter by
    # project_id: a foreign-project (or foreign-subject) claim sharing
    # subject/field could otherwise both falsely block this proposal and
    # leak its value into the returned contradictions.
    conflicts = _conflicts(safe_project_id, list(fact.claims))
    subject_conflicts = [conflict for conflict in conflicts if conflict.subject == fact.subject]
    if subject_conflicts:
        contradictions = tuple(
            sorted(
                f"{conflict.field}: "
                + " vs ".join(sorted({c.claim for c in conflict.claims}))
                for conflict in subject_conflicts
            )
        )
        return OriginationProposal(
            work_id=_work_id(safe_project_id, fact.subject, intent.claim_id),
            project_id=safe_project_id,
            title=title,
            why_this_work=why_this_work,
            source_evidence=evidence_signals,
            source_locations=source_locations,
            proposed_scope=proposed_scope,
            success_criteria=(),
            dependencies=(),
            contradictions=contradictions,
            authority_class=authority_class,
            confidence="EVIDENCE_PARTIAL",
            status="BLOCKED",
            block_reason="CONFLICTING_PROJECT_EVIDENCE",
        )

    success_criteria = _derive_success_criteria(evidence_signals)
    if not success_criteria:
        return OriginationProposal(
            work_id=_work_id(safe_project_id, fact.subject, intent.claim_id),
            project_id=safe_project_id,
            title=title,
            why_this_work=why_this_work,
            source_evidence=evidence_signals,
            source_locations=source_locations,
            proposed_scope=proposed_scope,
            success_criteria=(),
            dependencies=(),
            contradictions=(),
            authority_class=authority_class,
            confidence="EVIDENCE_PARTIAL",
            status="INSUFFICIENT_ACCEPTANCE_CONTRACT",
            block_reason="INSUFFICIENT_ACCEPTANCE_CONTRACT",
        )

    return OriginationProposal(
        work_id=_work_id(safe_project_id, fact.subject, intent.claim_id),
        project_id=safe_project_id,
        title=title,
        why_this_work=why_this_work,
        source_evidence=evidence_signals,
        source_locations=source_locations,
        proposed_scope=proposed_scope,
        success_criteria=success_criteria,
        dependencies=(),
        contradictions=(),
        authority_class=authority_class,
        confidence="EVIDENCE_COMPLETE",
        status="VALID",
        block_reason=None,
    )


def _work_id(project_id: str, subject: str, authoritative_claim_id: str) -> str:
    material = "|".join((project_id, subject, authoritative_claim_id))
    return "wk-" + _digest(material)[:20]


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _roadmap_path(vault: Path, project_id: str) -> Path:
    safe_project_id = _safe_project_id(project_id)
    return vault / "projects" / safe_project_id / "roadmap.md"


def _record_for_proposal(proposal: OriginationProposal) -> dict[str, Any]:
    """Project a VALID proposal into the roadmap_items[] shape
    project_roadmap._load_roadmap_source/_parse_fenced_record expect.

    An OWNER_HELD proposal is projected as status=BLOCKED with an explicit
    owner-authorization blocker reason -- the generic mechanism
    build_roadmap_lens already understands for "do not treat as ready" --
    so an OWNER_HELD record is never silently surfaced as EXECUTION_READY
    downstream (directive OWNER_GATE_PRESERVED).
    """
    notes = [
        f"AS-ORIGIN-001:authority_class={proposal.authority_class}",
        f"AS-ORIGIN-001:confidence={proposal.confidence}",
    ]
    if proposal.authority_class == "OWNER_HELD":
        status = "BLOCKED"
        blockers = [
            {
                "reason": "owner_authorization_required",
                "waiting_on": "owner-review",
                "unlock_condition": (
                    "owner reviews proposed scope touching an owner-gated "
                    "surface before this item may proceed"
                ),
            }
        ]
    else:
        status = "planned"
        blockers = []
    return {
        "id": proposal.work_id,
        "title": proposal.title,
        "status": status,
        "lifecycle": "READY",
        "depends_on": list(proposal.dependencies),
        "evidence": list(proposal.proposed_scope),
        "blockers": blockers,
        "notes": notes,
    }


def _load_existing_record(path: Path) -> tuple[str, dict[str, Any]]:
    if not path.is_file():
        return "", {"schema_version": 1, "roadmap_items": [], "origination": {}}
    text = path.read_text(encoding="utf-8")
    record = _parse_fenced_record(text)
    if record is None:
        return text, {"schema_version": 1, "roadmap_items": [], "origination": {}}
    record = dict(record)
    # Normalize the legacy "items" key into "roadmap_items" and then drop
    # "items" entirely -- project_roadmap.build_roadmap_lens reads
    # `source.get("items") or source.get("roadmap_items")`, so leaving the
    # stale "items" list in place would make it keep winning that `or` and
    # silently hide every roadmap_items entry this module appends from then
    # on. After this, the written record carries exactly one items key.
    record.setdefault("roadmap_items", record.get("items") or [])
    record.pop("items", None)
    record.setdefault("origination", {})
    return text, record


_JSON_FENCE_SUB_RE = re.compile(
    r"(## (?:Roadmap|Semantic) record\s*```json\s*).*?(\s*```)",
    re.DOTALL | re.IGNORECASE,
)


def _render_roadmap_markdown(existing_text: str, project_id: str, record: dict[str, Any]) -> str:
    body = json.dumps(record, indent=2, sort_keys=True)
    if existing_text and _JSON_FENCE_SUB_RE.search(existing_text):
        return _JSON_FENCE_SUB_RE.sub(
            lambda m: m.group(1) + body + m.group(2), existing_text, count=1
        )
    if existing_text:
        separator = "" if existing_text.endswith("\n") else "\n"
        return f"{existing_text}{separator}\n## Roadmap record\n```json\n{body}\n```\n"
    return f"# Roadmap — {project_id}\n\n## Roadmap record\n```json\n{body}\n```\n"


def write_origination_record(vault: Path, project_id: str, proposal: OriginationProposal) -> Path:
    """Upsert one VALID proposal into projects/<id>/roadmap.md, atomically.

    Idempotent by work_id: re-running origination against unchanged
    evidence replaces the same item in place rather than duplicating it
    (NO_DUPLICATE_ORIGINATION), and the full proposal is round-tripped
    under the top-level "origination" key so PROVENANCE_SURVIVES_RESTART
    can be verified by reading it back in a fresh call.
    """
    safe_project_id = _safe_project_id(project_id)
    path = _roadmap_path(vault, safe_project_id)
    existing_text, record = _load_existing_record(path)

    items = [item for item in record.get("roadmap_items") or [] if isinstance(item, dict)]
    items = [item for item in items if str(item.get("id")) != proposal.work_id]
    items.append(_record_for_proposal(proposal))
    items.sort(key=lambda item: str(item.get("id")))
    record["roadmap_items"] = items
    record["schema_version"] = 1
    record["generated"] = {"by": GENERATOR_ID}

    origination = dict(record.get("origination") or {})
    origination[proposal.work_id] = proposal.model_dump(mode="json")
    record["origination"] = origination

    markdown = _render_roadmap_markdown(existing_text, safe_project_id, record)
    _write_atomic(path, markdown.encode("utf-8"))
    return path


def _reconcile_stale_origination_items(
    vault: Path, project_id: str, current_proposals: tuple[OriginationProposal, ...]
) -> None:
    """Remove any previously-written AS-ORIGIN-001 roadmap item whose
    evidence has since stopped qualifying.

    Without this, a proposal written on an earlier run stays in both
    ``roadmap_items`` and ``origination`` forever once its backing claims
    change to completed, conflicting, insufficient, or removed -- the next
    run's write loop only ever adds/replaces *currently* VALID proposals,
    it never subtracts, so the roadmap lens would keep presenting obsolete
    work as the next unlock indefinitely.

    Only ever touches entries this module itself wrote: every candidate
    for removal is read out of the record's own ``origination`` map (which
    only this module populates), matched back to its authoritative-intent
    claim id, and dropped only when that same claim id no longer produces
    a VALID proposal with the *same* work_id this run. A hand-authored
    roadmap item (no matching ``origination`` entry) is never inspected.
    """
    safe_project_id = _safe_project_id(project_id)
    path = _roadmap_path(vault, safe_project_id)
    existing_text, record = _load_existing_record(path)
    origination = record.get("origination")
    if not isinstance(origination, dict) or not origination:
        return

    current_valid_by_intent_claim: dict[str, OriginationProposal] = {}
    for proposal in current_proposals:
        if proposal.status != "VALID":
            continue
        intent_signal = next(
            (s for s in proposal.source_evidence if s.signal_role == "authoritative_intent"),
            None,
        )
        if intent_signal is not None:
            current_valid_by_intent_claim[intent_signal.claim_id] = proposal

    stale_work_ids: set[str] = set()
    for work_id, raw in origination.items():
        if not isinstance(raw, dict):
            stale_work_ids.add(work_id)
            continue
        try:
            stored = OriginationProposal.model_validate(raw)
        except Exception:
            stale_work_ids.add(work_id)
            continue
        intent_signal = next(
            (s for s in stored.source_evidence if s.signal_role == "authoritative_intent"),
            None,
        )
        if intent_signal is None:
            stale_work_ids.add(work_id)
            continue
        fresh = current_valid_by_intent_claim.get(intent_signal.claim_id)
        if fresh is None or fresh.work_id != work_id:
            stale_work_ids.add(work_id)

    if not stale_work_ids:
        return

    record["origination"] = {
        work_id: raw for work_id, raw in origination.items() if work_id not in stale_work_ids
    }
    items = [item for item in record.get("roadmap_items") or [] if isinstance(item, dict)]
    record["roadmap_items"] = [
        item for item in items if str(item.get("id")) not in stale_work_ids
    ]
    record["schema_version"] = 1
    record["generated"] = {"by": GENERATOR_ID}

    markdown = _render_roadmap_markdown(existing_text, safe_project_id, record)
    _write_atomic(path, markdown.encode("utf-8"))


def read_origination_proposal(
    vault: Path, project_id: str, work_id: str
) -> OriginationProposal | None:
    """Re-read a previously written proposal from disk (fresh call, no
    in-memory state) -- proves PROVENANCE_SURVIVES_RESTART.

    Fails closed: a missing file, malformed JSON, or a tampered/corrupted
    ``origination[work_id]`` entry that no longer round-trips through the
    ``OriginationProposal`` schema is treated the same as "no such proposal"
    -- ``None`` is returned, never an uncaught exception (mirrors
    ``load_project_claims``'s fail-closed handling of malformed claim
    records).
    """
    safe_project_id = _safe_project_id(project_id)
    path = _roadmap_path(vault, safe_project_id)
    if not path.is_file():
        return None
    record = _parse_fenced_record(path.read_text(encoding="utf-8"))
    if record is None:
        return None
    origination = record.get("origination")
    if not isinstance(origination, dict):
        return None
    raw = origination.get(work_id)
    if not isinstance(raw, dict):
        return None
    try:
        return OriginationProposal.model_validate(raw)
    except Exception:
        return None


def load_project_claims(vault: Path, project_id: str) -> tuple[Claim, ...]:
    """Load a project's persisted claims (state/claims/<id>.json) written
    by ``atlas ingest`` / ``knowledge_compiler.compile_knowledge``. Fails
    closed: a missing file, malformed JSON, or a single malformed claim
    record never raises -- it is simply excluded from evidence.
    """
    safe_project_id = _safe_project_id(project_id)
    path = vault.expanduser().resolve() / "state" / "claims" / f"{safe_project_id}.json"
    if not path.is_file():
        return ()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ()
    if not isinstance(raw, dict):
        return ()
    items = raw.get("claims")
    if not isinstance(items, list):
        return ()
    claims: list[Claim] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            claims.append(Claim.model_validate(item))
        except Exception:
            continue
    return tuple(claims)


def run_origination(vault: Path, project_id: str) -> OriginationProposal | None:
    """Extract -> correlate -> validate_policy -> (if VALID) write.

    Returns the proposal either way -- including BLOCKED/INSUFFICIENT_
    ACCEPTANCE_CONTRACT ones, for callers/tests to inspect without any
    record having been written -- or ``None`` when no evidence quorum was
    met anywhere in the project (silent-safe, not an error).

    Every VALID proposal found is written (upserted, idempotent by
    work_id); when multiple candidate subjects exist, the single returned
    proposal prefers VALID over INSUFFICIENT_ACCEPTANCE_CONTRACT over
    BLOCKED, tie-broken deterministically by work_id.
    """
    vault = vault.expanduser().resolve()
    safe_project_id = _safe_project_id(project_id)
    claims = load_project_claims(vault, safe_project_id)
    facts = extract_candidate_facts(claims, safe_project_id)

    proposals: list[OriginationProposal] = []
    for fact in facts:
        signals = correlate_evidence(fact)
        if signals is None:
            continue
        proposals.append(validate_policy(safe_project_id, fact, signals, claims))

    # Reconcile before (and regardless of) any new write this run: a
    # subject whose evidence stopped qualifying since the last run -- gone
    # entirely, no longer forming a quorum, now conflicting, or now
    # insufficient -- must have its previously-written item removed, not
    # left presenting stale work as the next unlock forever.
    _reconcile_stale_origination_items(vault, safe_project_id, tuple(proposals))

    if not proposals:
        return None

    for proposal in proposals:
        if proposal.status == "VALID":
            write_origination_record(vault, safe_project_id, proposal)

    status_priority = {"VALID": 0, "INSUFFICIENT_ACCEPTANCE_CONTRACT": 1, "BLOCKED": 2}
    proposals.sort(key=lambda item: (status_priority[item.status], item.work_id))
    return proposals[0]
