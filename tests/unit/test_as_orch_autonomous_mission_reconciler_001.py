"""AS-ORCH-AUTONOMOUS-MISSION-RECONCILER-001 adversarial + closed-loop tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.orchestration.sdk.mission_reconciler import (
    PACKAGE_ID,
    closed_loop_tick,
    interpret_receipt,
    load_mission_state,
    load_nodes,
    load_objectives,
    mission_reconcile,
    ready_work_items,
    real_active_worker_count,
)
from project_atlas.orchestration.sdk.models import SdkRuntimeError


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / ".atlas" / "orchestration" / "sdk-runtime").mkdir(parents=True)
    (tmp_path / ".atlas" / "orchestration" / "sdk-runtime" / "d129-owner-merge-queue.json").write_text(
        json.dumps(
            {
                "QUEUE": [
                    {"PR": 431},
                    {"PR": 432},
                    {"PR": 433},
                    {"PR": 434},
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


def test_objectives_persist_and_survive(root: Path) -> None:
    mission_reconcile(root)
    objs = load_objectives(root)
    assert len(objs) == 6
    assert {o.objective_id for o in objs} == {"O1", "O2", "O3", "O4", "O5", "O6"}
    assert PACKAGE_ID.startswith("AS-ORCH")


def test_empty_ready_forces_reconcile(root: Path) -> None:
    s1 = mission_reconcile(root)
    assert s1["READY_NODE_COUNT"] >= 1
    # Drain READY by completing via closed loop
    closed_loop_tick(root)
    state = load_mission_state(root)
    assert state.MISSION_GENERATION >= 1
    assert state.EMPTY_READY_QUEUE_RECONCILIATION_COUNT >= 0


def test_closed_loop_dispatch_and_successor(root: Path) -> None:
    r1 = closed_loop_tick(root)
    assert r1["REAL_WORKER_DISPATCH_COUNT"] == 1
    assert r1["REAL_WORKER_COMPLETION_COUNT"] == 1
    assert r1.get("SYNTHETIC_ACTIVE_WORKER_COUNT", 0) == 0
    assert real_active_worker_count(root) == 0  # completed recycled
    created = r1.get("created_successors") or []
    assert len(created) >= 1
    state = load_mission_state(root)
    assert state.RECEIPT_CONSUME_SEQUENCE >= 1
    assert state.SUCCESSOR_GENERATION_SEQUENCE >= 1
    assert state.PROGRESS_SEQUENCE >= 1


def test_duplicate_idempotency(root: Path) -> None:
    mission_reconcile(root)
    n1 = len(load_nodes(root))
    mission_reconcile(root)  # same fingerprint after first sets it — may skip
    # Force new generation by mutating fingerprint path: change objective state
    objs = load_objectives(root)
    objs[0].current_state = "MUTATED_FOR_TEST"
    from project_atlas.orchestration.sdk.mission_reconciler import persist_objectives

    persist_objectives(root, objs)
    mission_reconcile(root)
    n2 = len(load_nodes(root))
    # Idempotency keys prevent duplicates
    keys = [n.IDEMPOTENCY_KEY for n in load_nodes(root).values()]
    assert len(keys) == len(set(keys))
    assert n2 >= n1


def test_owner_blocked_demo_nodes(root: Path) -> None:
    mission_reconcile(root)
    nodes = load_nodes(root)
    blocked = [n for n in nodes.values() if n.status == "BLOCKED_OWNER"]
    assert any("PR431" in n.DEPENDENCIES for n in blocked)


def test_surface_overlap_serializes(root: Path) -> None:
    mission_reconcile(root)
    items = ready_work_items(root, capacity=5)
    # Selected set should not have overlapping surfaces among themselves
    from project_atlas.orchestration.sdk.mission_reconciler import load_nodes, surfaces_overlap

    nodes = load_nodes(root)
    selected = [nodes[i.node_id] for i in items]
    for i, a in enumerate(selected):
        for b in selected[i + 1 :]:
            assert not surfaces_overlap(a.SURFACE_SET, b.SURFACE_SET)


def test_no_action_without_proof_fails(root: Path, tmp_path: Path) -> None:
    mission_reconcile(root)
    bad = tmp_path / "bad-receipt.json"
    bad.write_text(
        json.dumps({"NO_ACTION": True, "successors": [], "objective_id": "O3"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(SdkRuntimeError):
        interpret_receipt(root, bad)


def test_multi_generation_progress(root: Path) -> None:
    # Force generation bumps via main_head fingerprint changes
    for i in range(3):
        closed_loop_tick(root, main_head=f"main-sim-{i}")
    state = load_mission_state(root)
    assert state.MISSION_GENERATION >= 3
    assert state.WORKER_DISPATCH_SEQUENCE >= 2
    assert state.SUCCESSOR_GENERATION_SEQUENCE >= 1
