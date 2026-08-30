"""Source facts — the only inputs an origination proposal may cite.

A ``SourceFact`` is a small, bounded, deterministic pointer into a real
file that already existed in a project's repository before Atlas ran.
Nothing here ever executes project code, calls an LLM, or invents a fact
from prose interpretation -- extraction (``adapter.py``) is regex/JSON
parsing only.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_REL_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class SourceFactKind(StrEnum):
    """Closed vocabulary. A third kind is a deliberate future extension,
    never silently inferred from unstructured prose."""

    AUTHORITATIVE_ROADMAP_ITEM = "AUTHORITATIVE_ROADMAP_ITEM"
    CORROBORATING_SPEC_TEST = "CORROBORATING_SPEC_TEST"


class SourceFact(BaseModel):
    """One deterministic, bounded pointer into real project evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SourceFactKind
    project_id: str = Field(min_length=1, max_length=128)
    location: str = Field(
        min_length=1,
        max_length=256,
        description="Path relative to the project root. Never absolute, never '..'.",
    )
    content_digest: str = Field(
        min_length=64,
        max_length=64,
        description="sha256 of the exact bytes read when this fact was extracted.",
    )
    excerpt: str = Field(
        max_length=1024,
        description="Bounded excerpt for provenance auditing. Never the full file.",
    )
    subject_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Stable structured item identifier for authoritative item facts.",
    )
    subject_digest: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        description="sha256 of the canonical structured roadmap item.",
    )

    @field_validator("project_id")
    @classmethod
    def _project_id(cls, value: str) -> str:
        if not _PROJECT_ID_RE.fullmatch(value):
            raise ValueError("project_id must be a safe identifier")
        return value

    @field_validator("location")
    @classmethod
    def _location(cls, value: str) -> str:
        # IV finding (D-PHASE2A, exact-head c4e1cba1 review): the previous
        # `.lstrip("./")` ran BEFORE the "unsafe" check, so it silently
        # normalized away a leading traversal/absolute marker instead of
        # rejecting it -- "../secret.py" stripped down to "secret.py" and
        # was accepted. Not currently reachable through any production
        # call site (both adapter.py fact constructors always pass an
        # already-root-relative canonical path, never a raw ref), but the
        # field's own documented contract ("Never absolute, never '..'")
        # must hold independent of caller discipline. Fixed: strip at
        # most one exact leading "./" prefix (not a greedy character-set
        # lstrip, which would also mangle a genuine leading-dot path like
        # ".github/workflows"), THEN reject on the untouched remainder --
        # so a real ".." segment or absolute path is always rejected, not
        # normalized away first.
        posix = value.replace("\\", "/")
        if posix.startswith("./"):
            posix = posix[2:]
        if not posix or posix.startswith("/") or ".." in posix.split("/"):
            raise ValueError("location must be a safe relative path")
        if not _REL_PATH_RE.fullmatch(posix):
            raise ValueError("location must be a safe relative path")
        return posix

    @field_validator("content_digest")
    @classmethod
    def _digest(cls, value: str) -> str:
        if not _HASH_RE.fullmatch(value):
            raise ValueError("content_digest must be a sha256 hex digest")
        return value

    @field_validator("subject_id")
    @classmethod
    def _subject_id(cls, value: str | None) -> str | None:
        if value is not None and not _PROJECT_ID_RE.fullmatch(value):
            raise ValueError("subject_id must be a safe identifier")
        return value

    @field_validator("subject_digest")
    @classmethod
    def _subject_digest(cls, value: str | None) -> str | None:
        if value is not None and not _HASH_RE.fullmatch(value):
            raise ValueError("subject_digest must be a sha256 hex digest")
        return value

    @model_validator(mode="after")
    def _authoritative_subject_is_explicit(self) -> SourceFact:
        if self.kind == SourceFactKind.AUTHORITATIVE_ROADMAP_ITEM:
            if self.subject_id is None or self.subject_digest is None:
                raise ValueError(
                    "authoritative roadmap facts require subject_id and subject_digest"
                )
        elif self.subject_id is not None or self.subject_digest is not None:
            raise ValueError("corroborating facts cannot declare an authoritative subject")
        return self
