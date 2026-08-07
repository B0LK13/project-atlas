"""AS-CORE-004: nine real false-conflict fixtures + conflict recalculation (S1/S6).

Research fixtures (read-only inputs):
D:/project-atlas-orphans/antigravity-post-as-ext/subject-scope/real-fixtures/
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from project_atlas.domain import SemanticSubject, SemanticSubjectKind
from project_atlas.domain.claims import ID_PATTERN, Claim, ProvenanceReference
from project_atlas.domain.vocabulary import ClaimType
from project_atlas.knowledge_compiler import _conflicts, compile_knowledge

INVENTORY_PATH = Path(
    r"D:/project-atlas-orphans/antigravity-post-as-ext/conflict-experiment/real/CONFLICT-INVENTORY.json"
)
FIXTURE_DIR = Path(
    r"D:/project-atlas-orphans/antigravity-post-as-ext/subject-scope/real-fixtures"
)

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

FIELD_DIMENSION_DEFECT_IDS: tuple[str, ...] = ("conflict-0156b0179de3db14dfaf",)

HASH_A = "a" * 64
HASH_B = "b" * 64


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
    assert len(inventory) == 9, "CONFLICT_EDGES"
    assert len(claim_ids) == 147, "TOTAL_CLAIM_PARTICIPATIONS"
    assert len(unique) == 147, "UNIQUE_CLAIM_IDS_PARTICIPATING"
    assert len(multi) == 0, "CLAIMS_IN_MULTIPLE_GROUPS"
    assert 91 != 147


def test_baseline_inventory_recorded_nine_collapsed_false_conflicts(
    inventory_by_id: dict[str, dict],
) -> None:
    """Historical pre-fix defect evidence (authoritative inventory)."""
    for conflict_id in NINE_FALSE_CONFLICT_IDS:
        entry = inventory_by_id[conflict_id]
        fixture = FIXTURE_DIR / f"{conflict_id}.md"
        assert fixture.is_file(), f"missing real fixture: {fixture}"
        text = fixture.read_text(encoding="utf-8")
        assert "FALSE CONFLICT" in text
        subject = str(entry["subject"])
        assert subject in {
            "project-atlas",
            "dark-factory",
            "documentation-rich",
            "graphify-present",
        }
        assert re.fullmatch(ID_PATTERN, subject)
        assert len(entry.get("claim_ids") or []) >= 2


def _prov(source_id: str, resource: str, digest: str) -> ProvenanceReference:
    return ProvenanceReference(source_id=source_id, resource=resource, sha256=digest)


def _claim(
    claim_id: str,
    subject: str,
    field: str,
    value: str,
    source_id: str,
    digest: str,
    *,
    project_id: str = "project-atlas",
) -> Claim:
    return Claim(
        claim_id=claim_id,
        project_id=project_id,
        subject=subject,
        claim_type=ClaimType.WORK_PACKAGE_STATUS,
        field=field,
        value=value,
        provenance=[_prov(source_id, f"sources/{source_id}.md", digest)],
    )


#: Executable refinements for each of the nine inventory cases.
#: Pattern: collapsed project-subject claims → refined subjects → no conflict.
NINE_REFINED_CASES: dict[str, list[Claim]] = {
    "conflict-ee101ef66159eb9a35c4": [  # architecture
        _claim("claim-arch1", "adr:ADR-007", "architecture", "hexagonal", "source-arch1", HASH_A),
        _claim(
            "claim-arch2",
            "doc:source-guidance",
            "architecture",
            "layered",
            "source-arch2",
            HASH_B,
        ),
    ],
    "conflict-6a2ddcbcb3748172eed8": [  # roadmap
        _claim(
            "claim-road1",
            "doc:source-roadmap-a",
            "planning_status",
            "active",
            "source-road1",
            HASH_A,
        ),
        _claim(
            "claim-road2",
            "doc:source-roadmap-b",
            "planning_status",
            "superseded",
            "source-road2",
            HASH_B,
        ),
    ],
    "conflict-0156b0179de3db14dfaf": [  # status + dimension
        _claim(
            "claim-st1",
            "wp:AS-EXT-001A",
            "package_status",
            "certified",
            "source-st1",
            HASH_A,
        ),
        _claim(
            "claim-st2",
            "wp:AS-CORE-004",
            "package_status",
            "implementation-complete",
            "source-st2",
            HASH_B,
        ),
        _claim(
            "claim-st3",
            "wp:AS-EXT-001A",
            "review_status",
            "pending",
            "source-st3",
            "c" * 64,
        ),
    ],
    "conflict-9e8effd046434b39e849": [  # title
        _claim(
            "claim-t1",
            "doc:source-title-a",
            "title",
            "Final bounded certification remediation",
            "source-t1",
            HASH_A,
        ),
        _claim(
            "claim-t2",
            "doc:source-title-b",
            "title",
            "Lexical Retrieval Index",
            "source-t2",
            HASH_B,
        ),
    ],
    "conflict-45bf6f992b1f4bae833e": [  # validation
        _claim(
            "claim-v1",
            "wp:AS-CORE-003",
            "test_status",
            "passed",
            "source-v1",
            HASH_A,
        ),
        _claim(
            "claim-v2",
            "doc:source-validation-template",
            "test_status",
            "{{result}}",
            "source-v2",
            HASH_B,
        ),
    ],
    "conflict-8f138e2b6c962499a740": [  # work-package
        _claim(
            "claim-wp1",
            "wp:AS-CORE-002",
            "work-package",
            "AS-CORE-002",
            "source-wp1",
            HASH_A,
        ),
        _claim(
            "claim-wp2",
            "wp:AS-GH-001",
            "work-package",
            "AS-GH-001",
            "source-wp2",
            HASH_B,
        ),
    ],
    "conflict-1206a69904bd485243c9": [  # dark-factory roadmap
        _claim(
            "claim-df1",
            "doc:source-df-a",
            "planning_status",
            "alpha-phase",
            "source-df1",
            HASH_A,
            project_id="dark-factory",
        ),
        _claim(
            "claim-df2",
            "doc:source-df-b",
            "planning_status",
            "beta-phase",
            "source-df2",
            HASH_B,
            project_id="dark-factory",
        ),
    ],
    "conflict-f1b4b22b94985a86751a": [  # documentation-rich
        _claim(
            "claim-dr1",
            "doc:source-dr-a",
            "planning_status",
            "certified",
            "source-dr1",
            HASH_A,
            project_id="documentation-rich",
        ),
        _claim(
            "claim-dr2",
            "doc:source-dr-b",
            "planning_status",
            "draft",
            "source-dr2",
            HASH_B,
            project_id="documentation-rich",
        ),
    ],
    "conflict-e319b7924971dd6bcf10": [  # graphify-present architecture
        _claim(
            "claim-gp1",
            "doc:source-gp-a",
            "architecture",
            "Primary architecture evidence.",
            "source-gp1",
            HASH_A,
            project_id="graphify-present",
        ),
        _claim(
            "claim-gp2",
            "doc:source-gp-b",
            "architecture",
            "Secondary architecture evidence.",
            "source-gp2",
            HASH_B,
            project_id="graphify-present",
        ),
    ],
}


@pytest.mark.parametrize("conflict_id", NINE_FALSE_CONFLICT_IDS)
def test_real_fixture_false_conflict_eliminated_after_refinement(
    conflict_id: str,
    inventory_by_id: dict[str, dict],
) -> None:
    """Nine real regression cases: refined subjects/dimensions → no false conflict."""
    entry = inventory_by_id[conflict_id]
    fixture = FIXTURE_DIR / f"{conflict_id}.md"
    text = fixture.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "EXPECTED RESULT**: NO CONFLICT" in text
    claims = NINE_REFINED_CASES[conflict_id]
    project = str(entry["subject"])
    conflicts = _conflicts(project, claims)
    assert conflicts == [], (
        f"{conflict_id}: expected 0 false conflicts after refinement, got {conflicts}"
    )
    # Refined subjects must not collapse to the inventory project root.
    assert all(claim.subject != project for claim in claims)


def test_field_dimension_defect_resolved_for_status_group() -> None:
    claims = NINE_REFINED_CASES["conflict-0156b0179de3db14dfaf"]
    # Same WP, different dimensions, different values → no conflict.
    same_wp = [c for c in claims if c.subject == "wp:AS-EXT-001A"]
    assert {c.field for c in same_wp} >= {"package_status", "review_status"}
    assert _conflicts("project-atlas", same_wp) == []


def test_true_conflict_same_subject_same_dimension_preserved() -> None:
    """TRUE CONFLICT PRESERVED — AS-CORE-004 must not suppress comparison."""
    claims = [
        _claim(
            "claim-true1",
            "wp:AS-CORE-004",
            "package_status",
            "certified",
            "source-true1",
            HASH_A,
        ),
        _claim(
            "claim-true2",
            "wp:AS-CORE-004",
            "package_status",
            "failed",
            "source-true2",
            HASH_B,
        ),
    ]
    conflicts = _conflicts("project-atlas", claims)
    assert len(conflicts) == 1
    assert conflicts[0].subject == "wp:AS-CORE-004"
    assert conflicts[0].field == "package_status"


def test_conflict_recalculation_metrics_summary() -> None:
    """S6 reporting shape: before groups → after false collapse groups."""
    before_groups = 9
    after_false_from_collapse = 0
    true_preserved = 1
    for conflict_id in NINE_FALSE_CONFLICT_IDS:
        assert _conflicts("project-atlas", NINE_REFINED_CASES[conflict_id]) == []
    true_claims = [
        _claim("claim-tA", "wp:AS-CORE-004", "package_status", "a", "sA", HASH_A),
        _claim("claim-tB", "wp:AS-CORE-004", "package_status", "b", "sB", HASH_B),
    ]
    assert len(_conflicts("project-atlas", true_claims)) == true_preserved
    assert before_groups == 9
    assert after_false_from_collapse == 0


def test_end_to_end_compile_removes_collapsed_status_conflict(tmp_path: Path) -> None:
    entries = [
        {
            "source_id": "source-e2e-a",
            "path": "docs/work-packages/AS-EXT-001A.md",
            "classification": "work-package",
            "source": "../../sources/imported-documents/source-e2e-a.md",
            "sha256": HASH_A,
            "text": "# AS-EXT-001A\nStatus: certified\n",
        },
        {
            "source_id": "source-e2e-b",
            "path": "docs/work-packages/AS-CORE-004.md",
            "classification": "work-package",
            "source": "../../sources/imported-documents/source-e2e-b.md",
            "sha256": HASH_B,
            "text": "# AS-CORE-004\nStatus: active\n",
        },
    ]
    bundle = compile_knowledge("project-atlas", entries, tmp_path)
    assert {c.subject for c in bundle.claims} == {"wp:AS-EXT-001A", "wp:AS-CORE-004"}
    assert not bundle.conflicts
