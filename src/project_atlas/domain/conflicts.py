"""Conflict records for contradictory claims (B-005; FR-008).

When two sources disagree, the system must never silently pick a value:
it creates an explicit :class:`ConflictRecord` disclosing the alternatives.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from project_atlas.domain.claims import ID_PATTERN, ProvenanceReference
from project_atlas.domain.vocabulary import ConflictType


class ConflictState(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"


class ConflictingClaim(BaseModel):
    """One side of a contradiction."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=ID_PATTERN)
    source_lineage_id: str | None = Field(default=None, pattern=r"^sline-[A-Za-z0-9]+$")
    claim: str = Field(min_length=1)


class ConflictRecord(BaseModel):
    """Explicit record of incompatible claims about one field (FR-008)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    conflict_id: str = Field(pattern=ID_PATTERN)
    project_id: str | None = Field(default=None, pattern=ID_PATTERN)
    subject: str = Field(pattern=ID_PATTERN, description="Concept ID the conflict is about")
    field: str = Field(min_length=1, description="Field with incompatible claims")
    claims: list[ConflictingClaim] = Field(min_length=2)
    claim_ids: list[str] = Field(default_factory=list)
    source_lineage_ids: list[str] = Field(default_factory=list)
    conflict_type: ConflictType = ConflictType.MATERIALLY_INCOMPATIBLE
    provenance: list[ProvenanceReference] = Field(default_factory=list)
    state: ConflictState = ConflictState.UNRESOLVED
    resolution: str | None = None

    @model_validator(mode="after")
    def _resolution_consistency(self) -> ConflictRecord:
        if self.state is ConflictState.RESOLVED and not self.resolution:
            raise ValueError("resolved conflicts must record a resolution")
        if self.state is ConflictState.UNRESOLVED and self.resolution is not None:
            raise ValueError("unresolved conflicts must not record a resolution")
        return self
