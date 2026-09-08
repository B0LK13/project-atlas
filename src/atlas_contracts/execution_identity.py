"""AT3-103 — Universal execution identity, v1 (Git/software profile).

One immutable, content-addressed description of *which exact object, under
which observable conditions* an activity ran. Every dimension that the
current runtime cannot observe is an explicit ``UNKNOWN`` — never a
placeholder, never a guess. ``UNKNOWN ENVIRONMENT != OBSERVED ENVIRONMENT``.

This module defines the contract only. It does not shell out to git, read
the environment, or observe anything (that wiring is a later package). It is
domain-neutral at the top level: ``source.kind`` is ``git`` in v1, and the
observation blocks carry a ``status`` so a research or learning profile can
reuse the same envelope later without a second identity system.

Authority: an identity is a reference, not a grant. It carries no merge,
owner, or verification field, and ``extra="forbid"`` refuses any attempt to
smuggle one in.

The shipped JSON schema pins the shape only; the OBSERVED/UNKNOWN consistency
rules and the digest self-verification live in this module.

What is hashed (``identity_digest``): the canonical JSON of the validated
record (``to_record()`` minus ``identity_digest`` and ``run_id``) — field
names by alias, ``Literal`` values as given, tokens as ASCII identifiers,
``tools`` as a JSON array sorted by name (order is validated, not
normalized). No scalar coercion is part of the contract.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationInfo, model_validator

from atlas_contracts.canonical import content_digest, short_id
from atlas_contracts.identity import safe_relative_component
from atlas_contracts.versions import HASH_PATTERN, ID_PATTERN

EXECUTION_IDENTITY_SCHEMA: Final[str] = "atlas.execution-identity.v1"
EXECUTION_IDENTITY_SCHEMA_VERSION: Final[int] = 1
GIT_SHA_PATTERN: Final[str] = r"^[0-9a-f]{40}$"
REPOSITORY_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._@:/-]{0,255}$"
RUN_ID_PREFIX: Final[str] = "run"
VERSION_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$"
_TOKEN_PATTERN: Final[str] = r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$"

ObservationStatus = Literal["OBSERVED", "UNKNOWN"]

_SEAL_CONTEXT_KEY: Final[str] = "atlas_contracts.seal"
_DIGEST_FIELDS: Final[frozenset[str]] = frozenset({"identity_digest", "run_id"})
_GIT_SHA_RE: Final[re.Pattern[str]] = re.compile(GIT_SHA_PATTERN)


class ExecutionIdentityError(ValueError):
    """Fail-closed identity error with a stable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _sealing(info: ValidationInfo) -> bool:
    context = info.context
    return bool(context and context.get(_SEAL_CONTEXT_KEY) is True)


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class GitSource(_Contract):
    """Exact Git object binding. ``candidate_*`` may be absent only together."""

    kind: Literal["git"] = "git"
    repository: str = Field(pattern=REPOSITORY_PATTERN)
    base_head: str = Field(pattern=GIT_SHA_PATTERN)
    base_tree: str = Field(pattern=GIT_SHA_PATTERN)
    candidate_head: str | None = Field(default=None, pattern=GIT_SHA_PATTERN)
    candidate_tree: str | None = Field(default=None, pattern=GIT_SHA_PATTERN)

    @model_validator(mode="after")
    def _candidate_pair(self) -> GitSource:
        if (self.candidate_head is None) != (self.candidate_tree is None):
            raise ExecutionIdentityError(
                "CANDIDATE_OBJECT_INCOMPLETE",
                "candidate_head and candidate_tree must be given together",
            )
        return self


class ToolVersion(_Contract):
    name: str = Field(pattern=ID_PATTERN, max_length=128)
    version: str = Field(pattern=VERSION_PATTERN)


