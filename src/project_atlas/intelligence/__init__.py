"""Atlas 2.0 derived intelligence (read-only, non-authoritative).

Import from this package, not from ``project_atlas.domain``. These types are
not Layer B records and must not be written as canonical truth.
"""

from project_atlas.intelligence.boundary import (
    AUTO_RESOLVE_CONTRADICTIONS,
    CONFIDENCE_SCORE_IS_FACT,
    CONTRADICTION_CANDIDATE_IS_PROVEN_FALSEHOOD,
    DERIVED_INTELLIGENCE_IS_AUTHORITY,
    DERIVED_STATE_WRITES_CANONICAL_TRUTH,
    PACKAGE_INTEL_001,
    PACKAGE_INTEL_002,
    PACKAGE_STATE_001,
    PROJECT_STATE_IS_CANONICAL,
    TRUTH_BOUNDARY_CONTRADICTION,
    TRUTH_BOUNDARY_EVIDENCE,
    TRUTH_BOUNDARY_STATE,
    UNKNOWN_IS_VALID,
)
from project_atlas.intelligence.contradictions import (
    ContradictionCandidate,
    ContradictionClass,
    ContradictionContext,
    SeverityClass,
    TemporalRelationship,
    find_contradiction_candidates,
)
from project_atlas.intelligence.evidence import assess_evidence, assess_evidence_many
from project_atlas.intelligence.types import (
    AssessableClaim,
    AssessmentContext,
    ConfidenceClass,
    EvidenceAssessment,
    EvidenceDimensions,
    EvidenceRef,
    EvidenceRole,
    LimitingFactor,
    LineageIntegrity,
    SourceObservation,
    ValidityWindowInput,
)

__all__ = [
    "AUTO_RESOLVE_CONTRADICTIONS",
    "CONFIDENCE_SCORE_IS_FACT",
    "CONTRADICTION_CANDIDATE_IS_PROVEN_FALSEHOOD",
    "DERIVED_INTELLIGENCE_IS_AUTHORITY",
    "DERIVED_STATE_WRITES_CANONICAL_TRUTH",
    "PACKAGE_INTEL_001",
    "PACKAGE_INTEL_002",
    "PACKAGE_STATE_001",
    "PROJECT_STATE_IS_CANONICAL",
    "TRUTH_BOUNDARY_CONTRADICTION",
    "TRUTH_BOUNDARY_EVIDENCE",
    "TRUTH_BOUNDARY_STATE",
    "UNKNOWN_IS_VALID",
    "AssessableClaim",
    "AssessmentContext",
    "ConfidenceClass",
    "ContradictionCandidate",
    "ContradictionClass",
    "ContradictionContext",
    "EvidenceAssessment",
    "EvidenceDimensions",
    "EvidenceRef",
    "EvidenceRole",
    "LimitingFactor",
    "LineageIntegrity",
    "SeverityClass",
    "SourceObservation",
    "TemporalRelationship",
    "ValidityWindowInput",
    "assess_evidence",
    "assess_evidence_many",
    "find_contradiction_candidates",
]
