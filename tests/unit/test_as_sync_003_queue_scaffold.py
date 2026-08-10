from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.sync_queue import (
    SyncQueueError,
    build_dry_run_sync_queue,
    write_dry_run_sync_queue,
)

UUID_A = "11111111-1111-4111-8111-111111111111"
UUID_B = "22222222-2222-4222-8222-222222222222"


def _plan() -> dict[str, object]:
    return {
        "schema_version": 1,
        "schema": "atlas.sync_plan.dry_run.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": (
            "DRY-RUN SYNC PLAN SCAFFOLD \N{NOT EQUAL TO} "
            "AS-SYNC-002 CERTIFIED / \N{NOT EQUAL TO} PILOT PASS"
        ),
        "package": "AS-SYNC-002-SCAFFOLD",
        "production_sync_certified": False,
        "estate_pilot_passed": False,
        "registry_id": "registry-fixture",
        "vault_identity": "vault-fixture",
        "project_order": [UUID_A, UUID_B],
        "entries": [
            {
                "project_uuid": UUID_B,
                "disposition": "disabled",
                "reason": "project_disabled",
                "root_id": "root-b",
                "project_root": "fixtures/b",
            },
            {
                "project_uuid": UUID_A,
                "disposition": "eligible",
                "reason": None,
                "root_id": "root-a",
                "project_root": "fixtures/a",
            },
        ],
        "quarantine_paths": [],
        "checkpoint": {
            "resume_from_project_uuid": None,
            "completed_project_uuids": [],
            "last_checkpoint_key": None,
        },
        "generated": {"by": "atlas-sync-002-scaffold"},
    }


def test_queue_is_deterministic_and_preserves_plan_order() -> None:
    first = build_dry_run_sync_queue(_plan())
    second = build_dry_run_sync_queue(copy.deepcopy(_plan()))
    assert first == second
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert [row["project_uuid"] for row in first["entries"]] == [UUID_A, UUID_B]
    assert [row["queue_index"] for row in first["entries"]] == [0, 1]
    assert [row["queue_state"] for row in first["entries"]] == ["pending", "blocked"]


def test_queue_validates_against_shipped_schema() -> None:
    queue = build_dry_run_sync_queue(_plan())
    validate_record(queue, "sync-queue-dry-run")
    assert queue["resume_cursor"]["next_queue_index"] is None
    assert queue["entries"][0]["retry_policy"]["max_attempts"] is None
    assert queue["entries"][0]["estate_receipt"]["status"] == "not_issued"


def test_write_is_limited_to_generated_ops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    queue = build_dry_run_sync_queue(_plan())
    path = write_dry_run_sync_queue(tmp_path, queue)
    assert path == (tmp_path / "generated" / "ops" / "sync-queue-dry-run.json").resolve()
    assert not (tmp_path / "00-system" / "sync").exists()

    monkeypatch.setattr(
        "project_atlas.sync_queue.REPORT_RELATIVE", Path("00-system/sync/sync-queue.json")
    )
    with pytest.raises(SyncQueueError, match="must not write under 00-system/sync"):
        write_dry_run_sync_queue(tmp_path, queue)
    assert not (tmp_path / "00-system" / "sync" / "sync-queue.json").exists()


def test_write_rejects_generated_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Symlink escape of generated/ must fail closed before any write (AT-013)."""
    queue = build_dry_run_sync_queue(_plan())
    outside = tmp_path / "outside"
    outside.mkdir()
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "generated").symlink_to(outside, target_is_directory=True)
    with pytest.raises(SyncQueueError, match="escapes vault root"):
        write_dry_run_sync_queue(vault, queue)
    assert not (outside / "ops" / "sync-queue-dry-run.json").exists()


@pytest.mark.parametrize("plan", [{}, {"entries": []}])
def test_empty_or_invalid_plan_fails_closed(plan: dict[str, object]) -> None:
    with pytest.raises(SyncQueueError):
        build_dry_run_sync_queue(plan)


def test_empty_schema_valid_plan_fails_closed() -> None:
    plan = _plan()
    plan["project_order"] = []
    plan["entries"] = []
    with pytest.raises(SyncQueueError, match="at least one"):
        build_dry_run_sync_queue(plan)


def test_certification_flags_cannot_be_raised() -> None:
    queue = build_dry_run_sync_queue(_plan())
    assert queue["production_sync_certified"] is False
    assert queue["estate_pilot_passed"] is False

    queue["production_sync_certified"] = True
    with pytest.raises(SchemaValidationError):
        validate_record(queue, "sync-queue-dry-run")

    plan = _plan()
    plan["estate_pilot_passed"] = True
    with pytest.raises(SyncQueueError):
        build_dry_run_sync_queue(plan)
