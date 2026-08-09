"""AS-SYNC-002-SCAFFOLD dry-run sync plan tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from project_atlas.schema import validate_record
from project_atlas.sync_plan import (
    SyncPlanError,
    build_dry_run_sync_plan,
    write_dry_run_sync_plan,
)
from project_atlas.workspace_registry import build_dry_run_registry

UUID_A = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
UUID_B = "bbbbbbbb-cccc-4ddd-8eee-ffffffffffff"
UUID_C = "cccccccc-dddd-4eee-8fff-000000000001"


def _marker(root: Path, *, project_id: str, name: str = "demo") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".atlas-project.yaml").write_text(
        f"schema_version: 1\nproject:\n  id: {project_id}\n  name: {name}\n",
        encoding="utf-8",
    )


def _fixture_registry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": 1,
        "schema": "atlas.workspace_registry.dry_run.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "DRY-RUN REGISTRY SCAFFOLD ≠ AS-SYNC-001 CERTIFIED / ≠ PILOT PASS",
        "package": "AS-SYNC-001-SCAFFOLD",
        "production_sync_certified": False,
        "estate_pilot_passed": False,
        "registry_id": "fixture-registry",
        "vault_identity": "fixture-vault",
        "allowed_root_prefixes": ["/fixture"],
        "workspaces": [],
        "projects": [
            {
                "project_uuid": UUID_B,
                "source_lineage_id": None,
                "root_id": "root-0001",
                "project_root": "/fixture/b",
                "enabled": True,
                "display_name": "B",
                "policy": None,
                "graphify_opt_in": False,
                "portfolio_opt_in": True,
            },
            {
                "project_uuid": UUID_A,
                "source_lineage_id": None,
                "root_id": "root-0000",
                "project_root": "/fixture/a",
                "enabled": True,
                "display_name": "A",
                "policy": None,
                "graphify_opt_in": False,
                "portfolio_opt_in": True,
            },
        ],
        "quarantine": [],
        "policy_defaults": {
            "include_globs": [],
            "exclude_globs": [],
            "sync_eligible": True,
            "priority": 100,
            "max_file_bytes": None,
            "max_files_per_sync": None,
            "sensitive_defaults": "exclude",
        },
        "generated": {"by": "test"},
    }
    base.update(overrides)
    return base


def test_plan_from_fixture_orders_uuids_and_marks_eligible() -> None:
    plan = build_dry_run_sync_plan(_fixture_registry())
    validate_record(plan, "sync-plan-dry-run")
    assert plan["production_sync_certified"] is False
    assert plan["estate_pilot_passed"] is False
    assert plan["project_order"] == [UUID_A, UUID_B]
    assert [e["disposition"] for e in plan["entries"]] == ["eligible", "eligible"]
    assert plan["checkpoint"]["resume_from_project_uuid"] is None
    assert plan["checkpoint"]["completed_project_uuids"] == []
    assert plan["checkpoint"]["last_checkpoint_key"] is None


def test_plan_dispositions_disabled_and_quarantined() -> None:
    registry = _fixture_registry(
        projects=[
            {
                "project_uuid": UUID_A,
                "source_lineage_id": None,
                "root_id": "root-0000",
                "project_root": "/fixture/a",
                "enabled": False,
                "display_name": "A",
                "policy": None,
                "graphify_opt_in": False,
                "portfolio_opt_in": True,
            },
            {
                "project_uuid": UUID_C,
                "source_lineage_id": None,
                "root_id": "root-0002",
                "project_root": "/fixture/c",
                "enabled": True,
                "display_name": "C",
                "policy": {"sync_eligible": False},
                "graphify_opt_in": False,
                "portfolio_opt_in": True,
            },
            {
                "project_uuid": UUID_B,
                "source_lineage_id": None,
                "root_id": "root-0001",
                "project_root": "/fixture/b",
                "enabled": True,
                "display_name": "B",
                "policy": None,
                "graphify_opt_in": False,
                "portfolio_opt_in": True,
            },
        ],
        quarantine=[
            {"path": "/fixture/b", "reason": "outside_allowed_root_prefixes"},
            {"path": "/fixture/orphan", "reason": "missing_atlas_project_marker"},
        ],
    )
    plan = build_dry_run_sync_plan(registry)
    validate_record(plan, "sync-plan-dry-run")
    by_uuid = {e["project_uuid"]: e for e in plan["entries"]}
    assert by_uuid[UUID_A]["disposition"] == "disabled"
    assert by_uuid[UUID_A]["reason"] == "project_disabled"
    assert by_uuid[UUID_B]["disposition"] == "quarantined"
    assert by_uuid[UUID_B]["reason"] == "outside_allowed_root_prefixes"
    assert by_uuid[UUID_C]["disposition"] == "disabled"
    assert by_uuid[UUID_C]["reason"] == "sync_eligible_false"
    assert plan["project_order"] == [UUID_A, UUID_B, UUID_C]
    assert [q["path"] for q in plan["quarantine_paths"]] == [
        "/fixture/b",
        "/fixture/orphan",
    ]


def test_plan_from_build_dry_run_registry(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    _marker(root, project_id=UUID_A)
    registry = build_dry_run_registry(
        explicit_roots=[root],
        vault_identity="fixture-vault",
    )
    plan = build_dry_run_sync_plan(registry)
    validate_record(plan, "sync-plan-dry-run")
    assert plan["project_order"] == [UUID_A]
    assert plan["entries"][0]["disposition"] == "eligible"
    assert plan["production_sync_certified"] is False
    assert plan["estate_pilot_passed"] is False


def test_plan_write_ops_only_never_production_sync(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    plan = build_dry_run_sync_plan(_fixture_registry())
    path = write_dry_run_sync_plan(vault, plan)
    assert path.as_posix().endswith("generated/ops/sync-plan-dry-run.json")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["package"] == "AS-SYNC-002-SCAFFOLD"
    assert not (vault / "00-system" / "sync").exists()


def test_plan_refuses_missing_registry_keys() -> None:
    with pytest.raises(SyncPlanError, match="missing required key"):
        build_dry_run_sync_plan({"registry_id": "x"})


def test_plan_refuses_duplicate_uuid() -> None:
    registry = _fixture_registry(
        projects=[
            {
                "project_uuid": UUID_A,
                "source_lineage_id": None,
                "root_id": "root-0000",
                "project_root": "/fixture/a",
                "enabled": True,
                "display_name": "A",
                "policy": None,
                "graphify_opt_in": False,
                "portfolio_opt_in": True,
            },
            {
                "project_uuid": UUID_A,
                "source_lineage_id": None,
                "root_id": "root-0001",
                "project_root": "/fixture/a2",
                "enabled": True,
                "display_name": "A2",
                "policy": None,
                "graphify_opt_in": False,
                "portfolio_opt_in": True,
            },
        ]
    )
    with pytest.raises(SyncPlanError, match="duplicate project_uuid"):
        build_dry_run_sync_plan(registry)


def test_plan_deterministic_repeat() -> None:
    registry = _fixture_registry()
    first = build_dry_run_sync_plan(registry)
    second = build_dry_run_sync_plan(registry)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
