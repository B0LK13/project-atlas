"""Adversarial tests for FEATURE_15: Global Control View / Dashboard.

CONTROL_VIEW != AUTHORITY
UI != CANONICAL TRUTH
TELEMETRY != AUTHORITY
Every denial has a load-bearing positive control.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import cli as cli_mod  # noqa: E402
from atlas_dag import control_view as cv  # noqa: E402
from atlas_dag import frontier_matrix as fm  # noqa: E402
from atlas_dag import handoff as handoff_mod  # noqa: E402
from atlas_dag import residuals as res  # noqa: E402
from atlas_dag.gh import GhClient  # noqa: E402
from test_atlas_dag_frontier_score import weights  # noqa: E402
from test_atlas_dag_handoff import (  # noqa: E402
    BOUND_POOL,
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


def build_view(*, nodes=None, events=None, agent="ubuntu-main", tmp_path=None,
               agent_registry=None, stacks=None, matrix=None,
               residual_registry=None, steal_plan=None, telemetry_packet=None,
               seal_by_pr=None, evidence_records=None, invalid_events=None,
               verifier_pool_path=None):
    if agent_registry is None and agent is not None:
        assert tmp_path is not None
        agent_registry = write_registry(tmp_path, [make_profile()])
    if nodes is None:
        nodes = [make_node("pr/800")]
    snap = snapshot_of(*nodes)
    snap["safe_runnable_count"] = sum(
        1 for n in nodes if str(n.get("state", "")).startswith("RUNNABLE"))
    snap["repository"] = REPO
    return cv.build_global_control_view(
        repository=REPO,
        snapshot=snap,
        stacks=stacks if stacks is not None else {},
        events=events or [],
        invalid_events=invalid_events,
        matrix=matrix,
        residual_registry=residual_registry,
        steal_plan=steal_plan,
        telemetry_packet=telemetry_packet,
        seal_by_pr=seal_by_pr,
        evidence_records=evidence_records,
        agent_id=agent,
        registry=agent_registry,
        verifier_pool_path=verifier_pool_path,
        clock=clock,
        seal_scan="skipped_for_latency",
    )


# --- 1 honesty consts -------------------------------------------------------


def test_honesty_consts_required(tmp_path):
    packet = build_view(tmp_path=tmp_path)
    assert cv.validate_control_view(packet) == []
    honesty = packet["honesty"]
    assert honesty["control_view_ne_authority"] is True
    assert honesty["ui_ne_canonical_truth"] is True
    assert honesty["grants_no_write_claim_dispatch_merge_iv"] is True
    assert honesty["aggregates_live_dag_only"] is True
    for key in ("control_view_ne_authority", "ui_ne_canonical_truth",
                "grants_no_write_claim_dispatch_merge_iv",
                "aggregates_live_dag_only"):
        assert packet["provenance"][key] is True
    bad = copy.deepcopy(packet)
    bad["honesty"]["control_view_ne_authority"] = False
    assert any("control_view_ne_authority" in e
               for e in cv.validate_control_view(bad))


# --- 2 never upgrades blocked → runnable ------------------------------------


def test_control_view_never_upgrades_blocked_to_runnable(tmp_path):
    node = make_node("pr/801", owner="other", frozen=True, state="FROZEN")
    events = [finding("evt-cv-1", pr=801)]
    agent_reg = write_registry(tmp_path, [make_profile()])
    residual = res.build_residual_registry(
        repository=REPO, events=events, snapshot=snapshot_of(node),
        stacks={}, seal_by_pr=None, agent_id="ubuntu-main", registry=agent_reg,
        clock=clock)
    matrix = fm.build_frontier_matrix(
        snapshot_of(node), agent_id="ubuntu-main", registry=agent_reg,
        residual_registry=residual, weights=weights(), clock=clock)
    blocked_actions = [
        a for a in matrix["actions"] if a["runnable_state"] == fm.BLOCKED
    ]
    assert blocked_actions
    packet = build_view(
        nodes=[node], events=events, agent_registry=agent_reg,
        matrix=matrix, residual_registry=residual)
    res_panel = packet["panels"]["residuals"]["summary"]
    assert res_panel["open_count"] >= 1
    # Blocked stays blocked in the injected residual registry.
    assert residual["residuals"][0]["derived_execution_state"] == res.BLOCKED
    assert res_panel["blocked_count"] >= 1
    # Frontier panel reports blocked count; does not invent eligible upgrades.
    assert packet["panels"]["frontier"]["summary"]["blocked_count"] >= 1
    matrix2 = fm.build_frontier_matrix(
        snapshot_of(node), agent_id="ubuntu-main", registry=agent_reg,
        residual_registry=residual, weights=weights(), clock=clock)
    still_blocked = {
        a["action_id"] for a in matrix2["actions"]
        if a["runnable_state"] == fm.BLOCKED
    }
    assert {a["action_id"] for a in blocked_actions} <= still_blocked


# --- 3 missing agent → portfolio panels -------------------------------------


def test_missing_agent_still_builds_portfolio_panels(tmp_path):
    nodes = [
        make_node("pr/804", ownership="OWNED"),
        make_node("pr/805", ownership="UNOWNED", owner=None, claimants=[],
                  state="RUNNABLE_READONLY"),
    ]
    agent_reg = write_registry(tmp_path, [make_profile()])
    packet = build_view(nodes=nodes, agent=None, agent_registry=agent_reg)
    assert packet["agent_status"] == "NONE"
    assert packet["panels"]["ownership"]["summary"]["owned_count"] == 1
    assert packet["panels"]["ownership"]["summary"]["unowned_count"] == 1
    assert packet["panels"]["steal"]["summary"]["utilization"] == "PORTFOLIO"
    assert packet["panels"]["agents"]["status"] in (cv.OK, cv.DEGRADED)
    assert cv.validate_control_view(packet) == []


# --- 4 determinism ----------------------------------------------------------


def test_determinism_same_inputs_same_view_fingerprint(tmp_path):
    nodes = [make_node("pr/806"), make_node("pr/807", ownership="UNOWNED",
                                            owner=None, claimants=[],
                                            state="RUNNABLE_READONLY")]
    events = [finding("evt-det-1", pr=806)]
    a = build_view(nodes=nodes, events=events, tmp_path=tmp_path, matrix=None,
                   agent=None, agent_registry=write_registry(
                       tmp_path, [make_profile()]))
    b = build_view(nodes=list(reversed(nodes)), events=list(reversed(events)),
                   agent=None,
                   agent_registry=write_registry(tmp_path, [make_profile()]),
                   matrix=None)
    assert a["view_fingerprint"] == b["view_fingerprint"]
    assert a["honesty"] == b["honesty"]


# --- 5 unbound verifiers → EXTERNAL_IV_GATED --------------------------------


def test_unbound_verifiers_system_honesty_external_iv_gated(tmp_path):
    # Default registry/verifiers.json has principal:null → DECLARED_BUT_UNBOUND.
    packet = build_view(tmp_path=tmp_path)
    honesty_panel = packet["panels"]["system_honesty"]
    assert honesty_panel["summary"]["external_iv_gated"] is True
    assert "EXTERNAL_IV_GATED" in honesty_panel["notes"]
    assert honesty_panel["status"] == cv.DEGRADED


# --- 6/7 handoff resume includes control_view; general omits ----------------


def test_handoff_resume_includes_control_view_general_omits(tmp_path):
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-cv-1"))
    pool = make_pool_file(tmp_path, BOUND_POOL)
    agent_reg = write_registry(tmp_path, [make_profile()])
    client = GhClient(repo=REPO, runner=env.runner())

    general = handoff_mod.build_handoff(
        10, "general", client, clock=clock, verifier_pool=pool,
        registry=agent_reg, agent_id="ubuntu-main")
    resume = handoff_mod.build_handoff(
        10, "resume", client, clock=clock, verifier_pool=pool,
        registry=agent_reg, agent_id="ubuntu-main")

    assert "control_view" not in general["presentation"]
    assert "control_view" in resume["presentation"]
    info = resume["presentation"]["control_view"]
    if "reason" not in info:
        assert info.get("view_fingerprint")
        assert info.get("honesty", {}).get("control_view_ne_authority") is True
        assert "panel_status" in info
    assert "FEATURE_15 global control view (presentation only)" in (
        resume["provenance"]["truth_sources"])
    assert general["truth_fingerprint"] == resume["truth_fingerprint"]


# --- 8 schema validation fail closed ----------------------------------------


def test_schema_validation_fail_closed(tmp_path):
    packet = build_view(tmp_path=tmp_path)
    assert cv.validate_control_view(packet) == []
    bad = copy.deepcopy(packet)
    del bad["panels"]["frontier"]
    assert cv.validate_control_view(bad)
    bad2 = copy.deepcopy(packet)
    bad2["panels"]["agents"]["status"] = "RUNNABLE"
    assert any("status" in e or "RUNNABLE" in e
               for e in cv.validate_control_view(bad2))


# --- 9 panels present -------------------------------------------------------


def test_panels_present_for_core_surfaces(tmp_path):
    packet = build_view(tmp_path=tmp_path)
    for key in ("agents", "ownership", "frontier", "residuals", "telemetry"):
        assert key in packet["panels"]
        assert packet["panels"][key]["status"] in (cv.OK, cv.DEGRADED, cv.UNKNOWN)
        assert isinstance(packet["panels"][key]["summary"], dict)
    assert set(packet["panels"]) == set(cv.PANEL_KEYS)


# --- 10 dashboard alias registered ------------------------------------------


def test_dashboard_alias_registered():
    assert "control-view" in cli_mod.COMMANDS
    assert "dashboard" in cli_mod.COMMANDS
    assert cli_mod.COMMANDS["dashboard"] is cli_mod.COMMANDS["control-view"]
    parser = cli_mod.build_parser()
    args = parser.parse_args(["dashboard", "--agent", "ubuntu-main"])
    assert args.command == "dashboard"
    args2 = parser.parse_args(["control-view", "--json"])
    assert args2.command == "control-view"
    assert args2.json is True


# --- 11 UNKNOWN panels when matrix absent without crash ---------------------


def test_unknown_frontier_when_matrix_absent_no_crash(tmp_path):
    packet = build_view(
        nodes=[make_node("pr/808")], tmp_path=tmp_path, matrix=None, agent=None,
        agent_registry=write_registry(tmp_path, [make_profile()]),
        telemetry_packet={
            "schema": "ATLAS_COORDINATION_TELEMETRY_V1",
            "generated_at_utc": FIXED,
            "repository": REPO,
            "agent": None,
            "agent_status": "NONE",
            "truth_fingerprint": "a" * 64,
            "telemetry_fingerprint": "b" * 64,
            "honesty": {
                "telemetry_ne_authority": True,
                "metrics_ne_authorization": True,
                "derived_from_live_dag_only": True,
                "grants_no_write_claim_dispatch_merge_iv": True,
            },
            "categories": {},
            "provenance": {},
        })
    assert packet["panels"]["frontier"]["status"] == cv.UNKNOWN
    assert "MATRIX_ABSENT" in packet["panels"]["frontier"]["notes"]
    assert packet["panels"]["evidence_health"]["status"] == cv.UNKNOWN
    assert packet["panels"]["postmerge"]["status"] == cv.UNKNOWN


# --- 12 positive residuals open reflected -----------------------------------


def test_positive_residuals_open_reflected(tmp_path):
    events = [finding("evt-back-1", pr=809)]
    agent_reg = write_registry(tmp_path, [make_profile()])
    residual = res.build_residual_registry(
        repository=REPO, events=events,
        snapshot=snapshot_of(make_node("pr/809")),
        stacks={}, agent_id="ubuntu-main", registry=agent_reg, clock=clock)
    packet = build_view(
        nodes=[make_node("pr/809")], events=events, agent_registry=agent_reg,
        residual_registry=residual, matrix={"frontier_fingerprint": "c" * 64,
                                            "eligible_actions": [],
                                            "blocked_actions": [],
                                            "ineligible_actions": [],
                                            "parallel_runnable_set": []})
    assert packet["panels"]["residuals"]["summary"]["open_count"] >= 1


# --- 13 view does not mutate snapshot ---------------------------------------


def test_view_does_not_mutate_snapshot(tmp_path):
    node = make_node("pr/810", waiting_on=["CI"])
    snap_nodes = [copy.deepcopy(node)]
    snap = snapshot_of(*snap_nodes)
    before = copy.deepcopy(snap)
    agent_reg = write_registry(tmp_path, [make_profile()])
    _ = cv.build_global_control_view(
        repository=REPO,
        snapshot=snap,
        stacks={},
        events=[],
        matrix=None,
        residual_registry=None,
        agent_id=None,
        registry=agent_reg,
        clock=clock,
    )
    assert snap == before


# --- 14 schema const + seal_scan note ---------------------------------------


def test_schema_const_and_seal_scan_note(tmp_path):
    packet = build_view(tmp_path=tmp_path)
    assert packet["schema"] == cv.SCHEMA_CONST
    assert packet["provenance"]["seal_scan"] == "skipped_for_latency"
    assert any("seal_scan" in n for n in packet["provenance"]["notes"])
