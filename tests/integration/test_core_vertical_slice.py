"""AT-002/004/007/008/010/012/020 Core vertical-slice coverage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main

pytestmark = pytest.mark.integration
def _fixture(root: Path) -> Path:
    source = root / "source"
    (source / "docs").mkdir(parents=True)
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: fixture-atlas\n", encoding="utf-8"
    )
    (source / "README.md").write_text("# Fixture Atlas\n\nProject overview.\n", encoding="utf-8")
    (source / "docs" / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nSystem design.\n", encoding="utf-8"
    )
    return source


def test_discover_ingest_indexes_validate_vertical_slice(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["inventory_sha256"]
    assert main(["init", "--output", str(vault)]) == EXIT_OK
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
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    assert (vault / "projects" / "fixture-atlas" / "project.md").is_file()
    assert "sources/imported-documents" in (
        vault / "projects" / "fixture-atlas" / "project.md"
    ).read_text(encoding="utf-8")


def test_discovery_manifest_is_stable(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    first = tmp_path / "one.json"
    second = tmp_path / "two.json"
    assert main(["discover", "--source", str(source), "--output", str(first)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(second)]) == EXIT_OK
    assert json.loads(first.read_text(encoding="utf-8"))["inventory_sha256"] == json.loads(
        second.read_text(encoding="utf-8")
    )["inventory_sha256"]


def test_unchanged_replay_has_zero_content_mutations(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
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
    # Genesis may allocate project_uuid into the source marker; rediscover so the
    # approved manifest matches on-disk bytes (CODEX-SEC-002 fail-closed).
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
    before = {
        path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in vault.rglob("*") if path.is_file()
    }
    before_mtimes = {
        path.relative_to(vault).as_posix(): path.stat().st_mtime_ns
        for path in vault.rglob("*") if path.is_file()
    }
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
    after = {
        path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in vault.rglob("*") if path.is_file()
    }
    after_mtimes = {
        path.relative_to(vault).as_posix(): path.stat().st_mtime_ns
        for path in vault.rglob("*") if path.is_file()
    }
    assert before == after
    assert before_mtimes == after_mtimes
