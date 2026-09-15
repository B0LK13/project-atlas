"""AT3-023 — Isolated graph != authority prover.

Declared graph claims only. Missing stays UNKNOWN.
Graph is never authority. Winners and trust scores fail closed.
Does not write AS-GRAPH-003 or Truth Core.
MERGE_AUTHORIZATION = NOT_GRANTED.
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

PACKAGE_ID: Final[str] = "AT3-023"
GENERATOR_ID: Final[str] = "atlas3-graph-authority-023"
DECLARED_NAME: Final[str] = "declared.json"


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "graph-authority" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "GRAPH_AUTHORITY_CORRUPT",
            "declared graph-authority payload is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error(
            "GRAPH_AUTHORITY_CORRUPT",
            "declared graph-authority payload must be an object",
        )
    return raw


def prove_graph_is_not_authority(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Fail closed if a payload claims graph authority, winners, or trust scores."""
    data = payload or {}
    if not isinstance(data, dict):
        raise Atlas3Error("GRAPH_AUTHORITY_CORRUPT", "graph-authority payload must be an object")
    if data.get("graph_is_authority") is True or data.get("graph_authority") is True:
        raise Atlas3Error(
            "GRAPH_AUTHORITY_CLAIMED",
            "graph is not authority",
        )
    if data.get("winner") is not None or data.get("authority_winner") is True:
        raise Atlas3Error(
            "GRAPH_WINNER_CLAIMED",
            "graph must not pick an authority winner",
        )
    if data.get("trust_score") is not None:
        raise Atlas3Error("TRUST_SCORE_FORBIDDEN", "graph must not store trust scores")
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "graph_is_authority": False,
        "accepted": True,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def compile_graph_authority(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Prove declared graph claims are not authority. Missing stays UNKNOWN."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _declared_path(root, pid)
    if not path.is_file():
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
            "project_id": pid,
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_GRAPH_AUTHORITY",
            "graph_is_authority": False,
            "writes_as_graph_003": False,
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
            "declared graph-authority project_id does not match request",
        )
    proof = prove_graph_is_not_authority(declared)
    proof["project_id"] = pid
    proof["status"] = "derived"
    proof["reason"] = "DECLARED_GRAPH_NON_AUTHORITY"
    proof["writes_as_graph_003"] = False
    return proof
