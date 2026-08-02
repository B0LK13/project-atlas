"""Controlled vocabularies for the Project Atlas domain model.

The values implement the lifecycle, maturity, and review vocabularies from
`docs/plan.md` sections 5-7. Objective signals are stored instead of
subjective trust scores (authority model, `docs/plan.md` section 6).
"""

from __future__ import annotations

from enum import StrEnum


class ConceptType(StrEnum):
    """OKF concept taxonomy (`docs/plan.md` section 5)."""

    PROJECT = "Project"
    PROJECT_STATUS = "Project Status"
    COMPONENT = "Component"
    ARCHITECTURE = "Architecture"
    CAPABILITY = "Capability"
    DECISION = "Decision"
    REQUIREMENT = "Requirement"
    WORK_PACKAGE = "Work Package"
    MILESTONE = "Milestone"
    VALIDATION = "Validation"
    DEPLOYMENT = "Deployment"
    ENVIRONMENT = "Environment"
    RISK = "Risk"
    ISSUE = "Issue"
    RUNBOOK = "Runbook"
    STANDARD = "Standard"
    REFERENCE = "Reference"
    REPOSITORY = "Repository"
    AGENT_INSTRUCTION = "Agent Instruction"
    DATASET = "Dataset"
    METRIC = "Metric"
    RELEASE = "Release"
    FINDING = "Finding"
    INDEX = "Index"


class LifecycleStatus(StrEnum):
    """Concept lifecycle vocabulary (`docs/plan.md` section 7)."""

    PROPOSED = "proposed"
    PLANNED = "planned"
    ACTIVE = "active"
    BLOCKED = "blocked"
    VALIDATION = "validation"
    OPERATIONAL = "operational"
    MAINTENANCE = "maintenance"
    PAUSED = "paused"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    UNKNOWN = "unknown"


class DocumentLifecycle(StrEnum):
    """Document-level lifecycle vocabulary (`docs/plan.md` section 7)."""

    DRAFT = "draft"
    REVIEW_REQUIRED = "review-required"
    VERIFIED = "verified"
    CANONICAL = "canonical"
    SUPERSEDED = "superseded"
    HISTORICAL = "historical"


class SourceChangeState(StrEnum):
    """Observation state for a discovered source file, not document meaning."""

    NEW = "new"
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    DELETED = "deleted"
    RESTORED = "restored"
    RESTORED_ELSEWHERE = "restored-elsewhere"
    RENAMED = "renamed"


class Maturity(StrEnum):
    """Implementation maturity vocabulary (`docs/plan.md` section 7)."""

    CONCEPT = "concept"
    PROTOTYPE = "prototype"
    MVP = "mvp"
    BETA = "beta"
    PRODUCTION_CANDIDATE = "production-candidate"
    PRODUCTION = "production"
    HARDENED = "hardened"


class KnowledgeState(StrEnum):
    """Authority levels A-E (`docs/plan.md` section 6)."""

    VERIFIED_CANONICAL = "verified-canonical"
    EVIDENCE_BACKED = "evidence-backed"
    IMPORTED_SOURCE = "imported-source"
    INFERRED = "inferred"
    HISTORICAL = "historical"


class AuthorityLevel(StrEnum):
    """Deterministic evidence authority used by AS-CORE-003."""

    PRIMARY = "primary"
    MAINTAINED = "maintained"
    VALIDATED_EXECUTION = "validated-execution"
    GENERATED = "generated"
    INFERRED = "inferred"
    PENDING = "pending"
    CONFLICTING = "conflicting"
    REJECTED = "rejected"


class ClaimLifecycle(StrEnum):
    """Lifecycle states retained for source-backed claims."""

    NEW = "new"
    UNCHANGED = "unchanged"
    UPDATED = "updated"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    STALE = "stale"
    REMOVED_SOURCE = "removed-source"
    RESTORED = "restored"
    REJECTED = "rejected"


class ClaimType(StrEnum):
    """Bounded deterministic claim classes for the first knowledge slice."""

    PROJECT_PURPOSE = "project-purpose"
    ARCHITECTURE = "architecture-statement"
    SETUP_REQUIREMENT = "setup-requirement"
    RUNTIME_DEPENDENCY = "runtime-dependency"
    DEPLOYMENT_TARGET = "deployment-target"
    TEST_RESULT = "test-validation-result"
    ROADMAP_STATUS = "roadmap-status"
    WORK_PACKAGE_STATUS = "work-package-status"
    DECISION = "decision"
    RISK = "risk-blocker"
    OPERATIONAL_INSTRUCTION = "operational-instruction"


class ReviewCategory(StrEnum):
    """Closed categories for governed review queue entries."""

    PENDING_CLAIM = "pending-claim"
    LOW_CONFIDENCE = "low-confidence"
    STALE_OR_SUPERSEDED = "stale-or-superseded"
    CONFLICT = "conflict"
    SUPERSEDED = "superseded"
    STALE = "stale"
    REJECTED = "rejected"


class ReviewEntryStatus(StrEnum):
    """Closed processing states for review queue entries."""

    PENDING = "pending"
    IN_REVIEW = "in-review"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ConflictType(StrEnum):
    """Closed material conflict classifications."""

    MATERIALLY_INCOMPATIBLE = "materially-incompatible"


class ConfidenceState(StrEnum):
    """Objective confidence state; not a subjective trust score."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ReviewState(StrEnum):
    """Human review state for generated knowledge."""

    UNREVIEWED = "unreviewed"
    PENDING_HUMAN_REVIEW = "pending-human-review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ClassificationState(StrEnum):
    """Classification state of a discovered source (FR-002, FR-004)."""

    UNCLASSIFIED = "unclassified"
    CLASSIFIED = "classified"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    """Validation finding severity (drives exit codes in later phases)."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationGate(StrEnum):
    """Quality gate categories (`docs/plan.md` section 16)."""

    STRUCTURAL = "structural"
    PROVENANCE = "provenance"
    CONTENT = "content"
    FRESHNESS = "freshness"
    SECURITY = "security"
