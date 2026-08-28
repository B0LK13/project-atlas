"""AT3-022 — Isolated conflict / UNKNOWN projection.

Declared conflicts and unknowns only. Missing stays UNKNOWN.
UNKNOWN remains UNKNOWN. No conflict winner. Graph != authority.
Does not silently filter corruption into a healthy projection.
Does not write Truth Core. MERGE_AUTHORIZATION = NOT_GRANTED.
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

PACKAGE_ID: Final[str] = "AT3-022"
GENERATOR_ID: Final[str] = "atlas3-conflict-unknown-022"
DECLARED_NAME: Final[str] = "declared.json"
ALLOWED_UNKNOWN_STATUSES: Final[frozenset[str]] = frozenset({"UNKNOWN", "unresolved"})


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "conflict-unknown" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "CONFLICT_UNKNOWN_CORRUPT",
            "declared conflict/UNKNOWN projection is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error(
            "CONFLICT_UNKNOWN_CORRUPT",
            "declared conflict/UNKNOWN projection must be an object",
        )
    return raw


def _conflicts(raw: object, *, project_id: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("CONFLICT_UNKNOWN_CORRUPT", "conflicts must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("CONFLICT_UNKNOWN_CORRUPT", "conflicts row is not an object")
        if item.get("winner") is not None or item.get("authority_winner") is True:
            raise Atlas3Error(
                "GRAPH_WINNER_CLAIMED",
                "conflict projection must not pick an authority winner",
            )
        status = str(item.get("status") or "open").strip() or "open"
        if item.get("resolved") is True and status == "open":
            raise Atlas3Error(
                "CONFLICT_STATE_INCOHERENT",
                "open conflicts cannot be marked resolved",
            )
        conflict_id = str(item.get("conflict_id") or item.get("id") or "").strip()
        if not conflict_id:
            raise Atlas3Error("CONFLICT_IDENTITY_INCOMPLETE", "conflict requires conflict_id")
        item_project = str(item.get("project_id") or "").strip()
        if item_project and item_project != project_id:
            raise Atlas3Error(
                "CROSS_PROJECT",
                "conflict project_id does not match request",
            )
        sides = item.get("sides") or item.get("claims")
        if not isinstance(sides, list):
            raise Atlas3Error(
                "CONFLICT_SIDES_REQUIRED",
                f"{conflict_id} requires at least two sides",
            )
        cleaned_sides = [str(side).strip() for side in sides if str(side).strip()]
        if len(cleaned_sides) < 2:
            raise Atlas3Error(
                "CONFLICT_SIDES_REQUIRED",
                f"{conflict_id} requires at least two sides",
            )
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{conflict_id} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        if not refs:
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{conflict_id} requires evidence_refs")
        rows.append(
            {
                "conflict_id": conflict_id,
                "project_id": project_id,
                "sides": cleaned_sides,
                "status": status,
                "winner": None,
                "evidence_refs": refs,
                "authority": "derived",
            }
        )
    return rows


def _unknowns(raw: object, *, project_id: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("CONFLICT_UNKNOWN_CORRUPT", "unknowns must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("CONFLICT_UNKNOWN_CORRUPT", "unknowns row is not an object")
        if item.get("resolved_as") is not None or item.get("invented_answer") is not None:
            raise Atlas3Error(
                "UNKNOWN_COLLAPSED",
                "UNKNOWN must remain UNKNOWN",
            )
        unknown_id = str(item.get("unknown_id") or item.get("id") or "").strip()
        text = str(item.get("text") or item.get("question") or "").strip()
        if not unknown_id or not text:
            raise Atlas3Error(
                "UNKNOWN_IDENTITY_INCOMPLETE",
                "unknown requires unknown_id and text",
            )
        item_project = str(item.get("project_id") or "").strip()
        if item_project and item_project != project_id:
            raise Atlas3Error(
                "CROSS_PROJECT",
                "unknown project_id does not match request",
            )
        status = str(item.get("status") or "UNKNOWN").strip() or "UNKNOWN"
        if status not in ALLOWED_UNKNOWN_STATUSES:
            raise Atlas3Error("UNKNOWN_STATUS_INVALID", f"unsupported unknown status {status!r}")
        rows.append(
            {
                "unknown_id": unknown_id,
                "project_id": project_id,
                "text": text,
                "status": "UNKNOWN",
                "authority": "derived",
            }
        )
    return rows


def compile_conflict_unknown(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Project declared conflicts and unknowns. Missing stays UNKNOWN."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _declared_path(root, pid)
    if not path.is_file():
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
            "project_id": pid,
            "conflicts": [],
            "unknowns": [],
            "counts": {"conflicts": 0, "unknowns": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_CONFLICT_UNKNOWN",
            "graph_is_authority": False,
            "unknown_collapsed": False,
            "filtered_corruption": False,
            "certified_for_merge": False,
            "merge_authorization": "NOT_GRANTED",
            "promoted_to_truth_core": 0,
            "write_applied": False,
            "truth_boundary": TRUTH_BOUNDARY,
            "honesty": honesty_block(),
        }
    declared = _load_declared(path)
    declared_project = str(declared.get("project_id") or "").strip()
    if declared_project and declared_project != pid:
        raise Atlas3Error(
            "CROSS_PROJECT",
            "declared conflict/UNKNOWN project_id does not match request",
        )
    if declared.get("graph_is_authority") is True:
        raise Atlas3Error(
            "GRAPH_AUTHORITY_CLAIMED",
            "conflict/UNKNOWN projection must not claim graph authority",
        )
    if declared.get("filter_corruption") is True or declared.get("healthy_partial") is True:
        raise Atlas3Error(
            "HEALTHY_FILTER_FORBIDDEN",
            "must not silently filter corruption into a healthy projection",
        )
    conflicts = _conflicts(declared.get("conflicts"), project_id=pid)
    unknowns = _unknowns(declared.get("unknowns"), project_id=pid)
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "conflicts": conflicts,
        "unknowns": unknowns,
        "counts": {"conflicts": len(conflicts), "unknowns": len(unknowns)},
        "status": "derived",
        "reason": "DECLARED_CONFLICT_UNKNOWN",
        "graph_is_authority": False,
        "unknown_collapsed": False,
        "filtered_corruption": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
