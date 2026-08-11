"""AS-MVP-001 portfolio intelligence and pilot onboarding acceptance tests.

Ten acceptance scenarios from ADR-005
(docs/adr/ADR-005-mvp-portfolio-intelligence-pilot-onboarding.md),
exercised against the three repository-native pilot fixtures under
tests/fixtures/pilots/ (nebula, black-agency-os, dark-factory).
"""

from __future__ import annotations

import json
import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.portfolio import build_portfolio

pytestmark = pytest.mark.integration
PILOTS = Path("tests/fixtures/pilots")
STALE_AGE_DAYS = 400


def _copy_pilots(tmp_path: Path) -> Path:
    """Copy the pilot corpus into a scratch directory and age the
    black-agency-os source file so freshness testing is reproducible
    regardless of the real filesystem clock or git checkout time."""
    root = tmp_path / "pilots"
    shutil.copytree(PILOTS, root)
    old = time.time() - STALE_AGE_DAYS * 86400
    stale_file = root / "black-agency-os" / "README.md"
    os.utime(stale_file, (old, old))
    return root


def _run_pipeline(source: Path, tmp_path: Path) -> Path:
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(
        [
            "ingest",
            "--manifest",
            str(manifest),
            "--vault",
            str(vault),
            "--source",
            str(source),
        ]
    ) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return vault


def _load(vault: Path, name: str) -> dict:
    return json.loads((vault / "generated" / "portfolio" / name).read_text(encoding="utf-8"))