class EnvironmentIdentity(_Contract):
    """Observable host facts only. No container digest, egress, or limits."""

    status: ObservationStatus
    os: str | None = Field(default=None, pattern=_TOKEN_PATTERN)
    arch: str | None = Field(default=None, pattern=_TOKEN_PATTERN)
    python: str | None = Field(default=None, pattern=_TOKEN_PATTERN)

    @model_validator(mode="after")
    def _consistent(self) -> EnvironmentIdentity:
        values = (self.os, self.arch, self.python)
        if self.status == "OBSERVED" and any(v is None for v in values):
            raise ExecutionIdentityError(
                "ENVIRONMENT_OBSERVATION_INCOMPLETE",
                "OBSERVED environment requires os, arch and python",
            )
        if self.status == "UNKNOWN" and any(v is not None for v in values):
            raise ExecutionIdentityError(
                "UNKNOWN_WITH_VALUES",
                "UNKNOWN environment must not carry os/arch/python values",
            )
        return self


class ToolchainIdentity(_Contract):
    status: ObservationStatus
    tools: tuple[ToolVersion, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> ToolchainIdentity:
        if self.status == "OBSERVED" and not self.tools:
            raise ExecutionIdentityError(
                "TOOLCHAIN_OBSERVATION_INCOMPLETE",
                "OBSERVED toolchain requires at least one tool",
            )
        if self.status == "UNKNOWN" and self.tools:
            raise ExecutionIdentityError(
                "UNKNOWN_WITH_VALUES", "UNKNOWN toolchain must not list tools"
            )
        names = [tool.name for tool in self.tools]
        if len(set(names)) != len(names):
            raise ExecutionIdentityError("TOOL_DUPLICATE", "tool names must be unique")
        if names != sorted(names):
            raise ExecutionIdentityError("TOOL_ORDER", "tools must be sorted by name")
        return self


class AgentIdentity(_Contract):
    status: ObservationStatus
    agent_id: str | None = Field(default=None, pattern=ID_PATTERN, max_length=128)
    skill_sha256: str | None = Field(default=None, pattern=HASH_PATTERN)

    @model_validator(mode="after")
    def _consistent(self) -> AgentIdentity:
        if self.status == "OBSERVED" and self.agent_id is None:
            raise ExecutionIdentityError(
                "AGENT_OBSERVATION_INCOMPLETE", "OBSERVED agent requires agent_id"
            )
        if self.status == "UNKNOWN" and (self.agent_id is not None or self.skill_sha256):
            raise ExecutionIdentityError(
                "UNKNOWN_WITH_VALUES", "UNKNOWN agent must not carry agent_id/skill_sha256"
            )
        return self


class ContextIdentity(_Contract):
    status: ObservationStatus
    context_digest: str | None = Field(default=None, pattern=HASH_PATTERN)

    @model_validator(mode="after")
    def _consistent(self) -> ContextIdentity:
        if self.status == "OBSERVED" and self.context_digest is None:
            raise ExecutionIdentityError(
                "CONTEXT_OBSERVATION_INCOMPLETE", "OBSERVED context requires context_digest"
            )
        if self.status == "UNKNOWN" and self.context_digest is not None:
            raise ExecutionIdentityError(
                "UNKNOWN_WITH_VALUES", "UNKNOWN context must not carry context_digest"
            )
        return self


class CapabilitiesIdentity(_Contract):
    status: ObservationStatus
    grant_ref: str | None = Field(default=None, pattern=ID_PATTERN, max_length=128)

    @model_validator(mode="after")
    def _consistent(self) -> CapabilitiesIdentity:
        if self.status == "OBSERVED" and self.grant_ref is None:
            raise ExecutionIdentityError(
                "CAPABILITIES_OBSERVATION_INCOMPLETE", "OBSERVED capabilities require grant_ref"
            )
        if self.status == "UNKNOWN" and self.grant_ref is not None:
            raise ExecutionIdentityError(
                "UNKNOWN_WITH_VALUES", "UNKNOWN capabilities must not carry grant_ref"
            )
        return self


class ExecutionIdentity(_Contract):
    """Content-addressed execution identity. ``identity_digest`` self-verifies."""

    schema_id: Literal["atlas.execution-identity.v1"] = Field(
        default="atlas.execution-identity.v1", alias="schema"
    )
    schema_version: StrictInt = Field(default=1, ge=1, le=1)
    project_id: str = Field(min_length=1, max_length=128)
    source: GitSource
    environment: EnvironmentIdentity
    toolchain: ToolchainIdentity
    agent: AgentIdentity
    context: ContextIdentity
    capabilities: CapabilitiesIdentity
    identity_digest: str = Field(pattern=HASH_PATTERN)
    run_id: str = Field(pattern=r"^run-[0-9a-f]{16}$")

    @model_validator(mode="before")
    @classmethod
    def _seal_placeholders(cls, data: Any, info: ValidationInfo) -> Any:
        """In seal mode the digest fields are computed; refuse caller-supplied ones."""
        if not _sealing(info) or not isinstance(data, Mapping):
            return data
        if any(key in data for key in _DIGEST_FIELDS):
            raise ExecutionIdentityError(
                "DIGEST_SUPPLIED_ON_SEAL", "identity_digest/run_id are computed, not supplied"
            )
        placeholder = "0" * 64
        return {
            **data,
            "identity_digest": placeholder,
            "run_id": short_id(RUN_ID_PREFIX, placeholder),
        }

    @model_validator(mode="after")
    def _verify(self, info: ValidationInfo) -> ExecutionIdentity:
        try:
            safe_relative_component(self.project_id, label="project id")
        except ValueError as exc:
            raise ExecutionIdentityError("UNSAFE_PROJECT_ID", str(exc)) from exc
        if _sealing(info):
            return self
        expected = self.compute_digest()
        if self.identity_digest != expected:
            raise ExecutionIdentityError(
                "IDENTITY_DIGEST_MISMATCH",
                "identity_digest does not match the canonical content",
            )
        if self.run_id != short_id(RUN_ID_PREFIX, expected):
            raise ExecutionIdentityError("RUN_ID_MISMATCH", "run_id is not derived from the digest")
        return self

    def body(self) -> dict[str, Any]:
        """Canonical content without the self-referential digest fields."""
        return self.model_dump(
            mode="json", by_alias=True, exclude=set(_DIGEST_FIELDS), warnings=False
        )

    def compute_digest(self) -> str:
        return content_digest(self.body())

    def to_record(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, warnings=False)

    def candidate_object(self) -> tuple[str, str] | None:
        if self.source.candidate_head is None or self.source.candidate_tree is None:
            return None
        return (self.source.candidate_head, self.source.candidate_tree)

    def bindings(self) -> dict[str, bool]:
        """Which dimensions are actually observed (and therefore bind evidence)."""
        return {
            "object_bound": self.candidate_object() is not None,
            "environment_bound": self.environment.status == "OBSERVED",
            "toolchain_bound": self.toolchain.status == "OBSERVED",
            "agent_bound": self.agent.status == "OBSERVED",
            "context_bound": self.context.status == "OBSERVED",
            "capabilities_bound": self.capabilities.status == "OBSERVED",
        }


def seal_execution_identity(payload: Mapping[str, Any]) -> ExecutionIdentity:
    """Validate an identity body and compute its ``identity_digest`` / ``run_id``."""
    draft = ExecutionIdentity.model_validate(dict(payload), context={_SEAL_CONTEXT_KEY: True})
    digest = draft.compute_digest()
    sealed = draft.model_copy(
        update={"identity_digest": digest, "run_id": short_id(RUN_ID_PREFIX, digest)}
    )
    # Round-trip through strict validation so the sealed object is exactly what
    # a reader will accept (frozen model_copy skips validators).
    return ExecutionIdentity.model_validate(sealed.to_record())


def load_execution_identity(payload: Mapping[str, Any]) -> ExecutionIdentity:
    """Strict read: the payload must carry a matching digest and run_id."""
    return ExecutionIdentity.model_validate(dict(payload))


def is_git_sha(value: str) -> bool:
    return bool(_GIT_SHA_RE.fullmatch(value))


__all__ = [
    "EXECUTION_IDENTITY_SCHEMA",
    "EXECUTION_IDENTITY_SCHEMA_VERSION",
    "GIT_SHA_PATTERN",
    "REPOSITORY_PATTERN",
    "RUN_ID_PREFIX",
    "VERSION_PATTERN",
    "AgentIdentity",
    "CapabilitiesIdentity",
    "ContextIdentity",
    "EnvironmentIdentity",
    "ExecutionIdentity",
    "ExecutionIdentityError",
    "GitSource",
    "ObservationStatus",
    "ToolVersion",
    "ToolchainIdentity",
    "is_git_sha",
    "load_execution_identity",
    "seal_execution_identity",
]
