"""AS-SPEC-004 public concept-type wiring coverage."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.cli import EXIT_OK, main


def _run_workflow(source: Path, tmp_path: Path) -> dict[str, object]:
    manifest = tmp_path / "manifest.json"
    vault = tmp_path / "vault"
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["ingest", "--manifest", str(manifest), "--vault", str(vault)]) == EXIT_OK
    assert main(["build-indexes", "--vault", str(vault)]) == EXIT_OK
    assert main(["validate", "--vault", str(vault)]) == EXIT_OK
    return json.loads(
        (vault / "state" / "concepts" / f"{source.name}.json").read_text(encoding="utf-8")
    )


def _source(tmp_path: Path, marker_extra: str = "") -> Path:
    source = tmp_path / "public-project"
    source.mkdir()
    (source / ".atlas-project.yaml").write_text(
        "schema_version: 1\nproject:\n  id: public-project\n" + marker_extra,
        encoding="utf-8",
    )
    (source / "README.md").write_text(
        "# Public project\n\nPurpose: source-backed workflow.\n", encoding="utf-8"
    )
    return source


def test_unknown_marker_concept_type_is_generic_through_public_workflow(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path, "concept_type: FutureConcept\n")
    state = _run_workflow(source, tmp_path)
    assert state["concepts"][0]["type"] == "Reference"


def test_marker_without_concept_type_preserves_project_default(tmp_path: Path) -> None:
    source = _source(tmp_path)
    state = _run_workflow(source, tmp_path)
    assert state["concepts"][0]["type"] == "Project"


def test_known_marker_concept_type_is_wired_through_public_workflow(tmp_path: Path) -> None:
    source = _source(tmp_path, "concept_type: Architecture\n")
    state = _run_workflow(source, tmp_path)
    assert state["concepts"][0]["type"] == "Architecture"
