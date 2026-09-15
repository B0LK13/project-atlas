"""AS-2.0-REALITY-GAP-UI-001 — Reality Gap UI panel catalog (read-only).

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

PACKAGE_ID = "AS-2.0-REALITY-GAP-UI-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "REALITY GAP UI ≠ CANONICAL WRITE / ≠ PILOT PASS"
SCHEMA_KIND = "reality-gap-ui-catalog"


class RealityGapUiError(ValueError):
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


def build_reality_gap_ui_catalog(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic reality-gap-ui-catalog record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise RealityGapUiError("reality-gap-ui-id-invalid")

    if bool(kwargs.get("allow_canonical_writes")):
        raise RealityGapUiError("reality-gap-ui-canonical-writes-forbidden")
    panels = kwargs.get("panels") or [
        {"panel_id": "estate-twin", "gap_id": "estate-twin", "read_only": True},
        {"panel_id": "federation", "gap_id": "federation", "read_only": True},
        {"panel_id": "advanced-ux", "gap_id": "advanced-ux", "read_only": True},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "catalog_id": rid,
        "canonical_writes": False,
        "panels": list(panels),
        "authority": {
            "level": "derived",
            "note": "Reality Gap UI panels are read-only operator lenses",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise RealityGapUiError(f"reality-gap-ui-catalog-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "reality-gap" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
