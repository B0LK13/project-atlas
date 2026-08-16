"""AS-ORCH-001A typed contracts: agent result evidence and classification output.

An agent result is evidence/input, not authority. This module defines the
machine-readable envelope and the classifier decision. It does not dispatch,
merge, grant authority, or mutate production state.

Truth boundaries (mandatory):
  RESULT != AUTHORITY
  RECEIPT != AUTHORITY
  PASS != MERGE AUTHORIZATION
  CERTIFIED != MERGED
  MERGE_ELIGIBLE != MERGED
  REQUESTED_TRANSITION != AUTHORIZED_TRANSITION
  AGENT RECOMMENDATION != OWNER APPROVAL
  CLASSIFICATION != EXECUTION
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from atlas_contracts.receipts import ReceiptReference
from atlas_contracts.versions import ID_PATTERN

PACKAGE_ID: Final[str] = "AS-ORCH-001A"
SCHEMA_KIND: Final[str] = "agent-result-envelope"
SCHEMA_VERSION: Final[int] = 1
TRUTH_BOUNDARY: Final[str] = (
    "RESULT != AUTHORITY / RECEIPT != AUTHORITY / PASS != MERGE AUTHORIZATION / "
    "CERTIFIED != MERGED / MERGE_ELIGIBLE != MERGED / "
    "REQUESTED_TRANSITION != AUTHORIZED_TRANSITION / "
    "AGENT RECOMMENDATION != OWNER APPROVAL / CLASSIFICATION != EXECUTION"
)

# Routing-critical states the classifier understands. Unknown states fail closed.
KNOWN_RESULT_STATES: Final[frozenset[str]] = frozenset({"CERTIFIED", "MERGE_ELIGIBLE"})
OWNER_GATED_STATES: Final[frozenset[str]] = frozenset({"MERGE_ELIGIBLE"})

_STATE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_BLOCKER_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_EXTRA_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ProducerRole(StrEnum):
    """Extension-friendly producer plane. Unknown roles fail closed at validation."""

    LOCAL = "local"
    INTEGRATION = "integration"
    AUTONOMOUS = "autonomous"


class ResultOutcome(StrEnum):
    """Semantically distinct routing outcomes. Not free-form prose."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class ReceiptStatus(StrEnum):
    """Same status vocabulary as ``atlas_contracts.receipts.ReceiptReference``."""

    VALID = "valid"
    PENDING = "pending"
    REJECTED = "rejected"


class RequestedTransition(StrEnum):
    """Advisory suggestion only. Never authority. Never overrides classification."""

    INTEGRATION_VERIFY = "INTEGRATION_VERIFY"
    RECERTIFY_REQUIRED = "RECERTIFY_REQUIRED"
    AUTONOMOUS_RECONCILE = "AUTONOMOUS_RECONCILE"
    REMEDIATION_REQUIRED = "REMEDIATION_REQUIRED"
    OWNER_REQUIRED = "OWNER_REQUIRED"
    MERGE = "MERGE"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"


class NextTransition(StrEnum):
    """Eligible next transition. Classification != execution."""

    INTEGRATION_VERIFY = "INTEGRATION_VERIFY"
    RECERTIFY_REQUIRED = "RECERTIFY_REQUIRED"
    BLOCKED = "BLOCKED"
    AUTONOMOUS_RECONCILE = "AUTONOMOUS_RECONCILE"
    REMEDIATION_REQUIRED = "REMEDIATION_REQUIRED"
    OWNER_REQUIRED = "OWNER_REQUIRED"
    REJECTED = "REJECTED"
    BLOCKED_UNKNOWN_STATE = "BLOCKED_UNKNOWN_STATE"


class WorkflowState(StrEnum):
    """Classifier-assigned workflow state. Not an authority grant."""

    LOCAL_ACCEPTED = "LOCAL_ACCEPTED"
    INTEGRATION_ACCEPTED = "INTEGRATION_ACCEPTED"
    RECERTIFY_REQUIRED = "RECERTIFY_REQUIRED"
    BLOCKED = "BLOCKED"
    REMEDIATION_REQUIRED = "REMEDIATION_REQUIRED"
    OWNER_REQUIRED = "OWNER_REQUIRED"
    REJECTED = "REJECTED"
    BLOCKED_UNKNOWN_STATE = "BLOCKED_UNKNOWN_STATE"


