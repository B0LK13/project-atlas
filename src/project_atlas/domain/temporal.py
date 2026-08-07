"""Temporal claim semantics and current-state dispositions (AS-CORE-005).

Claims remain immutable evidence. Current state is a derived disposition
over those claims. Temporal metadata must not enter Claim Identity v2.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.domain.claims import ID_PATTERN, validate_claim_subject


class TemporalRelationKind(StrEnum):
    """Minimum temporal relations required by the eight real conflict groups."""

    SUPERSEDES = "supersedes"
    REOBSERVES = "reobserves"
    COEXISTS = "coexists"
    PRECEDES = "precedes"


class TemporalEvidenceKind(StrEnum):
    """Which clock underpins a temporal fact (never observation-as-event silently)."""

    SEMANTIC_EVENT = "semantic-event"
    DOCUMENT_DECLARED = "document-declared"
    SOURCE_VERSION = "source-version"
    UNKNOWN = "unknown"


class TemporalStatus(StrEnum):
    """Derived disposition of a claim or subject+field projection."""

    CURRENT = "current"
    HISTORICAL = "historical"
    UNRESOLVED = "unresolved"
    AUTHORITY_PENDING = "authority-pending"


class ResolutionBasis(StrEnum):
    """Why a current/historical disposition was selected (or withheld)."""

    SUPERSEDES = "supersedes"
    LIFECYCLE_PAIR = "lifecycle-pair"
    REOBSERVATION = "reobservation"
    UNRESOLVED_INCOMPARABLE = "unresolved-incomparable"
    UNRESOLVED_SAME_SOURCE_MULTI = "unresolved-same-source-multi"
    UNRESOLVED_AMBIGUOUS = "unresolved-ambiguous"
    AUTHORITY_PENDING = "authority-pending"
    TITLE_COLLAPSE = "title-collapse"
    CYCLIC = "cyclic"
    BRANCHING = "branching"
    DANGLING = "dangling"
    MALFORMED = "malformed"


class TemporalRelation(BaseModel):
    """Directed temporal relation between claim identities."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    kind: TemporalRelationKind
    from_claim_id: str = Field(pattern=ID_PATTERN)
    to_claim_id: str = Field(pattern=ID_PATTERN)
    evidence_kind: TemporalEvidenceKind = TemporalEvidenceKind.UNKNOWN
    rationale: str = Field(min_length=1)


class CurrentStateRecord(BaseModel):
    """Derived current-state projection for one subject+field at a compilation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    project_id: str | None = Field(default=None, pattern=ID_PATTERN)
    subject: str = Field(min_length=1)
    field: str = Field(min_length=1)
    temporal_status: TemporalStatus
    resolution_basis: ResolutionBasis
    current_claim_id: str | None = Field(default=None, pattern=ID_PATTERN)
    historical_claim_ids: tuple[str, ...] = ()
    participating_claim_ids: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)
    compilation_id: str = Field(min_length=1)
    authority_status: str = Field(default="equivalent-or-unaffected", min_length=1)

    @field_validator("subject")
    @classmethod
    def _validate_subject(cls, value: str) -> str:
        return validate_claim_subject(value)
