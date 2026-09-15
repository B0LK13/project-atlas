"""AT3-010 — Isolated repository / component inventory.

Derived Layer C only. Inventory is not Truth Core and is not an estate copy.
Does not invent repositories from host filesystem roots.
Does not mutate certified 2.x production surfaces.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    require_project,
    require_vault,
)

PACKAGE_ID: Final[str] = "AT3-010"
DECLARED_NAME: Final[str] = "declared.json"


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "inventory" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error("INVENTORY_CORRUPT", "declared inventory is not readable JSON") from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("INVENTORY_CORRUPT", "declared inventory must be an object")
    return raw


def _rows(raw: object, *, field: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("INVENTORY_CORRUPT", f"{field} must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("INVENTORY_CORRUPT", f"{field} row is not an object")
        identity = str(item.get("id") or item.get("name") or "").strip()
        evidence = item.get("evidence_refs") or item.get("evidence") or []
        if not identity:
            raise Atlas3Error("INVENTORY_IDENTITY_INCOMPLETE", f"{field} row missing id")
        refs = [str(ref).strip() for ref in evidence] if isinstance(evidence, list) else []
        refs = [ref for ref in refs if ref]
        if not refs:
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{field} {identity!r} requires evidence_refs")
        rows.append(
            {
                "id": identity,
                "kind": field[:-1] if field.endswith("s") else field,
                "evidence_refs": refs,
                "authority": "derived",
            }
        )
    return rows


def compile_inventory(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compile a derived repository/component inventory. Never writes Truth Core."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _declared_path(root, pid)
    if not path.is_file():
        return {
            "package": PACKAGE_ID,
            "project_id": pid,
            "repositories": [],
            "components": [],
            "counts": {"repositories": 0, "components": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_INVENTORY",
            "inventory_is_truth_core": False,
            "graph_is_authority": False,
            "authentic_estate": False,
            "authentic_pilot": False,
            "promoted_to_truth_core": 0,
            "truth_boundary": TRUTH_BOUNDARY,
            "honesty": honesty_block(),
        }
    declared = _load_declared(path)
    declared_project = str(declared.get("project_id") or "").strip()
    if declared_project and declared_project != pid:
        raise Atlas3Error("CROSS_PROJECT", "declared inventory project_id does not match request")
    if declared.get("authentic_estate") is True or declared.get("authentic_pilot") is True:
        raise Atlas3Error(
            "INVENTORY_AUTHORITY_CLAIMED",
            "declared inventory must not claim authentic estate or pilot",
        )
    if str(declared.get("merge_authorization") or "").strip().upper() in {"GRANTED", "AUTHORIZED"}:
        raise Atlas3Error(
            "INVENTORY_AUTHORITY_CLAIMED",
            "declared inventory must not grant merge authorization",
        )
    repositories = _rows(declared.get("repositories"), field="repositories")
    components = _rows(declared.get("components"), field="components")
    return {
        "package": PACKAGE_ID,
        "project_id": pid,
        "repositories": repositories,
        "components": components,
        "counts": {"repositories": len(repositories), "components": len(components)},
        "status": "derived",
        "reason": "DECLARED_INVENTORY",
        "inventory_is_truth_core": False,
        "graph_is_authority": False,
        "authentic_estate": False,
        "authentic_pilot": False,
        "promoted_to_truth_core": 0,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
