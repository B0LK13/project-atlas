"""AS-2.0-CTX-002 — context pack composition deepen.

Layered composition rules for AS-2.0-CTX-001 packs. Never invents estate facts.
Bound to Atlas 1.0 compatibility anchor.
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

PACKAGE_ID = "AS-2.0-CTX-002"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "CTX COMPOSITION ≠ ESTATE FACTS / ≠ AUTHORITY"

DEFAULT_LAYERS = (
    {"layer_id": "evidence", "role": "evidence", "provenance_required": True},
    {"layer_id": "derived", "role": "derived", "provenance_required": True},
    {"layer_id": "operator", "role": "operator", "provenance_required": True},
)


class ContextCompositionError(ValueError):
    """Fail-closed context composition error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_context_pack_composition(
    vault: Path,
    *,
    composition_id: str,
    pack_id: str,
    invent_estate_facts: bool = False,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build a CTX-002 composition receipt for an existing pack id."""
    _ = anchor or require_compatibility_anchor()
    if invent_estate_facts:
        raise ContextCompositionError("ctx-estate-facts-forbidden")
    cid = composition_id.strip()
    pid = pack_id.strip()
    if not _ID_RE.fullmatch(cid) or not _ID_RE.fullmatch(pid):
        raise ContextCompositionError("ctx-composition-id-invalid")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "composition_id": cid,
        "pack_id": pid,
        "estate_facts_invented": False,
        "layers": [dict(row) for row in DEFAULT_LAYERS],
        "authority": {
            "level": "derived",
            "note": "Composition rules deepen CTX-001; never invent estate facts",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "context-pack-composition")
    except SchemaValidationError as exc:
        raise ContextCompositionError(f"ctx-schema-invalid:{exc}") from exc
    out = (
        vault
        / "generated"
        / "context"
        / f"{cid}-composition.json"
    )
    _atomic_write_json(out, payload)
    return payload
