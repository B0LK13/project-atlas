"""AS-PILOT-DEMO-FIXTURE-F1 — DEMO_FIXTURE must not classify as authentic estate.

``pilot_auth_prep.is_fixture_or_temp_marker`` already excludes
``tests/fixtures`` and ``fixtures/pilots``. The repo-root demo estate
``fixtures/demo/`` was omitted, so ``scan_known_pilot_roots`` labeled
those markers FOUND_AUTHENTIC, set ``owner_blocked=False``, and selected
them as ``selected_authentic_root``.

DEMO_FIXTURE != AUTHENTIC_PILOT. Estate availability is not authorization.
This package does not grant merge, wake OPT, or claim AUTHENTIC_PILOT=PASS.
"""

from __future__ import annotations

from pathlib import Path

from project_atlas.pilot_auth_prep import (
    is_fixture_or_temp_marker,
    scan_known_pilot_roots,
)


def _write_marker(root: Path) -> Path:
    root.mkdir(parents=True)
    marker = root / ".atlas-project.yaml"
    marker.write_text("project:\n  id: demo-twin\n", encoding="utf-8")
    return marker


def test_posix_fixtures_demo_marker_is_not_authentic(tmp_path: Path) -> None:
    marker = _write_marker(tmp_path / "repo" / "fixtures" / "demo" / "estate" / "project-a")
    assert is_fixture_or_temp_marker(marker) is True


def test_windows_fixtures_demo_path_is_classified() -> None:
    marker = Path("D:/project-atlas/fixtures/demo/estate/project-a/.atlas-project.yaml")
    assert is_fixture_or_temp_marker(marker) is True


def test_scan_refuses_fixtures_demo_as_selected_authentic_root(tmp_path: Path) -> None:
    demo = tmp_path / "repo" / "fixtures" / "demo" / "estate" / "project-a"
    harbor = tmp_path / "repo" / "tests" / "fixtures" / "demo" / "estate" / "harbor-api"
    _write_marker(demo)
    _write_marker(harbor)
    report = scan_known_pilot_roots(
        candidates=[demo, harbor],
        include_workspace_scan=False,
    )
    assert report["authentic_found"] == 0
    assert report["fixture_or_temp_found"] == 2
    assert report["owner_blocked"] is True
    assert report["escalation_required"] is True
    assert report["selected_authentic_root"] is None
    assert report["authentic_estate_pilot"] is False
    assert report["pilot_pass"] is False
    assert report["wake_event"] == "AUTHENTIC_ESTATE_ROOT_AVAILABLE"
    assert all(row["status"] == "FIXTURE_OR_TEMP" for row in report["fixture_or_temp_sample"])


def test_live_repo_fixtures_demo_still_classified() -> None:
    """Bind the shipped demo estate when present; skip if the tree moved."""
    repo = Path(__file__).resolve().parents[2]
    marker = (
        repo / "fixtures" / "demo" / "estate" / "project-a" / ".atlas-project.yaml"
    )
    if not marker.is_file():
        return
    assert is_fixture_or_temp_marker(marker) is True
    report = scan_known_pilot_roots(
        candidates=[marker.parent],
        include_workspace_scan=False,
    )
    assert report["authentic_found"] == 0
    assert report["owner_blocked"] is True
    assert report["selected_authentic_root"] is None
