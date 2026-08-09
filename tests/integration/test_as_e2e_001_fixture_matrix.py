"""AS-E2E-001 — Fixture pipeline determinism + recovery matrix.

Runs discover→ingest→build-indexes→validate twice on a synthetic vault and
asserts byte-identical second-pass outputs for unchanged sources. Also probes
CORE2-009 recovery receipt path remains available. Never invents estate roots.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.ingestion import recover_promote_orphans


def _snapshot(vault: Path) -> dict[str, bytes]:
    return {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
        and ".atlas-stage" not in path.parts
        and ".atlas-backup" not in path.parts
    }


def test_as_e2e_001_fixture_pipeline_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: e2e-fixture\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# E2E Fixture\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    first = _snapshot(vault)
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    second = _snapshot(vault)
    # Compare stable planes (exclude volatile agent-event noise if any).
    stable_keys = {
        key
        for key in first
        if key.startswith(("projects/", "state/", "generated/indexes/", "00-system/"))
    }
    for key in sorted(stable_keys):
        assert first[key] == second[key], f"drift at {key}"


def test_as_e2e_001_promote_recovery_noop_on_clean_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    result = recover_promote_orphans(vault)
    assert result.orphan_count == 0
    assert result.receipt_path is None


def test_as_e2e_001_lifecycle_cert_compatible_when_present(tmp_path: Path) -> None:
    """Optional soft bind: if CORE2-010 is on tip, matrix certifies without PILOT claim."""
    try:
        from project_atlas.lifecycle_cert import run_fixture_lifecycle_certification
    except ImportError:
        return
    report = run_fixture_lifecycle_certification(
        tmp_path / "work", case_ids=("new", "corrupt")
    )
    assert report["estate_pilot_passed"] is False
    assert report["package"] == "AS-CORE2-010"
    path = tmp_path / "report-vault"
    path.mkdir()
    from project_atlas.lifecycle_cert import write_report

    write_report(path, report)
    loaded = json.loads(
        (path / "generated" / "ops" / "lifecycle-cert-report.json").read_text(encoding="utf-8")
    )
    assert loaded["estate_pilot_passed"] is False
