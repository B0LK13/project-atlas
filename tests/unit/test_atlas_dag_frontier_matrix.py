"""Adversarial tests for FEATURE_12: MULTIDIMENSIONAL_RUNNABLE_FRONTIER.

FRONTIER != SINGLE_QUEUE. ACTION_RANK != ACTION_AUTHORITY.
Every denial has a load-bearing positive control.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import dispatch as dispatch_mod  # noqa: E402
from atlas_dag import frontier_matrix as fm  # noqa: E402
from atlas_dag import stack as stack_mod  # noqa: E402
from atlas_dag import steal as steal_mod  # noqa: E402
from test_atlas_dag_frontier_score import stack_rec, weights  # noqa: E402
from test_atlas_dag_router import make_node, make_profile, snapshot_of, write_registry  # noqa: E402

FIXED = "2026-09-08T12:00:00Z"


def clock():
    return FIXED


def matrix(nodes, agent="ubuntu-main", stacks=None, registry=None, tmp_path=None,
           dispatch_by_pr=None, seal_by_pr=None, extra_nodes=None, w=None):
    if registry is None:
        assert tmp_path is not None
        registry = write_registry(tmp_path, [make_profile()])
    return fm.build_frontier_matrix(
        snapshot_of(*nodes), agent_id=agent, registry=registry,
        stacks=stacks or {}, weights=w or weights(), weights_source="test",
        dispatch_by_pr=dispatch_by_pr or {}, seal_by_pr=seal_by_pr or {},
        extra_nodes=extra_nodes, clock=clock)


def by_id(packet, aid):
    return next(a for a in packet["actions"] if a["action_id"] == aid)


def test_ci_runnable_iv_blocked_same_lane(tmp_path):
    frozen = make_node("pr/900", frozen=True, state="FROZEN", ownership="OWNED")
    dispatch = {
        900: {
            "ci": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
            "iv": {"lane_state": dispatch_mod.BLOCKED,
                   "reasons": [dispatch_mod.VERIFIER_IDENTITY_UNBOUND]},
        }
    }
    packet = matrix([frozen], tmp_path=tmp_path, dispatch_by_pr=dispatch)
    assert by_id(packet, "pr/900:CI_DISPATCH")["runnable_state"] == fm.RUNNABLE
    assert by_id(packet, "pr/900:IV_REQUEST")["runnable_state"] == fm.BLOCKED
    assert dispatch_mod.VERIFIER_IDENTITY_UNBOUND in by_id(
        packet, "pr/900:IV_REQUEST")["blocking_reasons"]
    # Positive control: bind verifier → IV RUNNABLE
    dispatch[900]["iv"] = {"lane_state": dispatch_mod.RUNNABLE, "reasons": []}
    ok = matrix([frozen], tmp_path=tmp_path, dispatch_by_pr=dispatch)
    assert by_id(ok, "pr/900:IV_REQUEST")["runnable_state"] == fm.RUNNABLE


def test_frozen_cannot_expose_implement_runnable(tmp_path):
    frozen = make_node("pr/901", frozen=True, state="FROZEN")
    free = make_node("pr/902", state="RUNNABLE_WRITE")
    packet = matrix([frozen, free], tmp_path=tmp_path)
    assert by_id(packet, "pr/901:IMPLEMENT")["runnable_state"] == fm.BLOCKED
    assert "LANE_FROZEN_BY_REPOSITORY_TRUTH" in by_id(
        packet, "pr/901:IMPLEMENT")["blocking_reasons"]
    assert by_id(packet, "pr/902:IMPLEMENT")["runnable_state"] == fm.RUNNABLE


def test_foreign_ownership_blocks_write_not_readonly(tmp_path):
    foreign = make_node("pr/903", owner="other-agent", priority_class="P0")
    packet = matrix([foreign], tmp_path=tmp_path)
    assert by_id(packet, "pr/903:IMPLEMENT")["runnable_state"] == fm.BLOCKED
    assert by_id(packet, "pr/903:OWNERSHIP_CLAIM")["runnable_state"] == fm.BLOCKED
    assert by_id(packet, "pr/903:READONLY_ANALYZE")["runnable_state"] == fm.RUNNABLE


def test_inactive_agent_no_executable_actions(tmp_path):
    registry = write_registry(
        tmp_path, [make_profile(agent_id="windows-main", active=False,
                                platforms=["windows"])])
    node = make_node("pr/904")
    packet = matrix([node], agent="windows-main", registry=registry)
    assert packet["agent_status"] == "REGISTERED_INACTIVE"
    assert packet["eligible_actions"] == []
    assert all(
        by_id(packet, aid)["runnable_state"] in (
            fm.INELIGIBLE, fm.NOT_APPLICABLE, fm.BLOCKED)
        or not by_id(packet, aid).get("agent_eligible")
        for aid in [a["action_id"] for a in packet["actions"]]
    )


def test_capability_platform_mismatch_ineligible(tmp_path):
    registry = write_registry(tmp_path, [make_profile(
        capabilities=["READ_REPO", "READ_GITHUB"], platforms=["linux"])])
    node = make_node("pr/905", platform_requirements=["windows"])
    packet = matrix([node], registry=registry, tmp_path=tmp_path)
    impl = by_id(packet, "pr/905:IMPLEMENT")
    assert impl["runnable_state"] in (fm.BLOCKED, fm.INELIGIBLE)
    assert by_id(packet, "pr/905:READONLY_ANALYZE")["runnable_state"] == fm.RUNNABLE


def test_merged_lane_exposes_postmerge_not_implement(tmp_path):
    merged = make_node("pr/906", state="MERGED_UNSEALED", ownership="UNOWNED",
                       owner=None, claimants=[], merged=True)
    seal = {906: {"seal_state": "NOT_READY",
                  "required_actions": ["VALIDATE_CURRENT_MAIN_COMPATIBILITY",
                                       "RECONCILE_STACK_CHILD:pr/907"]}}
    packet = matrix([merged], tmp_path=tmp_path, seal_by_pr=seal)
    assert by_id(packet, "pr/906:IMPLEMENT")["runnable_state"] == fm.NOT_APPLICABLE
    assert by_id(packet, "pr/906:POSTMERGE_VALIDATE")["runnable_state"] == fm.RUNNABLE
    assert by_id(packet, "pr/906:POSTMERGE_RECONCILE")["runnable_state"] == fm.RUNNABLE


def test_sealed_lane_no_false_executable_closure(tmp_path):
    sealed = make_node("pr/908", state="MERGED_UNSEALED", merged=True,
                       seal_state="SEALED", ownership="UNOWNED", owner=None,
                       claimants=[])
    seal = {908: {"seal_state": "SEALED", "sealed": True, "required_actions": []}}
    packet = matrix([sealed], tmp_path=tmp_path, seal_by_pr=seal)
    assert by_id(packet, "pr/908:POSTMERGE_VALIDATE")["runnable_state"] == fm.NOT_APPLICABLE
    assert by_id(packet, "pr/908:POSTMERGE_RECONCILE")["runnable_state"] == fm.NOT_APPLICABLE
    assert "pr/908:POSTMERGE_VALIDATE" not in packet["eligible_actions"]


def test_restack_child_cannot_expose_write(tmp_path):
    child = make_node("pr/909", state="RUNNABLE_WRITE")
    stacks = {"pr/909": stack_rec(
        "pr/909", depth=1, parent_pr=908, stack_state=stack_mod.RESTACK_REQUIRED,
        restack_required=True)}
    packet = matrix([child], stacks=stacks, tmp_path=tmp_path)
    assert by_id(packet, "pr/909:IMPLEMENT")["runnable_state"] == fm.BLOCKED
    stacks_ok = {"pr/909": stack_rec(
        "pr/909", depth=1, parent_pr=908, stack_state=stack_mod.STACK_CURRENT)}
    ok = matrix([child], stacks=stacks_ok, tmp_path=tmp_path)
    assert by_id(ok, "pr/909:IMPLEMENT")["runnable_state"] == fm.RUNNABLE


def test_predecessor_evidence_does_not_satisfy_validation(tmp_path):
    frozen = make_node("pr/910", frozen=True, state="FROZEN")
    dispatch = {
        910: {
            "ci": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
            "iv": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
            "evidence": {"predecessor_only": ["ev-old"], "current_exact_head_complete": False},
        }
    }
    packet = matrix([frozen], tmp_path=tmp_path, dispatch_by_pr=dispatch)
    ci = by_id(packet, "pr/910:CI_DISPATCH")
    assert ci["runnable_state"] == fm.RUNNABLE
    assert ci["evidence_state"] == "PREDECESSOR_ONLY"
    assert ci["expected_downstream_unblock"] == "EXACT_HEAD_EVIDENCE"


def test_verifier_gate_blocks_iv_only_not_ci(tmp_path):
    frozen = make_node("pr/911", frozen=True, state="FROZEN")
    dispatch = {
        911: {
            "ci": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
            "iv": {"lane_state": dispatch_mod.BLOCKED,
                   "reasons": [dispatch_mod.VERIFIER_IDENTITY_UNBOUND]},
        }
    }
    packet = matrix([frozen], tmp_path=tmp_path, dispatch_by_pr=dispatch)
    assert by_id(packet, "pr/911:CI_DISPATCH")["runnable_state"] == fm.RUNNABLE
    assert by_id(packet, "pr/911:IV_REQUEST")["runnable_state"] == fm.BLOCKED


def test_owner_gate_blocks_only_owner_dependent(tmp_path):
    foreign = make_node("pr/912", owner="other-agent", frozen=True, state="FROZEN",
                        waiting_on=["OWNER", "HUMAN"])
    dispatch = {
        912: {
            "ci": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
            "iv": {"lane_state": dispatch_mod.BLOCKED,
                   "reasons": [dispatch_mod.VERIFIER_IDENTITY_UNBOUND]},
        }
    }
    packet = matrix([foreign], tmp_path=tmp_path, dispatch_by_pr=dispatch)
    assert by_id(packet, "pr/912:OWNER_DECISION")["runnable_state"] == fm.BLOCKED
    assert by_id(packet, "pr/912:READONLY_ANALYZE")["runnable_state"] == fm.RUNNABLE
    assert by_id(packet, "pr/912:CI_DISPATCH")["runnable_state"] == fm.RUNNABLE


def test_priority_never_converts_blocked_to_runnable(tmp_path):
    blocked = make_node("pr/913", frozen=True, state="FROZEN", priority_class="P0")
    free = make_node("pr/914", priority_class="P3")
    packet = matrix([blocked, free], tmp_path=tmp_path)
    assert by_id(packet, "pr/913:IMPLEMENT")["runnable_state"] == fm.BLOCKED
    # Score may exist on other actions but IMPLEMENT stays blocked.
    rankings = packet["typed_rankings"]["best_write"]
    assert "pr/913:IMPLEMENT" not in rankings
    assert "pr/914:IMPLEMENT" in rankings


def test_malformed_unknown_action_fails_closed():
    err = fm.explain_action({"actions": []}, "not-an-id")
    assert err["found"] is False
    assert "MALFORMED" in err["reason"] or "UNKNOWN" in err["reason"]
    err2 = fm.explain_action({"actions": []}, "pr/1:NOT_A_REAL_TYPE")
    assert err2["found"] is False
    assert "UNKNOWN_ACTION_TYPE" in err2["reason"]


def test_determinism_and_source_order_permutation(tmp_path):
    a = make_node("pr/920", priority_class="P1")
    b = make_node("pr/921", priority_class="P0")
    c = make_node("pr/922", frozen=True, state="FROZEN")
    p1 = matrix([a, b, c], tmp_path=tmp_path)
    p2 = matrix([c, a, b], tmp_path=tmp_path)
    assert p1["frontier_fingerprint"] == p2["frontier_fingerprint"]
    assert [x["action_id"] for x in p1["actions"]] == [
        x["action_id"] for x in p2["actions"]]


def test_schema_validation_passes(tmp_path):
    packet = matrix([make_node("pr/930")], tmp_path=tmp_path)
    errors = fm.validate_matrix(packet)
    assert errors == []


def test_steal_uses_canonical_write_projection(tmp_path):
    unowned = make_node("pr/940", state="RUNNABLE_READONLY", ownership="UNOWNED",
                        owner=None, claimants=[], priority_class="P0")
    foreign = make_node("pr/941", owner="other", priority_class="P0")
    registry = write_registry(tmp_path, [make_profile()])
    plan = steal_mod.plan_steal(
        snapshot_of(unowned, foreign), "ubuntu-main", registry, stacks={},
        weights=weights(), weights_source="test", clock=clock)
    assert plan["candidate"]["pr"] == 940
    assert plan["candidate"]["action_class_after_claim"] == "RUNNABLE_WRITE"
    assert "multidim_frontier_fingerprint" in plan


def test_dispatch_validation_projection(tmp_path):
    frozen = make_node("pr/950", frozen=True, state="FROZEN")
    dispatch = {
        950: {
            "ci": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
            "iv": {"lane_state": dispatch_mod.BLOCKED,
                   "reasons": [dispatch_mod.VERIFIER_IDENTITY_UNBOUND]},
        }
    }
    packet = matrix([frozen], tmp_path=tmp_path, dispatch_by_pr=dispatch)
    proj = fm.validation_dispatch_projection(packet)
    types = {a["action_type"]: a["runnable_state"] for a in proj}
    assert types[fm.CI_DISPATCH] == fm.RUNNABLE
    assert types[fm.IV_REQUEST] == fm.BLOCKED


def test_parallel_actions_independent(tmp_path):
    frozen = make_node("pr/960", frozen=True, state="FROZEN")
    other = make_node("pr/961", owner="other-agent")
    dispatch = {
        960: {
            "ci": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
            "iv": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
        }
    }
    packet = matrix([frozen, other], tmp_path=tmp_path, dispatch_by_pr=dispatch)
    parallel = packet["parallel_runnable_set"]
    assert any(
        "pr/960:CI_DISPATCH" in group and "pr/960:IV_REQUEST" in group
        for group in parallel
    )
    # Readonly on foreign-owned lane remains runnable despite owner gate elsewhere.
    assert by_id(packet, "pr/961:READONLY_ANALYZE")["runnable_state"] == fm.RUNNABLE


def test_typed_rankings_do_not_cross_compare_classes(tmp_path):
    write = make_node("pr/970", priority_class="P3")
    frozen = make_node("pr/971", frozen=True, state="FROZEN", priority_class="P0")
    dispatch = {
        971: {
            "ci": {"lane_state": dispatch_mod.RUNNABLE, "reasons": []},
            "iv": {"lane_state": dispatch_mod.BLOCKED,
                   "reasons": [dispatch_mod.VERIFIER_IDENTITY_UNBOUND]},
        }
    }
    packet = matrix([write, frozen], tmp_path=tmp_path, dispatch_by_pr=dispatch)
    best_write = packet["typed_rankings"]["best_write"]
    best_val = packet["typed_rankings"]["best_validation"]
    assert all(":IMPLEMENT" in a or ":OWNERSHIP_CLAIM" in a or ":REMEDIATE" in a
               for a in best_write)
    assert all(":CI_DISPATCH" in a or ":IV_REQUEST" in a or ":POSTMERGE" in a
               for a in best_val)


def test_compat_frontier_derives_from_matrix(tmp_path):
    node = make_node("pr/980")
    packet = matrix([node], tmp_path=tmp_path)
    compat = fm.score_compat_projection(packet, snapshot_of(node))
    assert compat["schema"] == "ATLAS_FRONTIER_SCORE_V1"
    assert compat["provenance"]["derived_from"] == fm.SCHEMA_CONST
    assert any(e["pr"] == 980 for e in compat["ranked"])


def test_cli_registers_frontier_matrix_commands():
    from atlas_dag.cli import COMMANDS, build_parser
    for name in ("frontier-matrix", "frontier-actions", "explain-action"):
        assert name in COMMANDS
    parser = build_parser()
    args = parser.parse_args(["explain-action", "--action-id", "pr/1:IMPLEMENT"])
    assert args.action_id == "pr/1:IMPLEMENT"
