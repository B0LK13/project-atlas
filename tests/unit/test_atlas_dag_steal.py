"""Adversarial tests for FEATURE_11: SAFE_CROSS_AGENT_WORK_STEALING.

WORK_STEALING != OWNERSHIP_BYPASS. Every denial has a positive control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import emitter as emitter_mod  # noqa: E402
from atlas_dag import stack as stack_mod  # noqa: E402
from atlas_dag import steal as steal_mod  # noqa: E402
from test_atlas_dag_frontier_score import stack_rec, weights  # noqa: E402
from test_atlas_dag_router import make_node, make_profile, snapshot_of, write_registry  # noqa: E402

FIXED = "2026-09-08T12:00:00Z"


def clock():
    return FIXED


def unowned(**overrides):
    node = make_node("pr/800", state="RUNNABLE_READONLY", ownership="UNOWNED",
                     owner=None, priority_class="P1", tree="b" * 40,
                     claimants=[])
    node.update(overrides)
    if "pr" in overrides and "lane" not in overrides:
        node["lane"] = f"pr/{overrides['pr']}"
    return node


def plan(nodes, agent="ubuntu-main", stacks=None, registry=None, tmp_path=None,
         w=None):
    if registry is None:
        assert tmp_path is not None
        registry = write_registry(tmp_path, [make_profile()])
    return steal_mod.plan_steal(
        snapshot_of(*nodes), agent, registry, stacks=stacks or {},
        weights=w or weights(), weights_source="test", clock=clock)


def test_unowned_high_value_is_stealable(tmp_path):
    node = unowned(priority_class="P0")
    result = plan([node], tmp_path=tmp_path)
    assert result["utilization"] == steal_mod.STEAL_AVAILABLE
    assert result["candidate"]["pr"] == 800
    assert result["candidate"]["action_class_after_claim"] == "RUNNABLE_WRITE"


def test_foreign_owned_high_score_cannot_be_stolen(tmp_path):
    foreign = make_node("pr/801", owner="other-agent", priority_class="P0")
    free = unowned(pr=802, lane="pr/802", priority_class="P3")
    result = plan([foreign, free], tmp_path=tmp_path)
    assert result["candidate"]["pr"] == 802
    assert all(c["pr"] != 801 for c in result["candidates"])
    released = unowned(pr=801, lane="pr/801", priority_class="P0")
    assert plan([released, free], tmp_path=tmp_path)["candidate"]["pr"] == 801


def test_frozen_cannot_be_stolen(tmp_path):
    frozen = unowned(frozen=True, state="FROZEN", priority_class="P0")
    free = unowned(pr=803, lane="pr/803", priority_class="P3")
    result = plan([frozen, free], tmp_path=tmp_path)
    assert result["candidate"]["pr"] == 803


def test_inactive_agent_cannot_steal(tmp_path):
    registry = write_registry(
        tmp_path, [make_profile(agent_id="windows-main", active=False,
                                platforms=["windows"])])
    result = plan([unowned()], agent="windows-main", registry=registry)
    assert result["utilization"] == steal_mod.NO_SAFE_STEAL
    assert result["candidate"] is None


def test_capability_mismatch_cannot_steal(tmp_path):
    registry = write_registry(tmp_path, [make_profile(
        capabilities=["READ_REPO", "READ_GITHUB"])])
    result = plan([unowned(priority_class="P0")], registry=registry, tmp_path=tmp_path)
    assert result["utilization"] == steal_mod.BLOCKED_BY_CAPABILITY
    assert result["candidate"] is None


def test_owned_lane_not_steal_target(tmp_path):
    owned = make_node("pr/810", priority_class="P0")
    result = plan([owned], tmp_path=tmp_path)
    assert result["candidate"] is None


def test_restack_required_child_cannot_be_stolen(tmp_path):
    child = unowned(pr=820, lane="pr/820", priority_class="P0")
    stacks = {"pr/820": stack_rec(
        "pr/820", depth=1, parent_pr=819, stack_state=stack_mod.RESTACK_REQUIRED,
        restack_required=True)}
    result = plan([child], stacks=stacks, tmp_path=tmp_path)
    assert result["candidate"] is None
    stacks_ok = {"pr/820": stack_rec("pr/820", depth=1, parent_pr=819,
                                     stack_state=stack_mod.STACK_CURRENT)}
    assert plan([child], stacks=stacks_ok, tmp_path=tmp_path)["candidate"]["pr"] == 820


def test_highest_ranked_unowned_selected(tmp_path):
    low = unowned(pr=830, lane="pr/830", priority_class="P3")
    high = unowned(pr=831, lane="pr/831", priority_class="P0")
    result = plan([low, high], tmp_path=tmp_path)
    assert result["candidate"]["pr"] == 831


def test_incompatible_higher_ranked_skipped(tmp_path):
    registry = write_registry(tmp_path, [make_profile(platforms=["linux"])])
    bad = unowned(pr=840, lane="pr/840", priority_class="P0",
                  platform_requirements=["windows"])
    good = unowned(pr=841, lane="pr/841", priority_class="P2")
    result = plan([bad, good], registry=registry, tmp_path=tmp_path)
    assert result["candidate"]["pr"] == 841


def test_all_compatible_owned_utilization(tmp_path):
    owned = make_node("pr/850", owner="other-agent", priority_class="P1")
    result = plan([owned], tmp_path=tmp_path)
    assert result["utilization"] == steal_mod.ALL_COMPATIBLE_WORK_OWNED
    assert result["owned_compatible_count"] >= 1


class FakeClient:
    def __init__(self, nodes_env):
        self.repo = "B0LK13/project-atlas"
        self._prs = []
        self._commits = {}
        self._events = []
        self._posted = []
        for node in nodes_env:
            self._prs.append({
                "number": node["pr"], "headRefOid": node["head"],
                "headRefName": f"branch-{node['pr']}", "baseRefName": "main",
            })
            self._commits[node["head"]] = {"sha": node["head"], "tree": node["tree"]}

    def open_prs(self):
        return list(self._prs)

    def commit(self, sha):
        return self._commits.get(sha)

    def default_branch(self):
        return "main"

    def branch_head(self, branch):
        return {"sha": "1" * 40, "tree": "2" * 40}

    def dag_issue(self):
        return {"number": 719}

    def issue_comments(self, number):
        return [{"body": "```json\n" + json.dumps(e) + "\n```"} for e in self._events]

    def run_gh(self, args):
        if "comment" in args:
            path = args[args.index("--body-file") + 1]
            self._posted.append(Path(path).read_text(encoding="utf-8"))
        return ""


def test_dry_run_zero_mutation(tmp_path, monkeypatch):
    node = unowned(priority_class="P0")
    client = FakeClient([node])
    registry = write_registry(tmp_path, [make_profile()])
    monkeypatch.setattr(steal_mod.model_mod, "build_snapshot",
                        lambda *a, **k: snapshot_of(node))
    monkeypatch.setattr(steal_mod.stack_mod, "build_stacks",
                        lambda *a, **k: {})
    result = steal_mod.execute_steal(
        client, "ubuntu-main", registry, dry_run=True,
        weights=weights(), weights_source="test", clock=clock,
        snapshot=snapshot_of(node), stacks={})
    assert result["outcome"] == steal_mod.WOULD_CLAIM
    assert result["mutated"] is False
    assert client._posted == []
    assert result["candidate"]["pr"] == 800


def test_stale_head_between_plan_and_claim_zero_mutation(tmp_path, monkeypatch):
    node = unowned(priority_class="P0")
    client = FakeClient([node])
    registry = write_registry(tmp_path, [make_profile()])
    monkeypatch.setattr(steal_mod.model_mod, "build_snapshot",
                        lambda *a, **k: snapshot_of(node))
    monkeypatch.setattr(steal_mod.stack_mod, "build_stacks", lambda *a, **k: {})

    orig_revalidate = steal_mod._revalidate_candidate
    calls = {"n": 0}

    def wrapping(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            client._prs[0]["headRefOid"] = "c" * 40
            client._commits["c" * 40] = {"sha": "c" * 40, "tree": "d" * 40}
        return orig_revalidate(*a, **k)

    monkeypatch.setattr(steal_mod, "_revalidate_candidate", wrapping)
    result = steal_mod.execute_steal(
        client, "ubuntu-main", registry, dry_run=False, max_retries=1,
        weights=weights(), weights_source="test", clock=clock,
        snapshot=snapshot_of(node), stacks={})
    assert result["mutated"] is False
    assert result["outcome"] == steal_mod.STEAL_PLAN_STALE
    assert client._posted == []


def test_ownership_race_no_double_owner(tmp_path, monkeypatch):
    node = unowned(priority_class="P0")
    client = FakeClient([node])
    client._events.append({
        "schema": "ATLAS_EVENT_V1", "event_id": "evt-other",
        "timestamp_utc": FIXED, "actor": "other-agent", "role": "AGENT",
        "session_id": "s", "lane": "pr/800", "pr": 800, "head": node["head"],
        "event": "OWNER_CLAIMED", "state": "CLAIMED", "dependencies": [],
        "evidence": [], "invalidates": [], "next_actions": [],
    })
    registry = write_registry(tmp_path, [make_profile()])
    monkeypatch.setattr(steal_mod.model_mod, "build_snapshot",
                        lambda *a, **k: snapshot_of(node))
    monkeypatch.setattr(steal_mod.stack_mod, "build_stacks", lambda *a, **k: {})
    result = steal_mod.execute_steal(
        client, "ubuntu-main", registry, dry_run=False, max_retries=1,
        weights=weights(), weights_source="test", clock=clock,
        snapshot=snapshot_of(node), stacks={})
    assert result["mutated"] is False
    assert "OWNERSHIP_MUTEX_HELD_BY:other-agent" in (result.get("reasons") or [])
    assert client._posted == []


def test_duplicate_claim_idempotent(tmp_path, monkeypatch):
    node = unowned(priority_class="P0")
    client = FakeClient([node])
    registry = write_registry(tmp_path, [make_profile()])
    monkeypatch.setattr(steal_mod.model_mod, "build_snapshot",
                        lambda *a, **k: snapshot_of(node))
    monkeypatch.setattr(steal_mod.stack_mod, "build_stacks", lambda *a, **k: {})
    posted: list[str] = []

    def fake_emit(client, registry, payload, dry_run=False):
        posted.append(payload["event_id"])
        return "posted"

    monkeypatch.setattr(steal_mod.emitter_mod, "emit_event", fake_emit)
    monkeypatch.setattr(
        steal_mod.emitter_mod, "resolve_context",
        lambda client, pr, profile, expected_repo=None:
        emitter_mod.ResolvedContext(
            repo=client.repo, pr=pr, lane=f"pr/{pr}",
            head=node["head"], tree=node["tree"],
            base_branch="main", base_head="1" * 40,
            main_branch="main", main_head="1" * 40,
            parent_pr=None, parent_head=None,
            actor="ubuntu-main", role="COORDINATOR",
            session_id="ubuntu-main-20260908"))
    r1 = steal_mod.execute_steal(
        client, "ubuntu-main", registry, dry_run=False, max_retries=1,
        weights=weights(), weights_source="test", clock=clock,
        snapshot=snapshot_of(node), stacks={})
    assert r1["outcome"] == steal_mod.CLAIMED
    client._events.append({
        "schema": "ATLAS_EVENT_V1", "event_id": r1["event_id"],
        "timestamp_utc": FIXED, "actor": "ubuntu-main", "role": "COORDINATOR",
        "session_id": "s", "lane": "pr/800", "pr": 800, "head": node["head"],
        "event": "OWNER_CLAIMED", "state": "CLAIMED", "dependencies": [],
        "evidence": [], "invalidates": [], "next_actions": [],
    })
    r2 = steal_mod.execute_steal(
        client, "ubuntu-main", registry, dry_run=False, max_retries=1,
        weights=weights(), weights_source="test", clock=clock,
        snapshot=snapshot_of(node), stacks={})
    assert r2["outcome"] == steal_mod.ALREADY_OWNED
    assert r2["mutated"] is False


def test_race_retries_next_safe_candidate(tmp_path, monkeypatch):
    first = unowned(pr=860, lane="pr/860", priority_class="P0")
    second = unowned(pr=861, lane="pr/861", priority_class="P1")
    client = FakeClient([first, second])
    registry = write_registry(tmp_path, [make_profile()])
    snaps = [snapshot_of(first, second), snapshot_of(second)]

    def build_snap(*a, **k):
        return snaps[min(build_snap.i, len(snaps) - 1)]

    build_snap.i = 0
    monkeypatch.setattr(steal_mod.model_mod, "build_snapshot", build_snap)
    monkeypatch.setattr(steal_mod.stack_mod, "build_stacks", lambda *a, **k: {})

    def revalidate(client, profile, candidate, stacks, expected_repo):
        if candidate["pr"] == 860:
            build_snap.i = 1
            return ["OWNERSHIP_MUTEX_HELD_BY:other-agent"]
        return []

    monkeypatch.setattr(steal_mod, "_revalidate_candidate", revalidate)
    monkeypatch.setattr(steal_mod.emitter_mod, "emit_event",
                        lambda *a, **k: "posted")
    monkeypatch.setattr(
        steal_mod.emitter_mod, "resolve_context",
        lambda client, pr, profile, expected_repo=None:
        emitter_mod.ResolvedContext(
            repo=client.repo, pr=pr, lane=f"pr/{pr}",
            head=second["head"] if pr == 861 else first["head"],
            tree=second["tree"] if pr == 861 else first["tree"],
            base_branch="main", base_head="1" * 40,
            main_branch="main", main_head="1" * 40,
            parent_pr=None, parent_head=None,
            actor="ubuntu-main", role="COORDINATOR",
            session_id="ubuntu-main-20260908"))
    result = steal_mod.execute_steal(
        client, "ubuntu-main", registry, dry_run=False, max_retries=3,
        weights=weights(), weights_source="test", clock=clock,
        snapshot=snapshot_of(first, second), stacks={})
    assert result["outcome"] == steal_mod.CLAIMED
    assert result["candidate"]["pr"] == 861
    assert result["attempt"] == 2


def test_verifier_role_cannot_gain_implementer_write(tmp_path):
    registry = write_registry(tmp_path, [make_profile(
        agent_id="independent-verifier",
        role="independent verifier lane (formal IV)",
        capabilities=["READ_REPO", "READ_GITHUB", "RUN_TESTS"],
        verification_class="INDEPENDENT_VERIFIER")])
    result = plan([unowned(priority_class="P0")], agent="independent-verifier",
                  registry=registry)
    assert result["candidate"] is None
    assert result["utilization"] in (
        steal_mod.BLOCKED_BY_CAPABILITY, steal_mod.NO_SAFE_STEAL)


def test_cli_registers_steal_commands():
    from atlas_dag.cli import build_parser
    p = build_parser()
    assert p.parse_args(["steal-status", "--agent", "ubuntu-main"]).agent
    assert p.parse_args(["steal", "--agent", "ubuntu-main", "--dry-run"]).dry_run
