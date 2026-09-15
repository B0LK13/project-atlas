"""AS-2.0-DECISION-001 — library-only decision candidate model.

Represents a decision question and its evidenced surroundings.
Never selects a correct option. Never issues a command.
``DECISION_CANDIDATE_IS_COMMAND = NO``
``DECISION_ENGINE_IS_AUTHORITY = NO``
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.agent_context import (
    DerivedAgentContext,
    compose_agent_context,
)
from project_atlas.intelligence.boundary import (
    DECISION_CANDIDATE_IS_COMMAND,
    DECISION_ENGINE_IS_AUTHORITY,
    GENERATED_BY,
    TRUTH_BOUNDARY_DECISION,
)
from project_atlas.intelligence.normalize import normalize_value
from project_atlas.intelligence.types import (
    AssessableClaim,
    SourceObservation,
    ValidityWindowInput,
    coerce_claims,
)

_QUESTION_FIELDS = frozenset({"decision_question", "decision-question", "question"})
_OPTION_FIELDS = frozenset({"decision_option", "decision-option", "option"})
_CONSTRAINT_FIELDS = frozenset(
    {"decision_constraint", "decision-constraint", "constraint"}
)
_REVERSIBILITY_FIELDS = frozenset({"reversibility", "decision_reversibility"})
_STANDING_CONSTRAINTS = (
    "DECISION_CANDIDATE_IS_COMMAND=NO",
    "DECISION_ENGINE_IS_AUTHORITY=NO",
    "DERIVED_INTELLIGENCE_IS_AUTHORITY=NO",
    "UNKNOWN_IS_VALID=YES",
    "CANONICAL_WRITE=NO",
)


class ReversibilityClass(StrEnum):
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"
    UNKNOWN = "unknown"


class DecisionOption(BaseModel):
    """An evidenced alternative. Never a selected decision."""

    model_config = ConfigDict(extra="forbid")

    option_id: str
    label: str
    claim_id: str
    source_class: Literal["explicit-option", "contested-alternative"]
    selected: None = None


class DecisionCandidate(BaseModel):
    """Decision support record. Not a command and not authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-DECISION-001"] = "AS-2.0-DECISION-001"
    candidate_id: str
    project_id: str
    question: str
    known_evidence: tuple[str, ...]
    unknowns: tuple[str, ...]
    conflicts: tuple[str, ...]
    options: tuple[DecisionOption, ...]
    constraints: tuple[str, ...]
    evidence_gaps: tuple[str, ...]
    reversibility: ReversibilityClass
    selected: None = None
    is_command: Literal[False] = False
    is_authority: Literal[False] = False
    command_flag: Literal["NO"] = "NO"
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["decision-not-authority"] = "decision-not-authority"


def compose_decision_candidate(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
    *,
    question: str | None = None,
    sources: tuple[SourceObservation, ...] | None = None,
    validity_windows: tuple[ValidityWindowInput, ...] = (),
    identity_ambiguous_claim_ids: tuple[str, ...] = (),
    as_of_valid_time: str | None = None,
) -> DecisionCandidate:
    """Compose one decision candidate. Never selects an option."""
    if DECISION_CANDIDATE_IS_COMMAND != "NO":
        raise RuntimeError("decision-command-flag-broken")
    if DECISION_ENGINE_IS_AUTHORITY != "NO":
        raise RuntimeError("decision-authority-flag-broken")
    if not project_id.strip():
        raise ValueError("project_id is required")
    scoped = tuple(item for item in coerce_claims(claims) if item.project_id == project_id)
    context = compose_agent_context(
        project_id,
        scoped,
        sources=sources,
        validity_windows=validity_windows,
        identity_ambiguous_claim_ids=identity_ambiguous_claim_ids,
        as_of_valid_time=as_of_valid_time,
    )
    values = {item.claim_id: item.value for item in scoped}
    resolved_question = _question(question, scoped, context)
    options = _options(scoped, context, values)
    constraints = _constraints(scoped)
    reversibility = _reversibility(scoped)
    known = tuple(item.fact_id for item in context.known_facts)
    unknowns = tuple(item.fact_id for item in context.unknown_facts)
    conflicts = tuple(item.candidate_id for item in context.contradictions)
    gaps = tuple(item.gap_id for item in context.gaps)
    option_ids = ",".join(item.option_id for item in options)
    material = "|".join(
        (
            project_id,
            resolved_question,
            ",".join(known),
            ",".join(conflicts),
            option_ids,
            reversibility.value,
        )
    )
    return DecisionCandidate(
        candidate_id="dec-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        project_id=project_id,
        question=resolved_question,
        known_evidence=known,
        unknowns=unknowns,
        conflicts=conflicts,
        options=options,
        constraints=constraints,
        evidence_gaps=gaps,
        reversibility=reversibility,
        truth_boundary=TRUTH_BOUNDARY_DECISION,
    )


