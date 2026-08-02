"""Canonical AS-ID-001 source-lineage registry records."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.domain.claims import ID_PATTERN
from project_atlas.domain.vocabulary import DocumentLifecycle, SourceChangeState
from project_atlas.source_identity import (
    canonicalize_project_path,
    lineage_id,
    validate_project_uuid,
)

LINEAGE_ID_PATTERN = r"^sline-[A-Za-z0-9]+$"


class PathHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    from_sequence: int = Field(ge=1)
    to_sequence: int | None = Field(default=None, ge=1)

    @field_validator("path")
    @classmethod
    def _canonical_path(cls, value: str) -> str:
        if canonicalize_project_path(value) != value:
            raise ValueError("path history paths must be canonical project-relative paths")
        return value


class SourceLineageRecord(BaseModel):
    """One immutable logical source and its mutable path/lifecycle history."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[2] = 2
    source_id: str = Field(pattern=ID_PATTERN)
    source_lineage_id: str = Field(pattern=LINEAGE_ID_PATTERN)
    lineage_generation: int = Field(ge=1)
    canonical_project_id: str
    first_seen_path: str = Field(min_length=1)
    current_path: str = Field(min_length=1)
    path_history: list[PathHistoryEntry] = Field(default_factory=list)
    first_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    current_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    first_seen_sequence: int = Field(ge=1)
    document_lifecycle: DocumentLifecycle
    source_change_state: SourceChangeState
    renamed_from: str | None = None
    restored_as: str | None = Field(default=None, pattern=LINEAGE_ID_PATTERN)
    supersedes_lineage: str | None = Field(default=None, pattern=LINEAGE_ID_PATTERN)
    superseded_by_lineage: str | None = Field(default=None, pattern=LINEAGE_ID_PATTERN)

    @field_validator("canonical_project_id")
    @classmethod
    def _canonical_project_uuid(cls, value: str) -> str:
        return validate_project_uuid(value)

    @field_validator("first_seen_path", "current_path", "renamed_from")
    @classmethod
    def _canonical_paths(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if canonicalize_project_path(value) != value:
            raise ValueError("source registry paths must be canonical project-relative paths")
        return value

    @model_validator(mode="after")
    def _lineage_id_matches_formula(self) -> SourceLineageRecord:
        expected = lineage_id(
            self.canonical_project_id,
            self.first_seen_path,
            self.first_content_sha256,
            self.lineage_generation,
        )
        if self.source_lineage_id != expected:
            raise ValueError("source_lineage_id does not match the canonical lineage formula")
        return self
