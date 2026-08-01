"""Canonical governed agent-event records."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from atlas_contracts.versions import EVENT_ID_PATTERN, HASH_PATTERN, ID_PATTERN


class EventType(StrEnum):
    SESSION_START = "session-start"
    IMPLEMENTATION = "implementation"
    DECISION = "decision"
    VALIDATION = "validation"
    BLOCKER = "blocker"
    FAILURE = "failure"
    RECOVERY = "recovery"
    COMPLETION = "completion"
    RECEIPT = "receipt"


class AgentEvent(BaseModel):
    """Identity and human-readable payload for one governed event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(pattern=EVENT_ID_PATTERN)
    event_type: EventType
    project_id: str = Field(pattern=ID_PATTERN)
    session_id: str = Field(min_length=1, pattern=ID_PATTERN)
    agent_id: str = Field(min_length=1, pattern=ID_PATTERN)
    adapter_id: str = Field(min_length=1, pattern=ID_PATTERN)
    timestamp: datetime
    work_package_id: str | None = Field(default=None, pattern=ID_PATTERN)
    summary: str = Field(min_length=1, max_length=4000)


class SkillBinding(BaseModel):
    """Skill identity that governed the producing session."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, pattern=ID_PATTERN)
    version: str = Field(min_length=1)
    sha256: str = Field(pattern=HASH_PATTERN)


class VaultIdentity(BaseModel):
    """Logical Vault identity, independent of a physical path."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    vault_id: str = Field(min_length=1, pattern=ID_PATTERN)
    vault_uuid: str = Field(min_length=1)
    name: str | None = None
