"""Project Atlas domain model (Epic B).

Import the record types from here rather than the individual modules:

    from project_atlas.domain import SourceRecord, ConceptRecord, Claim, ...
"""

from project_atlas.domain.claims import Claim, ProvenanceReference
from project_atlas.domain.concepts import ConceptRecord
from project_atlas.domain.conflicts import ConflictingClaim, ConflictRecord, ConflictState
from project_atlas.domain.findings import ValidationFinding
from project_atlas.domain.relationships import Relationship, RelationType
from project_atlas.domain.sources import RepositoryInfo, SourceRecord
from project_atlas.domain.vocabulary import (
    ClassificationState,
    ConceptType,
    DocumentLifecycle,
    KnowledgeState,
    LifecycleStatus,
    Maturity,
    ReviewState,
    Severity,
    ValidationGate,
)

__all__ = [
    "Claim",
    "ClassificationState",
    "ConceptRecord",
    "ConceptType",
    "ConflictRecord",
    "ConflictState",
    "ConflictingClaim",
    "DocumentLifecycle",
    "KnowledgeState",
    "LifecycleStatus",
    "Maturity",
    "ProvenanceReference",
    "RelationType",
    "Relationship",
    "RepositoryInfo",
    "ReviewState",
    "Severity",
    "SourceRecord",
    "ValidationFinding",
    "ValidationGate",
]
