"""AS-ENG-005 canonical-index and read-only retrieval coverage."""

from __future__ import annotations

import json
import os
from pathlib import Path

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.retrieval import VaultRetriever


def _workflow(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: retrieval-project\n", encoding="utf-8"
    )
    (source / "README.md").write_text(
        "# Retrieval project\n\nPurpose: indexed source.\n", encoding="utf-8"
    )
    (source / "ARCHITECTURE.md").write_text(
        "# Architecture\n\nDeployment: port 8000\n", encoding="utf-8"
    )
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return source, vault


def test_indexes_cover_canonical_state_and_retrieval_is_read_only(tmp_path: Path) -> None:
    _source, vault = _workflow(tmp_path)
    index_names = {path.name for path in (vault / "indexes").glob("*.json")}
    assert index_names == {
        "authority.json",
        "claims.json",
        "concepts.json",
        "conflicts.json",
        "provenance.json",
        "sources.json",
    }
    retriever = VaultRetriever(vault)
    claim_results = retriever.lookup("claim", "purpose")
    assert claim_results
    assert claim_results[0].record["field"] == "purpose"
    assert claim_results[0].provenance
    assert retriever.lookup("concept", "retrieval-project")
    assert retriever.lookup("concept", "retr", prefix=True)
    assert retriever.lookup("source", "README", prefix=True)
    assert retriever.lookup("authority", "source-", prefix=True)
    assert retriever.lookup("provenance", "sline-", prefix=True)

    before = {
        path.relative_to(vault).as_posix(): (path.read_bytes(), os.stat(path).st_mtime_ns)
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    after = {
        path.relative_to(vault).as_posix(): (path.read_bytes(), os.stat(path).st_mtime_ns)
        for path in vault.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_validate_rejects_index_state_drift(tmp_path: Path) -> None:
    _source, vault = _workflow(tmp_path)
    index_path = vault / "indexes" / "claims.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["ids"] = []
    index_path.write_text(json.dumps(index), encoding="utf-8")
    assert main(["validate", "--vault", str(vault)]) == EXIT_ERROR
