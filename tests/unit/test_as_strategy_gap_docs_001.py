"""Strategy docs presence + two-backlog discipline."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRATEGY = ROOT / "docs" / "strategy"


def test_strategy_docs_present() -> None:
    required = [
        "ATLAS-NORTH-STAR-GAP-ANALYSIS.md",
        "ATLAS-GAP-REGISTER.md",
        "ATLAS-2.1-RELEASE-CRITICAL-DAG.md",
        "ATLAS-2.2-EXECUTABLE-ROADMAP.md",
        "ATLAS-2.3-STRATEGIC-BACKLOG.md",
        "ATLAS-3.0-NORTH-STAR-BACKLOG.md",
        "README.md",
    ]
    for name in required:
        assert (STRATEGY / name).is_file(), name


def test_gap_register_separates_backlogs() -> None:
    text = (STRATEGY / "ATLAS-GAP-REGISTER.md").read_text(encoding="utf-8")
    assert "2.1 release-critical" in text
    assert "North-star backlog" in text
    assert "GAP-2.1-001" in text
    assert "RELEASE_BLOCKING" in text
    assert "do not merge" in text.lower() or "Do not merge" in text


def test_gap_analysis_does_not_claim_release_certified() -> None:
    text = (STRATEGY / "ATLAS-NORTH-STAR-GAP-ANALYSIS.md").read_text(encoding="utf-8")
    assert "Do not declare" in text
    assert "RELEASE COMPLETENESS" in text
    assert "AUTHENTIC_ESTATE_ROOT" in text
    assert "ATLAS_2_1_RELEASE_CERTIFIED = YES" not in text


def test_2_2_unlock_after_2_1() -> None:
    text = (STRATEGY / "ATLAS-2.2-EXECUTABLE-ROADMAP.md").read_text(encoding="utf-8")
    assert "ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED" in text
    assert "destabilize 2.1" in text.lower() or "destabilize 2.1" in text