class ResultProducer(BaseModel):
    """Who produced the result. Role is a closed enum; agent_id is an identifier."""

    model_config = ConfigDict(extra="forbid")

    role: ProducerRole
    agent_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)


class ResultTask(BaseModel):
    """Task identity must be structured. Never inferred from prose."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    attempt: int = Field(ge=1, le=10_000)


class ResultReceiptBinding(BaseModel):
    """Bind a result to governed receipt evidence.

    Reuses ``ReceiptReference`` status vocabulary. ``event_id`` is optional so
    session receipts (``ASR-…``) can bind without a package event. When
    ``event_id`` is present the binding composes into ``ReceiptReference``.
    """

    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    status: Literal["valid", "pending", "rejected"]
    event_id: str | None = Field(default=None, max_length=128)

    @field_validator("event_id")
    @classmethod
    def _safe_event_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _EVENT_ID_RE.fullmatch(value):
            raise ValueError("receipt.event_id must be a safe identifier, not a path")
        return value

    def is_valid_evidence(self) -> bool:
        """Envelope-claimed receipt status only. Not canonical authenticity."""
        return self.status == "valid"

    def to_receipt_reference(self) -> ReceiptReference | None:
        """Compose the canonical receipt primitive when an event_id is present."""
        if self.event_id is None:
            return None
        return ReceiptReference(
            receipt_id=self.receipt_id,
            status=self.status,
            event_id=self.event_id,
        )


class ResultObservations(BaseModel):
    """Structured facts used by Atlas integration workflows.

    Required routing facts are explicit fields. Additional facts go in
    ``extras`` as a typed identifier→scalar map — not an arbitrary object.
    """

    model_config = ConfigDict(extra="forbid")

    target_moved: bool
    unauthorized_mutations: int = Field(ge=0, le=1_000_000)
    extras: dict[str, bool | int | str] = Field(default_factory=dict, max_length=32)

    @field_validator("extras")
    @classmethod
    def _typed_extras(cls, value: dict[str, bool | int | str]) -> dict[str, bool | int | str]:
        for key, item in value.items():
            if not _EXTRA_KEY_RE.fullmatch(key):
                raise ValueError("observation extra keys must be snake_case identifiers")
            if isinstance(item, str) and len(item) > 256:
                raise ValueError("observation extra string values must be <= 256 characters")
            if isinstance(item, int) and not isinstance(item, bool) and (
                item < -1_000_000 or item > 1_000_000
            ):
                raise ValueError("observation extra integer values are out of bounds")
        return value


class ResultBlocker(BaseModel):
    """Structured blocker. Downstream must not parse prose such as 'blocked because'."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    detail: str | None = Field(default=None, max_length=256)

    @field_validator("code")
    @classmethod
    def _blocker_code(cls, value: str) -> str:
        if not _BLOCKER_CODE_RE.fullmatch(value):
            raise ValueError("blocker.code must be an uppercase identifier")
        return value


