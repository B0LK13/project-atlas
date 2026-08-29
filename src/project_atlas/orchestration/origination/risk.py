"""O1 risk classification — observable attributes only, never LLM judgment.

``classify()`` looks at what the proposal's declared ``proposed_scope``
actually touches and returns O1 only when every disqualifying attribute
is absent. Any single disqualifier routes to OWNER_HELD. This mirrors
the directive's explicit instruction: "Do not ask an LLM to freely decide
whether a task is safe."
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.origination.proposal import RiskClass

#: Mirrors orchestration.autonomy.models.MutationSurface's own path
#: validator exactly (that pattern is module-private there too). A
#: proposed_scope entry that doesn't match this is not just "unusual" --
#: it cannot be registered as an authorized WorkNode.mutation_surface
#: path at all (see materialize.py). Independent-IV finding (D-PHASE2A):
#: silently dropping such a path from an O1 node's registered surface
#: while still routing it O1 would understate what the node's own
#: mutation_surface actually covers. Checking it HERE, as its own
#: disqualifying attribute, means an unrepresentable path forces
#: OWNER_HELD instead -- fails safe by escalation, not by silent
#: narrowing.
_SAFE_MUTATION_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")

#: Path fragments that, if any proposed_scope entry touches them, force
#: OWNER_HELD. Deliberately broad and conservative -- a false positive
#: (an O1-eligible change routed to OWNER_HELD) is safe; a false negative
#: is not.
_DISQUALIFYING_PATH_FRAGMENTS: tuple[str, ...] = (
    ".github/workflows",  # WORKFLOW_CHANGE
    ".github/",  # WORKFLOW_CHANGE (broader CI/governance surface)
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "poetry.lock",
    "Pipfile",
    "go.mod",
    "Cargo.toml",  # DEPENDENCY_CHANGE
    "Dockerfile",
    "docker-compose",
    "infra/",
    "terraform/",
    "deploy/",
    "deployment/",  # DEPLOYMENT_EFFECT
    ".env",
    "secrets",
    "credentials",  # CREDENTIAL_REQUIREMENT
    "auth",
    "security",
    "permission",  # SECURITY_SURFACE
    "migration",
    "migrations/",  # IRREVERSIBLE_MIGRATION
)


class DisqualifyingAttribute(StrEnum):
    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"
    WORKFLOW_CHANGE = "WORKFLOW_CHANGE"
    SECURITY_SURFACE = "SECURITY_SURFACE"
    CREDENTIAL_REQUIREMENT = "CREDENTIAL_REQUIREMENT"
    DEPLOYMENT_EFFECT = "DEPLOYMENT_EFFECT"
    DATA_MUTATION = "DATA_MUTATION"
    EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"
    OUT_OF_SPECIFICATION_COVERAGE = "OUT_OF_SPECIFICATION_COVERAGE"
    UNSAFE_MUTATION_PATH = "UNSAFE_MUTATION_PATH"


class RiskClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_class: RiskClass
    disqualifying_attributes: tuple[DisqualifyingAttribute, ...] = Field(
        default_factory=tuple, max_length=8
    )


def classify(
    *,
    proposed_scope: tuple[str, ...],
    success_criteria: tuple[str, ...],
    requires_external_spend: bool = False,
    requires_history_rewrite: bool = False,
    scope_exceeds_specification: bool = False,
) -> RiskClassification:
    """Classify O1 eligibility from observable attributes only.

    ``requires_external_spend`` / ``requires_history_rewrite`` /
    ``scope_exceeds_specification`` are explicit boolean inputs the caller
    must supply from its own deterministic check (e.g. "did the executor
    plan touch a file outside proposed_scope"), never inferred here from
    free text.
    """
    disqualifiers: list[DisqualifyingAttribute] = []

    for path in proposed_scope:
        # IV round-2 hardening note: _SAFE_MUTATION_PATH_RE is character-
        # class-only and would in isolation accept an embedded "../"
        # traversal segment. Today that's unreachable in practice --
        # proposed_scope only ever comes from pipeline.py, which sources
        # it from evidence paths project_roadmap._evidence_exists()
        # already rejects on any ".." segment -- but checking it again
        # here, explicitly, is cheap defense-in-depth rather than relying
        # solely on that upstream filter never changing.
        has_traversal_segment = ".." in path.replace("\\", "/").split("/")
        if has_traversal_segment or not _SAFE_MUTATION_PATH_RE.fullmatch(path):
            # Cannot be registered as a WorkNode.mutation_surface path at
            # all (see materialize.py) -- escalate rather than silently
            # drop it from an O1-authorized surface.
            disqualifiers.append(DisqualifyingAttribute.UNSAFE_MUTATION_PATH)
            continue
        lowered = path.lower()
        if any(fragment.lower() in lowered for fragment in _DISQUALIFYING_PATH_FRAGMENTS):
            for fragment in _DISQUALIFYING_PATH_FRAGMENTS:
                if fragment.lower() in lowered:
                    disqualifiers.append(_attribute_for_fragment(fragment))
                    break

    if requires_external_spend:
        disqualifiers.append(DisqualifyingAttribute.EXTERNAL_SIDE_EFFECT)
    if requires_history_rewrite:
        disqualifiers.append(DisqualifyingAttribute.DATA_MUTATION)
    if scope_exceeds_specification:
        disqualifiers.append(DisqualifyingAttribute.OUT_OF_SPECIFICATION_COVERAGE)
    if not success_criteria:
        # No success criteria at all means nothing bounds the
        # implementation -- unbounded scope is itself a disqualifier.
        disqualifiers.append(DisqualifyingAttribute.OUT_OF_SPECIFICATION_COVERAGE)

    deduped = tuple(dict.fromkeys(disqualifiers))
    if deduped:
        return RiskClassification(risk_class=RiskClass.OWNER_HELD, disqualifying_attributes=deduped)
    return RiskClassification(
        risk_class=RiskClass.O1_LOW_RISK_SPECIFICATION_BOUND_IMPLEMENTATION,
        disqualifying_attributes=(),
    )


def _attribute_for_fragment(fragment: str) -> DisqualifyingAttribute:
    if fragment in {".github/workflows", ".github/"}:
        return DisqualifyingAttribute.WORKFLOW_CHANGE
    if fragment in {
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "poetry.lock",
        "Pipfile",
        "go.mod",
        "Cargo.toml",
    }:
        return DisqualifyingAttribute.DEPENDENCY_CHANGE
    deployment_fragments = {
        "Dockerfile",
        "docker-compose",
        "infra/",
        "terraform/",
        "deploy/",
        "deployment/",
    }
    if fragment in deployment_fragments:
        return DisqualifyingAttribute.DEPLOYMENT_EFFECT
    if fragment in {".env", "secrets", "credentials"}:
        return DisqualifyingAttribute.CREDENTIAL_REQUIREMENT
    if fragment in {"auth", "security", "permission"}:
        return DisqualifyingAttribute.SECURITY_SURFACE
    if fragment in {"migration", "migrations/"}:
        return DisqualifyingAttribute.DATA_MUTATION
    return DisqualifyingAttribute.OUT_OF_SPECIFICATION_COVERAGE  # pragma: no cover - defensive
