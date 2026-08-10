"""AS-KF2-002 — Knowledge Fabric inventory export (derived ≠ authority).

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

PACKAGE_ID = "AS-KF2-002"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "KF2 INVENTORY ≠ AUTHORITY / ≠ CROSS PROMOTE"
SCHEMA_KIND = "kf2-fabric-inventory"


class Kf2InventoryError(ValueError):
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


def build_kf2_fabric_inventory(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic kf2-fabric-inventory record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise Kf2InventoryError("kf2-inventory-id-invalid")

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "inventory_id": rid,
        "namespace_count": int(kwargs.get("namespace_count", 0)),
        "entity_count": int(kwargs.get("entity_count", 0)),
        "relationship_count": int(kwargs.get("relationship_count", 0)),
        "cross_promote": False,
        "authority": {
            "level": "derived",
            "note": "KF2 inventory is fabric accounting only",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise Kf2InventoryError(f"kf2-fabric-inventory-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "kf2" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
