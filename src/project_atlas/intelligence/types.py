"""Public conceptual types for Atlas 2.0 derived intelligence.

These types are in-memory only. They are not Layer B records and are not
registered in the canonical schema catalog (no schema migration).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.domain import (
    AuthorityLevel,
    Claim,
    ClaimLifecycle,
    ConfidenceState,
    ProvenanceReference,
)
from project_atlas.intelligence.boundary import GENERATED_BY


class ConfidenceClass(StrEnum):
    """Discrete explainable confidence. Not a probability."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class LimitingFactor(StrEnum):
    """Why confidence is limited. Empty list does not mean authority."""

    MISSING_PROVENANCE = "missing-provenance"
    MISSING_SOURCE = "missing-source"
    UNKNOWN_PROVENANCE = "unknown-provenance"
    SINGLE_SOURCE = "single-source"
    SAME_LINEAGE_ONLY = "same-lineage-only"
    LINEAGE_INTEGRITY_UNKNOWN = "lineage-integrity-unknown"
    LINEAGE_INTEGRITY_BROKEN = "lineage-integrity-broken"
    AUTHORITY_WEAK = "authority-weak"
    AUTHORITY_MISMATCH = "authority-mismatch"
    AUTHORITY_DISAGREEMENT = "authority-disagreement"
    TEMPORAL_STALE = "temporal-stale"
    TEMPORAL_NOT_YET_VALID = "temporal-not-yet-valid"
    TEMPORAL_UNKNOWN = "temporal-unknown"
    CONTRADICTORY_EVIDENCE = "contradictory-evidence"
    MISSING_EVIDENCE = "missing-evidence"
    CLAIM_IDENTITY_UNSTABLE = "claim-identity-unstable"
    UNSUPPORTED_CLAIM = "unsupported-claim"
    UNKNOWN_CLAIM = "unknown-claim"
    REPEATED_SAME_SOURCE = "repeated-same-source"
    INDEPENDENCE_UNKNOWN = "independence-unknown"
    IDENTITY_AMBIGUOUS = "identity-ambiguous"


class EvidenceRole(StrEnum):
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"
    UNKNOWN = "unknown"


class LineageIntegrity(StrEnum):
    OK = "ok"
    UNKNOWN = "unknown"
    BROKEN = "broken"


_STRONG_AUTHORITY = frozenset(
    {
        AuthorityLevel.PRIMARY,
        AuthorityLevel.MAINTAINED,
        AuthorityLevel.VALIDATED_EXECUTION,
    }
)
_WEAK_AUTHORITY = frozenset({AuthorityLevel.GENERATED, AuthorityLevel.INFERRED})
_MISMATCH_AUTHORITY = frozenset({AuthorityLevel.CONFLICTING, AuthorityLevel.REJECTED})


class EvidenceRef(BaseModel):
    """Pointer back to evidence. Never embeds secret material."""

    model_config = ConfigDict(extra="forbid")

    source_id: str | None = None
    source_lineage_id: str | None = None
    resource: str | None = None
    sha256: str | None = None
    claim_id: str | None = None
    role: EvidenceRole = EvidenceRole.UNKNOWN


class EvidenceDimensions(BaseModel):
    """Explainable signals. Independence is never inferred from path."""

    model_config = ConfigDict(extra="forbid")

    source_presence: Literal["present", "missing", "unknown"] = "unknown"
    distinct_lineage_count: int = Field(ge=0)
    distinct_source_count: int = Field(ge=0)
    repeated_same_source: bool = False
    durable_identity_preserved_after_move: bool = False
    lineage_integrity: LineageIntegrity = LineageIntegrity.UNKNOWN
    independence_known: bool = False
    authority_class: str = "unknown"
    authority_disagreement: bool = False
    temporal_applicability: str = "unspecified"
    claim_identity_stable: bool = True
    corroborating_lineage_count: int = Field(ge=0)
    contradicting_peer_count: int = Field(ge=0)
    provenance_complete: bool = False
    observation_recency_known: bool = False


