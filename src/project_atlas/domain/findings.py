"""Validation findings produced by quality gates (B-006; FR-012).

Findings are objective, machine-readable records. Severity drives exit
codes via ``validation_exit_code`` (backlog H-010 / AS-H-010).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain.claims import ID_PATTERN
from project_atlas.domain.vocabulary import Severity, ValidationGate


class ValidationFinding(BaseModel):
    """A single quality-gate result tied to a rule and location."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(pattern=ID_PATTERN)
    rule_id: str = Field(
        pattern=ID_PATTERN, description="Stable rule identifier, e.g. link-unresolved"
    )
    severity: Severity
    gate: ValidationGate
    message: str = Field(min_length=1)
    path: str | None = Field(default=None, description="Vault-relative path of the offending note")
    concept_id: str | None = Field(default=None, pattern=ID_PATTERN)
