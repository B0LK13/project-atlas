"""AS-2.0-FED-002 — consume-only federation read lens (no cross-vault promote).

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

PACKAGE_ID = "AS-2.0-FED-002"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "FED READ LENS ≠ CROSS-VAULT PROMOTE / ≠ AUTHORITY"
SCHEMA_KIND = "federation-read-lens"


class FederationLensError(ValueError):
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


def build_federation_read_lens(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic federation-read-lens record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise FederationLensError("federation-lens-id-invalid")

    federation_id = str(kwargs.get("federation_id", "")).strip()
    if not _ID_RE.fullmatch(federation_id):
        raise FederationLensError("federation-id-invalid")
    members = list(kwargs.get("members_visible") or [])
    if not members:
        raise FederationLensError("federation-members-empty")
    if bool(kwargs.get("allow_cross_promote")):
        raise FederationLensError("federation-cross-promote-forbidden")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "lens_id": rid,
        "federation_id": federation_id,
        "cross_vault_promote": False,
        "members_visible": [str(m) for m in members],
        "authority": {
            "level": "derived",
            "note": "Federation read lens is consume-only membership visibility",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise FederationLensError(f"federation-read-lens-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "federation" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
