"""Versionable task-context packet model and digests.

Content identity (digest inputs) is separated from report metadata such as
observation time. Identical explicit inputs must yield the same content
digest barring demonstrable source changes.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PACKAGE_ID: Final[Literal["AS-TASK-CONTEXT-AND-CONTINUITY-001"]] = (
    "AS-TASK-CONTEXT-AND-CONTINUITY-001"
)
SCHEMA_VERSION: Final[Literal[1]] = 1
TRUTH_BOUNDARY: Final[str] = (
    "TASK CONTEXT PACKET ≠ AUTHORITY / ≠ DISPATCH / ≠ POLICY PROMOTION; "
    "RETRIEVED ≠ INSTRUCTION; CONTINUATION ≠ RESUME AUTHORIZATION; "
    "PACKET SNAPSHOT ≠ LIVE ENVIRONMENT"
)

# Fields excluded from content digest (variable report metadata / derived ids).
_DIGEST_EXCLUDE: Final[frozenset[str]] = frozenset(
    {
        "packet_id",  # derived from content digest
        "content_digest",
        "observation_time",
        "report_metadata",
        "generated",
        "human_view",
        "budget_report",  # report surface; inclusion/sizes live on fragments
    }
)


class TrustLayer(StrEnum):
    """Structural trust class. Labels alone are not the boundary."""

    POLICY = "policy"
    TASK_REQUIREMENT = "task_requirement"
    RETRIEVED = "retrieved"


class ContentTier(StrEnum):
    """Budget priority. Background is dropped first; mandatory is never silently truncated."""

    MANDATORY = "mandatory"
    EVIDENCE = "evidence"
    BACKGROUND = "background"


class FreshnessKind(StrEnum):
    GIT_OBJECT = "git_object"
    CONTENT_DIGEST = "content_digest"
    SNAPSHOT = "snapshot"
    UNKNOWN = "unknown"


class FreshnessStatus(StrEnum):
    UNCHANGED = "unchanged"
    MUST_REBUILD = "must_rebuild"
    MISSING_OR_UNVERIFIABLE = "missing_or_unverifiable"


class TokenMeasureKind(StrEnum):
    EXACT = "exact"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class TaskContextError(ValueError):
    """Fail-closed task-context error with a stable code."""

    def __init__(self, message: str, *, code: str = "TASK_CONTEXT_ERROR") -> None:
        super().__init__(message)
        self.code = code


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SourceIdentity(BaseModel):
    """How a used source is pinned for freshness checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: FreshnessKind
    identity: str = Field(min_length=1, max_length=128)
    path: str | None = Field(default=None, max_length=1024)
    fetched_at: str | None = Field(default=None, max_length=64)
    note: str = Field(default="", max_length=512)


class SelectionReason(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1, max_length=64)
    detail: str = Field(min_length=1, max_length=512)


class PacketFragment(BaseModel):
    """One included or excluded fragment with trust + tier + provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fragment_id: str = Field(min_length=1, max_length=128)
    trust_layer: TrustLayer
    tier: ContentTier
    title: str = Field(min_length=1, max_length=256)
    #: Body text. For RETRIEVED, treated as quoted evidence only.
    body: str = Field(default="", max_length=200_000)
    source_path: str | None = Field(default=None, max_length=1024)
    source_identity: SourceIdentity | None = None
    selection_reasons: tuple[SelectionReason, ...] = Field(default_factory=tuple)
    byte_size: int = Field(default=0, ge=0)
    char_size: int = Field(default=0, ge=0)
    included: bool = True
    exclusion_reason: str | None = Field(default=None, max_length=512)
    #: When true, body must never be interpreted as executable instruction.
    retrieved_quarantine: bool = False

    @field_validator("body")
    @classmethod
    def _no_nul(cls, value: str) -> str:
        if "\x00" in value:
            raise TaskContextError("fragment body contains NUL", code="FRAGMENT_NUL")
        return value


class OpenUncertainty(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    uncertainty_id: str = Field(min_length=1, max_length=128)
    kind: Literal["conflict", "missing_source", "open_question", "unverifiable"]
    statement: str = Field(min_length=1, max_length=2048)
    source_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=16)


class PriorAction(BaseModel):
    """An earlier action only when backed by structured evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=1024)
    evidence_ref: str = Field(min_length=1, max_length=512)
    evidence_digest: str = Field(min_length=8, max_length=128)
    outcome: Literal["passed", "failed", "unknown", "blocked"]
    #: Agent closing prose alone never sets this true.
    completion_proven: bool = False


class BudgetPartReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    part_id: str
    tier: ContentTier
    bytes: int = Field(ge=0)
    chars: int = Field(ge=0)
    tokens: int | None = None
    token_measure: TokenMeasureKind = TokenMeasureKind.UNAVAILABLE
    included: bool
    exclusion_reason: str | None = None


class BudgetReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    budget_chars: int = Field(ge=1)
    used_chars: int = Field(ge=0)
    remaining_chars: int
    overflow: bool
    incomplete_mandatory: bool
    overflow_parts: tuple[str, ...] = Field(default_factory=tuple)
    parts: tuple[BudgetPartReport, ...] = Field(default_factory=tuple)
    notes: tuple[str, ...] = Field(default_factory=tuple)
    #: Packet budget does not bound total runtime context.
    runtime_context_unbounded: Literal[True] = True
    prompt_cache_savings_claimed: Literal[False] = False


class ContractBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_id: str = Field(min_length=1, max_length=128)
    contract_digest: str = Field(min_length=8, max_length=128)
    contract_version: int = Field(ge=1)
    repository: str = Field(min_length=1, max_length=512)
    candidate_identity: str | None = Field(default=None, max_length=128)
    objective: str = Field(min_length=1, max_length=2048)
    observable_outcome: str = Field(min_length=1, max_length=2048)
    mutation_paths: tuple[str, ...] = Field(default_factory=tuple)
    scope: tuple[str, ...] = Field(default_factory=tuple)
    exclusions: tuple[str, ...] = Field(default_factory=tuple)
    policy_refs: tuple[str, ...] = Field(default_factory=tuple)
    acceptance_ids: tuple[str, ...] = Field(default_factory=tuple)
    requirement_ids: tuple[str, ...] = Field(default_factory=tuple)


class TaskContextPacket(BaseModel):
    """Machine-readable packet. Content digest excludes observation metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = SCHEMA_VERSION
    package_id: Literal["AS-TASK-CONTEXT-AND-CONTINUITY-001"] = PACKAGE_ID
    packet_id: str = Field(min_length=1, max_length=128)
    content_digest: str = Field(min_length=64, max_length=64)
    contract: ContractBinding
    fragments: tuple[PacketFragment, ...] = Field(default_factory=tuple)
    prior_actions: tuple[PriorAction, ...] = Field(default_factory=tuple)
    uncertainties: tuple[OpenUncertainty, ...] = Field(default_factory=tuple)
    selection_limits: tuple[str, ...] = Field(default_factory=tuple)
    honesty: dict[str, bool] = Field(default_factory=dict)
    truth_boundary: str = TRUTH_BOUNDARY
    # --- report metadata (excluded from content digest) ---
    observation_time: str | None = Field(default=None, max_length=64)
    budget_report: BudgetReport | None = None
    report_metadata: dict[str, Any] = Field(default_factory=dict)
    generated: dict[str, str] = Field(default_factory=dict)


def packet_content_payload(packet: TaskContextPacket | dict[str, Any]) -> dict[str, Any]:
    """Slice used for content identity."""
    raw = packet.model_dump(mode="json") if isinstance(packet, TaskContextPacket) else dict(packet)
    return {
        key: value
        for key, value in raw.items()
        if key not in _DIGEST_EXCLUDE and key != "content_digest"
    }


def content_digest(packet: TaskContextPacket | dict[str, Any]) -> str:
    return sha256_text(_canonical(packet_content_payload(packet)))


def honesty_defaults() -> dict[str, bool]:
    return {
        "packet_is_authority": False,
        "retrieved_is_policy": False,
        "retrieved_widens_mutation_scope": False,
        "continuation_authorizes_resume": False,
        "agent_prose_is_evidence": False,
        "packet_guarantees_live_match": False,
        "prompt_cache_savings_proven": False,
        "incomplete_means_fail_closed_visible": True,
    }
