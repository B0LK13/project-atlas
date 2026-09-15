"""AT3-020 — Isolated claim / decision / requirement nodes.

Declared twin nodes only. Missing stays UNKNOWN.
Does not write Truth Core or AS-GRAPH-003.
Graph != authority. Model paraphrase is not an owner decision.
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
from project_atlas.atlas3.twin import make_node

PACKAGE_ID: Final[str] = "AT3-020"
GENERATOR_ID: Final[str] = "atlas3-claim-nodes-020"
DECLARED_NAME: Final[str] = "declared.json"
NODE_KINDS: Final[frozenset[str]] = frozenset({"claim", "decision", "requirement"})


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "claim-nodes" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "CLAIM_NODES_CORRUPT",
            "declared claim/decision/requirement nodes are not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error(
            "CLAIM_NODES_CORRUPT",
            "declared claim/decision/requirement nodes must be an object",
        )
    return raw


def _rows(raw: object, *, project_id: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("CLAIM_NODES_CORRUPT", "nodes must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("CLAIM_NODES_CORRUPT", "nodes row is not an object")
        if item.get("winner") is not None or item.get("authority_winner") is True:
            raise Atlas3Error(
                "GRAPH_WINNER_CLAIMED",
                "claim nodes must not pick an authority winner",
            )
        if item.get("trust_score") is not None:
            raise Atlas3Error("TRUST_SCORE_FORBIDDEN", "claim nodes must not store trust scores")
        if (
            item.get("model_is_owner") is True
            or item.get("model_paraphrase") is True
            or item.get("inferred_from_model") is True
        ):
            raise Atlas3Error(
                "FALSE_OWNER_DECISION",
                "model paraphrase is not an owner decision",
            )
        kind = str(item.get("node_kind") or item.get("kind") or item.get("node_type") or "")
        kind = kind.strip().lower()
        if kind not in NODE_KINDS:
            raise Atlas3Error(
                "UNKNOWN_CLAIM_NODE",
                "node_kind must be claim, decision, or requirement",
            )
        node_id = str(item.get("node_id") or item.get("id") or "").strip()
        if not node_id:
            raise Atlas3Error("CLAIM_IDENTITY_INCOMPLETE", "node requires node_id")
        item_project = str(item.get("project_id") or "").strip()
        if item_project and item_project != project_id:
            raise Atlas3Error(
                "CROSS_PROJECT",
                "claim node project_id does not match request",
            )
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{node_id} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        row = make_node(
            node_type=kind,
            node_id=node_id,
            project_id=project_id,
            evidence_refs=refs,
            valid_from=str(item["valid_from"]) if item.get("valid_from") else None,
            valid_to=str(item["valid_to"]) if item.get("valid_to") else None,
        )
        row["package"] = PACKAGE_ID
        row["label"] = str(item.get("label") or item.get("text") or "").strip() or None
        row["winner"] = None
        row["graph_is_authority"] = False
        row["model_is_owner"] = False
        rows.append(row)
    return rows


def compile_claim_nodes(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compile declared claim/decision/requirement nodes. Missing stays UNKNOWN."""
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
            "counts": {"nodes": 0, "claim": 0, "decision": 0, "requirement": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_CLAIM_NODES",
            "graph_is_authority": False,
            "writes_truth_core": False,
            "writes_as_graph_003": False,
            "model_is_owner": False,
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
            "declared claim-nodes project_id does not match request",
        )
    if declared.get("graph_is_authority") is True:
        raise Atlas3Error(
            "GRAPH_AUTHORITY_CLAIMED",
            "claim nodes must not claim graph authority",
        )
    if declared.get("model_is_owner") is True:
        raise Atlas3Error("FALSE_OWNER_DECISION", "model cannot be treated as owner")
    nodes = _rows(declared.get("nodes"), project_id=pid)
    counts = {
        "nodes": len(nodes),
        "claim": sum(1 for node in nodes if node["node_type"] == "claim"),
        "decision": sum(1 for node in nodes if node["node_type"] == "decision"),
        "requirement": sum(1 for node in nodes if node["node_type"] == "requirement"),
    }
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "nodes": nodes,
        "counts": counts,
        "status": "derived",
        "reason": "DECLARED_CLAIM_NODES",
        "graph_is_authority": False,
        "writes_truth_core": False,
        "writes_as_graph_003": False,
        "model_is_owner": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
