"""Versioned semantic records used by the Core compiler (AS-CORE-002)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain.claims import ID_PATTERN, Claim, ProvenanceReference
from project_atlas.domain.concepts import ConceptRecord
from project_atlas.domain.vocabulary import (
    AuthorityLevel,
    ClaimLifecycle,
    DocumentLifecycle,
    KnowledgeState,
    LifecycleStatus,
    ReviewCategory,
    ReviewEntryStatus,
    SourceChangeState,
)


class VersionedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1


class SourceLifecycleRecord(VersionedRecord):
    source_id: str = Field(pattern=ID_PATTERN)
    project_uuid: str | None = None
    source_lineage_id: str | None = Field(default=None, pattern=r"^sline-[A-Za-z0-9]+$")
    lineage_generation: int | None = Field(default=None, ge=1)
    path: str = Field(min_length=1)
    sha256: str | None = None
    document_lifecycle: DocumentLifecycle = DocumentLifecycle.VERIFIED
    source_change_state: SourceChangeState = SourceChangeState.UNCHANGED
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    previous_sha256: str | None = None
    renamed_from: str | None = None
    restored_as: str | None = None
    compatibility_repaired: bool = False
    compatibility_repair_reason: str | None = None

    @property
    def lifecycle(self) -> DocumentLifecycle:
        """Compatibility accessor for callers that read semantic lifecycle."""
        return self.document_lifecycle


class SourceAuthority(VersionedRecord):
    level: KnowledgeState = KnowledgeState.IMPORTED_SOURCE
    reason: str = Field(min_length=1)


class AuthorityRecord(VersionedRecord):
    """Authority classification attached to one source-backed item."""

    authority_id: str = Field(pattern=ID_PATTERN)
    project_id: str = Field(pattern=ID_PATTERN)
    subject_id: str = Field(pattern=ID_PATTERN)
    level: AuthorityLevel
    precedence: int = Field(ge=0)
    reason: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    source_lineage_ids: list[str] = Field(default_factory=list)


class ClaimLifecycleTransition(BaseModel):
    """Immutable, source- or policy-backed lifecycle transition evidence."""

    model_config = ConfigDict(extra="forbid")

    previous_state: ClaimLifecycle
    new_state: ClaimLifecycle
    reason: str = Field(min_length=1)
    reference_ids: list[str] = Field(default_factory=list)
    transition_at: datetime | None = None
    previous_content_sha256: str | None = Field(
        default=None, pattern=r"^[a-fA-F0-9]{64}$"
    )
    new_content_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    related_conflict_id: str | None = Field(default=None, pattern=ID_PATTERN)
    superseded_by_claim_id: str | None = Field(default=None, pattern=ID_PATTERN)


class ClaimLifecycleRecord(VersionedRecord):
    """Persisted claim state, including history across source changes."""

    claim_id: str = Field(pattern=ID_PATTERN)
    project_id: str = Field(pattern=ID_PATTERN)
    lifecycle: ClaimLifecycle
    content_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    source_ids: list[str] = Field(default_factory=list)
    source_lineage_ids: list[str] = Field(default_factory=list)
    previous_content_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    previous_source_ids: list[str] = Field(default_factory=list)
    predecessor_claim_id: str | None = Field(default=None, pattern=ID_PATTERN)
    superseded_by_claim_id: str | None = Field(default=None, pattern=ID_PATTERN)
    created_at: datetime | None = None
    last_observed_at: datetime | None = None
    observation_count: int = Field(default=1, ge=1)
    transitions: list[ClaimLifecycleTransition] = Field(default_factory=list)
    rejection_reason: str | None = None


class ReviewEntry(VersionedRecord):
    """Deterministic queue entry requiring human or follow-up processing."""

    review_id: str = Field(pattern=ID_PATTERN)
    project_id: str = Field(pattern=ID_PATTERN)
    category: ReviewCategory
    subject_id: str = Field(pattern=ID_PATTERN)
    reason: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)
    source_lineage_ids: list[str] = Field(default_factory=list)
    status: ReviewEntryStatus = ReviewEntryStatus.PENDING


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
    authorities: list[AuthorityRecord] = Field(default_factory=list)
    reviews: list[ReviewEntry] = Field(default_factory=list)
    agent_events: list[AgentEventReference] = Field(default_factory=list)
    validations: list[ValidationEvidence] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    relationships: list[dict[str, str]] = Field(default_factory=list)
