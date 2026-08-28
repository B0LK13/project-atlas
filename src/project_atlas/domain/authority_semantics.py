"""Domain-specific authority dispositions (AS-CORE-006).

Authority is a derived semantic layer over temporally evaluated claims.
It must not mutate claims, claim identity, or temporal dispositions.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.domain.claims import ID_PATTERN, validate_claim_subject


def _strict_registry_version(value: object) -> object:
    """Reject bool/float encodings that pydantic would coerce to live version 1."""
    if isinstance(value, (bool, float)):
        raise ValueError("registry_version must be an exact integer")
    return value


class AuthorityDisposition(StrEnum):
    """Derived authority outcome for a subject+field projection."""

    AUTHORITATIVE = "authoritative"
    SUBORDINATE = "subordinate"
    UNRESOLVED = "unresolved"
    AUTHORITY_PENDING = "authority-pending"
    AUTHORITY_CONFLICT = "authority-conflict"


class ArtifactRole(StrEnum):
    """Deterministic document/source roles recognized by the registry."""

    PACKAGE_GENESIS_RECEIPT = "package_genesis_receipt"
    REMEDIATION_EPISODE_RECEIPT = "remediation_episode_receipt"
    UNKNOWN = "unknown"


class AuthorityDomainId(StrEnum):
    """Machine-readable authority domains with proven registry rules."""

    WORK_PACKAGE_DURABLE_TITLE = "work_package.durable_title"


class AuthorityEvidence(BaseModel):
    """Why an authority relationship / rule application is justified."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    rule_id: str = Field(min_length=1)
    trust_root: str = Field(min_length=1)
    registry_version: int = Field(ge=1)
    artifact_role: ArtifactRole
    claim_id: str = Field(pattern=ID_PATTERN)
    source_id: str = Field(pattern=ID_PATTERN)
    source_path: str = Field(min_length=1)
    temporal_status: str = Field(min_length=1)
    notes: str = Field(default="", min_length=0)

    @field_validator("registry_version", mode="before")
    @classmethod
    def _registry_version_exact_int(cls, value: object) -> object:
        return _strict_registry_version(value)


class AuthoritativeStateRecord(BaseModel):
    """Derived authoritative-state projection (distinct from temporal current)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    project_id: str | None = Field(default=None, pattern=ID_PATTERN)
    subject: str = Field(min_length=1)
    field: str = Field(min_length=1)
    authority_domain: AuthorityDomainId
    disposition: AuthorityDisposition
    rule_id: str | None = Field(default=None, min_length=1)
    authoritative_claim_id: str | None = Field(default=None, pattern=ID_PATTERN)
    authoritative_value: str | None = Field(default=None, min_length=1)
    authoritative_role: ArtifactRole | None = None
    competing_claim_ids: tuple[str, ...] = ()
    subordinate_claim_ids: tuple[str, ...] = ()
    temporally_ineligible_claim_ids: tuple[str, ...] = ()
    evidence: tuple[AuthorityEvidence, ...] = ()
    rationale: str = Field(min_length=1)
    compilation_id: str = Field(min_length=1)
    registry_version: int = Field(ge=1)
    trust_root: str = Field(min_length=1)

    @field_validator("subject")
    @classmethod
    def _validate_subject(cls, value: str) -> str:
        return validate_claim_subject(value)

    @field_validator("registry_version", mode="before")
    @classmethod
    def _registry_version_exact_int(cls, value: object) -> object:
        return _strict_registry_version(value)
