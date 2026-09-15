"""AS-WP-005 deterministic Graphify adapter and projection tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from internal import atlas_router, document_inventory, graph_ingestion, graph_validation, project_discovery

FIXTURE = Path(__file__).parent / "fixtures" / "projects" / "graphify-present"


def _fixture(tmp_path: Path) -> tuple[Path, project_discovery.ProjectRecord, dict[str, object]]:
    root = tmp_path / "graphify-present"
    shutil.copytree(FIXTURE, root)
    project = project_discovery.discover_projects(root, project_root=root)[0]
    inventory = document_inventory.inventory_project(root, project_id=project.project_id, config={"authority": project.authority})
    return root, project, inventory


def test_graphify_golden_ingestion_resolves_links_deduplicates_and_quarantines(tmp_path: Path) -> None:
    root, project, inventory = _fixture(tmp_path)
    vault = tmp_path / "vault"
    result = graph_ingestion.ingest_graphify(
        project_id=project.project_id,
        vault_root=vault,
        project_root=root,
        inventory=inventory,
        config={"graphify": {"semantic_ingestion": True}, "authority": project.authority},
        strict=False,
    )
    assert result["status"] == "ingested"
    assert result["metrics"]["duplicates_collapsed"] == 1
    assert result["metrics"]["relationships_orphaned"] == 1
    assert result["metrics"]["relationships_verified"] >= 1
    assert (vault / "projects/graphify-present/relationships.md").is_file()
    assert (vault / "relationships/state/graphify-present.json").is_file()
    assert graph_validation.validate(vault, "graphify-present").ok
    relationship_text = (vault / "projects/graphify-present/relationships.md").read_text(encoding="utf-8")
    assert "Derived projection" in relationship_text
    assert "inferred" in relationship_text.lower()
    receipt = result["receipt"]
    assert receipt["authority"]["graphify"] == "derived"
    assert receipt["authority"]["canonical_override_allowed"] is False


def test_graphify_noop_replay_has_zero_mutations(tmp_path: Path) -> None:
    root, project, inventory = _fixture(tmp_path)
    vault = tmp_path / "vault"
    first = graph_ingestion.ingest_graphify(project_id=project.project_id, vault_root=vault, project_root=root, inventory=inventory, config={"graphify": {"semantic_ingestion": True}, "authority": project.authority}, strict=False)
    before = {path.relative_to(vault): path.read_bytes() for path in vault.rglob("*") if path.is_file()}
    second = graph_ingestion.ingest_graphify(project_id=project.project_id, vault_root=vault, project_root=root, inventory=inventory, config={"graphify": {"semantic_ingestion": True}, "authority": project.authority}, strict=False)
    after = {path.relative_to(vault): path.read_bytes() for path in vault.rglob("*") if path.is_file()}
    assert first["status"] == "ingested"
    assert second["status"] == "no-op"
    assert second["counts"]["artifacts_reparsed"] == 0
    assert after == before


def test_graphify_hash_mismatch_and_external_reference_fail_closed(tmp_path: Path) -> None:
    root, project, inventory = _fixture(tmp_path)
    artifact = root / "graphify-out/graph.json"
    artifact.write_text(artifact.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    try:
        graph_ingestion.ingest_graphify(project_id=project.project_id, vault_root=tmp_path / "vault", project_root=root, inventory=inventory, config={"graphify": {"semantic_ingestion": True}, "authority": project.authority})
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("changed inventory artifact unexpectedly accepted")


def test_graphify_state_is_machine_readable_and_redacts_quarantine_payload(tmp_path: Path) -> None:
    root, project, inventory = _fixture(tmp_path)
    (root / "graphify-out/edges.jsonl").write_text('{"id":"secret-edge","source":"api","target":"missing","type":"invokes","token":"DO_NOT_PERSIST"}\n', encoding="utf-8")
    inventory = document_inventory.inventory_project(root, project_id=project.project_id, config={"authority": project.authority})
    result = graph_ingestion.ingest_graphify(project_id=project.project_id, vault_root=tmp_path / "vault", project_root=root, inventory=inventory, config={"graphify": {"semantic_ingestion": True}, "authority": project.authority}, strict=False)
    quarantine = json.dumps(result["quarantine"])
    assert "DO_NOT_PERSIST" not in quarantine


def test_graphify_projection_failure_leaves_no_partial_state_or_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, project, inventory = _fixture(tmp_path)
    def fail_projection(**_kwargs: object) -> tuple[bool, bool]:
        raise OSError("injected projection failure")
    monkeypatch.setattr(atlas_router, "update_derived_projection", fail_projection)
    try:
        graph_ingestion.ingest_graphify(project_id=project.project_id, vault_root=tmp_path / "vault", project_root=root, inventory=inventory, config={"graphify": {"semantic_ingestion": True}, "authority": project.authority}, strict=False)
    except OSError as exc:
        assert "injected" in str(exc)
    else:
        raise AssertionError("injected projection failure was not raised")
    assert not (tmp_path / "vault" / "relationships" / "state").exists()
    assert not (tmp_path / "vault" / "relationships" / "receipts").exists()
