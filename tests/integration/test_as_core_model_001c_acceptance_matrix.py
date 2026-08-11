"""AS-CORE-MODEL-001C — acceptance matrix via ingest pipeline (A-1…A-12 subset)."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.domain import ConceptType
from project_atlas.knowledge_compiler import allowlist_concept_id, capability_concept_id
from project_atlas.portfolio import build_portfolio

_REFERENCE_DATE = datetime(2026, 4, 1, tzinfo=UTC)
PILOTS = Path("tests/fixtures/pilots")


def _run_pipeline(source: Path, tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    manifest = tmp_path / "manifest.json"
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
    build_portfolio(vault, reference_date=_REFERENCE_DATE)
    return vault


def _write_project(root: Path, project_id: str, marker: str, files: dict[str, str]) -> Path:
    project = root / project_id
    project.mkdir(parents=True)
    (project / ".atlas-project.yaml").write_text(marker, encoding="utf-8")
    for relative, body in files.items():
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return project


def test_a1_ordinary_readme_emits_no_allowlist(tmp_path: Path) -> None:
    source = tmp_path / "corpus"
    _write_project(
        source,
        "plain-demo",
        "project:\n  id: plain-demo\n",
        {
            "README.md": (
                "# Plain Demo\n\n## Components\n\n- Auth\n\n"
                "## Decisions\n\n- Use Postgres\n"
            )
        },
    )
    vault = _run_pipeline(source, tmp_path)
    concepts = json.loads(
        (vault / "state" / "concepts" / "plain-demo.json").read_text(encoding="utf-8")
    )
    types = [item["type"] for item in concepts["concepts"]]
    assert types == ["Project"] or (
        types[0] == "Project"
        and ConceptType.COMPONENT.value not in types
        and ConceptType.DECISION.value not in types
        and ConceptType.ARCHITECTURE.value not in types
        and ConceptType.PROJECT_STATUS.value not in types
    )


def test_a2_architecture_without_emit_concepts(tmp_path: Path) -> None:
    source = tmp_path / "corpus"
    _write_project(
        source,
        "arch-no-opt",
        "project:\n  id: arch-no-opt\n",
        {
            "README.md": "# Arch No Opt\n",
            "docs/architecture.md": "# Architecture\n\nSystem overview.\n",
        },
    )
    vault = _run_pipeline(source, tmp_path)
    concepts = json.loads(
        (vault / "state" / "concepts" / "arch-no-opt.json").read_text(encoding="utf-8")
    )
    assert not any(
        item["type"] == ConceptType.ARCHITECTURE.value for item in concepts["concepts"]
    )


def test_a3_a4_a5_a6_positive_markers(tmp_path: Path) -> None:
    source = tmp_path / "corpus"
    marker = (
        "project:\n"
        "  id: multi-demo\n"
        "emit_concepts:\n"
        "  - architecture\n"
        "  - decision\n"
        "project_status:\n"
        "  id: current\n"
        "  title: Current Status\n"
        "components:\n"
        "  - id: auth\n"
        "    title: Auth\n"
        "    relationships:\n"
        "      - type: part_of\n"
        "        target: multi-demo\n"
        "capabilities:\n"
        "  - id: search\n"
        "    title: Search\n"
        "    provides: index-service\n"
    )
    _write_project(
        source,
        "multi-demo",
        marker,
        {
            "README.md": "# Multi Demo\n",
            "docs/architecture.md": "# Architecture\n\nLayers.\n",
            "docs/adr/ADR-001-storage.md": "# ADR 001 Storage\n\nUse Postgres.\n",
        },
    )
    vault = _run_pipeline(source, tmp_path)
    concepts = json.loads(
        (vault / "state" / "concepts" / "multi-demo.json").read_text(encoding="utf-8")
    )
    by_type: dict[str, list[dict[str, object]]] = {}
    for item in concepts["concepts"]:
        by_type.setdefault(str(item["type"]), []).append(item)
    assert "Project" in by_type
    assert ConceptType.PROJECT_STATUS.value in by_type
    assert ConceptType.COMPONENT.value in by_type
    assert ConceptType.ARCHITECTURE.value in by_type
    assert ConceptType.DECISION.value in by_type
    assert ConceptType.CAPABILITY.value in by_type
    status = by_type[ConceptType.PROJECT_STATUS.value][0]
    assert status["concept_id"] == allowlist_concept_id(
        "multi-demo", ConceptType.PROJECT_STATUS.value, "current"
    )
    component = by_type[ConceptType.COMPONENT.value][0]
    assert component["concept_id"] == allowlist_concept_id(
        "multi-demo", ConceptType.COMPONENT.value, "auth"
    )
    assert any(
        rel.get("type") == "part_of" and rel.get("target") == "multi-demo"
        for rel in component.get("relationships", [])  # type: ignore[union-attr]
    )
    capability = by_type[ConceptType.CAPABILITY.value][0]
    assert capability["concept_id"] == capability_concept_id("multi-demo", "search")
    # A-8: singleton maturity unchanged (coverage-derived or None — project present)
    project = by_type["Project"][0]
    assert project["concept_id"] == "multi-demo"
    # Capability provides intact
    report = json.loads(
        (vault / "generated" / "portfolio" / "capability-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert "multi-demo" in report["projects"]
    provides = report["projects"]["multi-demo"]["provides"]
    assert any(item["target"] == "index-service" for item in provides)


def test_a8_capability_control_unchanged_vs_pilots(tmp_path: Path) -> None:
    source = tmp_path / "corpus"
    shutil.copytree(PILOTS, source)
    _write_project(
        source,
        "granularity-demo",
        (
            "project:\n"
            "  id: granularity-demo\n"
            "components:\n"
            "  - id: api\n"
            "    title: API\n"
        ),
        {"README.md": "# Granularity Demo\n"},
    )
    vault = _run_pipeline(source, tmp_path)
    report = json.loads(
        (vault / "generated" / "portfolio" / "capability-report.json").read_text(
            encoding="utf-8"
        )
    )
    # Pilots without capability declarations remain empty in capability report.
    for pilot in ("nebula", "dark-factory", "black-agency-os"):
        assert pilot not in report["projects"]
    concepts = json.loads(
        (vault / "state" / "concepts" / "granularity-demo.json").read_text(
            encoding="utf-8"
        )
    )
    assert any(item["type"] == ConceptType.COMPONENT.value for item in concepts["concepts"])
    assert not any(
        item["type"] == ConceptType.CAPABILITY.value for item in concepts["concepts"]
    )


def test_a9_concept_index_sorted_and_replay(tmp_path: Path) -> None:
    source = tmp_path / "corpus"
    _write_project(
        source,
        "replay-demo",
        (
            "project:\n"
            "  id: replay-demo\n"
            "components:\n"
            "  - id: beta\n"
            "    title: Beta\n"
            "  - id: alpha\n"
            "    title: Alpha\n"
            "project_status:\n"
            "  id: now\n"
            "  title: Now\n"
        ),
        {"README.md": "# Replay Demo\n"},
    )
    vault = _run_pipeline(source, tmp_path)
    concepts_path = vault / "state" / "concepts" / "replay-demo.json"
    first = concepts_path.read_bytes()
    concepts = json.loads(first.decode("utf-8"))
    ids = [item["concept_id"] for item in concepts["concepts"]]
    assert ids[0] == "replay-demo"
    assert ids[1:] == sorted(ids[1:])
    # Replay with the same post-allocation manifest (no rediscovery hash churn).
    manifest = tmp_path / "manifest.json"
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
    second = concepts_path.read_bytes()
    assert first == second
    assert [item["concept_id"] for item in json.loads(second)["concepts"]] == ids


def test_adv_c18_emit_concepts_capability_ignored(tmp_path: Path) -> None:
    source = tmp_path / "corpus"
    _write_project(
        source,
        "opt-overreach",
        (
            "project:\n"
            "  id: opt-overreach\n"
            "emit_concepts:\n"
            "  - capability\n"
            "  - requirement\n"
            "  - architecture\n"
        ),
        {
            "README.md": "# Opt Overreach\n",
            "docs/architecture.md": "# Architecture\n",
        },
    )
    vault = _run_pipeline(source, tmp_path)
    concepts = json.loads(
        (vault / "state" / "concepts" / "opt-overreach.json").read_text(encoding="utf-8")
    )
    types = [item["type"] for item in concepts["concepts"]]
    assert ConceptType.CAPABILITY.value not in types
    assert "Requirement" not in types
    assert ConceptType.ARCHITECTURE.value in types


def test_malformed_components_fail_closed(tmp_path: Path) -> None:
    from project_atlas.cli import EXIT_ERROR

    source = tmp_path / "corpus"
    _write_project(
        source,
        "bad-comp",
        (
            "project:\n"
            "  id: bad-comp\n"
            "components: auth\n"
        ),
        {"README.md": "# Bad Comp\n"},
    )
    vault = tmp_path / "vault"
    manifest = tmp_path / "manifest.json"
    assert main(["init", "--output", str(vault)]) == EXIT_OK
    assert main(["discover", "--source", str(source), "--output", str(manifest)]) == EXIT_OK
    code = main(
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
    concepts_path = vault / "state" / "concepts" / "bad-comp.json"
    assert code == EXIT_ERROR or not concepts_path.is_file()
