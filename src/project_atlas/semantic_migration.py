"""Semantic subject / dimension migration (AS-CORE-004 S5).

Reuses the existing Claim Identity v2 alias mechanism. Only provable 1:1
refinements may auto-promote aliases. 1:M splits emit
``SEMANTIC_REFINEMENT_SPLIT`` and never auto-alias.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from project_atlas.domain import CanonicalImpact, Diagnostic, DiagnosticCode, Severity
from project_atlas.locator_migration import (
    LocatorMigration,
    MigrationClass,
    RefinedClaimIdentity,
    build_alias_map_payload,
    classify_mapping_set,
)


class SemanticTransitionClass(StrEnum):
    """Claim transition classes for semantic subject/dimension refinement."""

    UNCHANGED = "unchanged"
    PROVABLE_ONE_TO_ONE = "provable-1-1-refinement"
    ONE_TO_MANY_SPLIT = "1-m-split"
    MANY_TO_ONE_COLLAPSE = "m-1-collapse"
    MANY_TO_MANY_AMBIGUITY = "m-m-ambiguity"
    DISCONTINUITY = "discontinuity"
    UNAFFECTED = "unaffected"


@dataclass(frozen=True)
class SemanticTransition:
    """One old claim identity mapped to zero or more refined identities."""

    old_claim_id: str | None
    old_subject: str | None
    old_field: str | None
    new_claim_ids: tuple[str, ...]
    transition: SemanticTransitionClass
    reason: str


def classify_semantic_transition(
    old_claim_id: str | None,
    new_claim_ids: tuple[str, ...] | list[str],
    *,
    old_subject: str | None = None,
    new_subjects: tuple[str, ...] | list[str] = (),
    old_field: str | None = None,
    new_fields: tuple[str, ...] | list[str] = (),
) -> SemanticTransition:
    """Classify one historical claim against its refined successors."""
    new_ids = tuple(sorted(set(new_claim_ids)))
    subjects = tuple(sorted(set(new_subjects)))
    fields = tuple(sorted(set(new_fields)))

    if old_claim_id is None:
        return SemanticTransition(
            old_claim_id=None,
            old_subject=old_subject,
            old_field=old_field,
            new_claim_ids=new_ids,
            transition=SemanticTransitionClass.DISCONTINUITY,
            reason="no stable historical claim identity for semantic refinement",
        )
    if len(new_ids) == 0:
        return SemanticTransition(
            old_claim_id=old_claim_id,
            old_subject=old_subject,
            old_field=old_field,
            new_claim_ids=(),
            transition=SemanticTransitionClass.DISCONTINUITY,
            reason="historical claim has no refined successor",
        )
    if len(new_ids) == 1 and new_ids[0] == old_claim_id:
        subject_changed = bool(subjects) and old_subject not in subjects and old_subject is not None
        field_changed = bool(fields) and old_field not in fields and old_field is not None
        if not subject_changed and not field_changed:
            return SemanticTransition(
                old_claim_id=old_claim_id,
                old_subject=old_subject,
                old_field=old_field,
                new_claim_ids=new_ids,
                transition=SemanticTransitionClass.UNCHANGED,
                reason="claim identity and semantics unchanged",
            )
        # Subject/display refinement without identity change (subject not hashed).
        return SemanticTransition(
            old_claim_id=old_claim_id,
            old_subject=old_subject,
            old_field=old_field,
            new_claim_ids=new_ids,
            transition=SemanticTransitionClass.UNAFFECTED,
            reason="semantic subject refined without Claim Identity v2 change",
        )
    if len(new_ids) == 1:
        return SemanticTransition(
            old_claim_id=old_claim_id,
            old_subject=old_subject,
            old_field=old_field,
            new_claim_ids=new_ids,
            transition=SemanticTransitionClass.PROVABLE_ONE_TO_ONE,
            reason="provable one-to-one semantic refinement",
        )
    return SemanticTransition(
        old_claim_id=old_claim_id,
        old_subject=old_subject,
        old_field=old_field,
        new_claim_ids=new_ids,
        transition=SemanticTransitionClass.ONE_TO_MANY_SPLIT,
        reason=(
            "semantic refinement split: one historical claim maps to multiple "
            "refined subjects/dimensions; no automatic alias promotion"
        ),
    )


def split_diagnostic(transition: SemanticTransition) -> Diagnostic:
    """Schema-compatible diagnostic for a 1:M semantic refinement split."""
    if transition.transition is not SemanticTransitionClass.ONE_TO_MANY_SPLIT:
        raise ValueError("split_diagnostic requires a 1:M transition")
    return Diagnostic(
        code=DiagnosticCode.SEMANTIC_REFINEMENT_SPLIT,
        severity=Severity.WARNING,
        subject=transition.old_subject,
        field=transition.old_field,
        reason=transition.reason,
        remediation=(
            "inspect refined claim ids and promote aliases only after proving "
            "each mapping; do not auto-alias 1:M splits"
        ),
        continued=True,
        canonical_impact=CanonicalImpact.NONE,
    )


def build_semantic_alias_payload(
    project_id: str,
    migrations: tuple[LocatorMigration, ...] | list[LocatorMigration],
    *,
    migrated_at: str,
    source_commits_scanned: int,
) -> tuple[dict[str, Any], tuple[Diagnostic, ...]]:
    """Build alias payload; only 1:1 mappings promote. 1:M → split diagnostics."""
    classes = classify_mapping_set(migrations)
    payload, _discontinuities = build_alias_map_payload(
        project_id,
        migrations,
        migrated_at=migrated_at,
        source_commits_scanned=source_commits_scanned,
    )
    diagnostics: list[Diagnostic] = []
    for old_id, migration_class in sorted(classes.items()):
        if migration_class is MigrationClass.ONE_TO_MANY:
            new_ids = tuple(
                sorted(
                    {
                        identity.claim_id
                        for migration in migrations
                        if migration.old_claim_id == old_id
                        for identity in migration.new
                    }
                )
            )
            transition = SemanticTransition(
                old_claim_id=old_id,
                old_subject=None,
                old_field=None,
                new_claim_ids=new_ids,
                transition=SemanticTransitionClass.ONE_TO_MANY_SPLIT,
                reason=(
                    "semantic refinement split: one historical claim maps to "
                    "multiple refined identities; no automatic alias promotion"
                ),
            )
            diagnostics.append(split_diagnostic(transition))
    return payload, tuple(diagnostics)


__all__ = [
    "RefinedClaimIdentity",
    "SemanticTransition",
    "SemanticTransitionClass",
    "build_semantic_alias_payload",
    "classify_semantic_transition",
    "split_diagnostic",
]
