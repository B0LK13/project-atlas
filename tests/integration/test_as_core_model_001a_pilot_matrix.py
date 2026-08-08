"""AS-CORE-MODEL-001A — pilot maturity-matrix differentiation (integration)."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.portfolio import build_portfolio

PILOTS = Path("tests/fixtures/pilots")
EXPECTED = Path("tests/fixtures/expected/portfolio/maturity-matrix.json")
_REFERENCE_DATE = datetime(2026, 4, 1, tzinfo=UTC)


def _run_pipeline(source: Path, tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    manifest = tmp_path / "manifest.json"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    build_portfolio(vault, reference_date=_REFERENCE_DATE)
    return vault


def test_pilot_maturity_matrix_is_differentiated_and_matches_golden(tmp_path: Path) -> None:
    """Contract acceptance §7 — nebula non-unknown; conflicted dark-factory unknown."""
    source = tmp_path / "pilots"
    shutil.copytree(PILOTS, source)
    vault = _run_pipeline(source, tmp_path)
    actual = json.loads(
        (vault / "generated" / "portfolio" / "maturity-matrix.json").read_text(encoding="utf-8")
    )
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["projects"]["nebula"]["maturity"] == "beta"
    assert actual["projects"]["nebula"]["maturity"] != "unknown"
    assert actual["projects"]["dark-factory"]["maturity"] == "unknown"
    assert actual["projects"]["black-agency-os"]["maturity"] == "prototype"


def test_maturity_replay_is_byte_identical(tmp_path: Path) -> None:
    source = tmp_path / "pilots"
    shutil.copytree(PILOTS, source)
    vault = _run_pipeline(source, tmp_path)
    first = (vault / "generated" / "portfolio" / "maturity-matrix.json").read_bytes()
    build_portfolio(vault, reference_date=_REFERENCE_DATE)
    second = (vault / "generated" / "portfolio" / "maturity-matrix.json").read_bytes()
    assert first == second


def test_no_capability_invention_from_ordinary_readme(tmp_path: Path) -> None:
    """Negative — Capability emission remains 001B territory."""
    source = tmp_path / "pilots"
    shutil.copytree(PILOTS, source)
    vault = _run_pipeline(source, tmp_path)
    capability = json.loads(
        (vault / "generated" / "portfolio" / "capability-report.json").read_text(encoding="utf-8")
    )
    for project_id, entries in capability["projects"].items():
        assert entries == [], f"{project_id} unexpectedly emitted Capability concepts"
