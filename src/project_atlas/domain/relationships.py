"""Relationships between OKF concepts (`docs/plan.md` section 8, stage 5).

Relationships use vault-relative POSIX paths (or concept IDs) as targets so
the graph can be derived from plain Markdown links without a database.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class RelationType(StrEnum):
    """Known relation kinds; consumers must tolerate unknown values."""

    DEPENDS_ON = "depends_on"
    PROVIDES = "provides"
    RELATED_PROJECT = "related_project"
    PART_OF = "part_of"
    DEPLOYED_TO = "deployed_to"
    VALIDATES = "validates"
    SUPERSEDES = "supersedes"
    REFERENCES = "references"


class Relationship(BaseModel):
    """A typed edge from one concept to another vault resource."""

    model_config = ConfigDict(extra="forbid")

    type: RelationType
    target: str = Field(min_length=1, description="Vault-relative path or concept ID")
    note: str | None = None
