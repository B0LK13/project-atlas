"""AS-2.0-WEB-SURFACE-001 — Twin UI / Canvas / Timeline surface catalog.

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

PACKAGE_ID = "AS-2.0-WEB-SURFACE-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "WEB SURFACE CATALOG ≠ UI REWRITE / ≠ ESTATE LIVE / ≠ AUTHORITY"
SCHEMA_KIND = "web-surface-catalog"


class WebSurfaceCatalogError(ValueError):
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


def build_web_surface_catalog(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic web-surface-catalog record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise WebSurfaceCatalogError("web-surface-catalog-id-invalid")

    if bool(kwargs.get("allow_ui_rewrite")):
        raise WebSurfaceCatalogError("web-surface-ui-rewrite-forbidden")
    surfaces = kwargs.get("surfaces") or [
        {"surface_id": "ask-atlas", "kind": "ask-atlas", "read_only": True, "estate_live": False},
        {"surface_id": "twin-ui", "kind": "twin-ui", "read_only": True, "estate_live": False},
        {"surface_id": "canvas", "kind": "canvas", "read_only": True, "estate_live": False},
        {"surface_id": "timeline", "kind": "timeline", "read_only": True, "estate_live": False},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "catalog_id": rid,
        "ui_rewrite": False,
        "surfaces": list(surfaces),
        "authority": {
            "level": "derived",
            "note": "Surface catalog is presentation binding only; estate_live=false",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise WebSurfaceCatalogError(f"web-surface-catalog-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "web" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
