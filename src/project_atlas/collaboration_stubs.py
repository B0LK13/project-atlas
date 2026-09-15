"""AS-2.0-COLLAB-001 — collaboration stubs registry (live_collab=false).

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

PACKAGE_ID = "AS-2.0-COLLAB-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "COLLAB STUBS ≠ LIVE COLLAB / ≠ AUTHORITY"
SCHEMA_KIND = "collaboration-stub-registry"


class CollaborationStubError(ValueError):
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


def build_collaboration_stub_registry(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic collaboration-stub-registry record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise CollaborationStubError("collab-registry-id-invalid")

    if bool(kwargs.get("enable_live_collab")):
        raise CollaborationStubError("collab-live-forbidden")
    stubs = kwargs.get("stubs") or [
        {"stub_id": "review-queue", "kind": "review-queue", "enabled": True},
        {"stub_id": "shared-receipt", "kind": "shared-receipt", "enabled": True},
        {"stub_id": "comment-thread", "kind": "comment-thread", "enabled": False},
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "registry_id": rid,
        "live_collab": False,
        "stubs": list(stubs),
        "authority": {
            "level": "derived",
            "note": "Collaboration stubs only; no live multi-user plane",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise CollaborationStubError(f"collaboration-stub-registry-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "collab" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
