"""AT3-053 — Isolated autonomy gate reuse.

Reuses landed orch DAG / lease / owner-gate contracts. Does not redefine
orchestration. Does not self-dispatch. Owner gates stay owner gates.
Missing stays UNKNOWN. No new CLI. MERGE_AUTHORIZATION = NOT_GRANTED.
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

PACKAGE_ID: Final[str] = "AT3-053"
GENERATOR_ID: Final[str] = "atlas3-autonomy-gate-053"
ORCH_PACKAGE_ID: Final[str] = "AS-ORCH-001"
LEASE_PACKAGE_ID: Final[str] = "AS-ORCH-LEASE"


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "autonomy-gate" / project_id / "declared.json"


def _read_object(path: Path, *, corrupt_code: str, label: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise Atlas3Error(corrupt_code, f"{label} must be a regular file")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(corrupt_code, f"{label} is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise Atlas3Error(corrupt_code, f"{label} must be an object")
    return raw


def _reject_authority_claims(payload: dict[str, Any], *, label: str) -> None:
    if payload.get("execution_authorized") is True:
        raise Atlas3Error("EXECUTION_AUTHORIZED", f"{label} must not self-authorize execution")
    if payload.get("self_dispatch") is True or payload.get("auto_dispatch") is True:
        raise Atlas3Error("SELF_DISPATCH", f"{label} must not self-dispatch")
    if payload.get("merge_authorization") in {"GRANTED", "granted", True}:
        raise Atlas3Error("MERGE_CLAIM_FORBIDDEN", f"{label} must not grant merge")
    if payload.get("owner_authority") is True or payload.get("owner_authorized") is True:
        raise Atlas3Error("OWNER_AUTHORITY_INVENTED", f"{label} must not invent owner authority")
    if payload.get("lease_is_merge_authority") is True:
        raise Atlas3Error("LEASE_IS_NOT_MERGE", f"{label} lease is not merge authority")
    if payload.get("graph_is_authority") is True or payload.get("graph_winner") is not None:
        raise Atlas3Error("GRAPH_WINNER_FORBIDDEN", f"{label} must not select a graph winner")
    if payload.get("trust_score") is not None:
        raise Atlas3Error("TRUST_SCORE_FORBIDDEN", f"{label} must not carry a trust score")


def _walk_reject(payload: Any, *, label: str) -> None:
    if isinstance(payload, dict):
        _reject_authority_claims(payload, label=label)
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                _walk_reject(value, label=f"{label}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            if isinstance(item, (dict, list)):
                _walk_reject(item, label=f"{label}[{index}]")


def compile_autonomy_gate_reuse(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compose autonomy-gate reuse. Owner gates remain owner-only."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    declared = _read_object(
        _declared_path(root, pid),
        corrupt_code="AUTONOMY_GATE_CORRUPT",
        label="autonomy-gate",
    )
    leases: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    owner_gates: list[str] = []
    if declared is not None:
        declared_pid = str(declared.get("project_id") or pid).strip()
        if declared_pid and declared_pid != pid:
            raise Atlas3Error("CROSS_PROJECT", "autonomy-gate project_id must match request")
        _walk_reject(declared, label="autonomy-gate")
        raw_leases = declared.get("leases") or []
        raw_nodes = declared.get("dag") or declared.get("nodes") or []
        raw_gates = declared.get("owner_gates") or []
        if raw_leases and not isinstance(raw_leases, list):
            raise Atlas3Error("AUTONOMY_GATE_CORRUPT", "leases must be a list")
        if raw_nodes and not isinstance(raw_nodes, list):
            raise Atlas3Error("AUTONOMY_GATE_CORRUPT", "dag/nodes must be a list")
        if raw_gates and not isinstance(raw_gates, list):
            raise Atlas3Error("AUTONOMY_GATE_CORRUPT", "owner_gates must be a list")
        if isinstance(raw_leases, list):
            for item in raw_leases:
                if not isinstance(item, dict):
                    raise Atlas3Error("AUTONOMY_GATE_CORRUPT", "lease row must be an object")
                _walk_reject(item, label="lease")
                leases.append(
                    {
                        "lease_id": str(item.get("lease_id") or item.get("id") or ""),
                        "lease_is_merge_authority": False,
                    }
                )
        if isinstance(raw_nodes, list):
            for item in raw_nodes:
                if not isinstance(item, dict):
                    raise Atlas3Error("AUTONOMY_GATE_CORRUPT", "dag row must be an object")
                _walk_reject(item, label="dag")
                nodes.append(
                    {
                        "node_id": str(item.get("node_id") or item.get("id") or ""),
                        "state": str(item.get("state") or "UNKNOWN"),
                        "execution_authorized": False,
                    }
                )
        if isinstance(raw_gates, list):
            owner_gates = [str(item).strip() for item in raw_gates if str(item).strip()]

    status = "derived" if declared is not None else "UNKNOWN"
    reason = "COMPOSED_AUTONOMY_GATE_REUSE" if status == "derived" else "NO_AUTONOMY_GATE"
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "data_package_ids": [ORCH_PACKAGE_ID, LEASE_PACKAGE_ID],
        "project_id": pid,
        "leases": leases,
        "nodes": nodes,
        "owner_gates": owner_gates,
        "counts": {
            "leases": len(leases),
            "nodes": len(nodes),
            "owner_gates": len(owner_gates),
        },
        "status": status,
        "reason": reason,
        "execution_authorized": False,
        "self_dispatch": False,
        "lease_is_merge_authority": False,
        "owner_authority_invented": False,
        "new_cli_command": False,
        "graph_is_authority": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
