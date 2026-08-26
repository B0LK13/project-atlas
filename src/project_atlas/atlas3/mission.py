"""AT3-096 — Isolated Mission Command Center.

Read-only declared orch DAG / lease projection. Self-merge is forbidden.
Estate availability is not owner authorization. Mission != Truth Core.
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

PACKAGE_ID: Final[str] = "AT3-096"
GENERATOR_ID: Final[str] = "atlas3-mission-096"
DECLARED_NAME: Final[str] = "declared.json"
ALLOWED_STATES: Final[frozenset[str]] = frozenset(
    {
        "READY",
        "DERIVABLE",
        "RUNNING",
        "DISPATCHED",
        "UNCERTIFIED",
        "SELF_REMEDIABLE",
        "OWNER_ONLY",
        "EXTERNAL_BLOCKED",
        "SATISFIED",
        "SUPERSEDED",
        "DEFERRED_NON_RELEASE",
    }
)


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "mission" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "MISSION_CORRUPT",
            "declared Mission Command data is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("MISSION_CORRUPT", "declared Mission Command data must be an object")
    return raw


def _nodes(raw: object, *, project_id: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("MISSION_CORRUPT", "nodes must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("MISSION_CORRUPT", "nodes row is not an object")
        if item.get("self_merge") is True or item.get("auto_merge") is True:
            raise Atlas3Error("SELF_MERGE_FORBIDDEN", "Mission Command must not self-merge")
        node_id = str(item.get("node_id") or item.get("id") or "").strip()
        state = str(item.get("state") or "").strip().upper()
        if not node_id or state not in ALLOWED_STATES:
            raise Atlas3Error("MISSION_NODE_INVALID", "node requires node_id and a known state")
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{node_id} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        if not refs:
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{node_id} requires evidence_refs")
        rows.append(
            {
                "node_id": node_id,
                "state": state,
                "package_id": str(item.get("package_id") or "").strip() or None,
                "project_id": project_id,
                "evidence_refs": refs,
                "self_merge": False,
                "authority": "derived",
            }
        )
    return rows


def _leases(raw: object, *, project_id: str) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("MISSION_CORRUPT", "leases must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("MISSION_CORRUPT", "leases row is not an object")
        if item.get("self_merge") is True or item.get("grants_merge") is True:
            raise Atlas3Error("SELF_MERGE_FORBIDDEN", "lease must not grant merge")
        lease_id = str(item.get("lease_id") or item.get("id") or "").strip()
        holder = str(item.get("holder") or "").strip()
        node_id = str(item.get("node_id") or "").strip()
        if not lease_id or not holder or not node_id:
            raise Atlas3Error("MISSION_LEASE_INVALID", "lease requires lease_id, holder, node_id")
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{lease_id} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        if not refs:
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{lease_id} requires evidence_refs")
        rows.append(
            {
                "lease_id": lease_id,
                "holder": holder,
                "node_id": node_id,
                "project_id": project_id,
                "evidence_refs": refs,
                "grants_merge": False,
                "authority": "derived",
            }
        )
    return rows


def compile_mission(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compile declared Mission Command Center data. Missing stays UNKNOWN."""
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
            "leases": [],
            "counts": {"nodes": 0, "leases": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_MISSION",
            "self_merge": False,
            "estate_is_authorization": False,
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
            "declared Mission Command project_id does not match request",
        )
    if declared.get("self_merge") is True or declared.get("auto_merge") is True:
        raise Atlas3Error("SELF_MERGE_FORBIDDEN", "Mission Command must not self-merge")
    merge_auth = str(declared.get("merge_authorization") or "NOT_GRANTED").strip()
    if merge_auth != "NOT_GRANTED":
        raise Atlas3Error("MERGE_CLAIMED", "Mission Command cannot grant merge authorization")
    if (
        declared.get("estate_is_authorization") is True
        or declared.get("estate_authorizes_owner") is True
    ):
        raise Atlas3Error(
            "ESTATE_AUTHORIZATION_CLAIMED",
            "estate availability is not owner authorization",
        )
    nodes = _nodes(declared.get("nodes"), project_id=pid)
    leases = _leases(declared.get("leases"), project_id=pid)
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "nodes": nodes,
        "leases": leases,
        "counts": {"nodes": len(nodes), "leases": len(leases)},
        "status": "derived",
        "reason": "DECLARED_MISSION",
        "self_merge": False,
        "estate_is_authorization": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
