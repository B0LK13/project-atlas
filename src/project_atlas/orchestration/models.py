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
        return self.status == ReceiptStatus.VALID

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
        return self.receipt is not None and self.receipt.is_valid_evidence()


class OrchestrationDecision(BaseModel):
    """Classifier output. AS-ORCH-001A never authorizes execution or merge."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-001A"] = PACKAGE_ID
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
    truth_boundary: Literal[
        "RESULT != AUTHORITY / RECEIPT != AUTHORITY / PASS != MERGE AUTHORIZATION / "
        "CERTIFIED != MERGED / MERGE_ELIGIBLE != MERGED / "
        "REQUESTED_TRANSITION != AUTHORIZED_TRANSITION / "
        "AGENT RECOMMENDATION != OWNER APPROVAL / CLASSIFICATION != EXECUTION"
    ] = TRUTH_BOUNDARY

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
