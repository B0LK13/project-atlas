"""Parser output contract (AS-EXT-001A, directive §7.2).

One immutable, validated record per parsed statement. Parser output is the
boundary between source-specific parsers and the knowledge compiler: it
carries everything the compiler needs to derive a Claim Identity v2 identity,
but it never calculates final claim identity itself — Claim Identity v2
(`project_atlas.claim_identity`) remains the sole identity contract. There is
intentionally no ``claim_id`` field on these models, and the JSON schema
forbids one.

Model selection rationale (frozen Pydantic v2): existing project convention
(`project_atlas.domain`, strict mypy), built-in boundary validation with
high-quality diagnostics, free JSON-schema generation through the existing
`project_atlas.schema` convention, corpus-scale real volumes (15 claims
today; hundreds-to-low-thousands of records at full success), and a single
modeling convention to maintain. The prototype 100k-object benchmark was not
decision-grade for these volumes.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from project_atlas.domain.claims import ID_PATTERN
from project_atlas.domain.vocabulary import AuthorityLevel, ClaimType


class LocatorKind(StrEnum):
    """How the stable semantic locator was derived (directive §7.2/§7.4/§7.7)."""

    EXPLICIT_ID = "explicit-id"
    SCHEMA_KEY = "schema-key"
    PROJECT_MANIFEST = "project-manifest"
    HEADING = "heading"
    HEADING_PATH = "heading-path"
    YAMLPATH = "yamlpath"
    BLOCK_SCOPED_KEY = "block-scoped-key"
    STRUCTURAL_KEY = "structural-key"


class LocatorConfidence(StrEnum):
    """Durability of the locator (§7.4: numeric sequence indexes are provisional)."""

    STABLE = "stable"
    PROVISIONAL = "provisional"


class AmbiguityStatus(StrEnum):
    """Whether the record is unambiguous, ambiguous, or withheld (§7.7/§7.10)."""

    UNAMBIGUOUS = "unambiguous"
    AMBIGUOUS = "ambiguous"
    WITHHELD = "withheld"


class SourceSpan(BaseModel):
    """1-based line span in the source, where known (directive §7.2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _end_not_before_start(self) -> SourceSpan:
        if (
            self.start_line is not None
            and self.end_line is not None
            and self.end_line < self.start_line
        ):
            raise ValueError("source span end_line must not precede start_line")
        return self


class ParserOutput(BaseModel):
    """One immutable, validated parser record (directive §7.2).

    Never carries final claim identity: identity derivation from these fields
    is exclusively the Claim Identity v2 algorithm in
    `project_atlas.claim_identity`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    parser_id: str = Field(pattern=ID_PATTERN)
    parser_version: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    document_profile: str = Field(min_length=1)
    claim_type: ClaimType
    subject: str = Field(pattern=ID_PATTERN)
    normalized_field: str = Field(min_length=1)
    raw_value: str
    normalized_value: str
    stable_semantic_locator: str = Field(min_length=1)
    locator_kind: LocatorKind
    locator_confidence: LocatorConfidence = LocatorConfidence.STABLE
    source_path: str = Field(min_length=1)
    source_span: SourceSpan = Field(default_factory=SourceSpan)
    structural_context: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Ordered ancestor context segments (heading path or YAML ancestors)",
    )
    authority_hint: AuthorityLevel = AuthorityLevel.INFERRED
    ambiguity_status: AmbiguityStatus = AmbiguityStatus.UNAMBIGUOUS

    @model_validator(mode="after")
    def _safe_source_path(self) -> ParserOutput:
        # Path traversal protection (§8, AT-013): vault-relative paths only.
        path = self.source_path.replace("\\", "/")
        if path.startswith("/") or any(part == ".." for part in path.split("/")):
            raise ValueError("parser output source_path must remain within the Vault")
        return self
