"""AS-2.0-SCHED-001 — Autonomy scheduler dry-run plan (no live dispatch).

Bound to the Atlas 1.0 compatibility anchor. Never Layer B authority.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-SCHED-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "SCHEDULER DRY-RUN ≠ LIVE DISPATCH / ≠ AUTHORITY"
SCHEMA_KIND = "scheduler-dry-run"


class SchedulerDryRunError(ValueError):
    """Fail-closed contract error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_scheduler_dry_run(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic scheduler-dry-run record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise SchedulerDryRunError("scheduler-plan-id-invalid")

    if bool(kwargs.get("enable_live_dispatch")):
        raise SchedulerDryRunError("scheduler-live-dispatch-forbidden")
    jobs = kwargs.get("jobs") or [
        {"job_id": "validate", "kind": "validate", "enabled": True},
        {"job_id": "build-indexes", "kind": "build-indexes", "enabled": True},
        {"job_id": "health", "kind": "health", "enabled": True},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "plan_id": rid,
        "live_dispatch": False,
        "jobs": list(jobs),
        "authority": {
            "level": "derived",
            "note": "Scheduler dry-run only; no live dispatch in this package",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise SchedulerDryRunError(f"scheduler-dry-run-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "scheduler" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
