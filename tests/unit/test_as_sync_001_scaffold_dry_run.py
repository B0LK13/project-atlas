"""AS-SYNC-001-SCAFFOLD dry-run workspace registry tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.cli import main
from project_atlas.schema import validate_record
from project_atlas.workspace_registry import (
    WorkspaceRegistryError,
    build_dry_run_registry,
    write_dry_run_registry,
)

UUID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _marker(root: Path, *, project_id: str = UUID, name: str = "demo") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".atlas-project.yaml").write_text(
        f"schema_version: 1\nproject:\n  id: {project_id}\n  name: {name}\n",
        encoding="utf-8",
    )


def test_as_sync_scaffold_dry_run_registers_uuid_root(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _marker(root)
    vault = tmp_path / "vault"
    vault.mkdir()
    doc = build_dry_run_registry(
        explicit_roots=[root],
        vault_identity="fixture-vault",
    )
    validate_record(doc, "workspace-registry-dry-run")
    assert doc["production_sync_certified"] is False
    assert doc["estate_pilot_passed"] is False
    assert len(doc["projects"]) == 1
    assert doc["projects"][0]["project_uuid"] == UUID
    path = write_dry_run_registry(vault, doc)
    assert path.as_posix().endswith("generated/ops/workspace-registry-dry-run.json")
    assert not (vault / "00-system" / "sync" / "workspace-registry.json").exists()


def test_as_sync_scaffold_quarantines_non_uuid_marker(tmp_path: Path) -> None:
    root = tmp_path / "nebula-like"
    _marker(root, project_id="nebula")
    doc = build_dry_run_registry(
        explicit_roots=[root],
        vault_identity="fixture-vault",
    )
    assert doc["projects"] == []
    assert doc["quarantine"][0]["reason"] == "missing_or_invalid_project_uuid"


def test_as_sync_scaffold_refuses_empty_roots(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceRegistryError, match="explicit_roots"):
        build_dry_run_registry(explicit_roots=[], vault_identity="x")


def test_as_sync_scaffold_refuses_home(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceRegistryError, match="home"):
        build_dry_run_registry(explicit_roots=[Path.home()], vault_identity="x")


def test_as_sync_scaffold_cli_dry_run(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _marker(root)
    vault = tmp_path / "vault"
    vault.mkdir()
    code = main(
        [
            "sync",
            "registry",
            "dry-run",
            "--root",
            str(root),
            "--vault",
            str(vault),
            "--vault-identity",
            "fixture-vault",
        ]
    )
    assert code == 0
    loaded = json.loads(
        (vault / "generated" / "ops" / "workspace-registry-dry-run.json").read_text(
            encoding="utf-8"
        )
    )
    assert loaded["production_sync_certified"] is False
