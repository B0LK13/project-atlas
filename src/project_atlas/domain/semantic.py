"""Versioned semantic records used by the Core compiler (AS-CORE-002)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain.claims import ID_PATTERN, Claim, ProvenanceReference
from project_atlas.domain.concepts import ConceptRecord
from project_atlas.domain.vocabulary import DocumentLifecycle, KnowledgeState, LifecycleStatus


class VersionedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1


class SourceLifecycleRecord(VersionedRecord):
    source_id: str = Field(pattern=ID_PATTERN)
    path: str = Field(min_length=1)
    sha256: str | None = None
    lifecycle: DocumentLifecycle = DocumentLifecycle.VERIFIED
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    previous_sha256: str | None = None
    renamed_from: str | None = None


class SourceAuthority(VersionedRecord):
    level: KnowledgeState = KnowledgeState.IMPORTED_SOURCE
    reason: str = Field(min_length=1)


class ValidationEvidence(VersionedRecord):
    validation_id: str = Field(pattern=ID_PATTERN)
    summary: str = Field(min_length=1)
    status: str = Field(min_length=1)
    provenance: list[ProvenanceReference] = Field(default_factory=list)


class DecisionRecord(VersionedRecord):
    decision_id: str = Field(pattern=ID_PATTERN)
    title: str = Field(min_length=1)
    status: str = Field(default="unknown", min_length=1)
    claims: list[Claim] = Field(default_factory=list)
    provenance: list[ProvenanceReference] = Field(default_factory=list)


class WorkPackageRecord(VersionedRecord):
    work_package_id: str = Field(pattern=ID_PATTERN)
    title: str = Field(min_length=1)
    status: LifecycleStatus = LifecycleStatus.UNKNOWN
    provenance: list[ProvenanceReference] = Field(default_factory=list)


class AgentEventReference(VersionedRecord):
    event_id: str = Field(pattern=r"^AE-[A-Za-z0-9][A-Za-z0-9._-]*$")
    event_type: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    receipt_id: str = Field(min_length=1)
    source_package: str = Field(min_length=1)


class CoverageRecord(VersionedRecord):
    category: str = Field(min_length=1)
    state: Literal["absent", "partial", "present", "stale", "conflicting"]
    source_ids: list[str] = Field(default_factory=list)


class ProjectRecord(VersionedRecord):
    """Validated project compilation record; unknown facts remain explicit."""

    project_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1)
    portfolio: str | None = None
    lifecycle: LifecycleStatus = LifecycleStatus.UNKNOWN
    generated: bool = True
    sources: list[SourceLifecycleRecord] = Field(default_factory=list)
    authority: list[SourceAuthority] = Field(default_factory=list)
    coverage: list[CoverageRecord] = Field(default_factory=list)
    concepts: list[ConceptRecord] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    agent_events: list[AgentEventReference] = Field(default_factory=list)
    validations: list[ValidationEvidence] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    relationships: list[dict[str, str]] = Field(default_factory=list)
