"""AS-CORE-004 S3: status-dimension refinement."""

from __future__ import annotations

from project_atlas.domain import Claim, ProvenanceReference
from project_atlas.domain.vocabulary import ClaimType
from project_atlas.knowledge_compiler import _conflicts
from project_atlas.status_dimensions import refine_status_dimension


def test_same_subject_different_dimensions_no_conflict() -> None:
    subject = "wp:AS-CORE-004"
    prov_a = ProvenanceReference(
        source_id="source-aaaaaaaabbbbbbbb",
        resource="docs/evidence/a.yaml",
        sha256="a" * 64,
    )
    prov_b = ProvenanceReference(
        source_id="source-ccccccccdddddddd",
        resource="docs/evidence/b.yaml",
        sha256="b" * 64,
    )
    claims = [
        Claim(
            claim_id="claim-dim-a",
            project_id="project-atlas",
            subject=subject,
            claim_type=ClaimType.WORK_PACKAGE_STATUS,
            field="package_status",
            value="certified",
            provenance=[prov_a],
        ),
        Claim(
            claim_id="claim-dim-b",
            project_id="project-atlas",
            subject=subject,
            claim_type=ClaimType.WORK_PACKAGE_STATUS,
            field="review_status",
            value="pending",
            provenance=[prov_b],
        ),
    ]
    assert _conflicts("project-atlas", claims) == []


def test_same_subject_same_dimension_incompatible_values_conflict() -> None:
    subject = "wp:AS-CORE-004"
    prov_a = ProvenanceReference(
        source_id="source-aaaaaaaabbbbbbbb",
        resource="docs/evidence/a.yaml",
        sha256="a" * 64,
    )
    prov_b = ProvenanceReference(
        source_id="source-ccccccccdddddddd",
        resource="docs/evidence/b.yaml",
        sha256="b" * 64,
    )
    claims = [
        Claim(
            claim_id="claim-true-a",
            project_id="project-atlas",
            subject=subject,
            claim_type=ClaimType.WORK_PACKAGE_STATUS,
            field="package_status",
            value="certified",
            provenance=[prov_a],
        ),
        Claim(
            claim_id="claim-true-b",
            project_id="project-atlas",
            subject=subject,
            claim_type=ClaimType.WORK_PACKAGE_STATUS,
            field="package_status",
            value="failed",
            provenance=[prov_b],
        ),
    ]
    conflicts = _conflicts("project-atlas", claims)
    assert len(conflicts) == 1
    assert conflicts[0].field == "package_status"


def test_work_package_lifecycle_is_package_status_not_implementation() -> None:
    result = refine_status_dimension(
        field="status",
        subject="wp:AS-EXT-001A",
        structural_path=("status",),
        profile="atlas-receipt",
        semantic_concept="status",
    )
    assert result.field == "package_status"
    assert not result.ambiguous


def test_adr_status_is_decision_status_not_review_status() -> None:
    result = refine_status_dimension(
        field="status",
        subject="adr:ADR-007",
        structural_path=("status",),
        profile="adr",
    )
    assert result.field == "decision_status"


def test_nested_receipt_status_paths() -> None:
    assert (
        refine_status_dimension(
            field="status",
            subject="wp:AS-EXT-001A",
            structural_path=("validation", "pytest", "status"),
            profile="atlas-receipt",
        ).field
        == "test_status"
    )
    assert (
        refine_status_dimension(
            field="status",
            subject="wp:AS-EXT-001A",
            structural_path=("review", "status"),
            profile="atlas-receipt",
        ).field
        == "review_status"
    )
    assert (
        refine_status_dimension(
            field="status",
            subject="wp:AS-EXT-001A",
            structural_path=("merge", "status"),
            profile="atlas-receipt",
        ).field
        == "merge_status"
    )


def test_roadmap_and_backlog_share_planning_status() -> None:
    roadmap = refine_status_dimension(
        field="status",
        subject="doc:source-roadmap",
        profile="roadmap",
    )
    backlog = refine_status_dimension(
        field="status",
        subject="doc:source-backlog",
        profile="backlog",
    )
    # Document kind without roadmap-item → document_status; profile roadmap forces planning.
    assert roadmap.field == "planning_status"
    assert backlog.field == "planning_status"
