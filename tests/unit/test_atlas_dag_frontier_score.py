"""Adversarial tests for FEATURE_10: DETERMINISTIC_FRONTIER_PRIORITIZATION.

PRIORITY != AUTHORITY. Authorization runs before scoring. Every denial has a
load-bearing positive control.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import router as router_mod  # noqa: E402
from atlas_dag import score as score_mod  # noqa: E402
from atlas_dag import stack as stack_mod  # noqa: E402
from test_atlas_dag_router import make_node, make_profile, snapshot_of, write_registry  # noqa: E402

FIXED = "2026-09-08T12:00:00Z"


def clock():
    return FIXED


def weights(**overrides) -> dict:
    cfg = copy.deepcopy(score_mod.SAFE_DEFAULT_WEIGHTS)
    for key, value in overrides.items():
        if key in cfg["weights"]:
            cfg["weights"][key] = value
        else:
            cfg[key] = value
    return cfg


def stack_rec(lane: str, **overrides) -> dict:
    number = int(lane.split("/")[1])
    rec = {
        "lane": lane,
        "pr": number,
        "stack_state": stack_mod.ROOT,
        "stack_root": lane,
        "parent_pr": None,
        "children": [],
        "depth": 0,
        "target_branch": "main",
        "parent_head": None,
        "child_head": "a" * 40,
        "parent_ancestor_of_child": None,
        "restack_required": False,
        "reasons": [],
    }
    rec.update(overrides)
    return rec


def rank(nodes, agent="ubuntu-main", stacks=None, w=None, registry=None,
         tmp_path=None):
    if registry is None:
        assert tmp_path is not None
        registry = write_registry(tmp_path, [make_profile()])
    packet = score_mod.rank_frontier(
        snapshot_of(*nodes), agent_id=agent, registry=registry,
        stacks=stacks or {}, weights=w or weights(), weights_source="test",
        clock=clock)
    assert score_mod.validate_score(packet) == []
    return packet


def test_schema_and_safe_default_weights():
    assert score_mod.validate_weights(score_mod.SAFE_DEFAULT_WEIGHTS) == []
    loaded, source = score_mod.load_weights(Path("/tmp/absent-frontier-weights.json"))
    assert source.startswith("safe_default")
    assert loaded["weights_id"] == "atlas-frontier-weights-safe-default"


def test_malformed_weights_fail_closed_to_safe_default(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    loaded, source = score_mod.load_weights(bad)
    assert source.startswith("safe_default")
    assert loaded["schema"] == score_mod.WEIGHTS_CONST


def test_authorization_before_scoring_frozen_stays_blocked(tmp_path):
    frozen = make_node("pr/10", state="FROZEN", frozen=True, priority_class="P0")
    writable = make_node("pr/11", priority_class="P3")
    packet = rank([frozen, writable], tmp_path=tmp_path)
    write_ranked = [e for e in packet["ranked"] if e["action_class"] == "RUNNABLE_WRITE"]
    assert all(e["pr"] != 10 for e in write_ranked)
    frozen_entry = next(e for e in packet["ranked"] + packet["blocked"] if e["pr"] == 10)
    assert frozen_entry["action_class"] != "RUNNABLE_WRITE"
    assert "LANE_FROZEN_BY_REPOSITORY_TRUTH" in frozen_entry["authorization"]["blockers"]
    # Positive control: unfreeze => write frontier leader.
    thawed = make_node("pr/10", priority_class="P0")
    packet2 = rank([thawed, writable], tmp_path=tmp_path)
    assert packet2["ranked"][0]["pr"] == 10
    assert packet2["ranked"][0]["action_class"] == "RUNNABLE_WRITE"

def test_foreign_owned_high_score_stays_blocked(tmp_path):
    foreign = make_node("pr/20", owner="other-agent", priority_class="P0")
    own = make_node("pr/21", priority_class="P2")
    packet = rank([foreign, own], tmp_path=tmp_path)
    assert all(e["pr"] != 20 or e["action_class"] != "RUNNABLE_WRITE"
               for e in packet["ranked"])
    write_lanes = [e for e in packet["ranked"] if e["action_class"] == "RUNNABLE_WRITE"]
    assert write_lanes and write_lanes[0]["pr"] == 21
    # Positive: claim foreign lane => write.
    claimed = make_node("pr/20", priority_class="P0")
    assert rank([claimed, own], tmp_path=tmp_path)["ranked"][0]["pr"] == 20


def test_inactive_agent_gets_empty_ranked(tmp_path):
    registry = write_registry(
        tmp_path, [make_profile(agent_id="windows-main", active=False,
                                platforms=["windows"])])
    packet = rank([make_node("pr/30")], agent="windows-main", registry=registry)
    assert packet["ranked"] == []
    assert packet["agent_status"] == "REGISTERED_INACTIVE"


def test_capability_mismatch_no_write(tmp_path):
    registry = write_registry(tmp_path, [make_profile(
        capabilities=["READ_REPO", "READ_GITHUB"])])
    node = make_node("pr/31", priority_class="P0")
    packet = rank([node], registry=registry, tmp_path=tmp_path)
    assert packet["ranked"]
    assert packet["ranked"][0]["action_class"] == "RUNNABLE_READONLY"
    assert "NO_WRITE_CAPABILITY" in packet["ranked"][0]["authorization"]["blockers"]


def test_restack_required_child_not_writable(tmp_path):
    child = make_node("pr/41", priority_class="P0")
    stacks = {"pr/41": stack_rec(
        "pr/41", depth=1, parent_pr=40, stack_state=stack_mod.RESTACK_REQUIRED,
        restack_required=True, children=[])}
    packet = rank([child], stacks=stacks, tmp_path=tmp_path)
    assert packet["ranked"][0]["action_class"] == "RUNNABLE_READONLY"
    assert any("STACK_NOT_CURRENT" in b
               for b in packet["ranked"][0]["authorization"]["blockers"])
    # Positive: current stack => write.
    stacks2 = {"pr/41": stack_rec("pr/41", depth=1, parent_pr=40,
                                  stack_state=stack_mod.STACK_CURRENT)}
    assert rank([child], stacks=stacks2, tmp_path=tmp_path)["ranked"][0][
        "action_class"] == "RUNNABLE_WRITE"


def test_p0_outranks_cosmetic_when_equally_runnable(tmp_path):
    cosmetic = make_node("pr/50", priority_class="COSMETIC")
    p0 = make_node("pr/51", priority_class="P0")
    packet = rank([cosmetic, p0], tmp_path=tmp_path)
    assert [e["pr"] for e in packet["ranked"]] == [51, 50]


def test_blocker_with_downstream_outranks_isolated(tmp_path):
    isolated = make_node("pr/60", priority_class="P1")
    blocker = make_node("pr/61", priority_class="P1")
    stacks = {
        "pr/60": stack_rec("pr/60"),
        "pr/61": stack_rec("pr/61", children=["pr/62", "pr/63", "pr/64"]),
    }
    packet = rank([isolated, blocker], stacks=stacks, tmp_path=tmp_path)
    assert packet["ranked"][0]["pr"] == 61
    assert packet["ranked"][0]["factors"]["blocker_value"]["raw"] > \
        packet["ranked"][1]["factors"]["blocker_value"]["raw"]


def test_starvation_within_safe_bounds(tmp_path):
    young = make_node("pr/70", priority_class="P1",
                      opened_at_utc="2026-09-08T11:00:00Z")
    old = make_node("pr/71", priority_class="P1",
                    opened_at_utc="2026-08-01T00:00:00Z")
    packet = rank([young, old], tmp_path=tmp_path)
    assert packet["ranked"][0]["pr"] == 71
    assert packet["ranked"][0]["factors"]["starvation"]["raw"] <= \
        score_mod.SAFE_DEFAULT_WEIGHTS["caps"]["starvation_max_raw"]


def test_risk_penalty_reduces_total(tmp_path):
    clean = make_node("pr/80", priority_class="P1", tree="b" * 40)
    risky = make_node("pr/81", priority_class="P1", tree=None,
                      ci_status="FAILURE", uncertainty=["X"])
    packet = rank([clean, risky], tmp_path=tmp_path)
    by_pr = {e["pr"]: e for e in packet["ranked"]}
    assert by_pr[81]["factors"]["risk_penalty"]["weighted"] < 0
    assert by_pr[81]["total"] < by_pr[80]["total"]


def test_weight_change_changes_ranking(tmp_path):
    a = make_node("pr/90", priority_class="P1")
    b = make_node("pr/91", priority_class="P1")
    stacks = {"pr/90": stack_rec("pr/90"),
              "pr/91": stack_rec("pr/91", children=["pr/92"] * 8)}
    # Equal severity: downstream blocker wins.
    base = rank([a, b], stacks=stacks, tmp_path=tmp_path)
    assert base["ranked"][0]["pr"] == 91
    # Severity weight dominates blocker_value.
    skewed = weights(severity=500.0, blocker_value=1.0)
    a_p0 = make_node("pr/90", priority_class="P0")
    b_p2 = make_node("pr/91", priority_class="P2")
    alt = rank([a_p0, b_p2], stacks=stacks, w=skewed, tmp_path=tmp_path)
    assert alt["ranked"][0]["pr"] == 90


def test_deterministic_same_snapshot_byte_identical(tmp_path):
    nodes = [make_node("pr/100", priority_class="P1"),
             make_node("pr/101", priority_class="P0")]
    a = rank(nodes, tmp_path=tmp_path)
    b = rank(nodes, tmp_path=tmp_path)
    assert a["ranking_fingerprint"] == b["ranking_fingerprint"]
    assert json.dumps(a["ranked"], sort_keys=True) == \
        json.dumps(b["ranked"], sort_keys=True)


def test_source_order_permutation_same_ranking(tmp_path):
    nodes = [make_node("pr/110", priority_class="P2"),
             make_node("pr/111", priority_class="P0"),
             make_node("pr/112", priority_class="P1")]
    a = rank(nodes, tmp_path=tmp_path)
    b = rank(list(reversed(nodes)), tmp_path=tmp_path)
    assert [e["pr"] for e in a["ranked"]] == [e["pr"] for e in b["ranked"]]
    assert a["ranking_fingerprint"] == b["ranking_fingerprint"]


def test_ties_resolve_deterministically_by_pr(tmp_path):
    # Identical material except PR number.
    a = make_node("pr/200", priority_class="P1")
    b = make_node("pr/201", priority_class="P1")
    packet = rank([b, a], tmp_path=tmp_path)
    assert [e["pr"] for e in packet["ranked"]] == [200, 201]


def test_blocked_enormous_nominal_never_executable(tmp_path):
    frozen = make_node("pr/300", state="FROZEN", frozen=True,
                       priority_class="P0", ownership="OWNED")
    stacks = {"pr/300": stack_rec("pr/300", children=[f"pr/{i}" for i in range(400, 408)])}
    ok = make_node("pr/301", priority_class="P3")
    packet = rank([frozen, ok], stacks=stacks, tmp_path=tmp_path)
    write_ranked = [e for e in packet["ranked"] if e["action_class"] == "RUNNABLE_WRITE"]
    assert write_ranked and write_ranked[0]["pr"] == 301
    frozen_entry = next(e for e in packet["ranked"] + packet["blocked"] if e["pr"] == 300)
    assert frozen_entry["action_class"] != "RUNNABLE_WRITE"
    assert frozen_entry["factors"]["severity"]["raw"] == 1.0


def test_readonly_never_promotes_to_write(tmp_path):
    node = make_node("pr/310", state="RUNNABLE_READONLY", ownership="UNOWNED",
                     owner=None, priority_class="P0")
    packet = rank([node], tmp_path=tmp_path)
    assert packet["ranked"][0]["action_class"] == "RUNNABLE_READONLY"
    assert packet["ranked"][0]["executable"] is True


def test_router_uses_scoring_order(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    low = make_node("pr/400", priority_class="P3")
    high = make_node("pr/401", priority_class="P0")
    # Snapshot order puts low first; scoring must prefer high.
    snap = snapshot_of(low, high)
    result = router_mod.route("ubuntu-main", snap, registry, stacks={},
                              weights=weights(), weights_source="test")
    assert result["routable"]
    assert result["lane"] == "pr/401"
    assert result["priority"]["top"][0]["lane"] == "pr/401"


def test_explain_priority_exposes_all_factors(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    node = make_node("pr/500", priority_class="P1")
    explained = score_mod.explain_priority(
        snapshot_of(node), 500, agent_id="ubuntu-main", registry=registry,
        stacks={}, weights=weights(), weights_source="test", clock=clock)
    assert explained["found"]
    assert set(explained["entry"]["factors"]) == set(score_mod.FACTOR_NAMES)


def test_cli_frontier_score_explain_registered():
    from atlas_dag.cli import build_parser
    parser = build_parser()
    assert parser.parse_args(["frontier", "--agent", "ubuntu-main", "--json"]).agent
    assert parser.parse_args(["score", "--pr", "10", "--agent", "ubuntu-main"]).pr == 10
    assert parser.parse_args(["explain-priority", "--pr", "10"]).pr == 10
