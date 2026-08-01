"""Source records produced by discovery (B-001; FR-002).

A :class:`SourceRecord` is the manifest entry for one discovered document.
Excluded files remain listed with an explicit exclusion reason; hashing is
streaming SHA-256 (implemented in the discovery work package).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from project_atlas.domain.claims import ID_PATTERN
from project_atlas.domain.vocabulary import ClassificationState

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class RepositoryInfo(BaseModel):
    """Version-control context for a source, when discoverable."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    root: str = Field(min_length=1, description="Repository root as a POSIX path")
    remote: str | None = None


class SourceRecord(BaseModel):
    """Manifest entry for a single discovered source document (FR-002)."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=ID_PATTERN)
    path: str = Field(min_length=1, description="Source path or URI as approved for ingestion")
    media_type: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)
    modified_at: datetime | None = None
    repository: RepositoryInfo | None = None
    likely_project: str | None = Field(default=None, pattern=ID_PATTERN)
    classification_state: ClassificationState = ClassificationState.UNCLASSIFIED
    exclusion_reason: str | None = None

    @model_validator(mode="after")
    def _exclusion_reason_consistency(self) -> SourceRecord:
        if self.classification_state is ClassificationState.EXCLUDED:
            if not self.exclusion_reason:
                raise ValueError("excluded sources must record an exclusion_reason")
        elif self.exclusion_reason is not None:
            raise ValueError("exclusion_reason is only valid for excluded sources")
        return self
