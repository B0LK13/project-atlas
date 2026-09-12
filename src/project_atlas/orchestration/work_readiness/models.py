"""Derived work-queue models. PROJECTION != AUTHORITY."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PACKAGE_ID: Final[Literal["AS-WORK-READINESS-001"]] = "AS-WORK-READINESS-001"
SCHEMA_VERSION: Final[Literal[1]] = 1

_ID_RE: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"


class TriState(StrEnum):
    """Explicit three-valued readiness flag. Missing data is UNKNOWN, never YES."""

    YES = "YES"
    NO = "NO"
    UNKNOWN = "UNKNOWN"


class BlockerCode(StrEnum):
    """Stable blocker identifiers. Extend only by addition."""

    MISSING_OR_STALE_CONTRACT = "MISSING_OR_STALE_CONTRACT"
    UNSATISFIED_DEPENDENCY = "UNSATISFIED_DEPENDENCY"
    UNKNOWN_DEPENDENCY = "UNKNOWN_DEPENDENCY"
    ACTIVE_FOREIGN_CLAIM = "ACTIVE_FOREIGN_CLAIM"
    MUTATION_SCOPE_OVERLAP = "MUTATION_SCOPE_OVERLAP"
    MISSING_RUNTIME_CAPACITY = "MISSING_RUNTIME_CAPACITY"
    CI_OR_REVIEW_INCOMPLETE = "CI_OR_REVIEW_INCOMPLETE"
    EXECUTION_LIMIT_EXHAUSTED = "EXECUTION_LIMIT_EXHAUSTED"
    MISSING_AUTHORIZATION = "MISSING_AUTHORIZATION"
    SOURCE_UNREACHABLE = "SOURCE_UNREACHABLE"
    SOURCE_CONFLICTING = "SOURCE_CONFLICTING"
    ACCEPTANCE_FAILED = "ACCEPTANCE_FAILED"
    WORKER_EXIT_NOT_COMPLETION = "WORKER_EXIT_NOT_COMPLETION"
    UNKNOWN_OWNERSHIP = "UNKNOWN_OWNERSHIP"
    AWAITING_INDEPENDENT_REVIEW = "AWAITING_INDEPENDENT_REVIEW"


class SelectionBucket(StrEnum):
    """How an item is reported to operators. Buckets are mutually exclusive."""

    #: Hard suitability passed; may be offered to an existing dispatcher.
    OFFERABLE_TO_DISPATCHER = "OFFERABLE_TO_DISPATCHER"
    #: Content/deps ready; launch authorization not demonstrated.
    CONTENT_READY_AWAITING_AUTHORIZATION = "CONTENT_READY_AWAITING_AUTHORIZATION"
    #: Hard exclusion with a concrete next step.
    BLOCKED = "BLOCKED"
    #: Lifecycle complete under the applicable definition.
    COMPLETE = "COMPLETE"


class Blocker(BaseModel):
    """One concrete, actionable blockage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: BlockerCode
    object_ref: str = Field(min_length=1, max_length=512)
    evidence: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    next_step: str = Field(min_length=1, max_length=1024)
    responsible_role: str = Field(min_length=1, max_length=128)
    known_owner: str | None = Field(default=None, max_length=128)
    recheck_fields: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    #: How many subsequent tasks this same cause blocks (dependency impact).
    dependency_impact: int | None = Field(default=None, ge=0, le=100_000)


class ReadinessAxes(BaseModel):
    """Readiness and authority kept as separate axes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content_prepared: TriState = TriState.UNKNOWN
    technically_prepared: TriState = TriState.UNKNOWN
    dependencies_satisfied: TriState = TriState.UNKNOWN
    ownership_clear: TriState = TriState.UNKNOWN
    mutation_conflict_clear: TriState = TriState.UNKNOWN
    runtime_available: TriState = TriState.UNKNOWN
    execution_authorized: TriState = TriState.UNKNOWN
    ready_for_independent_review: TriState = TriState.UNKNOWN
    lifecycle_complete: TriState = TriState.UNKNOWN


class DependencyStatus(BaseModel):
    """One dependency with its own status — never collapsed into a bool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dependency_id: str = Field(min_length=1, max_length=128)
    status: TriState = TriState.UNKNOWN
    evidence: str | None = Field(default=None, max_length=512)


