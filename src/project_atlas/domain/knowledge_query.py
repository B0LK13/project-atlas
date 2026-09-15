"""Knowledge Query answer envelopes (AS-CORE-007 / AS-CORE-008 / AS-QUERY-DIAG-001).

Query is a read-only consumer of persisted temporal and authoritative state.
It must not invent values or recompute AS-CORE-005 / AS-CORE-006 dispositions.

AS-CORE-008 adds a multi-field composition envelope over point (007) answers
under one shared compilation snapshot. Composition ≠ new authority.

AS-QUERY-DIAG-001 adds an additive operational diagnostic envelope over
existing answer statuses and KnowledgeQueryErrorCode values. Diagnostics are
never Layer-B/C truth and never authority.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.domain.claims import ID_PATTERN, validate_claim_subject


class QueryKind(StrEnum):
    """Contract query kinds (distinct from AS-RET-001 kinds)."""

    AUTHORITATIVE = "authoritative"
    TEMPORAL = "temporal"
    EXPLAIN = "explain"


class AnswerStatus(StrEnum):
    """Structured answer / non-answer status (exit 0 when returned)."""

    OK = "ok"
    NOT_FOUND = "not_found"
    AUTHORITY_PENDING = "authority-pending"
    AUTHORITY_CONFLICT = "authority-conflict"
    UNRESOLVED = "unresolved"
    TEMPORAL_STATE_MISSING = "temporal_state_missing"


class KnowledgeQueryErrorCode(StrEnum):
    """Operational / integrity failures (CLI exit 1)."""

    STATE_MISSING = "state_missing"
    STATE_CORRUPT = "state_corrupt"
    COMPILATION_MISMATCH = "compilation_mismatch"
    PROVENANCE_MISMATCH = "provenance_mismatch"
    VALUE_MISMATCH = "value_mismatch"
    UNSUPPORTED_KIND = "unsupported_kind"
    INVALID_INPUT = "invalid_input"
    STATE_RACE = "state_race"


class QueryOutcomeClass(StrEnum):
    """AS-QUERY-DIAG-001 operational outcome classes (never Layer-B/C truth)."""

    ANSWER = "answer"
    NONANSWER = "nonanswer"
    INTEGRITY_FAILURE = "integrity_failure"
    REQUEST_INVALID = "request_invalid"


class QueryShape(StrEnum):
    """Query request shape recorded on the diagnostic envelope."""

    POINT = "point"
    MULTIFIELD = "multifield"
    LIST = "list"
    UNKNOWN = "unknown"


class ClaimProjection(BaseModel):
    """Persisted claim fields projected into an answer (never invented)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str = Field(pattern=ID_PATTERN)
    value: str | None = None
    source_id: str | None = Field(default=None, pattern=ID_PATTERN)
    source_lineage_id: str | None = Field(default=None, pattern=r"^sline-[A-Za-z0-9]+$")
    resource: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")


