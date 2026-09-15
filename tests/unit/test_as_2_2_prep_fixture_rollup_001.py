"""AS-2.2-PREP-FIXTURE-ROLLUP-001 — docs rollup only (no src mutation)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / "docs" / "atlas-2.2"

DOCS = {
    "rollup": ATLAS / "AS-2.2-PREP-FIXTURE-ROLLUP-001.md",
    "fixture_plan": ATLAS / "FIXTURE-PLAN.md",
    "stubs": ATLAS / "PACKAGE-CONTRACT-STUBS.md",
    "fixtures_readme": ATLAS / "fixtures" / "README.md",
}


def test_rollup_docs_exist_and_name_deepen_wave() -> None:
    for path in DOCS.values():
        assert path.is_file(), path
        text = path.read_text(encoding="utf-8")
        assert "DEEPEN" in text.upper() or "deepen" in text
        assert "fixture-only" in text.lower() or "FIXTURE" in text.upper()


def test_rollup_non_claims() -> None:
    text = DOCS["rollup"].read_text(encoding="utf-8")
    assert "ATLAS_2_1_RELEASE_CERTIFIED" in text
    assert "**NO**" in text
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in text
    assert "Production mutation" in text and "NONE" in text
    assert "do not dual-own" in text.lower() or "do not relocate" in text.lower()


def test_fixture_plan_lists_reality_gap_and_doc_charter_deepen() -> None:
    text = DOCS["fixture_plan"].read_text(encoding="utf-8")
    assert "AS-2.2-REALITY-GAP-DEEPEN-PREP-001" in text
    assert "AS-2.2-DOC-CHARTER-DEEPEN-PREP-001" in text
    assert "Unlock NO" in text


def test_stubs_list_forbidden_action_schemas() -> None:
    text = DOCS["stubs"].read_text(encoding="utf-8")
    assert "forbidden-action" in text
    assert "reality-gap-forbidden-action.schema.json" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED=NO" in text
