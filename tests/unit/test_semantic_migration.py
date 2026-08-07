"""AS-CORE-004 S5: semantic migration / alias behavior."""

from __future__ import annotations

from project_atlas.domain import DiagnosticCode
from project_atlas.locator_migration import LocatorMigration, RefinedClaimIdentity
from project_atlas.semantic_migration import (
    SemanticTransitionClass,
    build_semantic_alias_payload,
    classify_semantic_transition,
    split_diagnostic,
)


def _identity(claim_id: str, field: str = "package_status") -> RefinedClaimIdentity:
    return RefinedClaimIdentity(
        claim_id=claim_id,
        project_identity="project-atlas",
        source_lineage_id="sline-abc",
        claim_type="work-package-status",
        field=field,
        stable_semantic_locator="yamlpath:status",
        source_commit="7bf974623071ac946ed542fffc84f134887eeae7",
        source_path="docs/evidence/x.yaml",
    )


def test_provable_one_to_one_alias() -> None:
    transition = classify_semantic_transition(
        "claim-old1",
        ["claim-new1"],
        old_subject="project-atlas",
        new_subjects=["wp:AS-EXT-001A"],
        old_field="status",
        new_fields=["package_status"],
    )
    assert transition.transition is SemanticTransitionClass.PROVABLE_ONE_TO_ONE
    payload, diagnostics = build_semantic_alias_payload(
        "project-atlas",
        [
            LocatorMigration(
                old_claim_id="claim-old1",
                old_locator="yamlpath:status",
                new=(_identity("claim-new1"),),
            )
        ],
        migrated_at="2026-08-07T00:00:00Z",
        source_commits_scanned=1,
    )
    assert len(payload["aliases"]) == 1
    assert payload["aliases"][0]["v1_claim_id"] == "claim-old1"
    assert payload["aliases"][0]["v2_claim_id"] == "claim-new1"
    assert diagnostics == ()


def test_one_to_many_split_no_auto_alias() -> None:
    transition = classify_semantic_transition(
        "claim-oldstatus",
        ["claim-wpa", "claim-wpb", "claim-adr"],
        old_subject="project-atlas",
        new_subjects=["wp:A", "wp:B", "adr:ADR-007"],
        old_field="status",
        new_fields=["package_status", "decision_status"],
    )
    assert transition.transition is SemanticTransitionClass.ONE_TO_MANY_SPLIT
    diagnostic = split_diagnostic(transition)
    assert diagnostic.code is DiagnosticCode.SEMANTIC_REFINEMENT_SPLIT
    payload, diagnostics = build_semantic_alias_payload(
        "project-atlas",
        [
            LocatorMigration(
                old_claim_id="claim-oldstatus",
                old_locator="heading:status",
                new=(
                    _identity("claim-wpa"),
                    _identity("claim-wpb"),
                    _identity("claim-adr", field="decision_status"),
                ),
            )
        ],
        migrated_at="2026-08-07T00:00:00Z",
        source_commits_scanned=1,
    )
    assert payload["aliases"] == []
    assert len(diagnostics) == 1
    assert diagnostics[0].code is DiagnosticCode.SEMANTIC_REFINEMENT_SPLIT


def test_subject_only_refinement_unaffected_identity() -> None:
    transition = classify_semantic_transition(
        "claim-same1",
        ["claim-same1"],
        old_subject="project-atlas",
        new_subjects=["doc:source-fcb48476ce167a33"],
        old_field="architecture",
        new_fields=["architecture"],
    )
    assert transition.transition is SemanticTransitionClass.UNAFFECTED


def test_unprovable_mapping_is_discontinuity() -> None:
    transition = classify_semantic_transition(
        "claim-old2",
        [],
        old_subject="project-atlas",
        old_field="status",
    )
    assert transition.transition is SemanticTransitionClass.DISCONTINUITY
