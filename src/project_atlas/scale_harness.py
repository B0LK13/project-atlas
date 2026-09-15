"""AS-2.0-SCALE-001 — scale harness plan (live_load=false).

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

PACKAGE_ID = "AS-2.0-SCALE-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "SCALE HARNESS ≠ LIVE LOAD / ≠ AUTHORITY"
SCHEMA_KIND = "scale-harness-plan"


class ScaleHarnessError(ValueError):
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


def build_scale_harness_plan(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic scale-harness-plan record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise ScaleHarnessError("scale-plan-id-invalid")

    if bool(kwargs.get("enable_live_load")):
        raise ScaleHarnessError("scale-live-load-forbidden")
    targets = kwargs.get("targets") or [
        {"target_id": "files", "metric": "files", "budget": 10000},
        {"target_id": "claims", "metric": "claims", "budget": 50000},
        {"target_id": "indexes", "metric": "indexes", "budget": 100},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "plan_id": rid,
        "live_load": False,
        "targets": list(targets),
        "authority": {
            "level": "derived",
            "note": "Scale harness plans budgets; no live load generation here",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise ScaleHarnessError(f"scale-harness-plan-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "scale" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
