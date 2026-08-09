"""Source records produced by discovery (B-001; FR-002).

A :class:`SourceRecord` is the manifest entry for one discovered document.
Excluded files remain listed with an explicit exclusion reason; hashing is
streaming SHA-256 (implemented in the discovery work package).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from project_atlas.domain.claims import ID_PATTERN
from project_atlas.domain.vocabulary import ClassificationState
from project_atlas.source_identity import validate_project_uuid

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class RepositoryInfo(BaseModel):
    """Version-control context for a source, when discoverable."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    root: str = Field(min_length=1, description="Repository root as a POSIX path")
    remote: str | None = None


class LineageResolution(BaseModel):
    """Explicit evidence-scoped decision for an ambiguous source slot."""

    model_config = ConfigDict(extra="forbid")

    outcome: Literal["continue_existing", "create_new_generation", "unresolved"]
    authority: Literal["system_proven", "curator_approved"]
    candidate_lineage_ids: list[str] = Field(default_factory=list)
    selected_lineage_id: str | None = Field(default=None, pattern=r"^sline-[A-Za-z0-9]+$")
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent_selection(self) -> LineageResolution:
        if len(self.candidate_lineage_ids) != len(set(self.candidate_lineage_ids)):
            raise ValueError("lineage resolution candidates must be unique")
        if (
            self.selected_lineage_id is not None
            and self.selected_lineage_id not in self.candidate_lineage_ids
        ):
            raise ValueError("selected lineage must be one of the candidates")
        if self.outcome == "continue_existing" and self.selected_lineage_id is None:
            raise ValueError("continue_existing requires selected_lineage_id")
        if self.outcome == "create_new_generation" and self.selected_lineage_id is not None:
            raise ValueError("create_new_generation cannot select an existing lineage")
        if self.outcome == "unresolved" and self.selected_lineage_id is not None:
            raise ValueError("unresolved cannot select a lineage")
        return self


class SourceRecord(BaseModel):
    """Manifest entry for a single discovered source document (FR-002)."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=ID_PATTERN)
    source_lineage_id: str | None = Field(default=None, pattern=r"^sline-[A-Za-z0-9]+$")
    lineage_resolution: LineageResolution | None = None
    project_uuid: str | None = None
    path: str = Field(min_length=1, description="Source path or URI as approved for ingestion")
    media_type: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    size_bytes: int = Field(ge=0)
    modified_at: datetime | None = None
    repository: RepositoryInfo | None = None
    likely_project: str | None = Field(default=None, pattern=ID_PATTERN)
    classification_state: ClassificationState = ClassificationState.UNCLASSIFIED
    exclusion_reason: str | None = None
    # AS-E-006: optional audit of which EXT classify rule fired (rule id string).
    classification_method: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Fired ClassificationRecord.classification_rule; "
            "null when unclassified/excluded"
        ),
    )

    @model_validator(mode="after")
    def _exclusion_reason_consistency(self) -> SourceRecord:
        if self.classification_state is ClassificationState.EXCLUDED:
            if not self.exclusion_reason:
                raise ValueError("excluded sources must record an exclusion_reason")
        elif self.exclusion_reason is not None:
            raise ValueError("exclusion_reason is only valid for excluded sources")
        return self

    @model_validator(mode="after")
    def _classification_method_consistency(self) -> SourceRecord:
        """AS-E-006: method audit is null for unclassified/excluded; optional otherwise."""
        if (
            self.classification_state
            in (ClassificationState.UNCLASSIFIED, ClassificationState.EXCLUDED)
            and self.classification_method is not None
        ):
            raise ValueError(
                "classification_method must be null for unclassified/excluded sources"
            )
        return self

    @model_validator(mode="after")
    def _project_uuid_is_uuidv4(self) -> SourceRecord:
        if self.project_uuid is not None:
            validate_project_uuid(self.project_uuid)
        return self
