"""Claims and provenance (B-003, B-004; FR-007).

Core principle: no claim without a traceable source. Every :class:`Claim`
must therefore carry at least one :class:`ProvenanceReference`.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.domain.vocabulary import (
    AuthorityLevel,
    ClaimLifecycle,
    ClaimType,
    ConfidenceState,
    ReviewState,
)

ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class ProvenanceReference(BaseModel):
    """Pointer from generated knowledge back to its source evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    source_id: str = Field(pattern=ID_PATTERN)
    source_lineage_id: str | None = Field(default=None, pattern=r"^sline-[A-Za-z0-9]+$")
    project_id: str | None = Field(default=None, pattern=ID_PATTERN)
    resource: str = Field(min_length=1, description="Vault-relative path or URI of the source")
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    receipt_id: str | None = Field(default=None, min_length=1)
    title: str | None = None
    author: str | None = None
    last_modified: date | None = None
    locator: str | None = Field(
        default=None, description="Optional section heading, anchor, or line range"
    )

    @field_validator("resource")
    @classmethod
    def _safe_resource(cls, value: str) -> str:
        path = value.replace("\\", "/")
        if path.startswith("/") or any(part == ".." for part in path.split("/")):
            raise ValueError("provenance resource must remain within the Vault")
        return value


class Claim(BaseModel):
    """A single evidence-backed statement about a concept field."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    claim_id: str = Field(pattern=ID_PATTERN)
    project_id: str | None = Field(default=None, pattern=ID_PATTERN)
    source_lineage_id: str | None = Field(default=None, pattern=r"^sline-[A-Za-z0-9]+$")
    subject: str = Field(pattern=ID_PATTERN, description="Concept ID the claim is about")
    claim_type: ClaimType = ClaimType.PROJECT_PURPOSE
    field: str = Field(min_length=1, description="Concept field the claim asserts, e.g. status")
    value: str = Field(min_length=1)
    normalized_text: str | None = Field(default=None, min_length=1)
    provenance: list[ProvenanceReference] = Field(min_length=1)
    source_hashes: list[str] = Field(default_factory=list)
    authority: AuthorityLevel = AuthorityLevel.INFERRED
    confidence: ConfidenceState = ConfidenceState.UNKNOWN
    lifecycle: ClaimLifecycle = ClaimLifecycle.NEW
    extraction_method: str = Field(default="manual", min_length=1)
    verification: ReviewState = ReviewState.UNREVIEWED
    predecessor_claim_id: str | None = Field(default=None, pattern=ID_PATTERN)

    def model_post_init(self, __context: object) -> None:
        if self.normalized_text is None:
            object.__setattr__(self, "normalized_text", self.value.strip())
        if not self.source_hashes:
            object.__setattr__(
                self,
                "source_hashes",
                sorted({ref.sha256 for ref in self.provenance if isinstance(ref.sha256, str)}),
            )
