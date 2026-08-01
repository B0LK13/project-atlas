"""Canonical OKF concept records (B-002; FR-006, FR-007).

A :class:`ConceptRecord` is the in-memory form of a Layer-B concept note.
Serialization to Markdown + YAML frontmatter happens in the generation work
package; this model only defines the validated data shape.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain.claims import ID_PATTERN, ProvenanceReference
from project_atlas.domain.relationships import Relationship
from project_atlas.domain.vocabulary import (
    ConceptType,
    KnowledgeState,
    LifecycleStatus,
    Maturity,
    ReviewState,
)


class ConceptRecord(BaseModel):
    """A single atomic OKF concept (project, component, decision, ...)."""

    model_config = ConfigDict(extra="forbid")

    concept_id: str = Field(pattern=ID_PATTERN)
    type: ConceptType
    title: str = Field(min_length=1)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
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
