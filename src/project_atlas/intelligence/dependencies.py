"""AS-2.0-DEP-001 — evidence-backed project dependencies.

Only explicit dependency claims become edges.
Never infer from shared words, shared files, similar technology,
simultaneous changes, or the same source owner.
``DEPENDENCY_IS_INFERRED = NO`` unless the claim itself is an
explicit candidate class.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import (
    DEPENDENCY_IS_INFERRED,
    GENERATED_BY,
    TRUTH_BOUNDARY_DEP,
)
from project_atlas.intelligence.normalize import normalize_value
from project_atlas.intelligence.types import AssessableClaim, EvidenceRef, coerce_claims

_EXPLICIT_FIELDS = frozenset(
    {"depends_on", "dependency", "runtime-dependency", "runtime_dependency"}
)
_EXPLICIT_TYPES = frozenset({"runtime-dependency"})
_CANDIDATE_FIELDS = frozenset({"dependency_candidate", "dependency-candidate"})
_CANDIDATE_TYPES = frozenset({"dependency-candidate"})


class ProjectDependencyClass(StrEnum):
    EXPLICIT = "explicit"
    EXPLICIT_CANDIDATE = "explicit-candidate"
    UNRESOLVED_TARGET = "unresolved-target"


class ProjectDependency(BaseModel):
    """An evidenced project dependency. Never an inferred edge."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-DEP-001"] = "AS-2.0-DEP-001"
    dependency_id: str
    source_project_id: str
    target_name: str
    target_project_id: str | None
    dep_class: ProjectDependencyClass
    claim_id: str
    evidence_refs: tuple[EvidenceRef, ...]
    inferred: Literal[False] = False
    reason: str
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["dependency-not-inferred"] = "dependency-not-inferred"


def detect_project_dependencies(
    project_id: str,
    claims: Sequence[Claim | AssessableClaim],
    *,
    known_project_ids: Sequence[str] = (),
) -> tuple[ProjectDependency, ...]:
    """Return only explicit evidenced dependencies for one project."""
    if DEPENDENCY_IS_INFERRED != "NO":
        raise RuntimeError("dependency-inferred-flag-broken")
    source = project_id.strip()
    if not source:
        raise ValueError("project_id is required")
    known = {item.strip() for item in known_project_ids if item.strip()}
    found: list[ProjectDependency] = []
    for item in coerce_claims(claims):
        if item.project_id != source:
            continue
        kind = _explicit_kind(item)
        if kind is None:
            continue
        target = normalize_value(item.value)
        if not target or target == source:
            continue
        if known and target in known:
            dep_class = kind
            target_project_id: str | None = target
            reason = (
                "explicit-candidate-claim-names-known-project"
                if kind is ProjectDependencyClass.EXPLICIT_CANDIDATE
                else "explicit-dependency-claim-names-known-project"
            )
        elif known:
            dep_class = ProjectDependencyClass.UNRESOLVED_TARGET
            target_project_id = None
            reason = "explicit-dependency-claim-target-not-in-known-set"
        else:
            dep_class = kind
            target_project_id = None
            reason = (
                "explicit-candidate-claim-without-resolved-project"
                if kind is ProjectDependencyClass.EXPLICIT_CANDIDATE
                else "explicit-dependency-claim-without-resolved-project"
            )
        found.append(
            _edge(
                source,
                target,
                target_project_id,
                dep_class,
                item,
                reason,
            )
        )
    found.sort(key=lambda item: item.dependency_id)
    return tuple(found)


def _explicit_kind(item: AssessableClaim) -> ProjectDependencyClass | None:
    field = item.field.strip().lower().replace(" ", "_")
    claim_type = (item.claim_type or "").strip().lower()
    if field in _CANDIDATE_FIELDS or claim_type in _CANDIDATE_TYPES:
        return ProjectDependencyClass.EXPLICIT_CANDIDATE
    if field in _EXPLICIT_FIELDS or claim_type in _EXPLICIT_TYPES:
        return ProjectDependencyClass.EXPLICIT
    return None


def _edge(
    source: str,
    target_name: str,
    target_project_id: str | None,
    dep_class: ProjectDependencyClass,
    item: AssessableClaim,
    reason: str,
) -> ProjectDependency:
    material = "|".join(
        (source, target_name, dep_class.value, item.claim_id, reason)
    )
    refs = tuple(
        EvidenceRef(
            source_id=ref.source_id,
            resource=ref.resource,
            sha256=ref.sha256,
            claim_id=item.claim_id,
        )
        for ref in item.provenance
    )
    return ProjectDependency(
        dependency_id="pdep-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        source_project_id=source,
        target_name=target_name,
        target_project_id=target_project_id,
        dep_class=dep_class,
        claim_id=item.claim_id,
        evidence_refs=refs,
        reason=reason,
        truth_boundary=TRUTH_BOUNDARY_DEP,
    )
