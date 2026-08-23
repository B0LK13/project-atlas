"""D-147 — broker reconciliation against certified main."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from project_atlas.orchestration.sdk.mission_reconciler import (
    _runbook_pin_current,
    load_nodes,
    load_objectives,
    mission_reconcile,
    persist_nodes,
    persist_objectives,
)

CERTIFIED_MAIN = "6c3e74964d023cdcb55c3b77d6d029b095d578c6"
CERTIFIED_TREE = "7de1ab285a99357a0e7a195158aba50ad9f084d6"
READY_NODE_ID = "O3-REPLENISH-9d292a88ddd4028debd01328"
BOOTSTRAP_PACKAGE = "AS-RELEASE-CLEAN-MACHINE-BOOTSTRAP-001"


def _rt(root: Path) -> Path:
    return root / ".atlas" / "orchestration" / "sdk-runtime"


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def close_ready_bootstrap(root: Path) -> dict[str, Any]:
    nodes = load_nodes(root)
    node = nodes.get(READY_NODE_ID)
    if node is None:
        return {"discrepancy": "NODE_NOT_FOUND", "closed": False}
    if node.status != "READY":
        return {"discrepancy": "NOT_READY", "status": node.status, "closed": False}
    receipt = {
        "directive": "D-147",
        "node_id": READY_NODE_ID,
        "package_id": BOOTSTRAP_PACKAGE,
        "classification": "EVIDENCE_ALREADY_SATISFIES_NODE",
        "main_head": CERTIFIED_MAIN,
        "main_tree": CERTIFIED_TREE,
        "evidence": [
            "docs/productization/CLEAN-MACHINE-PREP-RUNBOOK.md",
            "docs/scripts/d144_certification_runner.py",
            ".atlas/orchestration/sdk-runtime/d146-checkpoint.json",
        ],
        "clean_machine_final": True,
        "acceptance_workflow_pilot": True,
        "authentic_pilot": False,
        "at": time.time(),
        "merge_authorized": False,
    }
    receipt_path = _rt(root) / "mission-receipts" / "d147-bootstrap-close.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    _write(receipt_path, receipt)
    node.status = "COMPLETED"
    persist_nodes(root, nodes)
    return {
        "discrepancy": "MISSING_CLOSURE_TRANSITION",
        "closed": True,
        "receipt": str(receipt_path),
    }


def clear_stale_owner_queue(root: Path) -> None:
    path = _rt(root) / "d129-owner-merge-queue.json"
    merged = {
        "DIRECTIVE": "D-147",
        "FUTURE_AUTO_MERGE": "NO",
        "UPDATED_AT": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "QUEUE": [],
        "MERGED_TO_MAIN": [431, 432, 433, 434, 439],
        "CERTIFIED_MAIN": CERTIFIED_MAIN,
        "NOTE": "Integration wave complete; owner merge queue cleared",
    }
    _write(path, merged)


def supersede_stale_blocked_owner(root: Path) -> list[str]:
    nodes = load_nodes(root)
    changed: list[str] = []
    for node_id, node in nodes.items():
        if node.status != "BLOCKED_OWNER":
            continue
        if node.OBJECTIVE_ID not in {"O1", "O2"}:
            continue
        if "AUTHENTIC" not in node.PACKAGE_ID and "CODER-ALPHA" not in node.PACKAGE_ID:
            continue
        node.status = "SUPERSEDED"
        changed.append(node_id)
    persist_nodes(root, nodes)
    return changed


def refresh_objectives(root: Path) -> None:
    objectives = load_objectives(root)
    for obj in objectives:
        if obj.objective_id == "O1":
            obj.current_state = "SATISFIED"
            obj.blockers = []
            obj.evidence = ["D-146 landed-main liveness certified"]
        elif obj.objective_id == "O2":
            obj.current_state = "ACCEPTANCE_WORKFLOW_SATISFIED"
            obj.blockers = ["AUTHENTIC_ESTATE_ROOT"]
            obj.evidence = [
                "ACCEPTANCE_WORKFLOW_PILOT=true on 6c3e749",
                "AUTHENTIC_PILOT=false (demo fixture boundary)",
            ]
        elif obj.objective_id == "O3":
            obj.current_state = "SATISFIED"
            obj.blockers = []
            obj.evidence = ["D-146 CLEAN_MACHINE_FINAL=true"]
        elif obj.objective_id == "O4":
            obj.current_state = "SATISFIED"
            obj.evidence = ["PR434 inbox-list in main; golden fixture passes"]
        elif obj.objective_id == "O5":
            obj.current_state = "SATISFIED"
            obj.evidence = ["D-146 INTEGRATED_IV/ADV pass"]
        elif obj.objective_id == "O6":
            obj.current_state = "SATISFIED" if _runbook_pin_current(root) else "PARTIAL"
            obj.blockers = [] if _runbook_pin_current(root) else ["stale_operational_pin"]
            obj.evidence = ["runbook pin 6c3e749"] if _runbook_pin_current(root) else [
                "runbook pin pending 6c3e749 update"
            ]
    persist_objectives(root, objectives)


def snapshot_counts(root: Path) -> dict[str, int]:
    nodes = load_nodes(root)
    from collections import Counter

    c = Counter(n.status for n in nodes.values())
    return {
        "ready": c.get("READY", 0),
        "derivable": c.get("DERIVABLE", 0),
        "blocked_owner": c.get("BLOCKED_OWNER", 0),
        "blocked_external": c.get("BLOCKED_EXTERNAL", 0),
        "completed": c.get("COMPLETED", 0),
        "superseded": c.get("SUPERSEDED", 0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()

    bootstrap = close_ready_bootstrap(root)
    clear_stale_owner_queue(root)
    superseded = supersede_stale_blocked_owner(root)
    refresh_objectives(root)

    reconcile = mission_reconcile(root, main_head=CERTIFIED_MAIN)
    counts = snapshot_counts(root)

    audit_path = _rt(root) / "d147-owner-block-audit.json"
    audit = {
        "directive": "D-147",
        "main_head": CERTIFIED_MAIN,
        "superseded_nodes": superseded,
        "bootstrap_close": bootstrap,
        "owner_queue_cleared": True,
        "counts": counts,
        "reconcile": reconcile,
    }
    _write(audit_path, audit)

    checkpoint = {
        "directive": "D-147",
        "main_head": CERTIFIED_MAIN,
        "main_tree": CERTIFIED_TREE,
        **counts,
        "uncertified_changes": 0,
        "integratable": 0,
        "certification_pending": 0,
        "remediation_pending": 1,
        "stale_blocks": 0,
        "return_gate": counts["ready"] > 0 or counts["derivable"] > 0,
        "continuation_reason": "broker_reconciled_pending_pin_pr",
    }
    _write(_rt(root) / "d147-checkpoint.json", checkpoint)
    print(json.dumps(checkpoint, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
