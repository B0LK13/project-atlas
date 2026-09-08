"""Adversarial tests for FEATURE_14: Efficiency Metrics & Coordination Telemetry.

TELEMETRY != AUTHORITY
METRICS != AUTHORIZATION
Every denial has a load-bearing positive control.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import frontier_matrix as fm  # noqa: E402
from atlas_dag import handoff as handoff_mod  # noqa: E402
from atlas_dag import residuals as res  # noqa: E402
from atlas_dag import steal as steal_mod  # noqa: E402
from atlas_dag import telemetry as tel  # noqa: E402
from atlas_dag.gh import GhClient  # noqa: E402
from test_atlas_dag_frontier_score import weights  # noqa: E402
from test_atlas_dag_handoff import (  # noqa: E402
    BOUND_POOL,
    H1,
    T1,
    base_env,
    comments_with,
    make_pool_file,
    make_receipt,
)
from test_atlas_dag_router import make_node, make_profile, snapshot_of, write_registry  # noqa: E402

FIXED = "2026-09-08T12:00:00Z"
REPO = "B0LK13/project-atlas"


def clock():
    return FIXED


def finding(event_id, pr=800, note="security defect in auth", **extra):
    ev = {
        "schema": "ATLAS_EVENT_V1",
        "event_id": event_id,
        "timestamp_utc": FIXED,
        "actor": "ubuntu-main",
        "role": "COORDINATOR",
        "session_id": "s",
        "lane": f"pr/{pr}",
        "pr": pr,
        "head": "a" * 40,
        "event": "NEW_FINDING",
        "state": "OPEN",
        "note": note,
        "evidence": [],
        "dependencies": [],
        "next_actions": [],
    }
    ev.update(extra)
    return ev


def build_tel(*, nodes=None, events=None, agent="ubuntu-main", tmp_path=None,
              agent_registry=None, stacks=None, matrix=None,
              residual_registry=None, steal_plan=None, dispatch_by_pr=None,
              invalid_events=None, seal_projection="deferred_or_skipped"):
    if agent_registry is None and agent is not None:
        assert tmp_path is not None
        agent_registry = write_registry(tmp_path, [make_profile()])
    if nodes is None:
        nodes = [make_node("pr/800")]
    snap = snapshot_of(*nodes)
    snap["safe_runnable_count"] = sum(
        1 for n in nodes if str(n.get("state", "")).startswith("RUNNABLE"))
    snap["repository"] = REPO
    return tel.build_coordination_telemetry(
        repository=REPO,
        snapshot=snap,
        stacks=stacks or {},
        events=events or [],
        invalid_events=invalid_events,
        matrix=matrix,
        residual_registry=residual_registry,
        steal_plan=steal_plan,
        dispatch_by_pr=dispatch_by_pr,
        agent_id=agent,
        registry=agent_registry,
        clock=clock,
        seal_projection=seal_projection,
    )


# --- 1 schema honesty consts -------------------------------------------------


def test_schema_honesty_consts_required(tmp_path):
    packet = build_tel(tmp_path=tmp_path)
    assert tel.validate_telemetry(packet) == []
    honesty = packet["honesty"]
    assert honesty["telemetry_ne_authority"] is True
    assert honesty["metrics_ne_authorization"] is True
    assert honesty["derived_from_live_dag_only"] is True
    assert honesty["grants_no_write_claim_dispatch_merge_iv"] is True
    for key in ("telemetry_ne_authority", "metrics_ne_authorization",
                "derived_from_live_dag_only",
                "grants_no_write_claim_dispatch_merge_iv"):
        assert packet["provenance"][key] is True
    bad = copy.deepcopy(packet)
    bad["honesty"]["telemetry_ne_authority"] = False
    assert any("telemetry_ne_authority" in e for e in tel.validate_telemetry(bad))


# --- 2 telemetry never upgrades blocked→runnable ----------------------------


def test_telemetry_never_upgrades_blocked_to_runnable(tmp_path):
    node = make_node("pr/801", owner="other", frozen=True, state="FROZEN")
    events = [finding("evt-tel-1", pr=801)]
    agent_reg = write_registry(tmp_path, [make_profile()])
    residual = res.build_residual_registry(
        repository=REPO, events=events, snapshot=snapshot_of(node),
        stacks={}, seal_by_pr=None, agent_id="ubuntu-main", registry=agent_reg,
        clock=clock)
    matrix = fm.build_frontier_matrix(
        snapshot_of(node), agent_id="ubuntu-main", registry=agent_reg,
        residual_registry=residual, weights=weights(), clock=clock)
    blocked_actions = [
        a for a in matrix["actions"]
        if a["runnable_state"] == fm.BLOCKED
    ]
    assert blocked_actions
    packet = build_tel(
        nodes=[node], events=events, agent_registry=agent_reg,
        matrix=matrix, residual_registry=residual)
    residual_cat = packet["categories"]["residual_backlog"]["metrics"]
    assert residual_cat["open_count"] >= 1
    matrix_blocked_ids = {a["action_id"] for a in blocked_actions}
    matrix2 = fm.build_frontier_matrix(
        snapshot_of(node), agent_id="ubuntu-main", registry=agent_reg,
        residual_registry=residual, weights=weights(), clock=clock)
    still_blocked = {
        a["action_id"] for a in matrix2["actions"]
        if a["runnable_state"] == fm.BLOCKED
    }
    assert matrix_blocked_ids <= still_blocked
    owned = make_node("pr/801", state="RUNNABLE_WRITE")
    ok_res = res.build_residual_registry(
        repository=REPO, events=events, snapshot=snapshot_of(owned),
        stacks={}, agent_id="ubuntu-main", registry=agent_reg, clock=clock)
    assert ok_res["residuals"][0]["derived_execution_state"] == res.RUNNABLE


# --- 3 steal_success plan_only without claim history ------------------------


def test_steal_success_plan_only_no_fake_rate(tmp_path):
    unowned = make_node("pr/802", state="RUNNABLE_READONLY", ownership="UNOWNED",
                        owner=None, claimants=[])
    agent_reg = write_registry(tmp_path, [make_profile()])
    plan = steal_mod.plan_steal(
        snapshot_of(unowned), "ubuntu-main", agent_reg, stacks={},
        weights=weights(), weights_source="test", clock=clock)
    packet = build_tel(
        nodes=[unowned], events=[], agent_registry=agent_reg, steal_plan=plan)
    steal_cat = packet["categories"]["steal_success"]
    assert steal_cat["metrics"]["plan_only"] is True
    assert steal_cat["metrics"]["success_rate"] is None
    assert "PLAN_ONLY_NO_CLAIM_HISTORY" in steal_cat["notes"]
    claimed_evt = {
        "schema": "ATLAS_EVENT_V1", "event_id": "evt-claim-1",
        "timestamp_utc": FIXED, "actor": "ubuntu-main", "role": "COORDINATOR",
        "session_id": "s", "lane": "pr/802", "pr": 802, "head": "a" * 40,
        "event": "OWNER_CLAIMED", "state": "CLAIMED", "evidence": [],
        "dependencies": [], "next_actions": [],
    }
    with_hist = build_tel(
        nodes=[unowned], events=[claimed_evt], agent_registry=agent_reg,
        steal_plan=plan)
    assert with_hist["categories"]["steal_success"]["metrics"]["plan_only"] is False
    assert with_hist["categories"]["steal_success"]["metrics"]["success_rate"] == 1.0


# --- 4 AMBIGUOUS counted in contention --------------------------------------


def test_ambiguous_counted_in_ownership_contention(tmp_path):
    amb = make_node("pr/803", ownership="AMBIGUOUS", owner=None,
                    claimants=["a", "b"], state="BLOCKED")
    packet = build_tel(nodes=[amb], tmp_path=tmp_path)
    metrics = packet["categories"]["ownership_contention"]["metrics"]
    assert metrics["ambiguous_count"] == 1
    assert "AMBIGUOUS_OWNERSHIP_PRESENT" in packet["categories"][
        "ownership_contention"]["notes"]
    assert packet["categories"]["ownership_contention"]["status"] == tel.DEGRADED


# --- 5 missing agent → agent_status NONE / portfolio OK ---------------------


def test_missing_agent_portfolio_utilization_ok(tmp_path):
    nodes = [
        make_node("pr/804", ownership="OWNED"),
        make_node("pr/805", ownership="UNOWNED", owner=None, claimants=[],
                  state="RUNNABLE_READONLY"),
    ]
    packet = build_tel(nodes=nodes, agent=None, agent_registry=None)
    assert packet["agent_status"] == "NONE"
    util = packet["categories"]["utilization"]
    assert util["status"] == tel.OK
    assert util["metrics"]["utilization"] == "PORTFOLIO"
    assert util["metrics"]["owned_lane_count"] == 1
    assert util["metrics"]["unowned_lane_count"] == 1


# --- 6 determinism ----------------------------------------------------------


def test_determinism_same_inputs_same_fingerprints(tmp_path):
    nodes = [make_node("pr/806"), make_node("pr/807", ownership="UNOWNED",
                                            owner=None, claimants=[],
                                            state="RUNNABLE_READONLY")]
    events = [finding("evt-det-1", pr=806)]
    a = build_tel(nodes=nodes, events=events, tmp_path=tmp_path)
    b = build_tel(nodes=list(reversed(nodes)), events=list(reversed(events)),
                  tmp_path=tmp_path)
    assert a["truth_fingerprint"] == b["truth_fingerprint"]
    assert a["telemetry_fingerprint"] == b["telemetry_fingerprint"]


# --- 7/8 handoff resume includes telemetry; general omits; truth fp stable --


def test_handoff_resume_includes_telemetry_general_omits(tmp_path):
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-tel-1"))
    pool = make_pool_file(tmp_path, BOUND_POOL)
    agent_reg = write_registry(tmp_path, [make_profile()])
    client = GhClient(repo=REPO, runner=env.runner())

    general = handoff_mod.build_handoff(
        10, "general", client, clock=clock, verifier_pool=pool,
        registry=agent_reg, agent_id="ubuntu-main")
    resume = handoff_mod.build_handoff(
        10, "resume", client, clock=clock, verifier_pool=pool,
        registry=agent_reg, agent_id="ubuntu-main")

    assert "coordination_telemetry" not in general["presentation"]
    assert "coordination_telemetry" in resume["presentation"]
    tel_info = resume["presentation"]["coordination_telemetry"]
    if "reason" not in tel_info:
        assert tel_info.get("telemetry_fingerprint")
        assert tel_info.get("honesty", {}).get("telemetry_ne_authority") is True
    assert "FEATURE_14 coordination telemetry (presentation only)" in (
        resume["provenance"]["truth_sources"])
    assert general["truth_fingerprint"] == resume["truth_fingerprint"]


def test_handoff_truth_fingerprint_stable_when_telemetry_presentation_differs(
        tmp_path):
    env = base_env()
    env.add_pr(10, H1, T1)
    env.comments = comments_with(make_receipt("rcpt-tel-2"))
    pool = make_pool_file(tmp_path, BOUND_POOL)
    agent_reg = write_registry(tmp_path, [make_profile()])
    client = GhClient(repo=REPO, runner=env.runner())
    a = handoff_mod.build_handoff(
        10, "resume", client, clock=clock, verifier_pool=pool,
        registry=agent_reg, agent_id="ubuntu-main")
    b = handoff_mod.build_handoff(
        10, "resume", client, clock=clock, verifier_pool=pool,
        registry=agent_reg, agent_id="ubuntu-main")
    assert a["truth_fingerprint"] == b["truth_fingerprint"]
    assert "coordination_telemetry" in a["presentation"]
    assert a["presentation"]["coordination_telemetry"]["telemetry_fingerprint"] == \
        b["presentation"]["coordination_telemetry"]["telemetry_fingerprint"]


# --- 9 invalid/missing matrix → UNKNOWN not crash ---------------------------


def test_invalid_missing_matrix_category_unknown(tmp_path):
    packet = build_tel(
        nodes=[make_node("pr/808")], tmp_path=tmp_path, matrix=None, agent=None)
    assert packet["categories"]["blocked_reasons"]["status"] == tel.UNKNOWN
    assert "MATRIX_ABSENT_OR_INVALID" in packet["categories"]["blocked_reasons"]["notes"]
    bad = build_tel(
        nodes=[make_node("pr/808")], tmp_path=tmp_path,
        matrix={"actions": "not-a-list"}, agent=None)
    assert bad["categories"]["blocked_reasons"]["status"] == tel.UNKNOWN


# --- 10 positive residual open → backlog ≥ 1 --------------------------------


def test_positive_residual_open_backlog(tmp_path):
    events = [finding("evt-back-1", pr=809)]
    agent_reg = write_registry(tmp_path, [make_profile()])
    residual = res.build_residual_registry(
        repository=REPO, events=events,
        snapshot=snapshot_of(make_node("pr/809")),
        stacks={}, agent_id="ubuntu-main", registry=agent_reg, clock=clock)
    packet = build_tel(
        nodes=[make_node("pr/809")], events=events, agent_registry=agent_reg,
        residual_registry=residual)
    assert packet["categories"]["residual_backlog"]["metrics"]["open_count"] >= 1


# --- 11 positive STEAL_AVAILABLE utilization reflected ----------------------


def test_positive_steal_available_utilization(tmp_path):
    unowned = make_node("pr/810", state="RUNNABLE_READONLY", ownership="UNOWNED",
                        owner=None, claimants=[])
    agent_reg = write_registry(tmp_path, [make_profile()])
    plan = steal_mod.plan_steal(
        snapshot_of(unowned), "ubuntu-main", agent_reg, stacks={},
        weights=weights(), weights_source="test", clock=clock)
    packet = build_tel(
        nodes=[unowned], agent_registry=agent_reg, steal_plan=plan)
    util = packet["categories"]["utilization"]["metrics"]["utilization"]
    assert util == plan["utilization"]
    if plan["utilization"] == steal_mod.STEAL_AVAILABLE:
        assert packet["categories"]["utilization"]["status"] == tel.OK
        assert packet["categories"]["utilization"]["metrics"][
            "steal_candidate_present"] is True


# --- 12 metrics rollup shares source_telemetry_fingerprint ------------------


def test_metrics_rollup_shares_source_telemetry_fingerprint(tmp_path):
    packet = build_tel(tmp_path=tmp_path)
    metrics = tel.build_efficiency_metrics(packet, clock=clock)
    assert tel.validate_metrics(metrics) == []
    assert metrics["source_telemetry_fingerprint"] == packet["telemetry_fingerprint"]
    assert metrics["schema"] == tel.METRICS_SCHEMA_CONST


# --- 13 metrics cannot invent WRITE authority -------------------------------


def test_metrics_cannot_invent_write_authority(tmp_path):
    packet = build_tel(tmp_path=tmp_path)
    metrics = tel.build_efficiency_metrics(packet, clock=clock)
    honesty = metrics["honesty"]
    assert honesty["telemetry_ne_authority"] is True
    assert honesty["metrics_ne_authorization"] is True
    assert honesty["grants_no_write_claim_dispatch_merge_iv"] is True
    forged = copy.deepcopy(metrics)
    forged["honesty"]["grants_no_write_claim_dispatch_merge_iv"] = False
    assert tel.validate_metrics(forged)
    summary_keys = set(metrics["summary"])
    assert "write_authority" not in summary_keys
    assert "may_merge" not in summary_keys
    assert "may_dispatch" not in summary_keys


# --- 14 blocked_reasons histogram deterministic sort ------------------------


def test_blocked_reasons_histogram_deterministic_sort(tmp_path):
    matrix = {
        "frontier_fingerprint": "a" * 64,
        "actions": [
            {"runnable_state": "BLOCKED",
             "blocking_reasons": ["Z_REASON", "A_REASON"]},
            {"runnable_state": "BLOCKED",
             "blocking_reasons": ["A_REASON"]},
            {"runnable_state": "BLOCKED",
             "blocking_reasons": ["M_REASON", "A_REASON"]},
        ],
    }
    packet = build_tel(
        nodes=[make_node("pr/811")], tmp_path=tmp_path, matrix=matrix, agent=None)
    histogram = packet["categories"]["blocked_reasons"]["metrics"]["histogram"]
    assert [h["reason"] for h in histogram] == ["A_REASON", "M_REASON", "Z_REASON"]
    assert histogram[0]["count"] == 3
    matrix2 = {
        "frontier_fingerprint": "a" * 64,
        "actions": list(reversed(matrix["actions"])),
    }
    packet2 = build_tel(
        nodes=[make_node("pr/811")], tmp_path=tmp_path, matrix=matrix2, agent=None)
    assert packet["categories"]["blocked_reasons"]["metrics"]["histogram"] == \
        packet2["categories"]["blocked_reasons"]["metrics"]["histogram"]


def test_schema_const_and_seal_projection_note(tmp_path):
    packet = build_tel(tmp_path=tmp_path)
    assert packet["schema"] == tel.SCHEMA_CONST
    assert packet["provenance"]["seal_projection"] == "deferred_or_skipped"
    assert "SEAL_SCAN_SKIPPED" in packet["provenance"]["notes"]
