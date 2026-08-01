"""AT-013 ingestion-boundary regression tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main


def _crafted_manifest(
    tmp_path: Path,
    *,
    likely_project: str = "../../../../outside-vault-marker",
    source_id: str = "source-safe",
) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "source"
    vault = tmp_path / "vault"
    source_root.mkdir()
    document = source_root / "README.md"
    document.write_text("# Controlled source\n", encoding="utf-8")
    manifest = tmp_path / "crafted-manifest.json"
    record = {
        "source_id": source_id,
        "path": "README.md",
        "media_type": "text/markdown",
        "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
        "size_bytes": document.stat().st_size,
        "modified_at": "2026-08-01T00:00:00Z",
        "likely_project": likely_project,
        "classification_state": "unclassified",
        "exclusion_reason": None,
    }
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_root": str(source_root),
                "sources": [record],
                "duplicates": {},
                "inventory_sha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    return manifest, vault, tmp_path / "outside-vault-marker"


def test_public_ingest_rejects_manifest_project_traversal(tmp_path: Path) -> None:
    manifest, vault, outside = _crafted_manifest(tmp_path)
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    before = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_ERROR
    after = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert not outside.exists()


@pytest.mark.parametrize(
    ("likely_project", "source_id"),
    [
        ("../outside", "source-safe"),
        ("../../../../deeply/nested/outside", "source-safe"),
        ("/absolute/outside", "source-safe"),
        ("C:\\outside", "source-safe"),
        ("\\\\server\\share", "source-safe"),
        ("safe-project", "../../outside-source"),
    ],
)
def test_public_ingest_rejects_manifest_path_variants(
    tmp_path: Path, likely_project: str, source_id: str
) -> None:
    manifest, vault, outside = _crafted_manifest(
        tmp_path, likely_project=likely_project, source_id=source_id
    )
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_ERROR
    assert not outside.exists()


def test_rejected_manifest_preserves_previous_valid_vault(tmp_path: Path) -> None:
    manifest, vault, outside = _crafted_manifest(tmp_path, likely_project="safe-project")
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    before = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["sources"][0]["likely_project"] = "../../outside-vault-marker"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_ERROR
    after = {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert not outside.exists()
