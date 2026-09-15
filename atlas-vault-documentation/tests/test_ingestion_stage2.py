"""Controlled Stage 2 fixture certification scenarios for AS-WP-004."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from internal import (
    ingestion_orchestrator,
    ingestion_validation,
    project_discovery,
)

FIXTURES = Path(__file__).parent / "fixtures" / "projects"
MOCK_MDA = Path(__file__).parent / "fixtures" / "bin" / "mda"


def _copy_fixture(name: str, destination: Path) -> tuple[Path, project_discovery.ProjectRecord]:
    root = destination / name
    shutil.copytree(FIXTURES / name, root)
    return root, project_discovery.discover_projects(root, project_root=root)[0]


def test_stage2_workspace_discovery_and_monorepo_policy_are_deterministic(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    names = ("documentation-rich", "sparse-readme", "monorepo", "mixed-formats", "graphify-present")
    for name in names:
        shutil.copytree(FIXTURES / name, workspace / name)
    first = project_discovery.discover_projects(workspace)
    second = project_discovery.discover_projects(workspace)
    assert [item.project_id for item in first] == sorted(names)
    assert project_discovery.serialize_records(first) == project_discovery.serialize_records(second)
    separate = project_discovery.discover_projects(
        workspace / "monorepo", nested_repository_policy="separate-project"
    )
    assert {item.project_id for item in separate} == {"monorepo", "web", "api", "shared"}


def test_rich_sparse_mixed_and_graphify_fixtures_ingest_safely(tmp_path: Path) -> None:
    for name in ("documentation-rich", "sparse-readme", "mixed-formats", "graphify-present"):
        _root, project = _copy_fixture(name, tmp_path)
        vault = tmp_path / f"vault-{name}"
        result = ingestion_orchestrator.ingest_project(
            project, vault_root=vault, mda_command=str(MOCK_MDA)
        )
        assert result["ok"]
        assert ingestion_validation.validate(vault, project.project_id).ok
        replay = ingestion_orchestrator.ingest_project(
            project, vault_root=vault, mda_command=str(MOCK_MDA)
        )
        assert replay["status"] == "no-op"
        assert replay["processing"]["routed"] == 0
        serialized = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in vault.rglob("*")
            if path.is_file()
        )
        assert "must-not-be-captured" not in serialized
        if name == "sparse-readme":
            assert result["coverage"]["counts"]["missing"] >= 1
        if name == "mixed-formats":
            assert result["counts"]["files_sensitive"] == 3
            assert result["counts"]["files_unsupported"] == 3
        if name == "graphify-present":
            assert result["receipt"]["graphify"]["files_inventoried"] == 4
            assert not any(
                "graphify-out" in event.as_posix()
                for event in (vault / "routing" / "receipts").glob("*.yaml")
            )
        if name == "documentation-rich":
            assert any(
                item["authority"]["level"] == "primary"
                for item in result["inventory"]["documents"]
                if item["relative_path"] == "docs/decisions/ADR-001.md"
            )


def test_stage2_incremental_new_changed_deleted_rename_and_history(tmp_path: Path) -> None:
    root, project = _copy_fixture("documentation-rich", tmp_path)
    vault = tmp_path / "vault"
    ingestion_orchestrator.ingest_project(project, vault_root=vault, mda_command=str(MOCK_MDA))
    (root / "new.md").write_text("# New evidence\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Documentation Rich\nstatus: active\nchanged\n", encoding="utf-8"
    )
    old = root / "ROADMAP.md"
    renamed = root / "ROADMAP-RENAMED.md"
    old.rename(renamed)
    (root / "WORKLOG.md").unlink()
    result = ingestion_orchestrator.ingest_project(
        project, vault_root=vault, mda_command=str(MOCK_MDA)
    )
    assert result["counts"]["files_new"] == 1
    assert result["counts"]["files_changed"] == 1
    assert result["counts"]["files_deleted"] == 1
    assert result["counts"]["files_renamed"] == 1
    state = json.loads(
        (vault / "ingestion/state/documentation-rich.json").read_text(encoding="utf-8")
    )
    renamed_state = state["documents"]["documentation-rich:ROADMAP-RENAMED.md"]
    assert renamed_state["path_history"] == ["ROADMAP.md", "ROADMAP-RENAMED.md"]
    assert state["documents"]["documentation-rich:WORKLOG.md"]["state"] == "deleted"


def test_stage2_failed_incremental_transaction_preserves_previous_state(tmp_path: Path) -> None:
    root, project = _copy_fixture("sparse-readme", tmp_path)
    vault = tmp_path / "vault"
    ingestion_orchestrator.ingest_project(project, vault_root=vault, mda_command=str(MOCK_MDA))
    before = {
        path.relative_to(vault): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
    }
    (root / "new.md").write_text("# retryable\n", encoding="utf-8")
    try:
        ingestion_orchestrator.ingest_project(project, vault_root=vault, mda_command="/missing/mda")
    except ingestion_orchestrator.IngestionError:
        pass
    else:
        raise AssertionError("strict ingestion unexpectedly succeeded")
    after = {
        path.relative_to(vault): path.read_bytes()
        for path in vault.rglob("*")
        if path.is_file()
        and "ingestion/failures/" not in path.relative_to(vault).as_posix()
    }
    assert after == before
    retry = ingestion_orchestrator.ingest_project(
        project, vault_root=vault, mda_command=str(MOCK_MDA)
    )
    assert retry["processing"]["routed"] == 1