class AgentResultEnvelope(BaseModel):
    """Machine-readable agent work result. Evidence/input, not authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    producer: ResultProducer
    task: ResultTask
    outcome: ResultOutcome
    state: str = Field(min_length=1, max_length=64)
    observations: ResultObservations
    receipt: ResultReceiptBinding | None = None
    blockers: list[ResultBlocker] = Field(default_factory=list, max_length=64)
    requested_transition: RequestedTransition | None = None

    @field_validator("state")
    @classmethod
    def _state_identifier(cls, value: str) -> str:
        if not _STATE_RE.fullmatch(value):
            raise ValueError("state must be an uppercase identifier")
        return value

    def receipt_is_valid_evidence(self) -> bool:
        """True when the envelope claims ``receipt.status=valid``.

        Classification (001A) may use this as a structured signal. Dispatcher
        authenticity must verify a canonical Atlas receipt separately.
        ``ENVELOPE_RECEIPT_STATUS_ALONE_IS_SUFFICIENT = NO``.
        """
        return self.receipt is not None and self.receipt.is_valid_evidence()


class OrchestrationDecision(BaseModel):
    """Classifier output. AS-ORCH-001A never authorizes execution or merge."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-001A"] = "AS-ORCH-001A"
    valid: bool
    producer: ProducerRole | None = None
    task: str | None = None
    outcome: ResultOutcome | None = None
    workflow_state: WorkflowState
    next_transition: NextTransition
    execution_authorized: Literal[False] = False
    owner_required: bool
    merge_authorized: Literal[False] = False
    reasons: list[str] = Field(default_factory=list, max_length=32)
    requested_transition: RequestedTransition | None = None
    truth_boundary: str = TRUTH_BOUNDARY

    @model_validator(mode="after")
    def _no_execution_or_merge_authority(self) -> OrchestrationDecision:
        if self.execution_authorized is not False:
            raise ValueError("AS-ORCH-001A has no execution authority")
        if self.merge_authorized is not False:
            raise ValueError("AS-ORCH-001A never authorizes merge")
        if self.next_transition == NextTransition.OWNER_REQUIRED and not self.owner_required:
            raise ValueError("OWNER_REQUIRED classification must set owner_required")
        return self

    def to_public_dict(self) -> dict[str, object]:
        """Machine-readable decision, including CLI aliases. Always no execution."""
        producer = self.producer.value if self.producer is not None else None
        outcome = self.outcome.value if self.outcome is not None else None
        requested = (
            self.requested_transition.value if self.requested_transition is not None else None
        )
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "valid": self.valid,
            "producer": producer,
            "producer_role": producer,
            "task": self.task,
            "task_id": self.task,
            "outcome": outcome,
            "workflow_state": self.workflow_state.value,
            "next_transition": self.next_transition.value,
            "execution_authorized": False,
            "owner_required": self.owner_required,
            "merge_authorized": False,
            "reasons": list(self.reasons),
            "requested_transition": requested,
            "truth_boundary": self.truth_boundary,
        }


# --- AS-ORCH-001B: typed routing output (TaskDirective != execution) ---


class RouteKind(StrEnum):
    """Discriminated routing result. Owner/blocked paths are not fake agent tasks."""

    TASK = "task"
    OWNER_GATE = "owner_gate"
    TERMINAL = "terminal"


class TargetKind(StrEnum):
    """Where a route points. ``owner`` is not an executable agent role."""

    AGENT = "agent"
    OWNER_GATE = "owner_gate"
    TERMINAL = "terminal"


class TaskType(StrEnum):
    """Typed follow-up work. Semantics only — not a shell command or prompt."""

    CANDIDATE_VERIFICATION = "candidate_verification"
    RECERTIFICATION = "recertification"
    PROGRAM_RECONCILIATION = "program_reconciliation"
    REMEDIATION = "remediation"


class DirectivePermissions(BaseModel):
    """Explicit fail-closed privileges. AS-ORCH-001B never sets any flag true."""

    model_config = ConfigDict(extra="forbid")

    repository_write: Literal[False] = False
    branch_write: Literal[False] = False
    pull_request_write: Literal[False] = False
    merge: Literal[False] = False
    production_mutation: Literal[False] = False
    authority_grant: Literal[False] = False

    @model_validator(mode="after")
    def _fail_closed(self) -> DirectivePermissions:
        flags = (
            self.repository_write,
            self.branch_write,
            self.pull_request_write,
            self.merge,
            self.production_mutation,
            self.authority_grant,
        )
        if any(flags):
            raise ValueError("AS-ORCH-001B permissions are fail-closed; no privilege may be true")
        return self


class DirectiveSource(BaseModel):
    """Task/producer binding copied from the validated envelope. Not authority."""

    model_config = ConfigDict(extra="forbid")

    task_id: str | None = Field(default=None, max_length=128)
    attempt: int | None = Field(default=None, ge=1, le=10_000)
    producer_role: ProducerRole | None = None

    @field_validator("task_id")
    @classmethod
    def _safe_task_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(ID_PATTERN, value):
            raise ValueError("source.task_id must be a safe identifier")
        return value