class SourceObservation(BaseModel):
    """Freshness of one input the projection read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=128)
    revision: str | None = Field(default=None, max_length=128)
    observed_at: str = Field(min_length=1, max_length=64)
    reachable: bool
    stale: bool = False


class WorkItemProjection(BaseModel):
    """One derived work-queue row. Does not mutate backlog or supervisor state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    package_id: Literal["AS-WORK-READINESS-001"] = PACKAGE_ID

    task_id: str = Field(min_length=1, max_length=128, pattern=_ID_RE)
    source_ref: str = Field(min_length=1, max_length=512)
    source_revision: str | None = Field(default=None, max_length=128)

    contract_id: str | None = Field(default=None, max_length=128)
    contract_digest: str | None = Field(default=None, max_length=128)
    contract_valid: TriState = TriState.UNKNOWN

    objective: str = Field(min_length=1, max_length=2048)
    expected_result: str = Field(default="", max_length=2048)

    owner: str | None = Field(default=None, max_length=128)
    active_claim_id: str | None = Field(default=None, max_length=128)
    active_claim_agent: str | None = Field(default=None, max_length=128)

    dependencies: tuple[DependencyStatus, ...] = Field(default_factory=tuple, max_length=64)
    mutation_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    required_capabilities: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    required_adapter: str | None = Field(default=None, max_length=64)

    priority: int | None = Field(default=None, ge=0, le=10_000)
    deadline: str | None = Field(default=None, max_length=64)

    axes: ReadinessAxes = Field(default_factory=ReadinessAxes)
    blockers: tuple[Blocker, ...] = Field(default_factory=tuple, max_length=32)
    bucket: SelectionBucket = SelectionBucket.BLOCKED

    authorization_ref: str | None = Field(
        default=None,
        max_length=512,
        description="Verified pointer only; never a newly minted grant.",
    )
    acceptance_ref: str | None = Field(default=None, max_length=512)
    worker_exit_zero: bool | None = None
    acceptance_passed: bool | None = None

    sources: tuple[SourceObservation, ...] = Field(default_factory=tuple, max_length=32)
    observed_at: str = Field(min_length=1, max_length=64)
    selection_explanation: tuple[str, ...] = Field(default_factory=tuple, max_length=32)

    @field_validator("mutation_paths")
    @classmethod
    def _no_abs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for path in value:
            if path.startswith("/") or path.startswith("\\") or ".." in path.split("/"):
                raise ValueError(f"mutation path must be repository-relative: {path!r}")
        return value


class WorkQueueReport(BaseModel):
    """Machine-readable queue projection for one observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    package_id: Literal["AS-WORK-READINESS-001"] = PACKAGE_ID
    observed_at: str
    source_revisions: dict[str, str] = Field(default_factory=dict)
    items: tuple[WorkItemProjection, ...] = Field(default_factory=tuple)
    shared_blockers: tuple[Blocker, ...] = Field(default_factory=tuple)
    offerable: tuple[str, ...] = Field(default_factory=tuple)
    awaiting_authorization: tuple[str, ...] = Field(default_factory=tuple)
    blocked: tuple[str, ...] = Field(default_factory=tuple)
    empty_queue_reasons: tuple[str, ...] = Field(default_factory=tuple)
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False
    fixture_adapters_used: tuple[str, ...] = Field(default_factory=tuple)
    missing_integrations: tuple[str, ...] = Field(default_factory=tuple)

    def model_dump_json_stable(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"


class HandoffProposal(BaseModel):
    """Idempotent transfer preparation. PROPOSAL != CLAIM; does not reserve work."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    package_id: Literal["AS-WORK-READINESS-001"] = PACKAGE_ID
    handoff_id: str = Field(min_length=16, max_length=128)
    task_id: str = Field(min_length=1, max_length=128)
    contract_id: str | None = None
    contract_digest: str | None = None
    source_revisions: dict[str, str] = Field(default_factory=dict)
    proposed_agent_or_capabilities: str = Field(min_length=1, max_length=256)
    dependency_evidence: tuple[str, ...] = Field(default_factory=tuple)
    ownership_evidence: tuple[str, ...] = Field(default_factory=tuple)
    mutation_paths: tuple[str, ...] = Field(default_factory=tuple)
    execution_limits: dict[str, Any] = Field(default_factory=dict)
    acceptance_refs: tuple[str, ...] = Field(default_factory=tuple)
    freshness_conditions: tuple[str, ...] = Field(default_factory=tuple)
    observed_at: str
    expired: bool = False
    expire_reason: str | None = None
    reserves_work: Literal[False] = False
    execution_authorized: Literal[False] = False
    merge_authorized: Literal[False] = False


def stable_handoff_id(
    *,
    task_id: str,
    contract_digest: str | None,
    source_revisions: dict[str, str],
    mutation_paths: tuple[str, ...],
) -> str:
    """Idempotent id for an unchanged proposal body."""
    payload = {
        "task_id": task_id,
        "contract_digest": contract_digest,
        "source_revisions": dict(sorted(source_revisions.items())),
        "mutation_paths": list(mutation_paths),
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"wrh-{digest[:32]}"
