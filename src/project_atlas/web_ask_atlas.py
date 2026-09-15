"""AS-2.0-WEB-ASK-001 — Ask Atlas read-only query contract (UI≠canonical).

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

PACKAGE_ID = "AS-2.0-WEB-ASK-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "ASK ATLAS ≠ CANONICAL WRITE / ≠ AUTHORITY"
SCHEMA_KIND = "web-ask-atlas-contract"


class WebAskAtlasError(ValueError):
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


def build_web_ask_atlas_contract(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic web-ask-atlas-contract record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise WebAskAtlasError("web-ask-contract-id-invalid")

    shapes = list(kwargs.get("query_shapes") or ["exact", "prefix", "authoritative"])
    if bool(kwargs.get("allow_canonical_writes")):
        raise WebAskAtlasError("web-ask-canonical-writes-forbidden")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "contract_id": rid,
        "read_only": True,
        "canonical_writes": False,
        "query_shapes": [str(s) for s in shapes],
        "authority": {
            "level": "derived",
            "note": "Ask Atlas is a read lens over knowledge query; UI≠canonical",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise WebAskAtlasError(f"web-ask-atlas-contract-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "web" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