class AssessableClaim(BaseModel):
    """Claim-shaped input that may represent incomplete / unknown evidence.

    :class:`~project_atlas.domain.Claim` requires at least one provenance
    reference. Assessment must still be honest when provenance is missing,
    so this DTO is the public assessment input. It never writes back.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    project_id: str | None = None
    subject: str
    field: str
    value: str
    normalized_text: str | None = None
    provenance: tuple[ProvenanceReference, ...] = ()
    source_lineage_id: str | None = None
    authority: AuthorityLevel | None = None
    confidence: ConfidenceState | None = None
    lifecycle: ClaimLifecycle | None = None
    predecessor_claim_id: str | None = None
    source_hashes: tuple[str, ...] = ()
    claim_type: str | None = None

    @classmethod
    def from_claim(cls, claim: Claim) -> AssessableClaim:
        return cls(
            claim_id=claim.claim_id,
            project_id=claim.project_id,
            subject=claim.subject,
            field=claim.field,
            value=claim.value,
            normalized_text=claim.normalized_text,
            provenance=tuple(claim.provenance),
            source_lineage_id=claim.source_lineage_id,
            authority=claim.authority,
            confidence=claim.confidence,
            lifecycle=claim.lifecycle,
            predecessor_claim_id=claim.predecessor_claim_id,
            source_hashes=tuple(claim.source_hashes),
            claim_type=claim.claim_type.value,
        )


class SourceObservation(BaseModel):
    """Declared source inventory row used by assessment. Absence is explicit."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_lineage_id: str | None = None
    present: bool = True
    deleted: bool = False
    path_moved: bool = False
    current_path: str | None = None
    first_seen_path: str | None = None
    lineage_integrity: LineageIntegrity = LineageIntegrity.UNKNOWN
    observation_count: int = Field(default=1, ge=1)


class ValidityWindowInput(BaseModel):
    """Document-declared valid-time for one claim. Missing bounds stay unknown."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    valid_from: str | None = None
    valid_to: str | None = None
    evidence_kind: str = "unknown"


class AssessmentContext(BaseModel):
    """Read-only evaluation context. ``sources is None`` means presence unknown."""

    model_config = ConfigDict(extra="forbid")

    as_of_valid_time: str | None = None
    sources: tuple[SourceObservation, ...] | None = None
    peer_claims: tuple[AssessableClaim, ...] = ()
    validity_windows: tuple[ValidityWindowInput, ...] = ()
    identity_ambiguous: bool = False


class EvidenceAssessment(BaseModel):
    """Derived evidence-quality result. Not authority. Not a probability."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-2.0-INTEL-001"] = "AS-2.0-INTEL-001"
    claim_id: str
    project_id: str | None = None
    subject: str
    field: str
    confidence_class: ConfidenceClass
    confidence_reasons: tuple[str, ...]
    limiting_factors: tuple[LimitingFactor, ...]
    supporting_evidence: tuple[EvidenceRef, ...]
    contradicting_evidence: tuple[EvidenceRef, ...]
    unknown_factors: tuple[str, ...]
    as_of_valid_time: str | None = None
    evaluation_context: Literal["as-of-valid-time", "unspecified-valid-time"]
    dimensions: EvidenceDimensions
    provenance_links: tuple[str, ...]
    truth_boundary: str
    generated: Mapping[str, str] = Field(default_factory=lambda: {"by": GENERATED_BY})
    authority_note: Literal["derived-not-authoritative"] = "derived-not-authoritative"


def coerce_claim(claim: Claim | AssessableClaim) -> AssessableClaim:
    if isinstance(claim, AssessableClaim):
        return claim
    return AssessableClaim.from_claim(claim)


def coerce_claims(claims: Sequence[Claim | AssessableClaim]) -> tuple[AssessableClaim, ...]:
    return tuple(coerce_claim(item) for item in claims)