class TaskDirectiveSource(BaseModel):
    """Fully bound source for an agent TaskDirective."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=128, pattern=ID_PATTERN)
    attempt: int = Field(ge=1, le=10_000)
    producer_role: ProducerRole


class RouteTarget(BaseModel):
    """Typed destination. Agent roles reuse the existing producer taxonomy."""

    model_config = ConfigDict(extra="forbid")

    kind: TargetKind
    role: ProducerRole | None = None

    @model_validator(mode="after")
    def _role_matches_kind(self) -> RouteTarget:
        if self.kind == TargetKind.AGENT and self.role is None:
            raise ValueError("agent targets require an existing producer role")
        if self.kind != TargetKind.AGENT and self.role is not None:
            raise ValueError("non-agent targets must not invent an executable role")
        return self


class DirectiveInputs(BaseModel):
    """Bounded structured facts for a future target agent. Not an execution channel."""

    model_config = ConfigDict(extra="forbid")

    outcome: ResultOutcome
    state: str = Field(min_length=1, max_length=64)
    target_moved: bool
    unauthorized_mutations: int = Field(ge=0, le=1_000_000)
    receipt_status: Literal["valid", "pending", "rejected"] | None = None
    blocker_codes: list[str] = Field(default_factory=list, max_length=64)

    @field_validator("state")
    @classmethod
    def _state_identifier(cls, value: str) -> str:
        if not _STATE_RE.fullmatch(value):
            raise ValueError("inputs.state must be an uppercase identifier")
        return value

    @field_validator("blocker_codes")
    @classmethod
    def _blocker_codes(cls, value: list[str]) -> list[str]:
        for code in value:
            if not _BLOCKER_CODE_RE.fullmatch(code):
                raise ValueError("inputs.blocker_codes must be uppercase identifiers")
        return value


class TaskDirective(BaseModel):
    """Machine-readable follow-up task semantics. Not execution and not authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    source: TaskDirectiveSource
    transition: NextTransition
    target: RouteTarget
    task_type: TaskType
    permissions: DirectivePermissions
    owner_gate: Literal[False] = False
    execution_authorized: Literal[False] = False
    source_result_digest: str = Field(min_length=64, max_length=64)
    policy_id: Literal["atlas-orchestration-routing"] = "atlas-orchestration-routing"
    policy_version: Literal[1] = 1
    inputs: DirectiveInputs

    @field_validator("source_result_digest")
    @classmethod
    def _digest_hex(cls, value: str) -> str:
        if not re.fullmatch(r"^[0-9a-f]{64}$", value):
            raise ValueError("source_result_digest must be a SHA-256 hex digest")
        return value

    @model_validator(mode="after")
    def _task_invariants(self) -> TaskDirective:
        if self.execution_authorized is not False:
            raise ValueError("TaskDirective cannot authorize execution")
        if self.owner_gate is not False:
            raise ValueError("TaskDirective is not an owner gate")
        if self.target.kind != TargetKind.AGENT or self.target.role is None:
            raise ValueError("TaskDirective target must be an agent with an existing role")
        if self.transition == NextTransition.OWNER_REQUIRED:
            raise ValueError("OWNER_REQUIRED must not be encoded as a TaskDirective")
        if self.transition in {
            NextTransition.BLOCKED,
            NextTransition.REJECTED,
            NextTransition.BLOCKED_UNKNOWN_STATE,
        }:
            raise ValueError("terminal transitions must not be encoded as a TaskDirective")
        if self.permissions.merge or self.permissions.production_mutation:
            raise ValueError("TaskDirective cannot authorize merge or production mutation")
        if self.permissions.authority_grant:
            raise ValueError("TaskDirective cannot grant authority")
        return self


