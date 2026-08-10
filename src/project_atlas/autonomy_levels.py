"""AS-2.0-AUTONOMY-001 — Autonomy L0–L5 productize catalog (live_autonomy=false).

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

PACKAGE_ID = "AS-2.0-AUTONOMY-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "AUTONOMY CATALOG ≠ LIVE AUTONOMY / ≠ AUTHORITY"
SCHEMA_KIND = "autonomy-level-catalog"


class AutonomyLevelError(ValueError):
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


def build_autonomy_level_catalog(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic autonomy-level-catalog record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise AutonomyLevelError("autonomy-catalog-id-invalid")

    if bool(kwargs.get("enable_live_autonomy")):
        raise AutonomyLevelError("autonomy-live-forbidden")
    levels = kwargs.get("levels") or [
        {"level": 0, "name": "manual", "enabled": True, "requires_receipt": True},
        {"level": 1, "name": "assisted", "enabled": True, "requires_receipt": True},
        {"level": 2, "name": "supervised", "enabled": True, "requires_receipt": True},
        {"level": 3, "name": "bounded-auto", "enabled": False, "requires_receipt": True},
        {"level": 4, "name": "estate-auto", "enabled": False, "requires_receipt": True},
        {"level": 5, "name": "unbounded", "enabled": False, "requires_receipt": True},
    ]
    if len(levels) != 6:
        raise AutonomyLevelError("autonomy-levels-count-invalid")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "catalog_id": rid,
        "live_autonomy": False,
        "levels": list(levels),
        "authority": {
            "level": "derived",
            "note": "Autonomy catalog productizes L0-L5; live autonomy off",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise AutonomyLevelError(f"autonomy-level-catalog-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "autonomy" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
