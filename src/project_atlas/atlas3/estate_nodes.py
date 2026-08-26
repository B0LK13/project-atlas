"""AT3-012 — Isolated service / environment nodes.

Declared fixture nodes only. Estate availability is not owner authorization.
Missing declarations stay UNKNOWN. Does not copy or scan authentic estates.
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

PACKAGE_ID: Final[str] = "AT3-012"
DECLARED_NAME: Final[str] = "declared.json"


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "estate-nodes" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "ESTATE_NODES_CORRUPT",
            "declared estate nodes are not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("ESTATE_NODES_CORRUPT", "declared estate nodes must be an object")
    return raw


def _rows(raw: object, *, field: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("ESTATE_NODES_CORRUPT", f"{field} must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("ESTATE_NODES_CORRUPT", f"{field} row is not an object")
        identity = str(item.get("id") or item.get("name") or "").strip()
        if not identity:
            raise Atlas3Error("ESTATE_NODES_IDENTITY_INCOMPLETE", f"{field} row missing id")
        evidence = item.get("evidence_refs") or item.get("evidence") or []
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


def compile_estate_nodes(vault: Path | str, project_id: str) -> dict[str, Any]:
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _declared_path(root, pid)
    if not path.is_file():
        return {
            "package": PACKAGE_ID,
            "project_id": pid,
            "services": [],
            "environments": [],
            "counts": {"services": 0, "environments": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_ESTATE_NODES",
            "authentic_estate": False,
            "estate_availability_is_owner_authority": False,
            "promoted_to_truth_core": 0,
            "truth_boundary": TRUTH_BOUNDARY,
            "honesty": honesty_block(),
        }
    declared = _load_declared(path)
    declared_project = str(declared.get("project_id") or "").strip()
    if declared_project and declared_project != pid:
        raise Atlas3Error(
            "CROSS_PROJECT",
            "declared estate nodes project_id does not match request",
        )
    claimed_estate = declared.get("authentic_estate") is True
    claimed_pilot = declared.get("authentic_pilot") is True
    if claimed_estate or claimed_pilot:
        raise Atlas3Error(
            "ESTATE_NODES_AUTHORITY_CLAIMED",
            "declared estate nodes must not claim authentic estate or pilot",
        )
    services = _rows(declared.get("services"), field="services")
    environments = _rows(declared.get("environments"), field="environments")
    return {
        "package": PACKAGE_ID,
        "project_id": pid,
        "services": services,
        "environments": environments,
        "counts": {"services": len(services), "environments": len(environments)},
        "status": "derived",
        "reason": "DECLARED_ESTATE_NODES",
        "authentic_estate": False,
        "estate_availability_is_owner_authority": False,
        "promoted_to_truth_core": 0,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
