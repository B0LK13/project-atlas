"""AS-2.0-OBS-UX-001 — Obsidian non-canonical lens registry.

Read-only lens catalog for Obsidian-like surfaces. Never ships a plugin,
never writes canonical vault truth. Bound to Atlas 1.0 compatibility anchor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-OBS-UX-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "OBSIDIAN LENS ≠ CANONICAL / ≠ PLUGIN SHIP / ≠ AUTHORITY"

DEFAULT_LENSES: tuple[tuple[str, str], ...] = (
    ("mission-control", "Mission Control (read-only)"),
    ("graph-derived", "Derived graph enrichment"),
    ("ops-health", "Ops health lens"),
    ("impact", "Impact projection lens"),
)


class ObsidianUxError(ValueError):
    """Fail-closed Obsidian UX contract error."""


@dataclass(frozen=True, slots=True)
class ObsidianLens:
    lens_id: str
    title: str
    notes: str | None = None


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_obsidian_lens_registry(
    vault: Path,
    *,
    registry_id: str,
    lenses: list[ObsidianLens] | None = None,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build a disposable Obsidian lens registry (≠ plugin / ≠ canonical)."""
    _ = anchor or require_compatibility_anchor()
    rid = registry_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise ObsidianUxError("obsidian-registry-id-invalid")

    rows = lenses or [
        ObsidianLens(lens_id=i, title=t) for i, t in DEFAULT_LENSES
    ]
    seen: set[str] = set()
    serialized: list[dict[str, Any]] = []
    for row in rows:
        lid = row.lens_id.strip()
        if not _ID_RE.fullmatch(lid):
            raise ObsidianUxError(f"obsidian-lens-id-invalid:{lid}")
        if lid in seen:
            raise ObsidianUxError(f"obsidian-lens-duplicate:{lid}")
        seen.add(lid)
        title = row.title.strip()
        if not title:
            raise ObsidianUxError("obsidian-lens-title-empty")
        serialized.append(
            {
                "lens_id": lid,
                "title": title,
                "read_only": True,
                "authority_level": "derived",
                "notes": row.notes,
            }
        )

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "registry_id": rid,
        "plugin_shipped": False,
        "canonical_writes": False,
        "lenses": serialized,
        "authority": {
            "level": "derived",
            "note": "Obsidian lenses are presentation-only; UI≠canonical",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(payload, "obsidian-lens-registry")
    except SchemaValidationError as exc:
        raise ObsidianUxError(f"obsidian-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "obsidian" / f"{rid}-lens-registry.json"
    _atomic_write_json(out, payload)
    return payload
