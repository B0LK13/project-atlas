"""AT3-021 — Isolated derived relationship expansion.

Expands declared twin relationships through GRAPH_REUSE aliases.
Does not write the AS-GRAPH-003 store. Graph != authority.
Does not pick conflict winners. Missing declarations stay UNKNOWN.
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
from project_atlas.atlas3.domain import GRAPH_REUSE, TWIN_RELATIONSHIPS
from project_atlas.atlas3.twin import make_relationship

PACKAGE_ID: Final[str] = "AT3-021"
DECLARED_NAME: Final[str] = "declared.json"


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "rel-expand" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "REL_EXPAND_CORRUPT",
            "declared relationship expansion is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("REL_EXPAND_CORRUPT", "declared relationship expansion must be an object")
    return raw


def _rows(raw: object, *, project_id: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("REL_EXPAND_CORRUPT", "relationships must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("REL_EXPAND_CORRUPT", "relationships row is not an object")
        relationship = str(item.get("relationship") or "").strip().upper()
        if relationship not in TWIN_RELATIONSHIPS:
            raise Atlas3Error(
                "UNKNOWN_TWIN_RELATIONSHIP",
                f"unsupported relationship {relationship!r}",
            )
        from_id = str(item.get("from_id") or item.get("from") or "").strip()
        to_id = str(item.get("to_id") or item.get("to") or "").strip()
        if not from_id or not to_id:
            raise Atlas3Error("REL_IDENTITY_INCOMPLETE", "relationship requires from_id and to_id")
        if item.get("winner") is not None or item.get("authority_winner") is True:
            raise Atlas3Error(
                "GRAPH_WINNER_CLAIMED",
                "relationship expansion must not pick an authority winner",
            )
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{from_id}->{to_id} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        row = make_relationship(
            relationship=relationship,
            from_id=from_id,
            to_id=to_id,
            project_id=project_id,
            evidence_refs=refs,
        )
        row["package"] = PACKAGE_ID
        row["graph_alias"] = GRAPH_REUSE.get(relationship)
        row["expanded"] = relationship in GRAPH_REUSE
        row["winner"] = None
        rows.append(row)
    return rows


def expand_relationships(vault: Path | str, project_id: str) -> dict[str, Any]:
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _declared_path(root, pid)
    if not path.is_file():
        return {
            "package": PACKAGE_ID,
            "project_id": pid,
            "relationships": [],
            "counts": {"relationships": 0, "expanded": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_REL_EXPAND",
            "graph_is_authority": False,
            "writes_as_graph_003": False,
            "promoted_to_truth_core": 0,
            "truth_boundary": TRUTH_BOUNDARY,
            "honesty": honesty_block(),
        }
    declared = _load_declared(path)
    declared_project = str(declared.get("project_id") or "").strip()
    if declared_project and declared_project != pid:
        raise Atlas3Error(
            "CROSS_PROJECT",
            "declared relationship expansion project_id does not match request",
        )
    if declared.get("graph_is_authority") is True:
        raise Atlas3Error(
            "GRAPH_AUTHORITY_CLAIMED",
            "relationship expansion must not claim graph authority",
        )
    rows = _rows(declared.get("relationships"), project_id=pid)
    return {
        "package": PACKAGE_ID,
        "project_id": pid,
        "relationships": rows,
        "counts": {
            "relationships": len(rows),
            "expanded": sum(1 for row in rows if row.get("expanded") is True),
        },
        "status": "derived",
        "reason": "DECLARED_REL_EXPAND",
        "graph_is_authority": False,
        "writes_as_graph_003": False,
        "promoted_to_truth_core": 0,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