def _field_key(item: AssessableClaim) -> str:
    return item.field.strip().lower().replace(" ", "_")


def _question(
    explicit: str | None,
    claims: tuple[AssessableClaim, ...],
    context: DerivedAgentContext,
) -> str:
    if explicit is not None and explicit.strip():
        return explicit.strip()
    for item in claims:
        field = _field_key(item)
        claim_type = (item.claim_type or "").strip().lower()
        if field in _QUESTION_FIELDS or claim_type == "decision":
            text = item.value.strip()
            if text:
                return text
    if context.contested_facts:
        first = context.contested_facts[0]
        return f"which evidenced value is current for {first.field}?"
    if context.unknown_facts:
        first = context.unknown_facts[0]
        return f"what is evidenced for {first.field}?"
    return "what is currently evidenced for this project?"


def _options(
    claims: tuple[AssessableClaim, ...],
    context: DerivedAgentContext,
    values: dict[str, str],
) -> tuple[DecisionOption, ...]:
    found: list[DecisionOption] = []
    seen: set[str] = set()
    for item in claims:
        if _field_key(item) not in _OPTION_FIELDS:
            continue
        option = _option(item.claim_id, item.value, "explicit-option")
        if option.option_id in seen:
            continue
        seen.add(option.option_id)
        found.append(option)
    for candidate in context.contradictions:
        for claim_id in (candidate.claim_a_id, candidate.claim_b_id):
            label = values.get(claim_id)
            if not label:
                continue
            option = _option(claim_id, label, "contested-alternative")
            if option.option_id in seen:
                continue
            seen.add(option.option_id)
            found.append(option)
    found.sort(key=lambda item: item.option_id)
    return tuple(found)


def _option(
    claim_id: str,
    label: str,
    source_class: Literal["explicit-option", "contested-alternative"],
) -> DecisionOption:
    material = "|".join((claim_id, normalize_value(label), source_class))
    return DecisionOption(
        option_id="dopt-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        label=label,
        claim_id=claim_id,
        source_class=source_class,
        selected=None,
    )


def _constraints(claims: tuple[AssessableClaim, ...]) -> tuple[str, ...]:
    found = [item.value.strip() for item in claims if _field_key(item) in _CONSTRAINT_FIELDS]
    found = [item for item in found if item]
    found.extend(_STANDING_CONSTRAINTS)
    return tuple(found)


def _reversibility(claims: tuple[AssessableClaim, ...]) -> ReversibilityClass:
    for item in claims:
        if _field_key(item) not in _REVERSIBILITY_FIELDS:
            continue
        token = normalize_value(item.value)
        if token == ReversibilityClass.REVERSIBLE.value:
            return ReversibilityClass.REVERSIBLE
        if token == ReversibilityClass.IRREVERSIBLE.value:
            return ReversibilityClass.IRREVERSIBLE
        return ReversibilityClass.UNKNOWN
    return ReversibilityClass.UNKNOWN
