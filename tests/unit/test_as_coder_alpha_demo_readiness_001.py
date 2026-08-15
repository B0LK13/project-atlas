"""AS-CODER-ALPHA-DEMO-READINESS-001 — fixture journey, not AUTHENTIC_PILOT."""

from __future__ import annotations

from pathlib import Path

from project_atlas.demo_readiness import HONESTY, STAMPS, run_demo_readiness

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "demo"
    / "estate"
    / "harbor-api"
)


def test_demo_readiness_harbor_journey_is_honest(tmp_path: Path) -> None:
    report = run_demo_readiness(FIXTURE, work_root=tmp_path / "demo")
    assert report["honesty"] == HONESTY
    assert report["honesty"]["commercial_ga"] is False
    assert report["honesty"]["authentic_pilot"] is False
    assert report["demo_readiness"] in {"PASS", "PARTIAL"}
    assert report["checks"]["persistent_identity"] is True
    assert report["checks"]["second_session_continuity"] is True
    assert report["checks"]["cross_project_leak_count"] == 0
    assert report["checks"]["handoff_present"] is True
    assert report["checks"]["context_present"] is True
    assert report["checks"]["obsidian_present"] is True
    for stamp in STAMPS:
        assert stamp in report["stamps"]
    assert "RELEASE" not in report["demo_readiness"]
    assert report.get("commercial_ga") is None


def test_demo_readiness_never_claims_ga(tmp_path: Path) -> None:
    report = run_demo_readiness(FIXTURE, work_root=tmp_path / "demo2")
    dumped = str(report)
    assert "COMMERCIAL_GA" not in dumped or report["honesty"]["commercial_ga"] is False
    assert report["honesty"]["demo_is_release"] is False