class KnowledgeAnswer(BaseModel):
    """Deterministic query envelope (AS-CORE-007-FR-001 / FR-012)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    package: Literal["AS-CORE-007"] = "AS-CORE-007"
    status: AnswerStatus
    kind: QueryKind
    project_id: str = Field(pattern=ID_PATTERN)
    subject: str | None = Field(default=None, min_length=1)
    field: str | None = Field(default=None, min_length=1)
    compilation_id: str | None = Field(default=None, min_length=1)
    # Temporal layer (AS-CORE-005) — distinct from authority
    temporal_status: str | None = None
    temporal_resolution_basis: str | None = None
    temporal_current_claim_id: str | None = Field(default=None, pattern=ID_PATTERN)
    temporal_historical_claim_ids: tuple[str, ...] = ()
    temporal_rationale: str | None = None
    # Authority layer (AS-CORE-006)
    authority_disposition: str | None = None
    authority_domain: str | None = None
    rule_id: str | None = None
    registry_version: int | None = Field(default=None, ge=1)
    trust_root: str | None = None
    authoritative_role: str | None = None
    # Value only when disposition is authoritative (INV-005)
    value: str | None = None
    claim_id: str | None = Field(default=None, pattern=ID_PATTERN)
    competing_claim_ids: tuple[str, ...] = ()
    subordinate_claim_ids: tuple[str, ...] = ()
    temporally_ineligible_claim_ids: tuple[str, ...] = ()
    authority_rationale: str | None = None
    claim: ClaimProjection | None = None
    evidence: tuple[dict[str, Any], ...] = ()
    inspected_artifacts: tuple[str, ...] = ()
    reason_code: str | None = None
    notes: tuple[str, ...] = ()

    @field_validator("subject")
    @classmethod
    def _validate_subject(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_claim_subject(value)

    @model_validator(mode="after")
    def _no_value_without_authoritative(self) -> KnowledgeAnswer:
        # AS-CORE-007-INV-005
        if self.value is not None and self.authority_disposition != "authoritative":
            raise ValueError(
                "authoritative value requires authority_disposition='authoritative'"
            )
        return self


class KnowledgeMultiFieldAnswer(BaseModel):
    """Multi-field composition envelope (AS-CORE-008).

    No request-level ``value``. Per-field answers retain AS-CORE-007 point
    semantics (including ``package: AS-CORE-007`` on each item).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    package: Literal["AS-CORE-008"] = "AS-CORE-008"
    project_id: str = Field(pattern=ID_PATTERN)
    subject: str = Field(min_length=1)
    kind: QueryKind
    compilation_id: str | None = Field(default=None, min_length=1)
    fields: tuple[str, ...] = Field(min_length=1)
    results: tuple[KnowledgeAnswer, ...] = Field(min_length=1)
    inspected_artifacts: tuple[str, ...] = ()

    @field_validator("subject")
    @classmethod
    def _validate_subject(cls, value: str) -> str:
        return validate_claim_subject(value)

    @model_validator(mode="after")
    def _fields_align_with_results(self) -> KnowledgeMultiFieldAnswer:
        if len(self.fields) != len(self.results):
            raise ValueError(
                "fields and results length must match (AS-CORE-008-FR-004/FR-006)"
            )
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("duplicate fields are forbidden (AS-CORE-008-FR-007)")
        for field_name, item in zip(self.fields, self.results, strict=True):
            if item.field != field_name:
                raise ValueError(
                    f"result field {item.field!r} does not align with "
                    f"requested field {field_name!r} (AS-CORE-008-INV-007)"
                )
            if item.project_id != self.project_id:
                raise ValueError(
                    "multi-field item project_id must match envelope (AS-CORE-008-FR-002)"
                )
            if item.subject != self.subject:
                raise ValueError(
                    "multi-field item subject must match envelope (AS-CORE-008-FR-003)"
                )
            if item.kind != self.kind:
                raise ValueError(
                    "multi-field item kind must match envelope (AS-CORE-008-FR-013)"
                )
            # Shared snapshot: item compilation_id must match envelope when both set.
            if (
                self.compilation_id is not None
                and item.compilation_id is not None
                and item.compilation_id != self.compilation_id
            ):
                raise ValueError(
                    "item compilation_id must match envelope (AS-CORE-008-INV-004)"
                )
        return self


class QueryDiagnostic(BaseModel):
    """AS-QUERY-DIAG-001 structured query outcome diagnostic (operational only).

    Never invents authoritative ``value``. Nonanswer ≠ integrity_failure.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    package: Literal["AS-QUERY-DIAG-001"] = "AS-QUERY-DIAG-001"
    outcome_class: QueryOutcomeClass
    query_shape: QueryShape = QueryShape.UNKNOWN
    # project_id / subject are diagnostic metadata only; may be absent on
    # early request_invalid paths (do not re-validate claim subject here).
    project_id: str | None = None
    subject: str | None = None
    field: str | None = None
    fields: tuple[str, ...] | None = None
    kind: QueryKind | None = None
    compilation_id: str | None = None
    error_code: KnowledgeQueryErrorCode | None = None
    message: str | None = None
    answer_status: AnswerStatus | None = None
    item_outcome_classes: tuple[QueryOutcomeClass, ...] = ()
    inspected_artifacts: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _diagnostic_invariants(self) -> QueryDiagnostic:
        # AS-QUERY-DIAG-001-INV-003 — integrity/request failures never invent answer value.
        if self.outcome_class is QueryOutcomeClass.ANSWER and self.error_code is not None:
            raise ValueError("answer outcome_class forbids error_code (AS-QUERY-DIAG-001)")
        if (
            self.outcome_class is QueryOutcomeClass.NONANSWER
            and self.error_code is not None
        ):
            raise ValueError("nonanswer outcome_class forbids error_code (AS-QUERY-DIAG-001)")
        if (
            self.fields is not None
            and self.item_outcome_classes
            and len(self.fields) != len(self.item_outcome_classes)
        ):
            raise ValueError(
                "item_outcome_classes must align with fields (AS-QUERY-DIAG-001-FR-005)"
            )
        return self
