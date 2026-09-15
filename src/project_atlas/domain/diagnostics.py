"""Structured diagnostic model (AS-EXT-001A, directive §7.9).

One validated record per diagnostic: unresolved locator, duplicate locator,
ambiguous identity, duplicate YAML key, unknown receipt profile, unknown
structured field, invalid receipt, unsupported source kind, classification
ambiguity, parser failure, alias ambiguity, promotion failure. Diagnostics
reconcile with withheld sources and claims — nothing drops silently.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from project_atlas.domain.parser_output import SourceSpan
from project_atlas.domain.vocabulary import Severity


class DiagnosticCode(StrEnum):
    """Diagnostic taxonomy (directive §7.9)."""

    UNRESOLVED_LOCATOR = "unresolved-locator"
    DUPLICATE_LOCATOR = "duplicate-locator"
    AMBIGUOUS_IDENTITY = "ambiguous-identity"
    DUPLICATE_YAML_KEY = "duplicate-yaml-key"
    UNKNOWN_RECEIPT_PROFILE = "unknown-receipt-profile"
    UNKNOWN_STRUCTURED_FIELD = "unknown-structured-field"
    INVALID_RECEIPT = "invalid-receipt"
    UNSUPPORTED_SOURCE_KIND = "unsupported-source-kind"
    CLASSIFICATION_AMBIGUITY = "classification-ambiguity"
    PARSER_FAILURE = "parser-failure"
    ALIAS_AMBIGUITY = "alias-ambiguity"
    PROMOTION_FAILURE = "promotion-failure"
    SEMANTIC_REFINEMENT_SPLIT = "semantic-refinement-split"


class CanonicalImpact(StrEnum):
    """What the diagnostic means for canonical state (§7.9)."""

    NONE = "none"
    STAGING_ONLY = "staging-only"
    BLOCKED = "blocked"


class Diagnostic(BaseModel):
    """One structured, actionable diagnostic (§7.9). Immutable, no silent drop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    code: DiagnosticCode
    severity: Severity = Severity.ERROR
    source_path: str | None = Field(default=None, min_length=1)
    source_span: SourceSpan = Field(default_factory=SourceSpan)
    parser: str | None = Field(default=None, min_length=1)
    profile: str | None = Field(default=None, min_length=1)
    subject: str | None = Field(default=None, min_length=1)
    field: str | None = Field(default=None, min_length=1)
    locator: str | None = Field(default=None, min_length=1)
    reason: str = Field(min_length=1)
    remediation: str | None = Field(default=None, min_length=1)
    continued: bool = Field(
        description="Whether extraction of independent sources continued"
    )
    canonical_impact: CanonicalImpact = CanonicalImpact.NONE

    @model_validator(mode="after")
    def _safe_source_path(self) -> Diagnostic:
        # Path traversal protection (§8, AT-013): vault-relative paths only.
        if self.source_path is not None:
            path = self.source_path.replace("\\", "/")
            if path.startswith("/") or any(part == ".." for part in path.split("/")):
                raise ValueError("diagnostic source_path must remain within the Vault")
        return self
