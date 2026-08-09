"""AS-CORE2-008 tip-safe residual — FR coverage (C8-FR-*).

Contract: gen4-next-wave-parallel-001/AS-CORE2-008-PACKAGE-CONTRACT.md
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.conflict_projections import (
    DUPLICATE_SOURCE_KIND,
    conflict_index_companions,
    conflict_markdown_line,
    conflict_review_reason,
    distinct_source_ids,
    duplicate_source_facet,
    harden_conflict_reviews,
    review_index_companions,
)
from project_atlas.domain import (
    ConflictingClaim,
    ConflictRecord,
    ReviewCategory,
    ReviewEntry,
)
from project_atlas.domain.authority_semantics import (
    ArtifactRole,
    AuthoritativeStateRecord,
    AuthorityDisposition,
    AuthorityDomainId,
)
from project_atlas.domain.conflicts import ConflictState
from project_atlas.indexes import canonical_index_payloads


def _conflict(
    *,
    conflict_id: str = "conflict-demo-001",
    project_id: str = "proj-demo",
    subject: str = "project:demo",
    field: str = "status",
    sides: list[tuple[str, str, str | None]] | None = None,
) -> ConflictRecord:
    if sides is None:
        sides = [
            ("source-a", "alpha", "sline-aaa"),
            ("source-b", "beta", "sline-bbb"),
        ]
    return ConflictRecord(
        conflict_id=conflict_id,
        project_id=project_id,
        subject=subject,
        field=field,
        claims=[
            ConflictingClaim(source_id=sid, claim=value, source_lineage_id=lineage)
            for sid, value, lineage in sides
        ],
        claim_ids=[f"claim-{i}" for i in range(len(sides))],
        source_lineage_ids=sorted(
            {lineage for _sid, _value, lineage in sides if lineage is not None}
        ),
        state=ConflictState.UNRESOLVED,
    )


def _authority(
    *,
    subject: str = "project:demo",
    field: str = "status",
    disposition: AuthorityDisposition = AuthorityDisposition.UNRESOLVED,
) -> AuthoritativeStateRecord:
    return AuthoritativeStateRecord(
        project_id="proj-demo",
        subject=subject,
        field=field,
        authority_domain=AuthorityDomainId.WORK_PACKAGE_DURABLE_TITLE,
        disposition=disposition,
        rule_id="rule-fixture",
        authoritative_role=ArtifactRole.UNKNOWN,
        rationale="fixture disposition for review honesty",
        compilation_id="compile-fixture",
        registry_version=1,
        trust_root="fixture-trust-root",
    )


def test_c8_fr001_helper_module_exposes_projection_api() -> None:
    conflict = _conflict()
    assert duplicate_source_facet(conflict) is not None
    assert conflict_markdown_line(conflict).startswith("- `conflict-demo-001`")
    assert "duplicate-source" in conflict_review_reason(conflict)


def test_c8_fr002_duplicate_source_facet_when_multi_source() -> None:
    conflict = _conflict()
    facet = duplicate_source_facet(conflict)
    assert facet is not None
    assert facet["kind"] == DUPLICATE_SOURCE_KIND
    assert facet["source_ids"] == ["source-a", "source-b"]
    assert facet["source_lineage_ids"] == ["sline-aaa", "sline-bbb"]
    assert distinct_source_ids(conflict) == ("source-a", "source-b")


def test_c8_fr002_same_source_omits_facet_fail_closed() -> None:
    conflict = _conflict(
        sides=[
            ("source-same", "alpha", "sline-aaa"),
            ("source-same", "beta", "sline-aaa"),
        ]
    )
    assert duplicate_source_facet(conflict) is None
    line = conflict_markdown_line(conflict)
    assert DUPLICATE_SOURCE_KIND not in line


def test_c8_fr002_facet_deterministic_replay() -> None:
    conflict = _conflict()
    first = duplicate_source_facet(conflict)
    second = duplicate_source_facet(conflict)
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_c8_fr003_conflict_index_companions() -> None:
    conflict = _conflict()
    payload = conflict.model_dump(mode="json")
    companions = conflict_index_companions([payload])
    assert companions["by_source_id"]["source-a"] == ["conflict-demo-001"]
    assert companions["by_source_id"]["source-b"] == ["conflict-demo-001"]
    assert set(companions["by_source_lineage_id"]["sline-aaa"]) == {"conflict-demo-001"}
    assert companions["by_project_id"]["proj-demo"] == ["conflict-demo-001"]


def test_c8_fr003_indexes_emit_companion_keys(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    conflict_dir = vault / "review" / "conflicts"
    conflict_dir.mkdir(parents=True)
    conflict = _conflict()
    (conflict_dir / "proj-demo.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": "proj-demo",
                "entries": [conflict.model_dump(mode="json")],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    payloads = canonical_index_payloads(vault)
    conflicts_path = vault / "generated" / "indexes" / "conflicts.json"
    assert conflicts_path in payloads
    index = json.loads(payloads[conflicts_path].decode("utf-8"))
    assert "by_source_id" in index
    assert "by_source_lineage_id" in index
    assert "by_project_id" in index
    assert index["by_source_id"]["source-a"] == ["conflict-demo-001"]
    assert index["by_project_id"]["proj-demo"] == ["conflict-demo-001"]
    assert "by_conflict_id" in index
    assert "by_claim_pair" in index


def test_c8_fr004_review_reason_consumes_authority_disposition() -> None:
    conflict = _conflict()
    reason = conflict_review_reason(
        conflict,
        (_authority(disposition=AuthorityDisposition.AUTHORITY_CONFLICT),),
    )
    assert "materially incompatible source-backed claims" in reason
    assert "duplicate-source" in reason
    assert "sources=source-a,source-b" in reason
    assert "authority_disposition=authority-conflict" in reason
    assert "trust_score" not in reason
    assert "confidence_score" not in reason


def test_c8_fr004_harden_conflict_reviews_only() -> None:
    conflict = _conflict()
    reviews = [
        ReviewEntry(
            review_id="review-conflict-1",
            project_id="proj-demo",
            category=ReviewCategory.CONFLICT,
            subject_id=conflict.conflict_id,
            reason="materially incompatible source-backed claims",
            source_ids=["source-a", "source-b"],
        ),
        ReviewEntry(
            review_id="review-pending-1",
            project_id="proj-demo",
            category=ReviewCategory.PENDING_CLAIM,
            subject_id="claim-0",
            reason="claim requires human verification",
            source_ids=["source-a"],
        ),
    ]
    hardened = harden_conflict_reviews(
        reviews,
        [conflict],
        (_authority(disposition=AuthorityDisposition.UNRESOLVED),),
    )
    assert "authority_disposition=unresolved" in hardened[0].reason
    assert hardened[1].reason == "claim requires human verification"


def test_c8_fr005_reviews_index_companion(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    pending = vault / "review" / "pending"
    pending.mkdir(parents=True)
    entry = ReviewEntry(
        review_id="review-conflict-1",
        project_id="proj-demo",
        category=ReviewCategory.CONFLICT,
        subject_id="conflict-demo-001",
        reason="materially incompatible source-backed claims; duplicate-source",
        source_ids=["source-a", "source-b"],
    )
    (pending / "proj-demo.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": "proj-demo",
                "entries": [entry.model_dump(mode="json")],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    payloads = canonical_index_payloads(vault)
    reviews_path = vault / "generated" / "indexes" / "reviews.json"
    assert reviews_path in payloads
    index = json.loads(payloads[reviews_path].decode("utf-8"))
    assert index == review_index_companions([entry.model_dump(mode="json")])
    assert index["by_category"]["conflict"] == ["review-conflict-1"]
    assert index["by_project_id"]["proj-demo"] == ["review-conflict-1"]
    # Must not invent a second durable queue root under review/.
    assert not (vault / "review" / "queue").exists()


def test_c8_fr007_conflict_type_unchanged_materially_incompatible() -> None:
    conflict = _conflict()
    assert conflict.conflict_type.value == "materially-incompatible"
    dumped = conflict.model_dump(mode="json")
    assert dumped["conflict_type"] == "materially-incompatible"


def test_c8_fr012_index_payloads_sort_keys_deterministic(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    (vault / "review" / "conflicts").mkdir(parents=True)
    (vault / "review" / "pending").mkdir(parents=True)
    first = canonical_index_payloads(vault)
    second = canonical_index_payloads(vault)
    assert first == second
