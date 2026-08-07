"""Status-dimension refinement (AS-CORE-004 S3).

Do not apply coarse profile-wide rules. Derive dimensions from:

- subject kind
- structural path
- semantic concept
- profile semantics

Ambiguous ``status`` leaves emit no arbitrary dimension — callers should
preserve provenance and withhold from conflict comparison when needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from project_atlas.domain import SemanticSubject, SemanticSubjectKind, is_semantic_subject_serialized


@dataclass(frozen=True)
class DimensionRefinement:
    """Result of refining a possibly-overloaded field name."""

    field: str
    ambiguous: bool = False
    reason: str | None = None


def _subject_kind(subject: str | None) -> SemanticSubjectKind | None:
    if subject is None:
        return None
    if not is_semantic_subject_serialized(subject):
        return None
    return SemanticSubject.parse(subject).kind


def refine_status_dimension(
    *,
    field: str,
    subject: str | None,
    structural_path: tuple[str, ...] = (),
    profile: str | None = None,
    semantic_concept: str | None = None,
) -> DimensionRefinement:
    """Refine a field when it is a status-like leaf; otherwise return as-is."""
    normalized_field = field.strip()
    path = tuple(str(part) for part in structural_path)
    leaf = path[-1] if path else normalized_field
    parent = path[-2] if len(path) >= 2 else None
    kind = _subject_kind(subject)
    concept = (semantic_concept or normalized_field).replace("_", "-").lower()

    # Non-status fields pass through unchanged.
    if leaf.lower() != "status" and normalized_field.lower() not in {
        "status",
        "roadmap-status",
    }:
        return DimensionRefinement(field=normalized_field)

    # Structural path wins for nested receipt/VERIFY status leaves.
    if parent in {"pytest", "validation"} or (
        len(path) >= 2 and path[0] == "validation" and "pytest" in path
    ):
        return DimensionRefinement(field="test_status")
    if parent in {"review", "verify_disposition", "as_ret_disposition"} or (
        parent and parent.endswith("_disposition")
    ):
        return DimensionRefinement(field="review_status")
    if parent == "merge" or leaf == "merge_status":
        return DimensionRefinement(field="merge_status")
    if parent in {"certification", "certify"}:
        return DimensionRefinement(field="certification_status")
    if parent in {"implementation", "impl"}:
        return DimensionRefinement(field="implementation_status")
    if parent in {"closure", "close"}:
        return DimensionRefinement(field="closure_status")
    if parent in {"verification", "verify"} and kind is not SemanticSubjectKind.REVIEW:
        return DimensionRefinement(field="verification_status")
    if parent in {"experiment"}:
        return DimensionRefinement(field="experiment_status")
    if parent in {"supersession", "superseded"}:
        return DimensionRefinement(field="supersession_status")
    if parent in {"document", "doc"}:
        return DimensionRefinement(field="document_status")

    # Profile + subject-kind semantics for top-level status.
    if kind is SemanticSubjectKind.ADR or profile == "adr":
        return DimensionRefinement(field="decision_status")

    if kind is SemanticSubjectKind.WORK_PACKAGE or profile in {
        "work-package",
        "atlas-receipt",
    }:
        # Package lifecycle status — not automatically implementation_status.
        if concept in {"implementation", "implementation-status"}:
            return DimensionRefinement(field="implementation_status")
        if concept in {"certification", "certification-status"}:
            return DimensionRefinement(field="certification_status")
        return DimensionRefinement(field="package_status")

    if kind is SemanticSubjectKind.REVIEW or profile == "verify-structured":
        return DimensionRefinement(field="review_status")

    if kind is SemanticSubjectKind.ROADMAP_ITEM or profile in {"roadmap", "backlog"}:
        return DimensionRefinement(field="planning_status")

    if kind is SemanticSubjectKind.EXPERIMENT:
        return DimensionRefinement(field="experiment_status")

    if kind is SemanticSubjectKind.DOCUMENT:
        return DimensionRefinement(field="document_status")

    if kind is SemanticSubjectKind.PROJECT and normalized_field == "status":
        # Project-level status is rare; keep explicit rather than inventing.
        return DimensionRefinement(field="package_status")

    # Ambiguous: cannot safely determine dimension.
    return DimensionRefinement(
        field=normalized_field,
        ambiguous=True,
        reason=(
            f"ambiguous status dimension for subject={subject!r} "
            f"path={'.'.join(path) or normalized_field!r} profile={profile!r}"
        ),
    )
