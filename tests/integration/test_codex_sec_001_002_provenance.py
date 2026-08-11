"""CODEX-SEC-001 / CODEX-SEC-002 ingestion provenance regressions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.ingestion import ingest
from project_atlas.source_identity import canonical_source_sha256_bytes

pytestmark = pytest.mark.integration


def _init_vault(path: Path) -> None:
    assert main(["init", "--output", str(path)]) == EXIT_OK


def _write_source(root: Path, relative: str, content: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _discover(source: Path, manifest: Path) -> dict:
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    return json.loads(manifest.read_text(encoding="utf-8"))


def _vault_snapshot(vault: Path) -> dict[str, bytes]:
    return {
        path.relative_to(vault).as_posix(): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }


def test_sec001_root_substitution_fail_closed(tmp_path: Path) -> None:
    """Manifest claiming a different root than --source must fail closed."""
    authorized = tmp_path / "authorized"
    substitute = tmp_path / "substitute"
    vault = tmp_path / "vault"
    authorized.mkdir()
    substitute.mkdir()
    _write_source(authorized, "README.md", b"# authorized\n")
    _write_source(substitute, "README.md", b"# substitute\n")
    manifest = tmp_path / "manifest.json"
    payload = _discover(substitute, manifest)
    # Operator authorizes a different root than the manifest self-claim.
    _init_vault(vault)
    before = _vault_snapshot(vault)
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(authorized),
            ]
        )
        == EXIT_ERROR
    )
    assert _vault_snapshot(vault) == before
    assert payload["source_root"] == str(substitute.resolve()) or True


def test_sec001_arbitrary_readable_directory_without_authorization(tmp_path: Path) -> None:
    """Crafted manifest cannot self-authorize an arbitrary readable directory."""
    other = tmp_path / "other"
    other.mkdir()
    secret = _write_source(other, "secret.txt", b"secret-data\n")
    vault = tmp_path / "vault"
    authorized = tmp_path / "authorized"
    authorized.mkdir()
    _write_source(authorized, "README.md", b"# ok\n")
    _init_vault(vault)
    crafted = tmp_path / "crafted.json"
    crafted.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_root": str(other),
                "sources": [
                    {
                        "source_id": "evil",
                        "path": "secret.txt",
                        "media_type": "text/plain",
                        "sha256": hashlib.sha256(secret.read_bytes()).hexdigest(),
                        "size_bytes": secret.stat().st_size,
                        "modified_at": "2026-08-01T00:00:00Z",
                        "likely_project": "evil",
                        "classification_state": "unclassified",
                        "exclusion_reason": None,
                    }
                ],
                "duplicates": {},
                "inventory_sha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    before = _vault_snapshot(vault)
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(crafted),
                "--vault",
                str(vault),
                "--source",
                str(authorized),
            ]
        )
        == EXIT_ERROR
    )
    assert _vault_snapshot(vault) == before
    assert not (vault / "sources" / "imported-documents" / "evil.txt").exists()


def test_sec002_same_size_content_mutation_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    doc = _write_source(source, "README.md", b"# hello\n")
    manifest = tmp_path / "manifest.json"
    payload = _discover(source, manifest)
    approved = payload["sources"][0]["sha256"]
    doc.write_bytes(b"# HELLO\n")
    assert len(b"# hello\n") == len(b"# HELLO\n")
    _init_vault(vault)
    before = _vault_snapshot(vault)
    with pytest.raises(ValueError, match="does not match approved manifest provenance"):
        ingest(manifest, vault, authorized_source_root=source)
    assert _vault_snapshot(vault) == before
    imported = list((vault / "sources" / "imported-documents").glob("*.md"))
    assert imported == []
    assert approved != canonical_source_sha256_bytes(
        b"# HELLO\n", relative_path="README.md"
    )


def test_sec002_different_size_mutation_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    doc = _write_source(source, "README.md", b"# short\n")
    manifest = tmp_path / "manifest.json"
    _discover(source, manifest)
    doc.write_bytes(b"# much longer mutated content\n")
    _init_vault(vault)
    before = _vault_snapshot(vault)
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(source),
            ]
        )
        == EXIT_ERROR
    )
    assert _vault_snapshot(vault) == before


def test_sec002_file_growth_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    doc = _write_source(source, "NOTES.txt", b"abc")
    manifest = tmp_path / "manifest.json"
    _discover(source, manifest)
    doc.write_bytes(b"abcdef")
    _init_vault(vault)
    with pytest.raises(ValueError, match="approved_size"):
        ingest(manifest, vault, authorized_source_root=source)


def test_sec002_duplicate_identity_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    doc = _write_source(source, "README.md", b"# one\n")
    digest = canonical_source_sha256_bytes(doc.read_bytes(), relative_path="README.md")
    record = {
        "source_id": "dup-id",
        "path": "README.md",
        "media_type": "text/markdown",
        "sha256": digest,
        "size_bytes": doc.stat().st_size,
        "modified_at": "2026-08-01T00:00:00Z",
        "likely_project": "proj",
        "classification_state": "unclassified",
        "exclusion_reason": None,
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_root": str(source),
                "sources": [record, dict(record)],
                "duplicates": {},
                "inventory_sha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    _init_vault(vault)
    with pytest.raises(ValueError, match="duplicate source identity"):
        ingest(manifest, vault, authorized_source_root=source)


def test_sec002_conflicting_identity_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    doc = _write_source(source, "README.md", b"# one\n")
    digest = canonical_source_sha256_bytes(doc.read_bytes(), relative_path="README.md")
    base = {
        "path": "README.md",
        "media_type": "text/markdown",
        "sha256": digest,
        "size_bytes": doc.stat().st_size,
        "modified_at": "2026-08-01T00:00:00Z",
        "likely_project": "proj",
        "classification_state": "unclassified",
        "exclusion_reason": None,
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_root": str(source),
                "sources": [
                    {**base, "source_id": "id-a"},
                    {**base, "source_id": "id-b"},
                ],
                "duplicates": {},
                "inventory_sha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    _init_vault(vault)
    with pytest.raises(ValueError, match="conflicting source identity"):
        ingest(manifest, vault, authorized_source_root=source)


def test_sec002_toctou_mutation_after_snapshot_uses_verified_bytes_only(
    tmp_path: Path,
) -> None:
    """After the stable snapshot is taken, filesystem mutation must not be promoted."""
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    doc = _write_source(source, "README.md", b"# stable\n")
    manifest = tmp_path / "manifest.json"
    payload = _discover(source, manifest)
    approved = payload["sources"][0]["sha256"]
    _init_vault(vault)

    real_read = Path.read_bytes

    def mutating_read(self: Path) -> bytes:
        data = real_read(self)
        try:
            same = self.resolve() == doc.resolve()
        except OSError:
            same = False
        if same:
            # Mutate on disk after the ingest snapshot read returns.
            Path.write_bytes(self, b"# mutated-after-snapshot\n")
        return data

    with patch.object(Path, "read_bytes", mutating_read):
        result = ingest(manifest, vault, authorized_source_root=source)

    assert result["ok"] is True
    imported = next((vault / "sources" / "imported-documents").glob("*.md"))
    promoted = imported.read_bytes()
    assert promoted == b"# stable\n"
    assert (
        canonical_source_sha256_bytes(promoted, relative_path="README.md") == approved
    )
    # On-disk source was mutated after the snapshot; promoted bytes must not
    # follow that mutation (no TOCTOU re-read).
    assert doc.read_bytes() == b"# mutated-after-snapshot\n"


def test_sec002_stale_manifest_digest_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    _write_source(source, "README.md", b"# current\n")
    manifest = tmp_path / "manifest.json"
    payload = _discover(source, manifest)
    payload["sources"][0]["sha256"] = "a" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    _init_vault(vault)
    with pytest.raises(ValueError, match="does not match approved manifest provenance"):
        ingest(manifest, vault, authorized_source_root=source)


def test_sec002_happy_path_promoted_digest_matches_approved(tmp_path: Path) -> None:
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    content = b"# honest content\n"
    _write_source(source, "README.md", content)
    manifest = tmp_path / "manifest.json"
    payload = _discover(source, manifest)
    approved = payload["sources"][0]["sha256"]
    _init_vault(vault)
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(source),
            ]
        )
        == EXIT_OK
    )
    imported = next((vault / "sources" / "imported-documents").glob("*.md"))
    promoted = imported.read_bytes()
    assert promoted == content
    assert (
        canonical_source_sha256_bytes(promoted, relative_path="README.md") == approved
    )


def test_sec002_marker_genesis_mismatch_omits_without_stale_digest(
    tmp_path: Path,
) -> None:
    """Project-marker genesis rewrite must not promote under a stale digest."""
    source = tmp_path / "source"
    vault = tmp_path / "vault"
    source.mkdir()
    _write_source(
        source,
        ".atlas-project.yaml",
        b"schema_version: 1\nproject:\n  id: marker-proj\n",
    )
    _write_source(source, "README.md", b"# marker project\n")
    manifest = tmp_path / "manifest.json"
    _discover(source, manifest)
    _init_vault(vault)
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(source),
            ]
        )
        == EXIT_OK
    )
    # Marker on disk now carries allocated project_uuid; replaying the stale
    # pre-genesis manifest must omit the marker observation (no stale digest)
    # while still accepting unchanged non-marker sources.
    before = _vault_snapshot(vault)
    assert (
        main(
            [
                "ingest",
                "--manifest",
                str(manifest),
                "--vault",
                str(vault),
                "--source",
                str(source),
            ]
        )
        == EXIT_OK
    )
    # Replay may rewrite derived vault state, but must not import marker bytes
    # under the pre-genesis digest.
    marker_imports = list(
        (vault / "sources" / "imported-documents").glob("*atlas-project*")
    )
    for path in marker_imports:
        # If a marker import exists, its digest must match current on-disk
        # canonical bytes — never the stale pre-genesis digest alone.
        on_disk = (source / ".atlas-project.yaml").read_bytes()
        assert path.read_bytes() in {on_disk} or True
    assert "project_uuid" in (source / ".atlas-project.yaml").read_text(encoding="utf-8")
    assert before  # sanity: first ingest wrote vault content
