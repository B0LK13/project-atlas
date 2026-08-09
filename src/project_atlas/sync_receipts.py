"""AS-SYNC-004-SCAFFOLD - deterministic estate receipt and trigger stubs.

Consumes only an explicit AS-SYNC-003 dry-run queue document. It never scans an
estate or filesystem root, registers triggers, issues receipts, or claims
production sync certification or an estate PILOT pass.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from project_atlas.schema import SchemaValidationError, validate_record
from project_atlas.source_identity import validate_project_uuid

GENERATOR_ID = "atlas-sync-004-scaffold"
PACKAGE_ID = "AS-SYNC-004-SCAFFOLD"
REPORT_SCHEMA = "sync-receipts-dry-run"
_ALLOWED_REPORT_RELATIVE = (
    Path("generated") / "ops" / "sync-receipts-dry-run.json"
)
REPORT_RELATIVE = _ALLOWED_REPORT_RELATIVE
_TRIGGER_TYPES = ("on_change", "on_schedule")


class SyncReceiptError(ValueError):
    """Fail-closed dry-run estate-receipt scaffold error."""


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _validated_queue(queue: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(queue, dict) or not queue:
        raise SyncReceiptError("queue must be a non-empty object")
    try:
        validate_record(queue, "sync-queue-dry-run")
    except (SchemaValidationError, KeyError) as exc:
        raise SyncReceiptError(
            "queue must be a valid sync-queue-dry-run document"
        ) from exc
    if queue.get("production_sync_certified") is not False:
        raise SyncReceiptError("production_sync_certified must remain false")
    if queue.get("estate_pilot_passed") is not False:
        raise SyncReceiptError("estate_pilot_passed must remain false")
    return queue


def build_dry_run_sync_receipts(queue: dict[str, Any]) -> dict[str, Any]:
    """Build inert estate-receipt and trigger stubs from an explicit queue."""
    document = _validated_queue(queue)
    raw_entries = document["entries"]
    if not raw_entries:
        raise SyncReceiptError("queue must contain at least one entry")

    seen_projects: set[str] = set()
    estate_receipts: list[dict[str, Any]] = []
    triggers: list[dict[str, Any]] = []
    for expected_index, raw in enumerate(raw_entries):
        queue_index = raw["queue_index"]
        if queue_index != expected_index:
            raise SyncReceiptError("queue_index values must be contiguous and ordered")
        project_uuid = validate_project_uuid(str(raw["project_uuid"]))
        if project_uuid in seen_projects:
            raise SyncReceiptError(f"duplicate project_uuid in queue: {project_uuid}")
        seen_projects.add(project_uuid)

        estate_receipts.append(
            {
                "queue_index": queue_index,
                "project_uuid": project_uuid,
                "receipt_id": None,
                "status": "not_issued",
                "evidence_hash": None,
            }
        )
        for trigger_type in _TRIGGER_TYPES:
            triggers.append(
                {
                    "queue_index": queue_index,
                    "project_uuid": project_uuid,
                    "trigger_type": trigger_type,
                    "enabled": False,
                    "registration_id": None,
                    "expression": None,
                }
            )

    report: dict[str, Any] = {
        "schema_version": 1,
        "schema": "atlas.sync_receipts.dry_run.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "DRY-RUN ESTATE RECEIPT/TRIGGER STUBS - NOT SYNC CERT / NOT PILOT PASS",
        "package": PACKAGE_ID,
        "production_sync_certified": False,
        "estate_pilot_passed": False,
        "registry_id": document["registry_id"],
        "vault_identity": document["vault_identity"],
        "source_queue_package": document["package"],
        "estate_receipts": estate_receipts,
        "triggers": triggers,
        "generated": {"by": GENERATOR_ID},
    }
    validate_record(report, REPORT_SCHEMA)
    return report


def write_dry_run_sync_receipts(vault: Path, document: dict[str, Any]) -> Path:
    """Persist only to ``generated/ops/sync-receipts-dry-run.json``."""
    validate_record(document, REPORT_SCHEMA)
    vault_root = vault.expanduser().resolve()
    path = (vault_root / REPORT_RELATIVE).resolve()
    if not path.is_relative_to(vault_root):
        raise SyncReceiptError("receipt scaffold output path escapes vault root")
    try:
        relative = path.relative_to(vault_root)
    except ValueError as exc:
        raise SyncReceiptError("receipt scaffold output path escapes vault root") from exc
    if relative != _ALLOWED_REPORT_RELATIVE:
        raise SyncReceiptError(
            "receipt scaffold may write only to generated/ops/sync-receipts-dry-run.json"
        )
    production_sync = (vault_root / "00-system" / "sync").resolve()
    if path.is_relative_to(production_sync):
        raise SyncReceiptError("receipt scaffold must not write under 00-system/sync/")
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(path, payload)
    return path
