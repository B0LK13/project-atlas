"""Canonical OKF concept records (B-002; FR-006, FR-007).

A :class:`ConceptRecord` is the in-memory form of a Layer-B concept note.
Serialization to Markdown + YAML frontmatter happens in the generation work
package; this model only defines the validated data shape.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.domain.claims import ID_PATTERN, ProvenanceReference
from project_atlas.domain.relationships import Relationship
from project_atlas.domain.vocabulary import (
    ConceptType,
    KnowledgeState,
    LifecycleStatus,
    Maturity,
    ReviewState,
)


class ConceptPortfolio(BaseModel):
    """Optional portfolio metadata exposed by the OKF v0.2 profile."""

    model_config = ConfigDict(extra="forbid")

    domain: str | None = None
    strategic_role: str | None = None
    priority: str | None = None


class ConceptLifecycle(BaseModel):
    """Nested lifecycle view used by OKF notes."""

    model_config = ConfigDict(extra="forbid")

    status: LifecycleStatus = LifecycleStatus.UNKNOWN
    phase: str | None = None
    started: date | None = None


class GeneratedMetadata(BaseModel):
    """Objective generator provenance for an emitted OKF note."""

    model_config = ConfigDict(extra="forbid")

    by: str = Field(min_length=1)
    at: datetime | None = None


class VerificationMetadata(BaseModel):
    """Optional human or system verification provenance."""

    model_config = ConfigDict(extra="forbid")

    by: str | None = None
    at: datetime | None = None


class ConceptRecord(BaseModel):
    """A single atomic OKF concept (project, component, decision, ...)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    concept_id: str = Field(pattern=ID_PATTERN)
    project_id: str | None = Field(default=None, pattern=ID_PATTERN)
    type: ConceptType
    title: str = Field(min_length=1)
    description: str | None = None
    resource: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    portfolio: ConceptPortfolio | None = None
    lifecycle: ConceptLifecycle | None = None
    status: LifecycleStatus = LifecycleStatus.UNKNOWN
    phase: str | None = None
    maturity: Maturity | None = None
    knowledge_state: KnowledgeState = KnowledgeState.INFERRED
    review_state: ReviewState = ReviewState.UNREVIEWED
    started: date | None = None
    stale_after: date | None = None
    sources: list[ProvenanceReference] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    generated_by: str | None = Field(
        default=None, description="Generator identity, e.g. agent:atlas-ingestion"
    )
    generated: GeneratedMetadata | None = None
    verified: VerificationMetadata | None = None

    @field_validator("resource")
    @classmethod
    def _safe_resource(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = value.replace("\\", "/")
        if path.startswith("/") or any(part == ".." for part in path.split("/")):
            raise ValueError("concept resource must remain within the Vault")
        return value
