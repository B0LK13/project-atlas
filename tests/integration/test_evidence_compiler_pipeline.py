"""AS-EXT-001A end-to-end: mixed corpus completes per-file without batch abort."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "as-ext-001a"


def _fixture(root: Path) -> Path:
    """Mixed corpus: good Markdown, valid receipt, malformed YAML, VERIFY doc."""
    source = root / "source"
    (source / "docs" / "evidence").mkdir(parents=True)
    (source / "docs" / "architecture-governance").mkdir(parents=True)
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: fixture-atlas\n", encoding="utf-8"
    )
    (source / "README.md").write_text(
        "# Fixture Atlas\n\nPurpose: governed project\n", encoding="utf-8"
    )
    (source / "docs" / "evidence" / "receipt.yaml").write_bytes(
        (FIXTURES / "real" / "evidence-flat-as-core-002-post-merge-receipt.yaml").read_bytes()
    )
    (source / "docs" / "evidence" / "broken.yaml").write_bytes(
        (FIXTURES / "synthetic" / "malformed-yaml.yaml").read_bytes()
    )
    (source / "docs" / "architecture-governance" / "VERIFY-AS-CORE-003.md").write_bytes(
        (FIXTURES / "real" / "f01-verify-structured-document.md").read_bytes()
    )
    return source


def _ingest(source: Path, tmp_path: Path) -> Path:
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    return vault


def test_mixed_corpus_completes_without_batch_abort(tmp_path: Path) -> None:
    vault = _ingest(_fixture(tmp_path), tmp_path)
    outcomes = json.loads(
        (vault / "state" / "compilation-outcomes" / "fixture-atlas.json").read_text(
            encoding="utf-8"
        )
    )
    by_path = {item["source_path"]: item for item in outcomes["candidates"]}
    # Every source file obtained exactly one per-file outcome (§7.8).
    assert by_path["README.md"]["outcome"] == "COMPLETE_CANDIDATE"
    assert by_path[".atlas-project.yaml"]["outcome"] == "COMPLETE_CANDIDATE"
    assert by_path["docs/evidence/receipt.yaml"]["outcome"] == "COMPLETE_CANDIDATE"
    assert by_path["docs/evidence/broken.yaml"]["outcome"] == "FAILED"
    verify = by_path["docs/architecture-governance/VERIFY-AS-CORE-003.md"]
    assert verify["outcome"] == "COMPLETE_CANDIDATE"
    assert verify["claims_extracted"] >= 4
    # Good sources promoted claims despite the failed neighbor (§7.8 isolation).
    claims = json.loads(
        (vault / "state" / "claims" / "fixture-atlas.json").read_text(encoding="utf-8")
    )
    assert claims["claims"]
    diagnostics = json.loads(
        (vault / "state" / "diagnostics" / "fixture-atlas.json").read_text(encoding="utf-8")
    )
    assert any(
        record["source_path"] == "docs/evidence/broken.yaml"
        for record in diagnostics["diagnostics"]
    )
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK


def test_mixed_corpus_replay_is_byte_identical(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    vault = _ingest(source, tmp_path)
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    # Second run settles claim lifecycle (NEW -> UNCHANGED); the third run is
    # the deterministic replay under test.
    manifest = tmp_path / "manifest.json"
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK

    def snapshot() -> dict[str, str]:
        return {
            path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in vault.rglob("*")
            if path.is_file()
        }

    before = snapshot()
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert snapshot() == before
