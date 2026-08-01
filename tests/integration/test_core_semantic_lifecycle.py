"""AS-CORE-002 lifecycle, secret and regeneration behavior through CLI."""

import json
import os
from pathlib import Path

from project_atlas.cli import EXIT_OK, main


def _workflow(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: semantic-fixture\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# Semantic Fixture\n", encoding="utf-8")
    (source / "ARCHITECTURE.md").write_text("# Architecture\n", encoding="utf-8")
    (source / "secret-notes.txt").write_text(
        "password = 'fixture-only-secret-value'\n", encoding="utf-8"
    )
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return source, manifest, vault


def test_rich_project_record_secret_report_and_human_region(tmp_path: Path) -> None:
    source, manifest, vault = _workflow(tmp_path)
    project = vault / "projects" / "semantic-fixture" / "project.md"
    assert "schema_version: 1" in project.read_text(encoding="utf-8")
    report = json.loads(
        (vault / "generated" / "reports" / "secret-findings.json").read_text(encoding="utf-8")
    )
    assert report[0]["pattern"] == "password-assignment"
    project.write_text(
        project.read_text(encoding="utf-8")
        + "\n## Human notes\n\nKeep this text.\n",
        encoding="utf-8",
    )
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert "Keep this text." in project.read_text(encoding="utf-8")
    assert source.is_dir()


def test_removed_source_is_retained_as_lifecycle_state(tmp_path: Path) -> None:
    source, _manifest, vault = _workflow(tmp_path)
    (source / "ARCHITECTURE.md").unlink()
    next_manifest = tmp_path / "manifest-2.json"
    assert main(["discover", "--source", str(source), "--output", str(next_manifest)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(next_manifest), "--vault", str(vault)]) == EXIT_OK
    state = json.loads((vault / "state" / "sources.json").read_text(encoding="utf-8"))
    assert any(item["lifecycle"] == "deleted" for item in state["sources"])


def test_malformed_generated_markers_fail_closed(tmp_path: Path) -> None:
    _source, manifest, vault = _workflow(tmp_path)
    project = vault / "projects" / "semantic-fixture" / "project.md"
    before = project.read_bytes()
    project.write_text("<!-- atlas:generated:start -->\nuser text\n", encoding="utf-8")
    malformed = project.read_bytes()
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) != EXIT_OK
    assert project.read_bytes() == malformed
    assert project.read_bytes() != before


def test_unchanged_ingestion_has_zero_filesystem_writes(tmp_path: Path) -> None:
    _source, manifest, vault = _workflow(tmp_path)
    tracked = [
        vault / "projects" / "semantic-fixture" / "project.md",
        vault / "state" / "sources.json",
        vault / "generated" / "reports" / "ingestion-report.json",
    ]
    before = {path: (path.read_bytes(), os.stat(path).st_mtime_ns) for path in tracked}
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    after = {path: (path.read_bytes(), os.stat(path).st_mtime_ns) for path in tracked}
    assert after == before


def test_corrupt_source_state_fails_closed_before_ingestion_writes(tmp_path: Path) -> None:
    _source, manifest, vault = _workflow(tmp_path)
    state_path = vault / "state" / "sources.json"
    state_path.write_text(
        json.dumps({"schema_version": 999, "sources": [{"source_id": "source-bad"}]}),
        encoding="utf-8",
    )
    project = vault / "projects" / "semantic-fixture" / "project.md"
    before = project.read_bytes()
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) != EXIT_OK
    assert project.read_bytes() == before


def test_malformed_marker_in_one_project_aborts_before_other_project_writes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "multi-source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: project-a\n", encoding="utf-8"
    )
    (nested / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: project-b\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# A\n", encoding="utf-8")
    (nested / "README.md").write_text("# B\n", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    target = vault / "projects" / "project-b" / "project.md"
    target.write_text("<!-- atlas:generated:start -->\n", encoding="utf-8")
    imported_before = sorted((vault / "sources" / "imported-documents").iterdir())
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) != EXIT_OK
    assert sorted((vault / "sources" / "imported-documents").iterdir()) == imported_before
