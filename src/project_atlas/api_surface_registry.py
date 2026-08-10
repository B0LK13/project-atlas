"""AS-2.0-API-001 — API 2.0 surface registry (read-only; write_enabled=false).

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

PACKAGE_ID = "AS-2.0-API-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "API 2.0 REGISTRY ≠ WRITE BRIDGE / ≠ AUTHORITY"
SCHEMA_KIND = "api-surface-registry"


class ApiSurfaceRegistryError(ValueError):
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


def build_api_surface_registry(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic api-surface-registry record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise ApiSurfaceRegistryError("api-registry-id-invalid")

    if bool(kwargs.get("enable_writes")):
        raise ApiSurfaceRegistryError("api-writes-forbidden")
    surfaces = kwargs.get("surfaces") or [
        {"surface_id": "health", "route_class": "health", "enabled": True},
        {"surface_id": "projects", "route_class": "projects", "enabled": True},
        {"surface_id": "knowledge", "route_class": "knowledge", "enabled": True},
        {"surface_id": "graph", "route_class": "graph", "enabled": True},
        {"surface_id": "ops", "route_class": "ops", "enabled": True},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "registry_id": rid,
        "write_enabled": False,
        "surfaces": list(surfaces),
        "authority": {
            "level": "derived",
            "note": "API 2.0 registry documents read surfaces only",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise ApiSurfaceRegistryError(f"api-surface-registry-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "api" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