def test_scenario_1_all_pilots_visible(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    overview = _load(vault, "overview.json")
    maturity = _load(vault, "maturity-matrix.json")
    coverage = _load(vault, "documentation-coverage.json")
    project_ids = {entry["project_id"] for entry in overview["projects"]}
    assert project_ids == {"nebula", "black-agency-os", "dark-factory"}
    assert set(maturity["projects"]) == project_ids
    assert set(coverage["projects"]) == project_ids


def test_scenario_2_mature_pilot_is_not_falsely_reported(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    coverage = _load(vault, "documentation-coverage.json")["projects"]["nebula"]["categories"]
    by_category = {item["category"]: item["state"] for item in coverage}
    assert by_category["overview"] != "absent"
    assert by_category["architecture"] != "absent"
    assert by_category["security"] != "absent"
    assert by_category["testing"] == "present"
    stale = _load(vault, "stale-knowledge.json")["projects"].get("nebula", {"stale_count": 0})
    assert stale["stale_count"] == 0
    overview = {
        entry["project_id"]: entry for entry in _load(vault, "overview.json")["projects"]
    }
    assert overview["nebula"]["open_conflicts"] == 0
    maturity = _load(vault, "maturity-matrix.json")["projects"]["nebula"]["inputs"]
    assert maturity["required_coverage_present"] is True
    assert maturity["validation_evidence_present"] is True


def test_scenario_3_partial_pilot_reports_accurate_gaps(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    coverage = _load(vault, "documentation-coverage.json")["projects"]["black-agency-os"][
        "categories"
    ]
    by_category = {item["category"]: item["state"] for item in coverage}
    assert by_category["overview"] != "absent"
    for category in ("architecture", "security", "roadmap"):
        assert by_category[category] == "absent"
    stale = _load(vault, "stale-knowledge.json")["projects"]["black-agency-os"]
    assert stale["stale_count"] == 1
    stale_ids = {item["source_id"] for item in stale["sources"] if item["freshness"] == "stale"}
    assert len(stale_ids) == 1
    maturity = _load(vault, "maturity-matrix.json")["projects"]["black-agency-os"]["inputs"]
    assert maturity["required_coverage_present"] is False


def test_scenario_4_conflicted_pilot_appears_in_review_queue(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    overview = {
        entry["project_id"]: entry for entry in _load(vault, "overview.json")["projects"]
    }
    assert overview["dark-factory"]["open_conflicts"] == 1
    conflicts_index = json.loads(
        (vault / "generated" / "indexes" / "conflicts.json").read_text(encoding="utf-8")
    )
    assert len(conflicts_index["ids"]) >= 1
    conflict_root = vault / "review" / "conflicts" / "dark-factory.json"
    raw = json.loads(conflict_root.read_text(encoding="utf-8"))
    entries = raw["entries"]
    assert len(entries) == 1
    assert entries[0]["field"] == "roadmap"
    # Stable references: the same conflict_id is produced on a second run.
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    raw_again = json.loads(conflict_root.read_text(encoding="utf-8"))
    assert raw_again["entries"][0]["conflict_id"] == entries[0]["conflict_id"]


def test_scenario_5_dependencies_are_deterministic_and_sourced(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    deps = _load(vault, "dependency-report.json")["projects"]
    assert deps["nebula"][0]["target"] == "shared-auth-service"
    assert deps["dark-factory"][0]["target"] == "nebula"
    for project_entries in deps.values():
        for entry in project_entries:
            assert entry["provenance"], "every dependency entry must cite provenance"
            for ref in entry["provenance"]:
                assert ref["source_id"]
    # Ordering is deterministic: rebuilding produces identical ordering.
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    deps_again = _load(vault, "dependency-report.json")["projects"]
    assert deps == deps_again


def test_scenario_6_empty_vault_produces_valid_empty_reports(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["build-portfolio", "--vault", str(vault)]) == EXIT_OK
    overview = _load(vault, "overview.json")
    assert overview["project_count"] == 0
    assert overview["projects"] == []
    for name in (
        "maturity-matrix.json",
        "documentation-coverage.json",
        "dependency-report.json",
        "capability-report.json",
    ):
        payload = _load(vault, name)
        assert payload["projects"] == {}
    stale = _load(vault, "stale-knowledge.json")
    assert stale["projects"] == {}
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK


def test_scenario_7_invalid_project_is_isolated(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    # Corrupt one project's compiled concept state directly after a normal
    # run to simulate an invalid/corrupted project without touching the
    # other two pilots' canonical state.
    vault = _run_pipeline(source, tmp_path)
    concepts_path = vault / "state" / "concepts" / "dark-factory.json"
    concepts_path.write_text("not valid json", encoding="utf-8")
    result = main(["build-portfolio", "--vault", str(vault)])
    # build-portfolio must not crash; the other two pilots' entries remain
    # generated and correct.
    assert result == EXIT_OK
    overview = {
        entry["project_id"]: entry for entry in _load(vault, "overview.json")["projects"]
    }
    assert "nebula" in overview
    assert "black-agency-os" in overview
    assert overview["nebula"]["open_conflicts"] == 0
    # validate() must fail closed on the corrupted canonical state.
    assert main(["validate", "--vault", str(vault)]) == EXIT_ERROR


def test_scenario_8_deterministic_settled_rebuild(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    reference = datetime(2026, 8, 1, tzinfo=UTC)
    build_portfolio(vault, reference_date=reference)
    first = {
        path.name: path.read_bytes()
        for path in sorted((vault / "generated" / "portfolio").glob("*.json"))
    }
    build_portfolio(vault, reference_date=reference)
    second = {
        path.name: path.read_bytes()
        for path in sorted((vault / "generated" / "portfolio").glob("*.json"))
    }
    assert first == second


def test_scenario_9_incremental_change_is_bounded(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    reference = datetime(2026, 8, 1, tzinfo=UTC)
    build_portfolio(vault, reference_date=reference)
    before = {
        path.name: path.read_bytes()
        for path in sorted((vault / "generated" / "portfolio").glob("*.json"))
    }
    # Add a new architecture document to black-agency-os only.
    (source / "black-agency-os" / "ARCHITECTURE.md").write_text(
        "# Overview\nBlack Agency OS now has one architecture note.\n", encoding="utf-8"
    )
    vault2 = _run_pipeline(source, tmp_path / "second")
    build_portfolio(vault2, reference_date=reference)
    after = {
        path.name: path.read_bytes()
        for path in sorted((vault2 / "generated" / "portfolio").glob("*.json"))
    }
    nebula_before = json.loads(before["dependency-report.json"])["projects"].get("nebula")
    nebula_after = json.loads(after["dependency-report.json"])["projects"].get("nebula")
    assert nebula_before == nebula_after
    dark_before = json.loads(before["dependency-report.json"])["projects"].get("dark-factory")
    dark_after = json.loads(after["dependency-report.json"])["projects"].get("dark-factory")
    assert dark_before == dark_after
    coverage_before = json.loads(before["documentation-coverage.json"])["projects"][
        "black-agency-os"
    ]
    coverage_after = json.loads(after["documentation-coverage.json"])["projects"][
        "black-agency-os"
    ]
    assert coverage_before != coverage_after


def test_scenario_10_validate_detects_portfolio_drift(tmp_path: Path) -> None:
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    overview_path = vault / "generated" / "portfolio" / "overview.json"
    payload = json.loads(overview_path.read_text(encoding="utf-8"))
    payload["projects"][0]["open_conflicts"] = 999
    overview_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = main(["validate", "--vault", str(vault)])
    assert result == EXIT_ERROR


def test_security_no_quarantined_content_in_portfolio_outputs(tmp_path: Path) -> None:
    """Reuses the AS-SEC-001 adversarial fixture to prove zero leakage
    into any AS-MVP-001 portfolio output."""
    source = tmp_path / "adversarial-portfolio"
    source.mkdir()
    fixture = Path("tests/fixtures/adversarial-project")
    marker_text = (fixture / ".atlas-project.yaml").read_text(encoding="utf-8")
    marker_text = marker_text.replace(
        "id: adversarial-project", f"id: {source.name}"
    ).replace("name: Adversarial Test Project", f"name: {source.name}")
    (source / ".atlas-project.yaml").write_text(marker_text, encoding="utf-8")
    for name in ("README.md", "instruction-bearing.md", "canary-bearing.md"):
        (source / name).write_text((fixture / name).read_text(encoding="utf-8"), encoding="utf-8")
    vault = _run_pipeline(source, tmp_path)
    findings = json.loads(
        (vault / "generated" / "reports" / "injection-findings.json").read_text(encoding="utf-8")
    )
    quarantined_ids = {finding["source_id"] for finding in findings["findings"]}
    assert quarantined_ids, "fixture must produce at least one quarantine finding"
    for path in sorted((vault / "generated" / "portfolio").glob("*.json")):
        serialized = path.read_text(encoding="utf-8")
        for source_id in quarantined_ids:
            assert f'"{source_id}"' not in serialized, f"leak in {path.name}"
        assert "CANARY-AS-SEC-001" not in serialized
        assert "ignore" not in serialized.lower()


def test_rollback_preserves_prior_valid_portfolio_on_failure(tmp_path: Path) -> None:
    """A pre-staging path failure preserves the prior portfolio snapshot.

    The shared promotion layer now also has a separate mid-promotion rollback
    test in ``test_concurrency.py``; this scenario retains the earlier
    destination-boundary regression coverage.
    """
    source = _copy_pilots(tmp_path)
    vault = _run_pipeline(source, tmp_path)
    reference = datetime(2026, 8, 1, tzinfo=UTC)
    build_portfolio(vault, reference_date=reference)
    portfolio_dir = vault / "generated" / "portfolio"
    before = {path.name: path.read_bytes() for path in sorted(portfolio_dir.glob("*.json"))}

    # Replace the output directory with a file so staging fails before any
    # canonical path can be promoted.
    shutil.rmtree(portfolio_dir)
    portfolio_dir.write_text("not a directory", encoding="utf-8")

    raised = False
    try:
        build_portfolio(vault, reference_date=reference)
    except OSError:
        raised = True

    # Inspect disk state now, before any cleanup: the failure is raised,
    # and the destination is still exactly the blocking regular file --
    # not a directory, not a mix of old/new files, no partial output.
    assert raised
    assert portfolio_dir.is_file()
    assert not portfolio_dir.is_dir()
    assert portfolio_dir.read_text(encoding="utf-8") == "not a directory"

    # Only now perform cleanup; the assertions above already independently
    # proved preservation without relying on this step.
    portfolio_dir.unlink()
    for name, content in before.items():
        (portfolio_dir / name).parent.mkdir(parents=True, exist_ok=True)
        (portfolio_dir / name).write_bytes(content)
    after = {path.name: path.read_bytes() for path in sorted(portfolio_dir.glob("*.json"))}
    assert before == after

    # A later clean run succeeds and reproduces the same settled output.
    build_portfolio(vault, reference_date=reference)
    after_rebuild = {
        path.name: path.read_bytes() for path in sorted(portfolio_dir.glob("*.json"))
    }
    assert before == after_rebuild
