"""AS-CORE-MODEL-001B — marker Capability emission + I-008 portfolio matrix."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.knowledge_compiler import capability_concept_id
from project_atlas.portfolio import build_portfolio

_REFERENCE_DATE = datetime(2026, 4, 1, tzinfo=UTC)
PILOTS = Path("tests/fixtures/pilots")


def _run_pipeline(source: Path, tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    manifest = tmp_path / "manifest.json"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    build_portfolio(vault, reference_date=_REFERENCE_DATE)
    return vault


def _write_declaring_fixture(root: Path) -> Path:
    project = root / "cap-demo"
    project.mkdir(parents=True)
    (project / ".atlas-project.yaml").write_text(
        (
            "project:\n"
            "  id: cap-demo\n"
            "capabilities:\n"
            "  - id: search\n"
            "    title: Search\n"
            "    provides: index-service\n"
        ),
        encoding="utf-8",
    )
    (project / "README.md").write_text("# Cap Demo\n\nOrdinary prose.\n", encoding="utf-8")
    return project


def test_declaring_fixture_fills_capability_report_control_stays_empty(
    tmp_path: Path,
) -> None:
    source = tmp_path / "corpus"
    shutil.copytree(PILOTS, source)
    _write_declaring_fixture(source)
    vault = _run_pipeline(source, tmp_path)
    report = json.loads(
        (vault / "generated" / "portfolio" / "capability-report.json").read_text(
            encoding="utf-8"
        )
    )
    expected_id = capability_concept_id("cap-demo", "search")
    assert "cap-demo" in report["projects"]
    caps = report["projects"]["cap-demo"]["capabilities"]
    assert len(caps) == 1
    assert caps[0]["concept_id"] == expected_id
    assert caps[0]["title"] == "Search"
    provides = report["projects"]["cap-demo"]["provides"]
    assert any(item["target"] == "index-service" for item in provides)
    # Control pilots without declarations remain absent / empty.
    for pilot in ("nebula", "dark-factory", "black-agency-os"):
        assert pilot not in report["projects"]


def test_capability_report_replay_is_byte_identical(tmp_path: Path) -> None:
    source = tmp_path / "corpus"
    source.mkdir()
    _write_declaring_fixture(source)
    vault = _run_pipeline(source, tmp_path)
    path = vault / "generated" / "portfolio" / "capability-report.json"
    first = path.read_bytes()
    build_portfolio(vault, reference_date=_REFERENCE_DATE)
    second = path.read_bytes()
    assert first == second


def test_ordinary_pilots_still_emit_zero_capabilities(tmp_path: Path) -> None:
    source = tmp_path / "pilots"
    shutil.copytree(PILOTS, source)
    vault = _run_pipeline(source, tmp_path)
    report = json.loads(
        (vault / "generated" / "portfolio" / "capability-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["projects"] == {}
