"""Golden-fixture tests for AS-WP-004 discovery and governed ingestion."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from internal import (
    document_inventory,
    ingestion_orchestrator,
    ingestion_state,
    ingestion_validation,
    project_discovery,
)

FIXTURE = Path(__file__).parent / "fixtures" / "project-atlas"
MOCK_MDA = Path(__file__).parent / "fixtures" / "bin" / "mda"


def test_discovery_and_inventory_are_deterministic(tmp_path: Path) -> None:
    root = tmp_path / "project-atlas"
    shutil.copytree(FIXTURE, root)
    project = project_discovery.discover_projects(root, project_root=root)[0]
    config = {"authority": project.authority}
    first = document_inventory.inventory_project(root, project_id=project.project_id, config=config)
    second = document_inventory.inventory_project(root, project_id=project.project_id, config=config)
    assert first["inventory_sha256"] == second["inventory_sha256"]
    paths = [item["relative_path"] for item in first["documents"]]
    assert paths == sorted(paths, key=str.casefold)
    graph = next(item for item in first["documents"] if item["relative_path"] == "graphify-out/graph.json")
    assert graph["classification"]["type"] == "graphify-output"
    assert graph["authority"]["level"] == "derived"
    architecture = next(item for item in first["documents"] if item["relative_path"] == "docs/ARCHITECTURE.md")
    assert architecture["authority"]["level"] == "primary"
    assert graph["processing"]["state"] == "unsupported"
    secret = next(item for item in first["documents"] if item["relative_path"] == "credentials.json")
    assert secret["security"]["sensitivity"] == "sensitive"
    assert secret["processing"]["state"] == "sensitive"
    unsupported = next(item for item in first["documents"] if item["relative_path"] == "archive.pdf")
    assert unsupported["processing"]["state"] == "unsupported"


def test_incremental_diff_tracks_new_changed_unchanged_deleted(tmp_path: Path) -> None:
    root = tmp_path / "project-atlas"
    shutil.copytree(FIXTURE, root)
    first = document_inventory.inventory_project(root, project_id="project-atlas")
    state = ingestion_state.apply_inventory(
        ingestion_state.load_state(tmp_path / "state.json", "project-atlas"),
        first,
        ingestion_state.diff_inventory(first, {"documents": {}}),
    )
    (root / "README.md").write_text("# changed\n", encoding="utf-8")
    (root / "docs/roadmap.md").unlink()
    (root / "new.md").write_text("# new\n", encoding="utf-8")
    second = document_inventory.inventory_project(root, project_id="project-atlas")
    diff = ingestion_state.diff_inventory(second, state)
    assert any(item["relative_path"] == "README.md" for item in diff["changed"])
    assert any(item["relative_path"] == "new.md" for item in diff["new"])
    assert any(item["relative_path"] == "docs/roadmap.md" for item in diff["deleted"])
    assert diff["unchanged"]


def test_discovery_and_inventory_fail_closed_for_escape_and_symlink(tmp_path: Path) -> None:
    root = tmp_path / "project-atlas"
    shutil.copytree(FIXTURE, root)
    outside = tmp_path / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    link = root / "external.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable in this filesystem")
    with pytest.raises(ValueError, match="outside workspace"):
        project_discovery.discover_projects(tmp_path / "other", project_root=root)
    inventory = document_inventory.inventory_project(root, project_id="project-atlas")
    symlink = next(item for item in inventory["documents"] if item["relative_path"] == "external.md")
    assert symlink["processing"]["state"] == "quarantined"


def test_golden_ingestion_routes_and_no_op_replay(tmp_path: Path) -> None:
    root = tmp_path / "project-atlas"
    vault = tmp_path / "vault"
    shutil.copytree(FIXTURE, root)
    project = project_discovery.discover_projects(root, project_root=root)[0]
    first = ingestion_orchestrator.ingest_project(
        project, vault_root=vault, incremental=True, strict=True, mda_command=str(MOCK_MDA)
    )
    assert first["ok"]
    assert first["processing"]["routed"] == first["processing"]["verified"]
    assert (vault / "projects/project-atlas/documentation-map.md").is_file()
    assert len(list((vault / "routing/receipts").glob("*.yaml"))) == first["processing"]["routed"]
    validation = ingestion_validation.validate(vault, "project-atlas")
    assert validation.ok, validation.errors

    before = {path: path.read_bytes() for path in vault.rglob("*") if path.is_file()}
    second = ingestion_orchestrator.ingest_project(
        project, vault_root=vault, incremental=True, strict=True, mda_command=str(MOCK_MDA)
    )
    assert second["receipt"]["transaction"]["no_op"]
    assert second["counts"]["files_new"] == 0
    assert second["counts"]["files_changed"] == 0
    after = {path: path.read_bytes() for path in vault.rglob("*") if path.is_file()}
    assert after == before


def test_changed_and_deleted_source_are_incremental_and_historical(tmp_path: Path) -> None:
    root = tmp_path / "project-atlas"
    vault = tmp_path / "vault"
    shutil.copytree(FIXTURE, root)
    project = project_discovery.discover_projects(root, project_root=root)[0]
    ingestion_orchestrator.ingest_project(project, vault_root=vault, mda_command=str(MOCK_MDA))
    (root / "README.md").write_text("# Project Atlas\nstatus: active\n", encoding="utf-8")
    (root / "docs/roadmap.md").unlink()
    result = ingestion_orchestrator.ingest_project(project, vault_root=vault, mda_command=str(MOCK_MDA))
    assert result["counts"]["files_changed"] == 1
    assert result["counts"]["files_deleted"] == 1
    state = json.loads((vault / "ingestion/state/project-atlas.json").read_text(encoding="utf-8"))
    assert state["documents"]["project-atlas:docs/roadmap.md"]["state"] == "deleted"


def test_strict_ingestion_failure_rolls_back_previous_vault_state(tmp_path: Path) -> None:
    root = tmp_path / "project-atlas"
    vault = tmp_path / "vault"
    shutil.copytree(FIXTURE, root)
    project = project_discovery.discover_projects(root, project_root=root)[0]
    ingestion_orchestrator.ingest_project(project, vault_root=vault, mda_command=str(MOCK_MDA))
    before = {
        path.relative_to(vault): path.read_bytes()
        for path in vault.rglob("*") if path.is_file()
    }
    (root / "new.md").write_text("# will fail\n", encoding="utf-8")
    with pytest.raises(ingestion_orchestrator.IngestionError):
        ingestion_orchestrator.ingest_project(project, vault_root=vault, mda_command="/nonexistent/mda")
    after = {
        path.relative_to(vault): path.read_bytes()
        for path in vault.rglob("*") if path.is_file()
        if "ingestion/failures/" not in path.relative_to(vault).as_posix()
    }
    assert after == before
    assert list((vault / "ingestion/failures").glob("*.json"))
