"""AS-2.0-UX-002 — Advanced Command Center mode catalog deepen.

Extends AS-2.0-UX-001 entry freeze with an explicit mode→read-adapter
catalog. Forbidden: full UI rewrite, canonical writes. Bound to Atlas 1.0
compatibility anchor.
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

PACKAGE_ID = "AS-2.0-UX-002"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "UX MODE CATALOG ≠ UI REWRITE / ≠ CANONICAL / ≠ AUTHORITY"

DEFAULT_MODES: tuple[dict[str, str], ...] = (
    {
        "mode_id": "overview",
        "title": "Overview",
        "read_adapter": "web_api.read_status",
    },
    {
        "mode_id": "projects",
        "title": "Projects",
        "read_adapter": "web_api.projects",
    },
    {
        "mode_id": "ops",
        "title": "Ops Health",
        "read_adapter": "web_api.health",
    },
    {
        "mode_id": "impact",
        "title": "Impact",
        "read_adapter": "web_api.impact_graph_summary",
    },
    {
        "mode_id": "review",
        "title": "Review walkthrough",
        "read_adapter": "web_api.read_status",
    },
)


class UxModeCatalogError(ValueError):
    """Fail-closed UX mode catalog error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_ux_mode_catalog(
    vault: Path,
    *,
    catalog_id: str,
    allow_ui_rewrite: bool = False,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build Advanced Command Center mode catalog (no UI rewrite)."""
    _ = anchor or require_compatibility_anchor()
    if allow_ui_rewrite:
        raise UxModeCatalogError("ux-ui-rewrite-forbidden:AS-2.0-UX-002")
    cid = catalog_id.strip()
    if not _ID_RE.fullmatch(cid):
        raise UxModeCatalogError("ux-catalog-id-invalid")

    modes = [
        {
            "mode_id": row["mode_id"],
            "title": row["title"],
            "read_adapter": row["read_adapter"],
            "graph_authority": False,
        }
        for row in DEFAULT_MODES
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "catalog_id": cid,
        "ui_rewrite": False,
        "canonical_writes": False,
        "modes": modes,
        "authority": {
            "level": "derived",
            "note": "Mode catalog is presentation binding only; UI≠canonical",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "ux-mode-catalog")
    except SchemaValidationError as exc:
        raise UxModeCatalogError(f"ux-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "ux" / f"{cid}-mode-catalog.json"
    _atomic_write_json(out, payload)
    return payload
