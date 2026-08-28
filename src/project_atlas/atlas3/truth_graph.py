"""AT3-092 — Isolated Truth Graph UX.

Declared claim/decision/requirement nodes and twin relationships only.
Graph != authority. No winners or trust scores. Missing stays UNKNOWN.
Does not write AS-GRAPH-003. MERGE_AUTHORIZATION = NOT_GRANTED.
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
from project_atlas.atlas3.domain import TWIN_NODES, TWIN_RELATIONSHIPS

PACKAGE_ID: Final[str] = "AT3-092"
GENERATOR_ID: Final[str] = "atlas3-truth-graph-092"
DECLARED_NAME: Final[str] = "declared.json"


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "truth-graph" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "TRUTH_GRAPH_CORRUPT",
            "declared Truth Graph data is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("TRUTH_GRAPH_CORRUPT", "declared Truth Graph data must be an object")
    return raw


def _nodes(raw: object, *, project_id: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("TRUTH_GRAPH_CORRUPT", "nodes must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("TRUTH_GRAPH_CORRUPT", "nodes row is not an object")
        if item.get("winner") is not None or item.get("authority_winner") is True:
            raise Atlas3Error(
                "GRAPH_WINNER_CLAIMED",
                "Truth Graph must not pick an authority winner",
            )
        if item.get("trust_score") is not None:
            raise Atlas3Error("TRUST_SCORE_FORBIDDEN", "Truth Graph must not store trust scores")
        node_id = str(item.get("node_id") or item.get("id") or "").strip()
        kind = str(item.get("node_kind") or item.get("kind") or "").strip().lower()
        if not node_id or kind not in TWIN_NODES:
            raise Atlas3Error(
                "TRUTH_GRAPH_NODE_INVALID",
                "node requires node_id and a known twin node_kind",
            )
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{node_id} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        if not refs:
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{node_id} requires evidence_refs")
        rows.append(
            {
                "node_id": node_id,
                "node_kind": kind,
                "label": str(item.get("label") or item.get("text") or "").strip() or None,
                "project_id": project_id,
                "evidence_refs": refs,
                "authority": "derived",
                "winner": None,
                "graph_is_authority": False,
            }
        )
    return rows


def _edges(raw: object, *, project_id: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("TRUTH_GRAPH_CORRUPT", "edges must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("TRUTH_GRAPH_CORRUPT", "edges row is not an object")
        if item.get("winner") is not None or item.get("authority_winner") is True:
            raise Atlas3Error(
                "GRAPH_WINNER_CLAIMED",
                "Truth Graph must not pick an authority winner",
            )
        if item.get("trust_score") is not None:
            raise Atlas3Error("TRUST_SCORE_FORBIDDEN", "Truth Graph must not store trust scores")
        relationship = str(item.get("relationship") or "").strip().upper()
        if relationship not in TWIN_RELATIONSHIPS:
            raise Atlas3Error(
                "UNKNOWN_TWIN_RELATIONSHIP",
                f"unsupported relationship {relationship!r}",
            )
        from_id = str(item.get("from_id") or item.get("from") or "").strip()
        to_id = str(item.get("to_id") or item.get("to") or "").strip()
        if not from_id or not to_id:
            raise Atlas3Error("TRUTH_GRAPH_EDGE_INVALID", "edge requires from_id and to_id")
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{from_id}->{to_id} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        if not refs:
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{from_id}->{to_id} requires evidence_refs")
        rows.append(
            {
                "relationship": relationship,
                "from_id": from_id,
                "to_id": to_id,
                "project_id": project_id,
                "evidence_refs": refs,
                "authority": "derived",
                "winner": None,
                "graph_is_authority": False,
            }
        )
    return rows


def compile_truth_graph(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compile declared Truth Graph UX data. Missing stays UNKNOWN."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _declared_path(root, pid)
    if not path.is_file():
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
            "project_id": pid,
            "nodes": [],
            "edges": [],
            "counts": {"nodes": 0, "edges": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_TRUTH_GRAPH",
            "graph_is_authority": False,
            "trust_score_used": False,
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
            "declared Truth Graph project_id does not match request",
        )
    if declared.get("graph_is_authority") is True:
        raise Atlas3Error("GRAPH_AUTHORITY_CLAIMED", "Truth Graph must not claim graph authority")
    if declared.get("trust_score") is not None:
        raise Atlas3Error("TRUST_SCORE_FORBIDDEN", "Truth Graph must not use trust scores")
    nodes = _nodes(declared.get("nodes"), project_id=pid)
    edges = _edges(declared.get("edges"), project_id=pid)
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "nodes": nodes,
        "edges": edges,
        "counts": {"nodes": len(nodes), "edges": len(edges)},
        "status": "derived",
        "reason": "DECLARED_TRUTH_GRAPH",
        "graph_is_authority": False,
        "trust_score_used": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
