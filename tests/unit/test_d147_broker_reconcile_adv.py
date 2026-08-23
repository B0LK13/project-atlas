"""D-147 — broker reconciliation and evidence-bound gap classification."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from project_atlas.orchestration.sdk.mission_reconciler import (
    WorkNode,
    _gap_statuses,
    _idempotency_key,
    _owner_held_prs,
    closed_loop_tick,
    dispatch_local_analysis_worker,
    interpret_receipt,
    load_nodes,
    mission_reconcile,
    persist_nodes,
)


def _runtime(root: Path) -> Path:
    return root / ".atlas" / "orchestration" / "sdk-runtime"


def test_owner_held_prs_empty_when_queue_cleared(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    rt.mkdir(parents=True)
    (rt / "d129-owner-merge-queue.json").write_text(
        json.dumps({"QUEUE": [], "MERGED_TO_MAIN": [431]}) + "\n",
        encoding="utf-8",
    )
    assert _owner_held_prs(tmp_path) == set()


def test_gap_statuses_honor_certified_evidence(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    rt.mkdir(parents=True)
    (rt / "d146-checkpoint.json").write_text(
        json.dumps(
            {
                "MERGE_COMMIT": "6c3e74964d023cdcb55c3b77d6d029b095d578c6",
                "CLEAN_MACHINE_FINAL": True,
                "RELEASE_READINESS": "CERTIFIED",
                "ACCEPTANCE_WORKFLOW_PILOT": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runbook = tmp_path / "docs" / "productization" / "CLEAN-MACHINE-PREP-RUNBOOK.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text("HEAD = 6c3e74964d023cdcb55c3b77d6d029b095d578c6\n", encoding="utf-8")
    gaps = _gap_statuses(tmp_path, main_head="6c3e74964d023cdcb55c3b77d6d029b095d578c6")
    assert gaps["CLEAN_MACHINE_BOOTSTRAP"] == "SATISFIED"
    assert gaps["RELEASE_ARTIFACT"] == "SATISFIED"
    assert gaps["AUTHENTIC_INGEST"] == "BLOCKED_OWNER"


def test_release_validation_skips_satisfied_successors(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    rt.mkdir(parents=True)
    queue_path = rt / "d129-owner-merge-queue.json"
    queue_path.write_text(json.dumps({"QUEUE": []}) + "\n", encoding="utf-8")
    (rt / "d146-checkpoint.json").write_text(
        json.dumps(
            {
                "MERGE_COMMIT": "6c3e74964d023cdcb55c3b77d6d029b095d578c6",
                "CLEAN_MACHINE_FINAL": True,
                "RELEASE_READINESS": "CERTIFIED",
                "ACCEPTANCE_WORKFLOW_PILOT": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runbook = tmp_path / "docs" / "productization" / "CLEAN-MACHINE-PREP-RUNBOOK.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text("6c3e74964d023cdcb55c3b77d6d029b095d578c6\n", encoding="utf-8")
    mission_reconcile(tmp_path, main_head="6c3e74964d023cdcb55c3b77d6d029b095d578c6")
    key = _idempotency_key(
        objective="O3",
        kind="RELEASE_VALIDATION",
        package="AS-RELEASE-CLEAN-MACHINE-BOOTSTRAP-001",
        surface="docs/,scripts/,tests/",
    )
    node = WorkNode(
        NODE_ID=f"O3-RELEASE_VALIDATION-{key}",
        OBJECTIVE_ID="O3",
        PACKAGE_ID="AS-RELEASE-CLEAN-MACHINE-BOOTSTRAP-001",
        TASK_KIND="RELEASE_VALIDATION",
        PRIORITY=80,
        DEPENDENCIES=[],
        ALLOWED_PATHS=["docs/", "scripts/", "tests/"],
        SURFACE_SET=["docs/", "scripts/"],
        WORKER_ROLE="READ_ONLY_ANALYST",
        ACCEPTANCE_CRITERIA="verify satisfied gaps",
        REQUIRED_VERIFICATION=["receipt"],
        OWNER_GATE="NONE",
        GENERATION=1,
        IDEMPOTENCY_KEY=key,
        status="READY",
        fingerprint=key,
    )
    binding = dispatch_local_analysis_worker(tmp_path, node)
    interp = interpret_receipt(tmp_path, Path(binding.expected_receipt))
    assert interp["created"] == []
    assert interp["outcome"] == "NO_ACTION_WITH_PROOF"
    nodes_after = load_nodes(tmp_path)
    release_pkgs = [n.PACKAGE_ID for n in nodes_after.values()]
    assert not any(p.startswith("AS-RELEASE-CLEAN_MACHINE") for p in release_pkgs)


def test_closed_loop_no_ready_replenish_when_objectives_met(tmp_path: Path) -> None:
    rt = _runtime(tmp_path)
    rt.mkdir(parents=True)
    queue_path = rt / "d129-owner-merge-queue.json"
    queue_path.write_text(json.dumps({"QUEUE": []}) + "\n", encoding="utf-8")
    (rt / "d146-checkpoint.json").write_text(
        json.dumps(
            {
                "MERGE_COMMIT": "6c3e74964d023cdcb55c3b77d6d029b095d578c6",
                "CLEAN_MACHINE_FINAL": True,
                "RELEASE_READINESS": "CERTIFIED",
                "ACCEPTANCE_WORKFLOW_PILOT": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    runbook = tmp_path / "docs" / "productization" / "CLEAN-MACHINE-PREP-RUNBOOK.md"
    runbook.parent.mkdir(parents=True)
    runbook.write_text("6c3e74964d023cdcb55c3b77d6d029b095d578c6\n", encoding="utf-8")
    from project_atlas.orchestration.sdk.mission_reconciler import (
        load_objectives,
        persist_objectives,
    )

    mission_reconcile(tmp_path, main_head="6c3e74964d023cdcb55c3b77d6d029b095d578c6")
    objs = load_objectives(tmp_path)
    for obj in objs:
        if obj.objective_id in {"O1", "O3", "O4", "O5", "O6"}:
            obj.current_state = "SATISFIED"
        elif obj.objective_id == "O2":
            obj.current_state = "ACCEPTANCE_WORKFLOW_SATISFIED"
    persist_objectives(tmp_path, objs)
    mission_reconcile(tmp_path, main_head="6c3e74964d023cdcb55c3b77d6d029b095d578c6")
    closed_loop_tick(tmp_path, main_head="6c3e74964d023cdcb55c3b77d6d029b095d578c6")
    nodes = load_nodes(tmp_path)
    assert sum(1 for n in nodes.values() if n.status == "READY") == 0


def _load_d147_script() -> object:
    path = Path(__file__).resolve().parents[2] / "docs" / "scripts" / "d147_broker_reconcile.py"
    spec = importlib.util.spec_from_file_location("d147_broker_reconcile", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_snapshot_counts_include_active_nonterminal_states(tmp_path: Path) -> None:
    d147 = _load_d147_script()
    persist_nodes(
        tmp_path,
        {
            "run": WorkNode(
                NODE_ID="run",
                OBJECTIVE_ID="O1",
                PACKAGE_ID="AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001",
                TASK_KIND="IMPLEMENTATION",
                PRIORITY=50,
                DEPENDENCIES=[],
                ALLOWED_PATHS=["src/"],
                SURFACE_SET=["src/"],
                WORKER_ROLE="IMPLEMENTER",
                ACCEPTANCE_CRITERIA="running",
                REQUIRED_VERIFICATION=["unit"],
                OWNER_GATE="NONE",
                GENERATION=1,
                IDEMPOTENCY_KEY="run",
                status="RUNNING",
                fingerprint="run",
            ),
            "fail": WorkNode(
                NODE_ID="fail",
                OBJECTIVE_ID="O1",
                PACKAGE_ID="AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001",
                TASK_KIND="IMPLEMENTATION",
                PRIORITY=50,
                DEPENDENCIES=[],
                ALLOWED_PATHS=["src/"],
                SURFACE_SET=["src/"],
                WORKER_ROLE="IMPLEMENTER",
                ACCEPTANCE_CRITERIA="failed",
                REQUIRED_VERIFICATION=["unit"],
                OWNER_GATE="NONE",
                GENERATION=1,
                IDEMPOTENCY_KEY="fail",
                status="FAILED",
                fingerprint="fail",
            ),
        },
    )
    counts = d147.snapshot_counts(tmp_path)
    assert counts["running"] == 1
    assert counts["failed"] == 1
    assert counts["ready"] == 0
    assert counts["active_nonterminal"] == 2
    assert d147._project_terminal(tmp_path, counts) is False
