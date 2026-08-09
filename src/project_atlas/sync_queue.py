"""AS-SYNC-003-SCAFFOLD - deterministic dry-run queue/retry/resume stubs.

Consumes only an explicit AS-SYNC-002 dry-run plan document. It never scans an
estate or filesystem root, never writes production sync state, and never claims
production sync certification or an estate PILOT pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.source_identity import validate_project_uuid

GENERATOR_ID = "atlas-sync-003-scaffold"
PACKAGE_ID = "AS-SYNC-003-SCAFFOLD"
REPORT_SCHEMA = "sync-queue-dry-run"
REPORT_RELATIVE = Path("generated") / "ops" / "sync-queue-dry-run.json"


class SyncQueueError(ValueError):
    """Fail-closed dry-run sync queue error."""


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _validated_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict) or not plan:
        raise SyncQueueError("plan must be a non-empty object")
    try:
        validate_record(plan, "sync-plan-dry-run")
    except (SchemaValidationError, KeyError) as exc:
        raise SyncQueueError("plan must be a valid sync-plan-dry-run document") from exc
    if plan.get("production_sync_certified") is not False:
        raise SyncQueueError("production_sync_certified must remain false")
    if plan.get("estate_pilot_passed") is not False:
        raise SyncQueueError("estate_pilot_passed must remain false")
    return plan


def build_dry_run_sync_queue(plan: dict[str, Any]) -> dict[str, Any]:
    """Build a queue scaffold from an explicit, schema-valid dry-run plan."""
    document = _validated_plan(plan)
    raw_entries = document["entries"]
    project_order = document["project_order"]
    if not raw_entries or not project_order:
        raise SyncQueueError("plan must contain at least one ordered project entry")

    by_uuid: dict[str, dict[str, Any]] = {}
    for raw in raw_entries:
        project_uuid = validate_project_uuid(str(raw["project_uuid"]))
        if project_uuid in by_uuid:
            raise SyncQueueError(f"duplicate project_uuid in plan: {project_uuid}")
        by_uuid[project_uuid] = raw

    normalized_order = [validate_project_uuid(str(value)) for value in project_order]
    if len(normalized_order) != len(set(normalized_order)):
        raise SyncQueueError("project_order contains duplicate project_uuid values")
    if set(normalized_order) != set(by_uuid):
        raise SyncQueueError("project_order must match plan entries exactly")

    entries: list[dict[str, Any]] = []
    for queue_index, project_uuid in enumerate(normalized_order):
        source = by_uuid[project_uuid]
        disposition = str(source["disposition"])
        entries.append(
            {
                "queue_index": queue_index,
                "project_uuid": project_uuid,
                "disposition": disposition,
                "queue_state": "pending" if disposition == "eligible" else "blocked",
                "retry_policy": {
                    "max_attempts": None,
                    "backoff_seconds": [],
                    "retryable_errors": [],
                },
                "resume_checkpoint_key": None,
                "estate_receipt": {
                    "receipt_id": None,
                    "status": "not_issued",
                    "evidence_hash": None,
                },
            }
        )

    queue: dict[str, Any] = {
        "schema_version": 1,
        "schema": "atlas.sync_queue.dry_run.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "DRY-RUN SYNC QUEUE SCAFFOLD - NOT PRODUCTION CERTIFIED / NOT PILOT PASS",
        "package": PACKAGE_ID,
        "production_sync_certified": False,
        "estate_pilot_passed": False,
        "registry_id": document["registry_id"],
        "vault_identity": document["vault_identity"],
        "source_plan_package": document["package"],
        "entries": entries,
        "resume_cursor": {
            "next_queue_index": None,
            "next_project_uuid": None,
            "completed_project_uuids": [],
            "last_estate_receipt_id": None,
        },
        "generated": {"by": GENERATOR_ID},
    }
    validate_record(queue, REPORT_SCHEMA)
    return queue


def write_dry_run_sync_queue(vault: Path, document: dict[str, Any]) -> Path:
    """Persist only to ``generated/ops/sync-queue-dry-run.json``."""
    validate_record(document, REPORT_SCHEMA)
    vault_root = vault.expanduser().resolve()
    ops_root = (vault_root / "generated" / "ops").resolve()
    path = (vault_root / REPORT_RELATIVE).resolve()
    production_sync = (vault_root / "00-system" / "sync").resolve()
    if path.parent != ops_root or not path.is_relative_to(ops_root):
        raise SyncQueueError("queue scaffold may write only under generated/ops/")
    if path.is_relative_to(production_sync):
        raise SyncQueueError("queue scaffold must not write under 00-system/sync/")
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(path, payload)
    return path
