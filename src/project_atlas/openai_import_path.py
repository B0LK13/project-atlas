"""AS-2.0-OAI-IMPORT-002 — OAI importer path receipt (fixtures if no export).

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

PACKAGE_ID = "AS-2.0-OAI-IMPORT-002"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "OAI IMPORT PATH ≠ LIVE API / ≠ AUTHORITY"
SCHEMA_KIND = "openai-import-path-receipt"


class OpenaiImportPathError(ValueError):
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


def build_openai_import_path_receipt(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic openai-import-path-receipt record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise OpenaiImportPathError("oai-path-id-invalid")

    if bool(kwargs.get("enable_live_api")):
        raise OpenaiImportPathError("oai-live-api-forbidden")
    export_present = bool(kwargs.get("export_present", False))
    path_mode = "fixture-sample" if export_present else "fixture-no-export"
    status = "ready-fixture" if export_present else "blocked-no-export"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": rid,
        "live_api": False,
        "export_present": export_present,
        "path_mode": path_mode,
        "status": status,
        "authority": {
            "level": "derived",
            "note": "OAI path uses fixtures when no export; never live API",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise OpenaiImportPathError(f"openai-import-path-receipt-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "openai" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
