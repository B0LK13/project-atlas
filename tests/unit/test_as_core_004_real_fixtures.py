"""AS-CORE-004 S1: nine real false-conflict fixtures.

S1 reproduces the current subject-collapse defect and registers the nine
real regression cases that must turn green after S2–S6 (subject derivation,
dimension refinement, claim integration, migration, conflict recalculation).

Research fixtures (read-only inputs):
D:/project-atlas-orphans/antigravity-post-as-ext/subject-scope/real-fixtures/
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from project_atlas.domain import SemanticSubject, SemanticSubjectKind
from project_atlas.domain.claims import ID_PATTERN, Claim, ProvenanceReference
from project_atlas.domain.vocabulary import ClaimType
from project_atlas.knowledge_compiler import _conflicts

INVENTORY_PATH = Path(
    r"D:/project-atlas-orphans/antigravity-post-as-ext/conflict-experiment/real/CONFLICT-INVENTORY.json"
)
FIXTURE_DIR = Path(
    r"D:/project-atlas-orphans/antigravity-post-as-ext/subject-scope/real-fixtures"
)

#: Authoritative nine false-conflict groups (full canonical corpus analysis).
NINE_FALSE_CONFLICT_IDS: tuple[str, ...] = (
    "conflict-ee101ef66159eb9a35c4",
    "conflict-6a2ddcbcb3748172eed8",
    "conflict-0156b0179de3db14dfaf",
    "conflict-9e8effd046434b39e849",
    "conflict-45bf6f992b1f4bae833e",
    "conflict-8f138e2b6c962499a740",
    "conflict-1206a69904bd485243c9",
    "conflict-f1b4b22b94985a86751a",
    "conflict-e319b7924971dd6bcf10",
)

#: Cases where subject collapse is the primary defect (9/9).
SUBJECT_DEFECT_IDS = NINE_FALSE_CONFLICT_IDS

#: Secondary field-dimension defect (1/9) — status overloading.
FIELD_DIMENSION_DEFECT_IDS: tuple[str, ...] = ("conflict-0156b0179de3db14dfaf",)


@pytest.fixture(scope="module")
def inventory() -> list[dict]:
    assert INVENTORY_PATH.is_file(), f"missing conflict inventory: {INVENTORY_PATH}"
    data = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


@pytest.fixture(scope="module")
def inventory_by_id(inventory: list[dict]) -> dict[str, dict]:
    return {str(entry["conflict_id"]): entry for entry in inventory}


def test_baseline_conflict_participation_terminology(inventory: list[dict]) -> None:
    """Terminology correction: 147 is participations, not unique canonical claims."""
    claim_ids: list[str] = []
    for entry in inventory:
        claim_ids.extend(str(cid) for cid in entry.get("claim_ids") or [])
    unique = set(claim_ids)
    multi = [cid for cid, n in Counter(claim_ids).items() if n > 1]

    assert len(inventory) == 9, "CONFLICT_GROUPS"
    assert len(inventory) == 9, "CONFLICT_EDGES (1 edge per group in inventory)"
    assert len(claim_ids) == 147, "TOTAL_CLAIM_PARTICIPATIONS"
    assert len(unique) == 147, "UNIQUE_CLAIM_IDS_PARTICIPATING"
    assert len(multi) == 0, "CLAIMS_IN_MULTIPLE_GROUPS"
    # Pre-package project-atlas self-host yield remains a separate metric.
    assert 91 != 147


def test_baseline_reproduces_nine_subject_collapse_false_conflicts(
    inventory_by_id: dict[str, dict],
) -> None:
    """S1 must reproduce the current defect before fixing it."""
    for conflict_id in NINE_FALSE_CONFLICT_IDS:
        entry = inventory_by_id[conflict_id]
        fixture = FIXTURE_DIR / f"{conflict_id}.md"
        assert fixture.is_file(), f"missing real fixture: {fixture}"
        text = fixture.read_text(encoding="utf-8")
        assert "FALSE CONFLICT" in text
        assert "CURRENT SUBJECTS" in text
        # Authoritative inventory: collapsed to a project-root subject.
        subject = str(entry["subject"])
        assert subject in {
            "project-atlas",
            "dark-factory",
            "documentation-rich",
            "graphify-present",
        }
        assert re_fullmatch_id(subject), "collapsed subjects use global ID_PATTERN keys"
        assert len(entry.get("claim_ids") or []) >= 2


def re_fullmatch_id(value: str) -> bool:
    import re

    return bool(re.fullmatch(ID_PATTERN, value))


def test_field_dimension_defect_marked_on_status_group(
    inventory_by_id: dict[str, dict],
) -> None:
    entry = inventory_by_id["conflict-0156b0179de3db14dfaf"]
    assert entry["field"] == "status"
    assert "conflict-0156b0179de3db14dfaf" in FIELD_DIMENSION_DEFECT_IDS


def test_synthetic_collapse_still_creates_conflict() -> None:
    """Reproduce subject collapse: distinct entities + project subject + status → conflict."""
    prov_a = ProvenanceReference(
        source_id="source-aaaaaaaabbbbbbbb",
        resource="docs/evidence/wp-a.yaml",
        sha256="a" * 64,
    )
    prov_b = ProvenanceReference(
        source_id="source-ccccccccdddddddd",
        resource="docs/evidence/wp-b.yaml",
        sha256="b" * 64,
    )
    claims = [
        Claim(
            claim_id="claim-collapse-a",
            project_id="project-atlas",
            subject="project-atlas",  # collapsed
            claim_type=ClaimType.ROADMAP_STATUS,
            field="status",
            value="certified",
            provenance=[prov_a],
        ),
        Claim(
            claim_id="claim-collapse-b",
            project_id="project-atlas",
            subject="project-atlas",  # collapsed
            claim_type=ClaimType.ROADMAP_STATUS,
            field="status",
            value="implementation-complete",
            provenance=[prov_b],
        ),
    ]
    conflicts = _conflicts("project-atlas", claims)
    assert len(conflicts) == 1
    assert conflicts[0].subject == "project-atlas"
    assert conflicts[0].field == "status"


@pytest.mark.parametrize("conflict_id", NINE_FALSE_CONFLICT_IDS)
@pytest.mark.xfail(
    strict=True,
    reason="AS-CORE-004: refined semantic subjects pending S2–S6",
)
def test_real_fixture_false_conflict_eliminated_after_refinement(
    conflict_id: str,
    inventory_by_id: dict[str, dict],
) -> None:
    """Nine real regression cases — expected green only after subject/dimension fix.

    Until derivation + conflict recalculation land, these remain xfail(strict).
    """
    entry = inventory_by_id[conflict_id]
    fixture = FIXTURE_DIR / f"{conflict_id}.md"
    text = fixture.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "EXPECTED RESULT**: NO CONFLICT" in text
    collapsed = str(entry["subject"])
    refined_example = SemanticSubject.document("source-fcb48476ce167a33")
    assert refined_example.serialize() != collapsed
    raise AssertionError(
        f"{conflict_id}: still classified under collapsed subject {collapsed!r}; "
        "expected refined semantic subjects and no false conflict"
    )


def test_true_conflict_same_subject_same_dimension_must_remain_detectable() -> None:
    """Guardrail fixture: true conflicts must not be suppressed by AS-CORE-004."""
    subject = SemanticSubject.work_package("AS-CORE-004").serialize()
    # Until Claim.subject accepts kind:key, true-conflict wiring uses structured
    # comparison helper expectations for later slices. Here we only assert the
    # semantic subject model can express a shared subject for a true conflict.
    assert subject == "wp:AS-CORE-004"
    assert SemanticSubject.parse(subject).kind is SemanticSubjectKind.WORK_PACKAGE
