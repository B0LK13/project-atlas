"""AS-2.0-NEXT-001 — next-action candidate engine.

Proposes evidence-backed candidates only.
``NEXT_ACTION_CANDIDATE_IS_COMMAND = NO``.
No autonomous write or action execution.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.agent_context import compose_agent_context
from project_atlas.intelligence.boundary import (
    GENERATED_BY,
    NEXT_ACTION_CANDIDATE_IS_COMMAND,
    TRUTH_BOUNDARY_NEXT,
)
from project_atlas.intelligence.gaps import GapCurrentStatus
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
)

_FORBIDDEN_VERBS = frozenset(
    {"execute", "write", "merge", "promote", "resolve", "delete", "deploy"}
)


class NextActionKind(StrEnum):
    REVIEW_CONTRADICTION = "review-contradiction"
    GATHER_EVIDENCE = "gather-evidence"
    REVIEW_STALE = "review-stale"
    REVIEW_IDENTITY = "review-identity"
    REVIEW_UNKNOWN = "review-unknown"


class NextActionCandidate(BaseModel):
    """Evidence-backed candidate. Never a command and never executable."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-NEXT-001"] = "AS-2.0-NEXT-001"
    candidate_id: str
    project_id: str
    kind: NextActionKind
    reason: str
    evidence_refs: tuple[str, ...]
    is_command: Literal[False] = False
    executable: Literal[False] = False
    command_flag: Literal["NO"] = "NO"
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["candidate-not-command"] = "candidate-not-command"


def propose_next_action_candidates(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
    *,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
    as_of_valid_time: str | None = None,
) -> tuple[NextActionCandidate, ...]:
    """Propose review/gather candidates. Never executes and never writes."""
    if NEXT_ACTION_CANDIDATE_IS_COMMAND != "NO":
        raise RuntimeError("next-action-command-flag-broken")
    context = compose_agent_context(
        project_id,
        claims,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        as_of_valid_time=as_of_valid_time,
    )
    found: list[NextActionCandidate] = []
    for item in context.contradictions:
        found.append(
            _candidate(
                project_id,
                NextActionKind.REVIEW_CONTRADICTION,
                "human-review-of-unresolved-contradiction-candidate",
                (item.candidate_id, item.claim_a_id, item.claim_b_id),
            )
        )
    for gap in context.gaps:
        kind = (
            NextActionKind.REVIEW_UNKNOWN
            if gap.current_status is GapCurrentStatus.UNKNOWN_FROM_NO_EVIDENCE
            else NextActionKind.GATHER_EVIDENCE
        )
        found.append(
            _candidate(
                project_id,
                kind,
                gap.why_material,
                (*gap.related_claim_ids, gap.gap_id),
            )
        )
    for fact in context.stale_facts:
        found.append(
            _candidate(
                project_id,
                NextActionKind.REVIEW_STALE,
                "stale-is-not-invalid-human-review-of-validity-window",
                (fact.fact_id, *fact.claim_ids),
            )
        )
    for claim_id in identity_ambiguous_claim_ids:
        found.append(
            _candidate(
                project_id,
                NextActionKind.REVIEW_IDENTITY,
                "identity-ambiguity-requires-human-review",
                (claim_id,),
            )
        )
    if not found:
        found.append(
            _candidate(
                project_id,
                NextActionKind.REVIEW_UNKNOWN,
                "unknown-from-no-evidence-is-not-safe",
                (),
            )
        )
    found.sort(key=lambda item: item.candidate_id)
    return tuple(found)


def _candidate(
    project_id: str,
    kind: NextActionKind,
    reason: str,
    evidence_refs: tuple[str, ...],
) -> NextActionCandidate:
    lowered = reason.lower()
    if any(verb in lowered.split("-") or verb in lowered.split() for verb in _FORBIDDEN_VERBS):
        reason = "human-review-required-without-autonomous-action"
    material = "|".join((project_id, kind.value, reason, ",".join(evidence_refs)))
    return NextActionCandidate(
        candidate_id="nxt-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        project_id=project_id,
        kind=kind,
        reason=reason,
        evidence_refs=evidence_refs,
        truth_boundary=TRUTH_BOUNDARY_NEXT,
    )
