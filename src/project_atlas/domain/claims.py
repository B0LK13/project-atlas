"""Claims and provenance (B-003, B-004; FR-007).

Core principle: no claim without a traceable source. Every :class:`Claim`
must therefore carry at least one :class:`ProvenanceReference`.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain.vocabulary import ReviewState

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class ProvenanceReference(BaseModel):
    """Pointer from generated knowledge back to its source evidence."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=ID_PATTERN)
    resource: str = Field(min_length=1, description="Vault-relative path or URI of the source")
    title: str | None = None
    author: str | None = None
    last_modified: date | None = None
    locator: str | None = Field(
        default=None, description="Optional section heading, anchor, or line range"
    )


class Claim(BaseModel):
    """A single evidence-backed statement about a concept field."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(pattern=ID_PATTERN)
    subject: str = Field(pattern=ID_PATTERN, description="Concept ID the claim is about")
    field: str = Field(min_length=1, description="Concept field the claim asserts, e.g. status")
    value: str = Field(min_length=1)
    provenance: list[ProvenanceReference] = Field(min_length=1)
    verification: ReviewState = ReviewState.UNREVIEWED
