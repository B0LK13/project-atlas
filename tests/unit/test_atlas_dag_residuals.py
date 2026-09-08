"""Adversarial tests for FEATURE_13: EXECUTABLE_RESIDUAL_REGISTRY.

DISCOVERED_WORK != EPHEMERAL_PROSE
RESIDUAL_EXISTENCE != EXECUTION_AUTHORITY
Every denial has a load-bearing positive control.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import frontier_matrix as fm  # noqa: E402
from atlas_dag import residuals as res  # noqa: E402
from atlas_dag import steal as steal_mod  # noqa: E402
from test_atlas_dag_frontier_score import weights  # noqa: E402
from test_atlas_dag_router import make_node, make_profile, snapshot_of, write_registry  # noqa: E402

FIXED = "2026-09-08T12:00:00Z"
REPO = "B0LK13/project-atlas"


def clock():
    return FIXED


def finding(event_id, pr=800, note="security defect in auth", state="OPEN",
            **extra):
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
        "state": state,
        "note": note,
        "evidence": [],
        "dependencies": [],
        "next_actions": [],
    }
    ev.update(extra)
    return ev


def registry(events, nodes=None, agent="ubuntu-main", tmp_path=None,
             stacks=None, seal_by_pr=None, agent_registry=None):
    if agent_registry is None:
        assert tmp_path is not None
        agent_registry = write_registry(tmp_path, [make_profile()])
    if nodes is None:
        prs = sorted({int(e["pr"]) for e in events if e.get("pr") is not None})
        nodes = [make_node(f"pr/{pr}") for pr in prs] or [make_node("pr/800")]
    snap = snapshot_of(*nodes)
    return res.build_residual_registry(
        repository=REPO, events=events, snapshot=snap, stacks=stacks or {},
        seal_by_pr=seal_by_pr, agent_id=agent, registry=agent_registry,
        clock=clock)


def test_open_residual_persists_across_rebuild(tmp_path):
    events = [finding("evt-find-1")]
    r1 = registry(events, nodes=[make_node("pr/800")], tmp_path=tmp_path)
    r2 = registry(events, nodes=[make_node("pr/800")], tmp_path=tmp_path)
    assert r1["registry_fingerprint"] == r2["registry_fingerprint"]
    assert r1["open_count"] == 1
    rid = r1["residuals"][0]["residual_id"]
    assert rid.startswith("res-")
    assert r1["residuals"][0]["disposition"] == res.OPEN


def test_blocked_residual_visible_not_executable(tmp_path):
    events = [finding("evt-find-2", note="security finding")]
    node = make_node("pr/800", owner="other-agent", frozen=True, state="FROZEN")
    packet = registry(events, nodes=[node], tmp_path=tmp_path)
    rec = packet["residuals"][0]
    assert rec["disposition"] == res.OPEN
    assert rec["derived_execution_state"] == res.BLOCKED
    assert any("FROZEN" in b or "OWNERSHIP" in b for b in rec["blocking_reasons"])
    # Positive: unfreeze+own → may become RUNNABLE for REMEDIATE
    owned = make_node("pr/800", state="RUNNABLE_WRITE")
    ok = registry(events, nodes=[owned], tmp_path=tmp_path)
    assert ok["residuals"][0]["derived_execution_state"] == res.RUNNABLE


def test_prerequisite_satisfaction_blocked_to_runnable(tmp_path):
    rid = res.make_residual_id("manual", "research-q")
    events = [{
        "schema": "ATLAS_EVENT_V1", "event_id": "evt-reg-1",
        "timestamp_utc": FIXED, "actor": "ubuntu-main", "role": "COORDINATOR",
        "session_id": "s", "lane": "pr/801", "pr": 801, "head": "b" * 40,
        "event": res.EVT_REGISTERED, "state": "OPEN",
        "note": "research question on API shape",
        "residual_id": rid, "residual_type": res.RESEARCH,
        "required_action_type": res.READONLY_ANALYZE,
        "prerequisites": [], "evidence": [], "dependencies": [],
        "next_actions": [],
    }]
    node = make_node("pr/801", owner="other-agent")
    packet = registry(events, nodes=[node], tmp_path=tmp_path)
    assert packet["residuals"][0]["derived_execution_state"] == res.RUNNABLE
    assert packet["residuals"][0]["required_action_type"] == res.READONLY_ANALYZE


def test_high_severity_cannot_bypass_ownership_freeze(tmp_path):
    events = [finding("evt-p0", pr=802, note="SECURITY P0 critical", severity="P0")]
    node = make_node("pr/802", owner="other", frozen=True, state="FROZEN",
                     priority_class="P0")
    packet = registry(events, nodes=[node], tmp_path=tmp_path)
    rec = packet["residuals"][0]
    assert rec["derived_execution_state"] == res.BLOCKED
    # Score path: residual appears in F12 but stays blocked
    agent_reg = write_registry(tmp_path, [make_profile()])
    matrix = fm.build_frontier_matrix(
        snapshot_of(node), agent_id="ubuntu-main", registry=agent_reg,
        residual_registry=packet, weights=weights(), clock=clock)
    residual_actions = [a for a in matrix["actions"] if a.get("residual_id")]
    assert residual_actions
    assert all(a["runnable_state"] != fm.RUNNABLE for a in residual_actions)


def test_foreign_owned_residual_not_stealable(tmp_path):
    events = [finding("evt-steal", pr=803)]
    node = make_node("pr/803", owner="other-agent", state="RUNNABLE_WRITE")
    unowned = make_node("pr/804", state="RUNNABLE_READONLY", ownership="UNOWNED",
                        owner=None, claimants=[])
    agent_reg = write_registry(tmp_path, [make_profile()])
    registry(events, nodes=[node, unowned], agent_registry=agent_reg)
    plan = steal_mod.plan_steal(
        snapshot_of(node, unowned), "ubuntu-main", agent_reg, stacks={},
        weights=weights(), weights_source="test", clock=clock)
    # Steal may pick unowned 804; must never pick foreign 803 as claim target
    # via residual write bypass.
    if plan.get("candidate"):
        assert plan["candidate"]["pr"] != 803 or plan["candidate"].get(
            "ownership") == "UNOWNED"


def test_verifier_cannot_self_certify_resolution(tmp_path):
    events = [finding("evt-iv", note="missing IV verification")]
    packet = registry(events, nodes=[make_node("pr/805")], tmp_path=tmp_path)
    rec = packet["residuals"][0]
    # MISSING_VERIFICATION maps to IV_REQUEST → always blocked pending verifier
    assert rec["required_action_type"] == res.IV_REQUEST
    assert rec["derived_execution_state"] == res.BLOCKED
    assert "VERIFIER" in ",".join(rec["blocking_reasons"])


def test_pr_closure_alone_cannot_resolve(tmp_path):
    events = [finding("evt-close")]
    packet = registry(events, nodes=[make_node("pr/806")], tmp_path=tmp_path)
    rec = packet["residuals"][0]
    ok, reasons = res.resolution_evidence_valid(rec, ["PR_CLOSED"])
    assert ok is False
    assert "PR_CLOSURE_ALONE_CANNOT_RESOLVE" in reasons


def test_stale_evidence_cannot_resolve(tmp_path):
    events = [finding("evt-stale")]
    packet = registry(events, nodes=[make_node("pr/807")], tmp_path=tmp_path)
    rec = packet["residuals"][0]
    ok, reasons = res.resolution_evidence_valid(
        rec, ["stale:old-run", "predecessor:ev-1"], current_head="a" * 40)
    assert ok is False
    assert any(r.startswith("STALE_EVIDENCE:") for r in reasons)


def test_exact_valid_evidence_can_resolve(tmp_path):
    events = [finding("evt-fix")]
    packet = registry(events, nodes=[make_node("pr/808")], tmp_path=tmp_path)
    rec = packet["residuals"][0]
    ok, reasons = res.resolution_evidence_valid(
        rec, [f"head:{'a'*40}", "fix-commit:deadbeef", "test:pass"])
    assert ok is True
    assert reasons == []
    # Apply resolution event
    events2 = [*events, {
        "schema": "ATLAS_EVENT_V1", "event_id": "evt-resolved-1",
        "timestamp_utc": "2026-09-08T13:00:00Z", "actor": "ubuntu-main",
        "role": "COORDINATOR", "session_id": "s", "lane": "pr/808", "pr": 808,
        "head": "a" * 40, "event": res.EVT_RESOLVED, "state": "RESOLVED",
        "residual_id": rec["residual_id"],
        "evidence": [f"head:{'a'*40}", "fix-commit:deadbeef"],
        "dependencies": [], "next_actions": [],
    }]
    resolved = registry(events2, nodes=[make_node("pr/808")], tmp_path=tmp_path)
    assert resolved["residuals"][0]["disposition"] == res.RESOLVED
    assert resolved["residuals"][0]["resolution_history"]


def test_accepted_risk_requires_owner(tmp_path):
    events = [finding("evt-risk", pr=809)]
    foreign = make_node("pr/809", owner="other-agent")
    packet = registry(events, nodes=[foreign], tmp_path=tmp_path)
    rec = packet["residuals"][0]
    profile = make_profile()
    ok, reasons = res.accepted_risk_authorized(profile, rec, "other-agent")
    assert ok is False
    assert any("REQUIRES_OWNER" in r for r in reasons)
    ok2, _ = res.accepted_risk_authorized(profile, rec, "ubuntu-main")
    assert ok2 is True


def test_duplicate_event_idempotent(tmp_path):
    ev = finding("evt-dup-1")
    events = [ev, dict(ev)]  # identical duplicate
    packet = registry(events, nodes=[make_node("pr/800")], tmp_path=tmp_path)
    assert packet["open_count"] == 1


def test_distinct_findings_not_accidentally_deduped(tmp_path):
    events = [
        finding("evt-a", note="auth defect"),
        finding("evt-b", note="cache defect"),
    ]
    packet = registry(events, nodes=[make_node("pr/800")], tmp_path=tmp_path)
    assert packet["open_count"] == 2
    ids = {r["residual_id"] for r in packet["residuals"]}
    assert len(ids) == 2


def test_resolved_history_preserved_on_reopen(tmp_path):
    rid_events = [finding("evt-hist")]
    packet = registry(rid_events, nodes=[make_node("pr/810")], tmp_path=tmp_path)
    rid = packet["residuals"][0]["residual_id"]
    events = [*rid_events, {
        "schema": "ATLAS_EVENT_V1", "event_id": "evt-res",
        "timestamp_utc": "2026-09-08T13:00:00Z", "actor": "ubuntu-main",
        "role": "COORDINATOR", "session_id": "s", "lane": "pr/810", "pr": 810,
        "head": "a" * 40, "event": res.EVT_RESOLVED, "state": "RESOLVED",
        "residual_id": rid, "evidence": ["fix:1"], "dependencies": [],
        "next_actions": [],
    }, {
        "schema": "ATLAS_EVENT_V1", "event_id": "evt-reopen",
        "timestamp_utc": "2026-09-08T14:00:00Z", "actor": "ubuntu-main",
        "role": "COORDINATOR", "session_id": "s", "lane": "pr/810", "pr": 810,
        "head": "a" * 40, "event": res.EVT_REOPENED, "state": "REOPENED",
        "residual_id": rid, "evidence": ["invalidated:fix:1"],
        "dependencies": [], "next_actions": [],
    }]
    reopened = registry(events, nodes=[make_node("pr/810")], tmp_path=tmp_path)
    rec = reopened["residuals"][0]
    assert rec["disposition"] == res.OPEN
    assert len(rec["resolution_history"]) >= 2
    assert any(h.get("event") == res.EVT_RESOLVED for h in rec["resolution_history"])


def test_iv_substring_in_negative_does_not_force_verification():
    """'IV' inside 'Negative' or 'CI/IV/freeze' must not force MISSING_VERIFICATION."""
    assert res._finding_type({"note": "Negative-control tests included"}) == res.DEFECT
    assert res._finding_type({
        "note": "CI/IV/freeze/claim events keep head binding"}) == res.DEFECT
    assert res._finding_type({"note": "missing IV verification"}) == res.MISSING_VERIFICATION
    assert res._finding_type({"note": "independent verifier receipt required"}) == (
        res.MISSING_VERIFICATION)
    assert res._finding_type({"note": "awaiting IV on pr/723"}) == res.MISSING_VERIFICATION


def test_malformed_provenance_fails_closed():
    with pytest.raises(res.ResidualError, match="UNKNOWN_RESIDUAL_TYPE"):
        res._base_residual(
            residual_id="res-abcdef12", repository=REPO,
            residual_type="NOT_A_TYPE", description="x",
            required_action_type=res.REMEDIATE, source_kind="test")
    with pytest.raises(res.ResidualError, match="UNKNOWN_ACTION_TYPE"):
        res._base_residual(
            residual_id="res-ok12345", repository=REPO,
            residual_type=res.DEFECT, description="x",
            required_action_type="NOT_AN_ACTION", source_kind="test")
    errors = res.validate_residual(res._base_residual(
        residual_id="bad-id", repository=REPO, residual_type=res.DEFECT,
        description="x", required_action_type=res.REMEDIATE, source_kind="test"))
    assert errors  # schema rejects malformed residual_id


def test_residual_appears_in_f12_with_correct_type(tmp_path):
    events = [finding("evt-f12", note="security hardening needed")]
    node = make_node("pr/811", state="RUNNABLE_WRITE")
    agent_reg = write_registry(tmp_path, [make_profile()])
    packet = registry(events, nodes=[node], agent_registry=agent_reg)
    matrix = fm.build_frontier_matrix(
        snapshot_of(node), agent_id="ubuntu-main", registry=agent_reg,
        residual_registry=packet, weights=weights(), clock=clock)
    residual_actions = [a for a in matrix["actions"] if a.get("residual_id")]
    assert residual_actions
    assert residual_actions[0]["action_type"] == res.REMEDIATE
    assert residual_actions[0]["runnable_state"] == fm.RUNNABLE


def test_score_cannot_turn_blocked_residual_runnable(tmp_path):
    events = [finding("evt-score", pr=812, note="SECURITY P0")]
    node = make_node("pr/812", frozen=True, state="FROZEN", priority_class="P0",
                     owner="other")
    agent_reg = write_registry(tmp_path, [make_profile()])
    packet = registry(events, nodes=[node], agent_registry=agent_reg)
    matrix = fm.build_frontier_matrix(
        snapshot_of(node), agent_id="ubuntu-main", registry=agent_reg,
        residual_registry=packet, weights=weights(), clock=clock)
    for action in matrix["actions"]:
        if action.get("residual_id"):
            assert action["runnable_state"] == fm.BLOCKED
            assert action["action_id"] not in matrix["eligible_actions"]


def test_determinism_same_history(tmp_path):
    events = [
        finding("evt-d1", note="a"),
        finding("evt-d2", note="b"),
    ]
    # Permute event order — replay sorts by timestamp/id
    p1 = registry(events, nodes=[make_node("pr/800")], tmp_path=tmp_path)
    p2 = registry(list(reversed(events)), nodes=[make_node("pr/800")],
                  tmp_path=tmp_path)
    assert p1["registry_fingerprint"] == p2["registry_fingerprint"]


def test_postmerge_seal_projects_residual(tmp_path):
    seal = {900: {
        "seal_state": "NOT_READY",
        "required_actions": ["VALIDATE_CURRENT_MAIN_COMPATIBILITY",
                             "RECONCILE_STACK_CHILD:pr/901"],
    }}
    packet = registry(
        [], nodes=[make_node("pr/900", state="MERGED_UNSEALED", merged=True,
                             ownership="UNOWNED", owner=None, claimants=[])],
        seal_by_pr=seal, tmp_path=tmp_path)
    types = {r["residual_type"] for r in packet["residuals"]}
    assert res.COMPATIBILITY in types or res.POSTMERGE_FOLLOWUP in types
    assert packet["open_count"] >= 1


def test_await_merge_placeholder_not_projected_as_residual(tmp_path):
    seal = {901: {
        "seal_state": "NOT_READY",
        "required_actions": ["AWAIT_MERGE_DECISION"],
    }}
    packet = registry(
        [], nodes=[make_node("pr/901")], seal_by_pr=seal, tmp_path=tmp_path)
    assert packet["open_count"] == 0


def test_schema_validation(tmp_path):
    packet = registry([finding("evt-schema")], nodes=[make_node("pr/800")],
                      tmp_path=tmp_path)
    assert res.validate_registry(packet) == []


def test_cli_registers_residual_commands():
    from atlas_dag.cli import COMMANDS, build_parser
    for name in ("residuals", "residual", "residual-register",
                 "residual-resolve", "residual-frontier"):
        assert name in COMMANDS
    parser = build_parser()
    args = parser.parse_args(["residuals", "--state", "OPEN"])
    assert args.state == "OPEN"