class OrchestrationRoute(BaseModel):
    """Public AS-ORCH-001B routing output. Routing != dispatch."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-001B"] = "AS-ORCH-001B"
    policy_id: Literal["atlas-orchestration-routing"] = "atlas-orchestration-routing"
    policy_version: Literal[1] = 1
    source: DirectiveSource
    source_result_digest: str = Field(min_length=64, max_length=64)
    transition: NextTransition
    route_kind: RouteKind
    target: RouteTarget
    task_type: TaskType | None = None
    permissions: DirectivePermissions
    owner_gate: bool
    dispatchable: bool
    execution_authorized: Literal[False] = False
    task: TaskDirective | None = None
    reasons: list[str] = Field(default_factory=list, max_length=32)
    truth_boundary: str = (
        TRUTH_BOUNDARY + " / ROUTING != DISPATCH / TASK_DIRECTIVE != EXECUTION / "
        "TASK_DIRECTIVE != AUTHORITY / ELIGIBLE ACTION != AUTHORIZED PRIVILEGED ACTION"
    )

    @field_validator("source_result_digest")
    @classmethod
    def _digest_hex(cls, value: str) -> str:
        if not re.fullmatch(r"^[0-9a-f]{64}$", value):
            raise ValueError("source_result_digest must be a SHA-256 hex digest")
        return value

    @field_validator("reasons")
    @classmethod
    def _bound_reasons(cls, value: list[str]) -> list[str]:
        return [item[:2048] for item in value]

    @model_validator(mode="after")
    def _route_invariants(self) -> OrchestrationRoute:
        if self.execution_authorized is not False:
            raise ValueError("AS-ORCH-001B has no execution authority")
        if (
            self.permissions.merge
            or self.permissions.production_mutation
            or self.permissions.authority_grant
        ):
            raise ValueError("AS-ORCH-001B cannot grant privileged permissions")
        if self.route_kind == RouteKind.TASK:
            if not self.dispatchable:
                raise ValueError("task routes mark typed work as dispatchable, not executed")
            if self.owner_gate:
                raise ValueError("task routes are not owner gates")
            if self.task is None or self.task_type is None:
                raise ValueError("task routes require TaskDirective and task_type")
            if self.target.kind != TargetKind.AGENT or self.target.role is None:
                raise ValueError("task routes require an agent target role")
            if self.task.transition != self.transition:
                raise ValueError("TaskDirective.transition must match the route transition")
            if self.task.task_type != self.task_type:
                raise ValueError("TaskDirective.task_type must match the route task_type")
            if self.task.source_result_digest != self.source_result_digest:
                raise ValueError("TaskDirective digest must match the route binding")
        elif self.route_kind == RouteKind.OWNER_GATE:
            if self.dispatchable:
                raise ValueError("owner_gate routes are not dispatchable")
            if not self.owner_gate:
                raise ValueError("owner_gate routes must set owner_gate")
            if self.task is not None or self.task_type is not None:
                raise ValueError("owner_gate routes must not synthesize a TaskDirective")
            if self.target.kind != TargetKind.OWNER_GATE:
                raise ValueError("owner_gate target.kind must be owner_gate")
            if self.transition != NextTransition.OWNER_REQUIRED:
                raise ValueError("owner_gate is only valid for OWNER_REQUIRED")
        elif self.route_kind == RouteKind.TERMINAL:
            if self.dispatchable:
                raise ValueError("terminal routes are not dispatchable")
            if self.owner_gate:
                raise ValueError("terminal routes are not owner gates")
            if self.task is not None or self.task_type is not None:
                raise ValueError("terminal routes must not synthesize a TaskDirective")
            if self.target.kind != TargetKind.TERMINAL:
                raise ValueError("terminal target.kind must be terminal")
            if self.transition not in {
                NextTransition.BLOCKED,
                NextTransition.REJECTED,
                NextTransition.BLOCKED_UNKNOWN_STATE,
            }:
                raise ValueError("terminal route has an unexpected transition")
        return self

    def to_public_dict(self) -> dict[str, object]:
        """Compact machine-readable route for the read-only CLI."""
        role = self.target.role.value if self.target.role is not None else None
        task_type = self.task_type.value if self.task_type is not None else None
        return {
            "schema_version": self.schema_version,
            "package_id": self.package_id,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "route_kind": self.route_kind.value,
            "transition": self.transition.value,
            "target_kind": self.target.kind.value,
            "target_role": role,
            "task_type": task_type,
            "owner_gate": self.owner_gate,
            "dispatchable": self.dispatchable,
            "execution_authorized": False,
            "source_result_digest": self.source_result_digest,
            "task_id": self.source.task_id,
            "permissions": self.permissions.model_dump(mode="json"),
            "reasons": list(self.reasons),
        }
