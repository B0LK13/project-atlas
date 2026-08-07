"""Semantic subject model (AS-CORE-004).

Represents WHAT ENTITY a claim is about, distinct from source provenance
and from the global identifier grammar used for claim_id / source_id.

Claim Identity v2 hashing is unchanged. Global ``ID_PATTERN`` is unchanged.
Semantic subjects use a dedicated ``kind`` + ``key`` model with a bounded
serialization grammar ``<kind>:<key>``.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

#: Maximum length of a semantic subject key (corpus-bounded; security ceiling).
SUBJECT_KEY_MAX_LENGTH: Final[int] = 128

#: Documented ASCII key form for schemas/docs. The runtime validator also
#: accepts Unicode letters after NFC (see :func:`normalize_subject_key`).
SUBJECT_KEY_PATTERN: Final[str] = r"^[0-9A-Za-z][0-9A-Za-z._-]*$"

#: Kind token alternation used in serialization / docs.
_KIND_TOKEN_ALT: Final[str] = (
    "project|wp|adr|doc|review|experiment|roadmap-item|evidence"
)

#: Documented ASCII-oriented serialization pattern for schemas / docs.
SEMANTIC_SUBJECT_PATTERN: Final[str] = (
    rf"^(?:{_KIND_TOKEN_ALT}):[0-9A-Za-z][0-9A-Za-z._-]*$"
)

#: Control characters (C0 + DEL + C1) — rejected in keys.
_CONTROL_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class SemanticSubjectKind(StrEnum):
    """Bounded subject kinds required by supported real sources."""

    PROJECT = "project"
    WORK_PACKAGE = "wp"
    ADR = "adr"
    DOCUMENT = "doc"
    REVIEW = "review"
    EXPERIMENT = "experiment"
    ROADMAP_ITEM = "roadmap-item"
    EVIDENCE_ENTITY = "evidence"


_KIND_BY_TOKEN: Final[dict[str, SemanticSubjectKind]] = {
    kind.value: kind for kind in SemanticSubjectKind
}


class SemanticSubjectError(ValueError):
    """Raised when a semantic subject kind/key pair is invalid."""


def normalize_subject_key(raw: str) -> str:
    """Normalize a subject key under the AS-CORE-004 contract.

    - Unicode NFC normalization
    - Reject empty / whitespace-only / leading-trailing whitespace
    - Reject control characters
    - Reject path separators and kind separators inside the key
    - Enforce length and charset

    Does not case-fold: ``AS-EXT-001A`` and ``as-ext-001a`` remain distinct
    unless a profile explicitly normalizes.
    """
    if not isinstance(raw, str):
        raise SemanticSubjectError("subject key must be a string")
    if raw != raw.strip():
        raise SemanticSubjectError("subject key must not have leading or trailing whitespace")
    if not raw:
        raise SemanticSubjectError("subject key must be non-empty")
    if _CONTROL_RE.search(raw):
        raise SemanticSubjectError("subject key must not contain control characters")
    if "/" in raw or "\\" in raw:
        raise SemanticSubjectError("subject key must not contain path separators")
    if ":" in raw:
        raise SemanticSubjectError("subject key must not contain ':' (kind separator)")
    raw = unicodedata.normalize("NFC", raw)
    if len(raw) > SUBJECT_KEY_MAX_LENGTH:
        raise SemanticSubjectError(
            f"subject key exceeds max length {SUBJECT_KEY_MAX_LENGTH}"
        )
    if not raw[0].isalnum():
        raise SemanticSubjectError(
            "subject key must start with an alphanumeric character"
        )
    for index, char in enumerate(raw):
        if char.isalnum() or (index > 0 and char in "._-"):
            continue
        raise SemanticSubjectError(
            "subject key may contain letters, digits, and interior . _ - only"
        )
    return raw


class SemanticSubject(BaseModel):
    """Structured semantic subject: kind + stable key.

    Downstream code must use ``kind`` / ``key`` fields — not parse meaning
    back from the serialized form, except via :meth:`parse`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: SemanticSubjectKind
    key: str = Field(min_length=1, max_length=SUBJECT_KEY_MAX_LENGTH)

    @field_validator("key")
    @classmethod
    def _validate_key(cls, value: str) -> str:
        return normalize_subject_key(value)

    def serialize(self) -> str:
        """Canonical deterministic serialization ``<kind>:<key>``."""
        return f"{self.kind.value}:{self.key}"

    @classmethod
    def parse(cls, serialized: str) -> SemanticSubject:
        """Parse a canonical serialized subject into structured form."""
        if not isinstance(serialized, str):
            raise SemanticSubjectError("serialized subject must be a string")
        serialized = unicodedata.normalize("NFC", serialized)
        if serialized.count(":") != 1:
            raise SemanticSubjectError(
                "serialized subject must be exactly '<kind>:<key>'"
            )
        kind_token, key = serialized.split(":", 1)
        kind = _KIND_BY_TOKEN.get(kind_token)
        if kind is None:
            raise SemanticSubjectError(f"unsupported subject kind token: {kind_token}")
        return cls(kind=kind, key=key)

    @classmethod
    def project(cls, project_key: str) -> SemanticSubject:
        return cls(kind=SemanticSubjectKind.PROJECT, key=project_key)

    @classmethod
    def work_package(cls, package_id: str) -> SemanticSubject:
        return cls(kind=SemanticSubjectKind.WORK_PACKAGE, key=package_id)

    @classmethod
    def adr(cls, adr_id: str) -> SemanticSubject:
        return cls(kind=SemanticSubjectKind.ADR, key=adr_id)

    @classmethod
    def document(cls, source_uuid: str) -> SemanticSubject:
        """Generic document subject keyed by durable source identity."""
        return cls(kind=SemanticSubjectKind.DOCUMENT, key=source_uuid)

    @classmethod
    def review(cls, review_id: str) -> SemanticSubject:
        return cls(kind=SemanticSubjectKind.REVIEW, key=review_id)

    @classmethod
    def experiment(cls, experiment_id: str) -> SemanticSubject:
        return cls(kind=SemanticSubjectKind.EXPERIMENT, key=experiment_id)

    @classmethod
    def roadmap_item(cls, item_id: str) -> SemanticSubject:
        return cls(kind=SemanticSubjectKind.ROADMAP_ITEM, key=item_id)

    @classmethod
    def evidence_entity(cls, evidence_id: str) -> SemanticSubject:
        return cls(kind=SemanticSubjectKind.EVIDENCE_ENTITY, key=evidence_id)


def is_semantic_subject_serialized(value: object) -> bool:
    """Return True if ``value`` is a valid canonical semantic subject string."""
    if not isinstance(value, str):
        return False
    try:
        SemanticSubject.parse(value)
    except (SemanticSubjectError, ValidationError):
        return False
    return True
