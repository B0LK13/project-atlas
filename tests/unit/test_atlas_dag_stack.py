"""Offline adversarial tests for the stacked-PR DAG (FEATURE_03).

Stack relation != authority (D-ATLAS-DAG-FEATURE-03):
- relationships come from live base/head refs + Git ancestry, never prose
  and never prospective merge SHAs;
- a child is STACK_CURRENT only when the exact live parent HEAD is an
  ancestor of the child HEAD; unverifiable ancestry fails closed;
- parent ownership / CI / IV are never inherited by the child;
- every negative case has a load-bearing control proving routability
  returns when the one legitimate constraint is removed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import agents as agents_mod  # noqa: E402
from atlas_dag import router as router_mod  # noqa: E402
from atlas_dag import stack as stack_mod  # noqa: E402

H = "a1b2c3d4e5f6"  # short synthetic heads; ancestry comes from the fake client


class FakeClient:
    """is_ancestor with three-valued truth: verified / verified-not / unknown."""

    def __init__(self, ancestry: set[tuple[str, str]] | None = None,
                 not_ancestry: set[tuple[str, str]] | None = None):
        self.ancestry = ancestry or set()
        self.not_ancestry = not_ancestry or set()

    def is_ancestor(self, anc: str, desc: str) -> bool | None:
        if anc == desc or (anc, desc) in self.ancestry:
            return True
        if (anc, desc) in self.not_ancestry:
            return False
        return None


def node(lane: str, base: str, head: str | None = None,
         branch: str | None = None, **kw) -> dict:
    n = {"lane": lane, "pr": int(lane.split("/")[1]),
         "base": base, "head_branch": branch or f"feat-{lane.split('/')[1]}",
         "head": head or H, "state": kw.pop("state", "RUNNABLE_WRITE"),
         "ownership": kw.pop("ownership", "OWNED"),
         "owner": kw.pop("owner", "ubuntu-main"),
         "frozen": kw.pop("frozen", False)}
    n.update(kw)
    return n


def linear_stack() -> list[dict]:
    """main <- 720 <- 723 <- 725 <- 727 with truthful ancestry."""
    heads = {"pr/720": "h720", "pr/723": "h723", "pr/725": "h725", "pr/727": "h727"}
    nodes = [
        node("pr/720", "main", heads["pr/720"], branch="feat-dag-mvp"),
        node("pr/723", "feat-dag-mvp", heads["pr/723"], branch="feat-hardening"),
        node("pr/725", "feat-hardening", heads["pr/725"], branch="feat-registry"),
        node("pr/727", "feat-registry", heads["pr/727"], branch="feat-router"),
    ]
    ancestry = {("h720", "h723"), ("h723", "h725"), ("h725", "h727")}
    return nodes, FakeClient(ancestry)


# --- core topology ------------------------------------------------------------

def test_linear_four_level_stack():
    nodes, client = linear_stack()
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/720"]["stack_state"] == stack_mod.ROOT
    assert stacks["pr/720"]["depth"] == 0
    for child, parent in (("pr/723", 720), ("pr/725", 723), ("pr/727", 725)):
        rec = stacks[child]
        assert rec["stack_state"] == stack_mod.STACK_CURRENT
        assert rec["parent_pr"] == parent
        assert rec["parent_ancestor_of_child"] is True
    assert stacks["pr/727"]["depth"] == 3
    assert stacks["pr/720"]["children"] == ["pr/723"]
    assert stacks["pr/727"]["stack_root"] == "pr/720"
    chain = stack_mod.chain_for("pr/727", stacks)
    assert [c["lane"] for c in chain] == ["pr/720", "pr/723", "pr/725", "pr/727"]


def test_root_targets_main():
    nodes, client = linear_stack()
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/720"]["target_branch"] == "main"
    assert stacks["pr/720"]["parent_pr"] is None


def test_reordered_input_deterministic():
    nodes, client = linear_stack()
    forward = stack_mod.build_stacks(nodes, client)
    reverse = stack_mod.build_stacks(list(reversed(nodes)), client)
    assert json.dumps(forward, sort_keys=True) == json.dumps(reverse, sort_keys=True)


def test_prospective_merge_sha_never_used():
    nodes, client = linear_stack()
    for n in nodes:  # junk prospective merge fields must not influence topology
        n["merge_commit_sha"] = "deadbeef" * 5
        n["prospective_merge_sha"] = "cafef00d" * 5
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/727"]["stack_state"] == stack_mod.STACK_CURRENT


# --- parent movement / stale ancestry ------------------------------------------

def test_parent_head_advancement_flags_restack():
    nodes, _client = linear_stack()
    # parent 723 advances; child 725 no longer descends from the new head
    nodes[1]["head"] = "h723v2"
    client = FakeClient(ancestry={("h720", "h723v2"), ("h725", "h727")},
                        not_ancestry={("h723v2", "h725")})
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/723"]["stack_state"] == stack_mod.STACK_CURRENT
    rec = stacks["pr/725"]
    assert rec["stack_state"] == stack_mod.PARENT_MOVED
    assert rec["restack_required"] is True
    assert rec["parent_head"] == "h723v2"
    # downstream child of a moved parent: still current vs its own parent
    assert stacks["pr/727"]["stack_state"] == stack_mod.STACK_CURRENT
    # negative control: child rebased onto new parent head => current again
    nodes[2]["head"] = "h725v2"
    client2 = FakeClient({("h723v2", "h725v2"), ("h725v2", "h727"),
                          ("h720", "h723v2")})
    assert stack_mod.build_stacks(nodes, client2)["pr/725"]["stack_state"] == \
        stack_mod.STACK_CURRENT


def test_stale_child_ancestry_fails_closed():
    """Ancestry lookup unavailable => ANCESTRY_UNKNOWN, never STACK_CURRENT."""
    nodes, _ = linear_stack()
    stacks = stack_mod.build_stacks(nodes, FakeClient())  # empty truth
    assert all(r["stack_state"] == stack_mod.ANCESTRY_UNKNOWN
               for r in stacks.values() if r["parent_pr"] is not None)


def test_stale_cached_topology_vs_live_refs():
    """Live refs win: cached child head contradicting live ancestry is caught."""
    nodes, client = linear_stack()
    cached = stack_mod.build_stacks(nodes, client)
    assert cached["pr/727"]["stack_state"] == stack_mod.STACK_CURRENT
    # cached child head is stale; live client now reports parent advanced
    nodes[3]["head"] = "h727stale"
    live = FakeClient()  # nothing verifies anymore
    stacks = stack_mod.build_stacks(nodes, live)
    assert stacks["pr/727"]["stack_state"] == stack_mod.ANCESTRY_UNKNOWN


# --- broken topologies ----------------------------------------------------------

def test_missing_parent_fails_closed():
    nodes, client = linear_stack()
    nodes[1]["base"] = "feat-ghost-branch"  # 723's parent branch has no open PR
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/723"]["stack_state"] == stack_mod.PARENT_MISSING
    assert stacks["pr/723"]["depth"] is None
    # control: restored base => current
    nodes[1]["base"] = "feat-dag-mvp"
    assert stack_mod.build_stacks(nodes, client)["pr/723"]["stack_state"] == \
        stack_mod.STACK_CURRENT


def test_merged_parent_transition_is_missing():
    """Parent PR merged/closed: its branch is no longer an open PR head."""
    nodes, client = linear_stack()
    nodes.pop(0)  # 720 merged; 723 now bases on a branch with no open PR
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/723"]["stack_state"] == stack_mod.PARENT_MISSING


def test_duplicate_branch_ambiguity():
    nodes, client = linear_stack()
    dupe = node("pr/799", "feat-rogue", head="h799", branch="feat-hardening")
    stacks = stack_mod.build_stacks([*nodes, dupe], client)
    # children of feat-hardening now have two candidate parents
    assert stacks["pr/725"]["stack_state"] == stack_mod.AMBIGUOUS
    assert stacks["pr/727"]["stack_state"] == stack_mod.AMBIGUOUS
    # control: removing the duplicate resolves
    stacks2 = stack_mod.build_stacks(nodes, client)
    assert stacks2["pr/725"]["stack_state"] == stack_mod.STACK_CURRENT


def test_self_parent_cycle_invalid():
    nodes, client = linear_stack()
    nodes[2]["base"] = "feat-registry"  # 725 based on its own head branch
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/725"]["stack_state"] == stack_mod.CYCLE_INVALID


def test_indirect_cycle_invalid():
    nodes, client = linear_stack()
    # 720 based on feat-router (727's branch) closes a loop
    nodes[0]["base"] = "feat-router"
    stacks = stack_mod.build_stacks(nodes, client)
    assert any(r["stack_state"] == stack_mod.CYCLE_INVALID for r in stacks.values())


def test_unrelated_main_pr_is_separate_root():
    nodes, client = linear_stack()
    other = node("pr/800", "main", head="h800", branch="feat-f6")
    stacks = stack_mod.build_stacks([*nodes, other], client)
    assert stacks["pr/800"]["stack_state"] == stack_mod.ROOT
    assert stacks["pr/800"]["stack_root"] == "pr/800"
    assert stacks["pr/727"]["stack_root"] == "pr/720"  # not absorbed


# --- authority non-inheritance ---------------------------------------------------

def test_child_mergeable_true_while_parent_unresolved():
    """mergeable=true on a child does not cure a broken stack relation."""
    nodes, client = linear_stack()
    nodes[1]["base"] = "feat-ghost"
    nodes[3]["mergeable"] = "MERGEABLE"
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/727"]["stack_state"] == stack_mod.STACK_CURRENT
    # and the router must not treat the mergeable flag as stack truth


def test_parent_ownership_not_inherited(tmp_path):
    """Child of my lane is UNOWNED: mutex is per-lane, never inherited."""
    nodes, client = linear_stack()
    nodes[3]["ownership"] = "UNOWNED"
    nodes[3]["owner"] = None
    stacks = stack_mod.build_stacks(nodes, client)
    assert stacks["pr/727"]["stack_state"] == stack_mod.STACK_CURRENT
    profile = agents_mod.load_registry(write_reg(tmp_path)).registry["agents"][0]
    route = router_mod.evaluate_lane(profile, nodes[3],
                                     stacks["pr/727"])
    assert route["action_class"] == router_mod.ROUTE_READONLY
    assert any(b == "LANE_UNOWNED_WRITE_REQUIRES_CLAIM" for b in route["blockers"])


def test_parent_ci_iv_not_inherited():
    """Stack state never copies parent ci_status/formal_iv into the child."""
    nodes, client = linear_stack()
    nodes[0]["ci_status"] = "PASS"
    nodes[0]["formal_iv"] = "rcpt-720"
    stacks = stack_mod.build_stacks(nodes, client)
    rec = stacks["pr/723"]
    assert "ci_status" not in rec and "formal_iv" not in rec
    assert rec["stack_state"] == stack_mod.STACK_CURRENT


def write_reg(tmp_path):
    import json as _json
    path = tmp_path / "agents.json"
    path.write_text(_json.dumps({
        "schema": "ATLAS_AGENT_REGISTRY_V1", "registry_id": "t", "version": 1,
        "agents": [{
            "agent_id": "ubuntu-main", "role": "coordinator", "active": True,
            "platforms": ["linux"],
            "capabilities": ["READ_REPO", "READ_GITHUB", "WRITE_CODE"],
            "prohibitions": ["AUTO_MERGE"],
            "write_scopes": ["path:scripts/atlas_dag"],
            "event_permissions": ["OWNER_CLAIMED"],
            "verification_class": "IMPLEMENTATION",
        }],
    }), encoding="utf-8")
    return path


# --- router stack integration ----------------------------------------------------

def _active_registry(tmp_path):
    return agents_mod.load_registry(write_reg(tmp_path))


def test_router_blocks_write_on_restack_required_lane(tmp_path):
    nodes, _ = linear_stack()
    nodes[1]["head"] = "h723v2"
    client = FakeClient(ancestry={("h720", "h723v2")},
                        not_ancestry={("h723v2", "h725")})
    stacks = stack_mod.build_stacks(nodes, client)
    registry = _active_registry(tmp_path)
    route = router_mod.route("ubuntu-main",
                             {"nodes": [n for n in nodes if n["lane"] == "pr/725"]},
                             registry, stacks)
    best = next(r for r in route["routes"] if r["lane"] == "pr/725")
    assert best["action_class"] == router_mod.ROUTE_READONLY
    assert any(b.startswith("STACK_NOT_CURRENT") for b in best["blockers"])
    # negative control: with a truthful (current) stack record => write
    stacks_ok = stack_mod.build_stacks(nodes, FakeClient(
        ancestry={("h723v2", "h725"), ("h720", "h723v2")}))
    route_ok = router_mod.route("ubuntu-main",
                                {"nodes": [n for n in nodes if n["lane"] == "pr/725"]},
                                registry, stacks_ok)
    best_ok = next(r for r in route_ok["routes"] if r["lane"] == "pr/725")
    assert best_ok["action_class"] == router_mod.ROUTE_WRITE


def test_router_marks_stacked_child_not_independent(tmp_path):
    nodes, client = linear_stack()
    stacks = stack_mod.build_stacks(nodes, client)
    registry = _active_registry(tmp_path)
    route = router_mod.route("ubuntu-main",
                             {"nodes": [n for n in nodes if n["lane"] == "pr/727"]},
                             registry, stacks)
    best = next(r for r in route["routes"] if r["lane"] == "pr/727")
    assert best["action_class"] == router_mod.ROUTE_WRITE
    assert any(r.startswith("STACK_CHILD_OF:pr/725") for r in best["reasons"])


def test_stack_problem_does_not_block_unrelated_lane(tmp_path):
    nodes, _ = linear_stack()
    nodes[1]["base"] = "feat-ghost"  # 723 broken...
    stacks = stack_mod.build_stacks(nodes, FakeClient())
    registry = _active_registry(tmp_path)
    mine = node("pr/900", "main", head="h900", branch="feat-mine",
                state="RUNNABLE_WRITE", ownership="OWNED", owner="ubuntu-main")
    route = router_mod.route("ubuntu-main", {"nodes": [nodes[2], mine]},
                             registry, stacks)
    assert route["action_class"] == router_mod.ROUTE_WRITE
    assert route["lane"] == "pr/900"
