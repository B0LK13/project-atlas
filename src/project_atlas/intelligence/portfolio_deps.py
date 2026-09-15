"""AS-2.0-PORTFOLIO-002 — cross-project dependency intelligence.

Only explicit evidenced dependency claims become edges.
Shared vocabulary or values are never inferred as dependencies.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import Claim
from project_atlas.intelligence.boundary import GENERATED_BY, TRUTH_BOUNDARY_PORTFOLIO
from project_atlas.intelligence.normalize import normalize_value
from project_atlas.intelligence.types import AssessableClaim, coerce_claims

_EXPLICIT_FIELDS = frozenset(
    {"depends_on", "dependency", "runtime-dependency", "runtime_dependency"}
)
_EXPLICIT_TYPES = frozenset({"runtime-dependency"})


class DependencyClass(StrEnum):
    EXPLICIT = "explicit"
    UNRESOLVED_TARGET = "unresolved-target"


class PortfolioDependency(BaseModel):
    """An evidenced cross-project dependency. Never an inferred edge."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-PORTFOLIO-002"] = "AS-2.0-PORTFOLIO-002"
    dependency_id: str
    source_project_id: str
    target_project_id: str | None
    dep_class: DependencyClass
    claim_id: str
    reason: str
    truth_boundary: str
    generated: dict[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["dependency-not-inferred"] = "dependency-not-inferred"


def detect_portfolio_dependencies(
    projects: Mapping[str, Sequence[Claim | AssessableClaim]],
) -> tuple[PortfolioDependency, ...]:
    """Return only explicit dependency edges. Never infers from shared values."""
    known = {project_id.strip() for project_id in projects if project_id.strip()}
    found: list[PortfolioDependency] = []
    for project_id, claims in sorted(projects.items(), key=lambda item: item[0]):
        source = project_id.strip()
        if not source:
            continue
        for item in coerce_claims(claims):
            if item.project_id != source:
                continue
            if not _explicit(item):
                continue
            target = normalize_value(item.value)
            if target == source:
                continue
            if target in known:
                found.append(
                    _edge(
                        source,
                        target,
                        DependencyClass.EXPLICIT,
                        item.claim_id,
                        "explicit-dependency-claim-names-known-project",
                    )
                )
                continue
            found.append(
                _edge(
                    source,
                    None,
                    DependencyClass.UNRESOLVED_TARGET,
                    item.claim_id,
                    "explicit-dependency-claim-target-not-in-portfolio",
                )
            )
    found.sort(key=lambda item: item.dependency_id)
    return tuple(found)


def _explicit(item: AssessableClaim) -> bool:
    field = item.field.strip().lower().replace(" ", "_")
    claim_type = (item.claim_type or "").strip().lower()
    return field in _EXPLICIT_FIELDS or claim_type in _EXPLICIT_TYPES


def _edge(
    source: str,
    target: str | None,
    dep_class: DependencyClass,
    claim_id: str,
    reason: str,
) -> PortfolioDependency:
    material = "|".join((source, target or "", dep_class.value, claim_id, reason))
    return PortfolioDependency(
        dependency_id="dep-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20],
        source_project_id=source,
        target_project_id=target,
        dep_class=dep_class,
        claim_id=claim_id,
        reason=reason,
        truth_boundary=TRUTH_BOUNDARY_PORTFOLIO,
    )
