"""Project Atlas domain model (Epic B).

Import the record types from here rather than the individual modules:

    from project_atlas.domain import SourceRecord, ConceptRecord, Claim, ...
"""

from project_atlas.domain.claims import Claim, ProvenanceReference
from project_atlas.domain.concepts import (
    ConceptLifecycle,
    ConceptPortfolio,
    ConceptRecord,
    GeneratedMetadata,
    VerificationMetadata,
)
from project_atlas.domain.conflicts import ConflictingClaim, ConflictRecord, ConflictState
from project_atlas.domain.diagnostics import CanonicalImpact, Diagnostic, DiagnosticCode
from project_atlas.domain.findings import ValidationFinding
from project_atlas.domain.parser_output import (
    AmbiguityStatus,
    LocatorConfidence,
    LocatorKind,
    ParserOutput,
    SourceSpan,
)
from project_atlas.domain.relationships import Relationship, RelationType
from project_atlas.domain.semantic import (
    AgentEventReference,
    AuthorityRecord,
    ClaimLifecycleRecord,
    ClaimLifecycleTransition,
    CoverageRecord,
    DecisionRecord,
    ProjectRecord,
    ReviewEntry,
    SourceAuthority,
    SourceLifecycleRecord,
    ValidationEvidence,
    WorkPackageRecord,
)
from project_atlas.domain.source_registry import PathHistoryEntry, SourceLineageRecord
from project_atlas.domain.sources import RepositoryInfo, SourceRecord
from project_atlas.domain.vocabulary import (
    AuthorityLevel,
    ClaimLifecycle,
    ClaimType,
    ClassificationState,
    ConceptType,
    ConfidenceState,
    ConflictType,
    DocumentLifecycle,
    KnowledgeState,
    LifecycleStatus,
    Maturity,
    ReviewCategory,
    ReviewEntryStatus,
    ReviewState,
    Severity,
    SourceChangeState,
    ValidationGate,
)

__all__ = [
    "AgentEventReference",
    "AmbiguityStatus",
    "AuthorityLevel",
    "AuthorityRecord",
    "CanonicalImpact",
    "Claim",
    "ClaimLifecycle",
    "ClaimLifecycleRecord",
    "ClaimLifecycleTransition",
    "ClaimType",
    "ClassificationState",
    "ConceptLifecycle",
    "ConceptPortfolio",
    "ConceptRecord",
    "ConceptType",
    "ConfidenceState",
    "ConflictRecord",
    "ConflictState",
    "ConflictType",
    "ConflictingClaim",
    "CoverageRecord",
    "DecisionRecord",
    "Diagnostic",
    "DiagnosticCode",
    "DocumentLifecycle",
    "GeneratedMetadata",
    "KnowledgeState",
    "LifecycleStatus",
    "LocatorConfidence",
    "LocatorKind",
    "Maturity",
    "ParserOutput",
    "PathHistoryEntry",
    "ProjectRecord",
    "ProvenanceReference",
    "RelationType",
    "Relationship",
    "RepositoryInfo",
    "ReviewCategory",
    "ReviewEntry",
    "ReviewEntryStatus",
    "ReviewState",
    "Severity",
    "SourceAuthority",
    "SourceChangeState",
    "SourceLifecycleRecord",
    "SourceLineageRecord",
    "SourceRecord",
    "SourceSpan",
    "ValidationEvidence",
    "ValidationFinding",
    "ValidationGate",
    "VerificationMetadata",
    "WorkPackageRecord",
]
