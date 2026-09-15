"""AS-2.0-OBS-UX-002 — Obsidian workspace binding deepen (≠ plugin ship).

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

PACKAGE_ID = "AS-2.0-OBS-UX-002"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "OBSIDIAN WORKSPACE ≠ PLUGIN SHIP / ≠ CANONICAL"
SCHEMA_KIND = "obsidian-workspace-binding"


class ObsidianWorkspaceError(ValueError):
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


def build_obsidian_workspace_binding(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic obsidian-workspace-binding record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise ObsidianWorkspaceError("obsidian-binding-id-invalid")

    if bool(kwargs.get("ship_plugin")):
        raise ObsidianWorkspaceError("obsidian-plugin-ship-forbidden")
    lenses = list(kwargs.get("lens_ids") or ["mission-control", "ops-health", "impact"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "binding_id": rid,
        "plugin_shipped": False,
        "canonical_writes": False,
        "lens_ids": [str(x) for x in lenses],
        "authority": {
            "level": "derived",
            "note": "Obsidian workspace binding is presentation-only",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise ObsidianWorkspaceError(f"obsidian-workspace-binding-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "obsidian" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
