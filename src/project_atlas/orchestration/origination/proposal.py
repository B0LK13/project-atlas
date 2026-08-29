"""The origination proposal contract (D-PHASE2A).

Every field is either copied verbatim from a ``SourceFact`` or computed by
deterministic policy/risk code (``policy.py`` / ``risk.py``). Nothing here
is free-form model prose accepted as authority: ``why_this_work`` /
``why_now`` / ``success_criteria`` are template-filled from structured
facts so the proposal stays reconstructable from ``source_evidence`` alone
with no model in the loop.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.orchestration.origination.facts import SourceFact, SourceFactKind

_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_WORK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class RiskClass(StrEnum):
    """Only O1 is autonomously executable in Phase 2A. Everything else is
    a conservative, structural OWNER_HELD routing, not an LLM judgment
    call."""

    O1_LOW_RISK_SPECIFICATION_BOUND_IMPLEMENTATION = (
        "O1_LOW_RISK_SPECIFICATION_BOUND_IMPLEMENTATION"
    )
    OWNER_HELD = "OWNER_HELD"


class AuthorityClass(StrEnum):
    AUTHORITATIVE = "AUTHORITATIVE"
    CORROBORATING = "CORROBORATING"
    INSUFFICIENT = "INSUFFICIENT"


class EvidenceCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    INTENT_ONLY = "INTENT_ONLY"
    NONE = "NONE"


class ExecutionReadyReason(StrEnum):
    """Closed vocabulary of policy-gate outcomes. See ADR-033 Policy Gate."""

    READY = "READY"
    INSUFFICIENT_ACCEPTANCE_CONTRACT = "INSUFFICIENT_ACCEPTANCE_CONTRACT"
    CONFLICTING_PROJECT_EVIDENCE = "CONFLICTING_PROJECT_EVIDENCE"
    OWNER_HELD_RISK = "OWNER_HELD_RISK"


class Provenance(BaseModel):
    """Enough to prove replay-stability without re-reading the source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_version: str = Field(min_length=1, max_length=32)
    consulted_digests: tuple[str, ...] = Field(min_length=1, max_length=16)


class OriginationProposal(BaseModel):
    """The durable origination-proposal contract (D-PHASE2A)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str = Field(min_length=1, max_length=144)
    project_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    intent: str = Field(min_length=1, max_length=512)
    why_this_work: str = Field(min_length=1, max_length=1024)
    why_now: str = Field(min_length=1, max_length=1024)
    source_evidence: tuple[SourceFact, ...] = Field(min_length=1, max_length=32)
    source_locations: tuple[str, ...] = Field(min_length=1, max_length=32)
    authoritative_source: SourceFact
    acceptance_evidence: tuple[SourceFact, ...] = Field(default_factory=tuple, max_length=32)
    success_criteria: tuple[str, ...] = Field(min_length=1, max_length=32)
    dependencies: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    blockers: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    contradictions: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    proposed_scope: tuple[str, ...] = Field(
        default_factory=tuple,
        max_length=64,
        description="Relative path allow-list. Mirrors WorkNode.mutation_surface.paths.",
    )
    risk_class: RiskClass
    authority_class: AuthorityClass
    evidence_completeness: EvidenceCompleteness
    provenance: Provenance
    origination_identity: str = Field(min_length=64, max_length=64)

    @field_validator("project_id")
    @classmethod
    def _project_id(cls, value: str) -> str:
        if not _PROJECT_ID_RE.fullmatch(value):
            raise ValueError("project_id must be a safe identifier")
        return value

    @field_validator("work_id")
    @classmethod
    def _work_id(cls, value: str) -> str:
        if not _WORK_ID_RE.fullmatch(value):
            raise ValueError("work_id must be a safe identifier")
        return value

    @field_validator("origination_identity")
    @classmethod
    def _identity(cls, value: str) -> str:
        if not re.fullmatch(r"^[0-9a-f]{64}$", value):
            raise ValueError("origination_identity must be a sha256 hex digest")
        return value

    @model_validator(mode="after")
    def _authoritative_source_is_authoritative(self) -> OriginationProposal:
        if self.authoritative_source.kind != SourceFactKind.AUTHORITATIVE_ROADMAP_ITEM:
            raise ValueError("authoritative_source must carry an AUTHORITATIVE_ROADMAP_ITEM fact")
        if self.authoritative_source not in self.source_evidence:
            raise ValueError("authoritative_source must also appear in source_evidence")
        for fact in self.acceptance_evidence:
            if fact.kind != SourceFactKind.CORROBORATING_SPEC_TEST:
                raise ValueError(
                    "acceptance_evidence must carry only CORROBORATING_SPEC_TEST facts"
                )
            if fact not in self.source_evidence:
                raise ValueError("acceptance_evidence facts must also appear in source_evidence")
        return self
