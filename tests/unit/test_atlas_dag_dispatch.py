"""Adversarial tests for FEATURE_06: AUTOMATIC_PARALLEL_CI_IV_DISPATCH.

CI and formal IV are independent sibling lanes: `CI_RUNNABLE != IV_RUNNABLE`.
Every denial has a load-bearing positive control: the denial must become
acceptable only when the specific legitimate constraint is removed. No
network: a fake `gh` client mirrors tests/unit/test_atlas_dag.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import cli as cli_mod  # noqa: E402
from atlas_dag import dispatch as dispatch_mod  # noqa: E402
from atlas_dag import events as events_mod  # noqa: E402
from atlas_dag import verifiers as verifiers_mod  # noqa: E402
from atlas_dag.events import validator_for  # noqa: E402
from atlas_dag.model import build_snapshot  # noqa: E402

REPO = "B0LK13/project-atlas"
MAIN_SHA = "1" * 40
MAIN_TREE = "2" * 40
H1 = "a" * 40
T1 = "b" * 40
H2 = "c" * 40
T2 = "d" * 40

AGENT = "ubuntu-main"


def fenced(payload: dict) -> str:
    return "```json\n" + json.dumps(payload) + "\n```"


def make_event(event_id: str, event: str, *, pr: int = 10, head: str = H1,
               state: str = "FROZEN", actor: str = AGENT,
               ts: str = "2026-09-01T00:00:00Z") -> dict:
    return {
        "schema": "ATLAS_EVENT_V1",
        "event_id": event_id,
        "timestamp_utc": ts,
        "actor": actor,
        "role": "COORDINATOR",
        "session_id": f"sess-{actor}",
        "lane": f"pr/{pr}",
        "pr": pr,
        "head": head,
        "tree": T1,
        "event": event,
        "state": state,
        "dependencies": [],
        "evidence": [],
        "invalidates": [],
        "next_actions": [],
    }


def comments_with(*payloads, author: str = AGENT) -> list[dict]:
    return [
        {"body": fenced(p), "id": 1000 + i,
         "user": {"login": author}, "html_url": f"https://example/c/{1000 + i}"}
        for i, p in enumerate(payloads)
    ]


def freeze_event(pr: int = 10, head: str = H1) -> dict:
    return make_event(f"evt-freeze-{pr}", "HUMAN_GATE_REQUIRED", pr=pr,
                      head=head, state="FROZEN")


class FakeEnv:
    def __init__(self) -> None:
        self.prs: list[dict] = []
        self.commits: dict[str, dict] = {}
        self.runs: dict[str, list[dict]] = {}
        self.issue: dict | None = None
        self.issue_body = ""
        self.comments: list[dict] = []
        self.dispatched: list[tuple[str, str]] = []  # (workflow_id, ref)
        self.gh_calls: list[list[str]] = []

    def add_pr(self, number: int, head: str, tree: str, *,
               author: str = "someone") -> None:
        self.prs.append({
            "number": number, "title": f"PR {number}",
            "author": {"login": author}, "isDraft": False,
            "headRefName": f"branch-{number}", "headRefOid": head,
            "baseRefName": "main", "mergeable": "MERGEABLE",
            "url": f"https://example/{number}", "updatedAt": "2026-09-01T00:00:00Z",
        })
        self.commits[head] = {"sha": head, "commit": {"tree": {"sha": tree}}}

    def add_issue(self, comments: list[dict] | None = None, body: str = "") -> None:
        self.issue = {"number": 719, "title": "Atlas Autonomous DAG Control",
                      "state": "OPEN"}
        self.issue_body = body
        self.comments = comments or []

    @property
    def mutation_count(self) -> int:
        return len(self.dispatched) + len(self.gh_calls)


class FakeClient:
    def __init__(self, env: FakeEnv):
        self._env = env
        self.repo = REPO

    def default_branch(self) -> str:
        return "main"

    def branch_head(self, branch: str) -> dict:
        return {"sha": MAIN_SHA, "tree": MAIN_TREE}

    def dag_issue(self) -> dict | None:
        return self._env.issue

    def issue_body(self, number: int) -> str | None:
        return self._env.issue_body

    def issue_comments(self, number: int) -> list[dict]:
        return list(self._env.comments)

    def open_prs(self) -> list[dict]:
        return list(self._env.prs)

    def commit(self, sha: str) -> dict | None:
        data = self._env.commits.get(sha)
        if not data:
            return None
        return {"sha": data["sha"], "tree": data["commit"]["tree"]["sha"]}

    def runs_for_head(self, sha: str) -> list[dict]:
        return list(self._env.runs.get(sha, []))

    def review_comments(self, pr: int) -> list[dict]:
        return []

    def dispatch_workflow(self, workflow_id: str, ref: str) -> dict:
        self._env.dispatched.append((workflow_id, ref))
        return {}

    def run_gh(self, args: list[str]) -> str:
        self._env.gh_calls.append(list(args))
        if args[:2] == ["issue", "comment"]:
            body_path = args[args.index("--body-file") + 1]
            body = Path(body_path).read_text(encoding="utf-8")
            self._env.comments.append({
                "body": body, "id": 5000 + len(self._env.comments),
                "user": {"login": AGENT},
                "html_url": f"https://example/posted/{len(self._env.comments)}",
            })
        return ""


def frozen_env(*, head: str = H1, tree: str = T1, pr: int = 10,
               author: str = "someone") -> FakeEnv:
    env = FakeEnv()
    env.add_pr(pr, head, tree, author=author)
    env.add_issue(comments=comments_with(freeze_event(pr=pr, head=head)))
    return env


def bound_entry(verifier_id: str, principal: str | None, *,
                active: bool = True, repos: list[str] | None = None) -> dict:
    return {
        "verifier_id": verifier_id,
        "principal": principal,
        "active": active,
        "allowed_repositories": repos if repos is not None else [REPO],
        "capabilities": ["formal_iv"],
        "prohibitions": ["no_merge_authority", "no_write_authority", "no_self_iv"],
    }


BOUND_POOL = [bound_entry("IV-A", "github:iv-a-user"),
              bound_entry("IV-B", "github:iv-b-user")]


def resolution_for(tmp_path: Path, entries: list[dict]) -> verifiers_mod.PoolResolution:
    path = tmp_path / "verifiers.json"
    path.write_text(json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1", "version": 1,
                                "verifiers": entries}), encoding="utf-8")
    return verifiers_mod.resolve_pool(None, path=path, repo=REPO)


def bound_resolution(tmp_path: Path) -> verifiers_mod.PoolResolution:
    return resolution_for(tmp_path, BOUND_POOL)


def unbound_resolution() -> verifiers_mod.PoolResolution:
    """The live state today: committed registry present, no authenticated
    principal binding."""
    return verifiers_mod.resolve_pool(None, path=verifiers_mod.default_pool_path(),
                                      repo=REPO)


def profile(*, active: bool = True, ci_dispatch: bool = True,
            iv_request: bool = True, agent_id: str = AGENT) -> dict:
    return {
        "agent_id": agent_id,
        "role": "coordinator",
        "active": active,
        "platforms": ["linux"],
        "capabilities": ["READ_REPO", "READ_GITHUB"]
        + (["ci_dispatch"] if ci_dispatch else []),
        "prohibitions": ["AUTO_MERGE"],
        "write_scopes": ["github:issue-comment:719"],
        "event_permissions": (["IV_REQUEST"] if iv_request else []),
        "verification_class": "NONE",
        "principal": None,
    }


def plan_for(env: FakeEnv, pool: verifiers_mod.PoolResolution,
             node: dict | None = None) -> dict:
    node = node or {"pr": 10, "frozen": True}
    return dispatch_mod.plan_dispatch(node, FakeClient(env), None, None, pool)


def execute(env: FakeEnv, plan: dict, agent_profile: dict, *,
            dry_run: bool = False) -> dict:
    return dispatch_mod.execute_dispatch(plan, FakeClient(env), AGENT,
                                         agent_profile, dry_run=dry_run)


# -- planner: sibling lane independence --------------------------------------


def test_ci_runnable_iv_unbound_dispatches_ci_blocks_iv():
    env = frozen_env()
    plan = plan_for(env, unbound_resolution())
    assert plan["ci"] == {"lane_state": "RUNNABLE", "reasons": []}
    assert plan["iv"]["lane_state"] == "BLOCKED"
    assert plan["iv"]["reasons"] == ["VERIFIER_IDENTITY_UNBOUND"]
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "DISPATCHED"
    assert env.dispatched == [("ci.yml", "branch-10")]
    assert result["iv"]["outcome"] == "BLOCKED"
    assert env.gh_calls == []  # zero IV mutation


def test_ci_runnable_iv_unbound_positive_control_bound_pool(tmp_path):
    env = frozen_env()
    plan = plan_for(env, bound_resolution(tmp_path))
    assert plan["iv"]["lane_state"] == "RUNNABLE"
    assert plan["iv"]["verifiers"] == ["IV-A", "IV-B"]


def test_iv_runnable_ci_already_running_no_duplicate_ci(tmp_path):
    env = frozen_env()
    env.runs[H1] = [{"id": 55, "created_at": "2026-09-01T09:00:00Z",
                     "status": "in_progress"}]
    plan = plan_for(env, bound_resolution(tmp_path))
    # Sibling states are independent: CI observed, IV still evaluated.
    assert plan["ci"]["lane_state"] == "ALREADY_RUNNING"
    assert plan["ci"]["run_id"] == "55"
    assert plan["iv"]["lane_state"] == "RUNNABLE"
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "ALREADY_RUNNING"
    assert env.dispatched == []  # no duplicate CI dispatch
    assert result["iv"]["outcome"] == "REQUESTED"
    assert len(env.gh_calls) == 1


def test_iv_request_event_is_a_request_not_a_receipt(tmp_path):
    env = frozen_env()
    plan = plan_for(env, bound_resolution(tmp_path))
    result = execute(env, plan, profile())
    assert result["iv"]["outcome"] == "REQUESTED"
    body = env.comments[-1]["body"]
    payload = json.loads(body.strip().removeprefix("```json").removesuffix("```"))
    assert payload["event"] == "IV_REQUEST"
    assert payload["state"] == "REQUESTED"
    assert "NOT an ATLAS_IV_RECEIPT_V1 receipt" in payload["note"]
    assert payload["actor"] == AGENT
    # A request is an event, never an IV receipt: the receipt stream stays empty.
    ingested = events_mod.ingest_comments(env.comments)
    assert ingested.receipts == []


def test_both_runnable_both_dispatched_no_ordering_dependency(tmp_path):
    env = frozen_env()
    pool = bound_resolution(tmp_path)
    plan = plan_for(env, pool)
    # The plan contains BOTH lanes before any execution: there is no
    # sequencing between CI and IV.
    assert plan["ci"]["lane_state"] == "RUNNABLE"
    assert plan["iv"]["lane_state"] == "RUNNABLE"
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "DISPATCHED"
    assert result["iv"]["outcome"] == "REQUESTED"
    assert len(env.dispatched) == 1 and len(env.gh_calls) == 1


def test_not_frozen_candidate_blocks_both_lanes():
    env = frozen_env()
    node = {"pr": 10, "frozen": False}
    plan = plan_for(env, unbound_resolution(), node)
    assert plan["frozen"] is False
    for lane in ("ci", "iv"):
        assert plan[lane]["lane_state"] == "BLOCKED"
        assert plan[lane]["reasons"] == ["CANDIDATE_NOT_FROZEN"]
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "BLOCKED"
    assert result["iv"]["outcome"] == "BLOCKED"
    assert env.mutation_count == 0


def test_both_blocked_zero_mutation():
    env = frozen_env()
    env.runs[H1] = [{"id": 60, "created_at": "2026-09-01T09:00:00Z",
                     "status": "in_progress"}]
    plan = plan_for(env, unbound_resolution())
    assert plan["ci"]["lane_state"] == "ALREADY_RUNNING"
    assert plan["iv"]["lane_state"] == "BLOCKED"
    result = execute(env, plan, profile())
    assert env.mutation_count == 0
    assert result["ci"]["outcome"] == "ALREADY_RUNNING"
    assert result["iv"]["outcome"] == "BLOCKED"


def test_unknown_tree_blocks_both_lanes():
    env = frozen_env()
    env.commits = {}  # head unresolvable: tree unknown
    plan = plan_for(env, unbound_resolution())
    assert plan["head"] == H1 and plan["tree"] is None
    for lane in ("ci", "iv"):
        assert plan[lane]["lane_state"] == "BLOCKED"
        assert plan[lane]["reasons"] == ["TREE_UNKNOWN"]
    assert execute(env, plan, profile())["ci"]["outcome"] == "BLOCKED"
    assert env.mutation_count == 0


def test_unknown_head_blocks_both_lanes():
    env = frozen_env()
    env.prs = []  # PR left the open frontier
    plan = plan_for(env, unbound_resolution())
    assert plan["head"] is None
    for lane in ("ci", "iv"):
        assert plan[lane]["lane_state"] == "BLOCKED"
        assert plan[lane]["reasons"] == ["HEAD_UNKNOWN"]
    assert env.mutation_count == 0


def test_stale_head_never_dispatches(tmp_path):
    # Candidate moved H1 -> H2; CI evidence on the predecessor head H1 can
    # never satisfy the successor.
    env = frozen_env(head=H2, tree=T2)
    env.runs[H1] = [{"id": 70, "created_at": "2026-09-01T09:00:00Z",
                     "status": "completed", "conclusion": "success"}]
    plan = plan_for(env, bound_resolution(tmp_path))
    assert plan["head"] == H2
    assert plan["ci"]["lane_state"] == "RUNNABLE"  # predecessor PASS ignored
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "DISPATCHED"
    assert env.dispatched == [("ci.yml", "branch-10")]


def test_existing_exact_head_pass_is_complete_no_rerun():
    env = frozen_env()
    env.runs[H1] = [{"id": 101, "created_at": "2026-09-01T10:00:00Z",
                     "status": "completed", "conclusion": "success"}]
    plan = plan_for(env, unbound_resolution())
    assert plan["ci"]["lane_state"] == "COMPLETE"
    assert plan["ci"]["run_id"] == "101"
    assert plan["ci"]["conclusion"] == "success"
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "COMPLETE"
    assert env.mutation_count == 0


def test_concluded_failure_is_complete_not_runnable():
    env = frozen_env()
    env.runs[H1] = [{"id": 102, "created_at": "2026-09-01T10:00:00Z",
                     "status": "completed", "conclusion": "failure"}]
    plan = plan_for(env, unbound_resolution())
    assert plan["ci"]["lane_state"] == "COMPLETE"
    assert plan["ci"]["conclusion"] == "failure"
    # Dispatch never re-runs a concluded run for the same head; a human or a
    # new head is required. Zero mutation either way.
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "COMPLETE"
    assert env.mutation_count == 0


def test_self_verifier_bound_principal_is_author_blocks_iv(tmp_path):
    env = frozen_env(author="someone")
    pool = resolution_for(tmp_path, [bound_entry("IV-A", "github:someone")])
    plan = plan_for(env, pool)
    assert plan["iv"]["lane_state"] == "BLOCKED"
    assert plan["iv"]["reasons"] == ["INDEPENDENCE_CONFLICT"]
    assert plan["ci"]["lane_state"] == "RUNNABLE"  # sibling unaffected
    # Positive control: an independent principal makes IV runnable.
    plan_ok = plan_for(env, resolution_for(
        tmp_path, [bound_entry("IV-A", "github:someone"),
                   bound_entry("IV-B", "github:iv-b-user")]))
    assert plan_ok["iv"]["lane_state"] == "RUNNABLE"
    assert plan_ok["iv"]["verifiers"] == ["IV-B"]


def test_stale_iv_binding_after_freeze_blocks_iv(tmp_path):
    env = frozen_env()
    # Verifier deactivated / principal unbound after the freeze: BLOCKED,
    # never idle silence.
    deactivated = resolution_for(tmp_path, [bound_entry("IV-A", "github:iv-a-user",
                                                        active=False)])
    plan = plan_for(env, deactivated)
    assert plan["iv"]["lane_state"] == "BLOCKED"
    assert plan["iv"]["reasons"] == ["VERIFIER_IDENTITY_UNBOUND"]
    # Positive control: reactivated binding is runnable again.
    plan_ok = plan_for(env, bound_resolution(tmp_path))
    assert plan_ok["iv"]["lane_state"] == "RUNNABLE"


def test_invalid_pool_blocks_iv_with_pool_invalid(tmp_path):
    env = frozen_env()
    bad = tmp_path / "verifiers.json"
    bad.write_text("{broken", encoding="utf-8")
    pool = verifiers_mod.resolve_pool(None, path=bad, repo=REPO)
    assert pool.pool_invalid
    plan = plan_for(env, pool)
    assert plan["iv"]["lane_state"] == "BLOCKED"
    assert plan["iv"]["reasons"] == ["VERIFIER_POOL_INVALID"]
    assert plan["ci"]["lane_state"] == "RUNNABLE"


def test_lane_failure_does_not_reclassify_sibling(tmp_path):
    # Structural independence: an explicitly BLOCKED CI lane never demotes a
    # RUNNABLE IV lane, and vice versa. The executor operates on the plan as
    # given — neither lane's outcome is computed from the other.
    env = frozen_env()
    pool = bound_resolution(tmp_path)
    plan = plan_for(env, pool)
    plan["ci"] = {"lane_state": "BLOCKED", "reasons": ["CANDIDATE_NOT_FROZEN"]}
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "BLOCKED"
    assert result["iv"]["outcome"] == "REQUESTED"

    env2 = frozen_env()
    plan2 = plan_for(env2, pool)
    plan2["iv"] = {"lane_state": "BLOCKED", "reasons": ["VERIFIER_IDENTITY_UNBOUND"]}
    result2 = execute(env2, plan2, profile())
    assert result2["iv"]["outcome"] == "BLOCKED"
    assert result2["ci"]["outcome"] == "DISPATCHED"
    assert env2.dispatched == [("ci.yml", "branch-10")]


def test_duplicate_invocation_is_idempotent(tmp_path):
    env = frozen_env()
    pool = bound_resolution(tmp_path)
    profile_full = profile()
    plan = plan_for(env, pool)
    first = execute(env, plan, profile_full)
    assert first["ci"]["outcome"] == "DISPATCHED"
    assert first["iv"]["outcome"] == "REQUESTED"
    # Live state now reflects both dispatches: a queued CI run appears and
    # the IV_REQUEST event is on the bus.
    env.runs[H1] = [{"id": 77, "created_at": "2026-09-01T11:00:00Z",
                     "status": "queued"}]
    plan2 = plan_for(env, pool)
    assert plan2["ci"]["lane_state"] == "ALREADY_RUNNING"
    assert plan2["iv"]["lane_state"] == "ALREADY_RUNNING"
    assert plan2["iv"]["request_id"].startswith("evt-")
    second = execute(env, plan2, profile_full)
    assert second["ci"]["outcome"] == "ALREADY_RUNNING"
    assert second["iv"]["outcome"] == "ALREADY_RUNNING"
    assert len(env.dispatched) == 1 and len(env.gh_calls) == 1


def test_head_move_between_plan_and_execute_blocks_all_mutation(tmp_path):
    env = frozen_env()
    plan = plan_for(env, bound_resolution(tmp_path))
    assert plan["ci"]["lane_state"] == "RUNNABLE"
    assert plan["iv"]["lane_state"] == "RUNNABLE"
    env.prs[0]["headRefOid"] = H2  # candidate moved after planning
    env.commits[H2] = {"sha": H2, "commit": {"tree": {"sha": T2}}}

    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "HEAD_MOVED"
    assert result["iv"]["outcome"] == "HEAD_MOVED"
    assert env.mutation_count == 0


def test_dry_run_reports_would_and_mutates_nothing(tmp_path):
    env = frozen_env()
    plan = plan_for(env, bound_resolution(tmp_path))
    result = execute(env, plan, profile(), dry_run=True)
    assert result["dry_run"] is True
    assert result["ci"]["outcome"] == "WOULD_DISPATCH"
    assert result["ci"]["workflow_id"] == "ci.yml"
    assert result["iv"]["outcome"] == "WOULD_REQUEST"
    assert env.mutation_count == 0
    # Deterministic: two dry-run executions are byte-identical.
    again = execute(env, plan, profile(), dry_run=True)
    assert json.dumps(result, sort_keys=True) == json.dumps(again, sort_keys=True)


def test_dry_run_still_denies_without_capability(tmp_path):
    env = frozen_env()
    plan = plan_for(env, bound_resolution(tmp_path))
    result = execute(env, plan, profile(ci_dispatch=False), dry_run=True)
    assert result["ci"]["outcome"] == "PERMISSION_DENIED"
    assert "CAPABILITY_MISSING:ci_dispatch" in result["ci"]["reasons"]
    assert env.mutation_count == 0


def test_plan_is_deterministic_and_reasons_sorted(tmp_path):
    env = frozen_env()
    env.runs[H1] = [{"id": 9, "created_at": "2026-09-01T09:00:00Z",
                     "status": "in_progress"}]
    pool = resolution_for(
        tmp_path, [bound_entry("IV-B", None), bound_entry("IV-A", None)])
    plan1 = plan_for(env, pool)
    plan2 = plan_for(env, pool)
    assert json.dumps(plan1, sort_keys=True) == json.dumps(plan2, sort_keys=True)
    assert plan1["iv"]["reasons"] == ["VERIFIER_IDENTITY_UNBOUND"]


# -- executor permission + ownership -----------------------------------------


def test_inactive_agent_denied_zero_mutation(tmp_path):
    env = frozen_env()
    plan = plan_for(env, bound_resolution(tmp_path))
    result = execute(env, plan, profile(active=False))
    assert result["ci"]["outcome"] == "PERMISSION_DENIED"
    assert result["ci"]["reasons"] == ["AGENT_INACTIVE"]
    assert result["iv"]["outcome"] == "PERMISSION_DENIED"
    assert env.mutation_count == 0


def test_missing_ci_capability_denies_only_ci(tmp_path):
    env = frozen_env()
    plan = plan_for(env, bound_resolution(tmp_path))
    result = execute(env, plan, profile(ci_dispatch=False))
    assert result["ci"]["outcome"] == "PERMISSION_DENIED"
    assert "CAPABILITY_MISSING:ci_dispatch" in result["ci"]["reasons"]
    # The IV lane is a sibling: the CI denial does not reclassify it.
    assert result["iv"]["outcome"] == "REQUESTED"
    assert len(env.gh_calls) == 1


def test_missing_iv_event_permission_denies_only_iv(tmp_path):
    env = frozen_env()
    plan = plan_for(env, bound_resolution(tmp_path))
    result = execute(env, plan, profile(iv_request=False))
    assert result["iv"]["outcome"] == "PERMISSION_DENIED"
    assert any(r.startswith("EVENT_NOT_PERMITTED") for r in result["iv"]["reasons"])
    assert result["ci"]["outcome"] == "DISPATCHED"


def test_foreign_lane_owner_blocks_dispatch_fail_closed(tmp_path):
    env = frozen_env()
    claim = make_event("evt-claim-1", "OWNER_CLAIMED", actor="other-agent")
    env.comments.extend(comments_with(claim))
    plan = plan_for(env, bound_resolution(tmp_path))
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "PERMISSION_DENIED"
    assert result["ci"]["reasons"] == ["OWNERSHIP_MUTEX_HELD_BY:other-agent"]
    assert result["iv"]["outcome"] == "PERMISSION_DENIED"
    assert env.mutation_count == 0
    # Positive control: the lane owner dispatches freely.
    env_owner = frozen_env()
    own_claim = make_event("evt-claim-2", "OWNER_CLAIMED", actor=AGENT)
    env_owner.comments.extend(comments_with(own_claim))
    plan_owner = plan_for(env_owner, bound_resolution(tmp_path))
    result_owner = execute(env_owner, plan_owner, profile())
    assert result_owner["ci"]["outcome"] == "DISPATCHED"
    assert result_owner["iv"]["outcome"] == "REQUESTED"


def test_ambiguous_ownership_fails_closed(tmp_path):
    env = frozen_env()
    for actor in ("agent-x", "agent-y"):
        env.comments.extend(comments_with(
            make_event(f"evt-claim-{actor}", "OWNER_CLAIMED", actor=actor)))
    plan = plan_for(env, bound_resolution(tmp_path))
    result = execute(env, plan, profile())
    assert result["ci"]["outcome"] == "PERMISSION_DENIED"
    assert result["ci"]["reasons"] == ["OWNERSHIP_AMBIGUOUS_FAIL_CLOSED"]
    assert env.mutation_count == 0


# -- model-level: node dispatch field -----------------------------------------


def test_snapshot_frozen_node_carries_dispatch_plan(tmp_path):
    pool_path = tmp_path / "verifiers.json"
    pool_path.write_text(json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1",
                                     "version": 1, "verifiers": BOUND_POOL}),
                         encoding="utf-8")
    env = frozen_env()
    snapshot = build_snapshot(FakeClient(env), pool_path=pool_path)
    node = snapshot["nodes"][0]
    assert node["frozen"] is True
    assert node["dispatch"]["pr"] == 10
    assert node["dispatch"]["ci"]["lane_state"] == "RUNNABLE"
    assert node["dispatch"]["iv"]["lane_state"] == "RUNNABLE"
    errors = list(validator_for("dag_snapshot_v1.schema.json").iter_errors(snapshot))
    assert errors == [], "; ".join(
        f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors)


def test_snapshot_unfrozen_node_dispatch_is_null(tmp_path):
    env = FakeEnv()
    env.add_pr(10, H1, T1, author="someone")
    env.add_issue(comments=[])  # no freeze event: not frozen
    snapshot = build_snapshot(FakeClient(env))
    node = snapshot["nodes"][0]
    assert node["frozen"] is False
    assert node["dispatch"] is None


def test_snapshot_frozen_unbound_pool_dispatch_iv_blocked(tmp_path):
    env = frozen_env()
    snapshot = build_snapshot(FakeClient(env))  # committed registry: unbound
    node = snapshot["nodes"][0]
    assert node["dispatch"]["iv"]["lane_state"] == "BLOCKED"
    assert node["dispatch"]["iv"]["reasons"] == ["VERIFIER_IDENTITY_UNBOUND"]
    assert node["dispatch"]["ci"]["lane_state"] == "RUNNABLE"


# -- CLI ----------------------------------------------------------------------


def _write_registry(tmp_path: Path, agent_profile: dict) -> Path:
    path = tmp_path / "agents.json"
    path.write_text(json.dumps({
        "schema": "ATLAS_AGENT_REGISTRY_V1",
        "registry_id": "test-registry",
        "version": 1,
        "agents": [agent_profile],
    }), encoding="utf-8")
    return path


def test_cli_dispatch_status_json_any_agent(tmp_path, monkeypatch, capsys):
    env = frozen_env()
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: FakeClient(env))
    argv = ["--repo", REPO, "--json", "dispatch-status", "--pr", "10"]
    assert cli_mod.main(argv) == 0
    first = capsys.readouterr().out
    assert cli_mod.main(argv) == 0
    assert capsys.readouterr().out == first  # byte-identical
    plan = json.loads(first)
    assert plan["pr"] == 10
    assert plan["ci"]["lane_state"] == "RUNNABLE"
    assert plan["iv"]["lane_state"] == "BLOCKED"
    assert plan["iv"]["reasons"] == ["VERIFIER_IDENTITY_UNBOUND"]
    assert env.mutation_count == 0  # read-only


def test_cli_dispatch_dry_run_zero_mutation(tmp_path, monkeypatch, capsys):
    env = frozen_env()
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: FakeClient(env))
    registry = _write_registry(tmp_path, profile())
    pool = tmp_path / "verifiers.json"
    pool.write_text(json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1", "version": 1,
                                "verifiers": BOUND_POOL}), encoding="utf-8")
    rc = cli_mod.main(["--repo", REPO, "--registry", str(registry),
                       "--verifier-registry", str(pool), "--json",
                       "dispatch", "--pr", "10", "--agent", AGENT, "--dry-run"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["result"]["ci"]["outcome"] == "WOULD_DISPATCH"
    assert out["result"]["iv"]["outcome"] == "WOULD_REQUEST"
    assert env.mutation_count == 0


def test_cli_dispatch_executes_permitted_lanes(tmp_path, monkeypatch, capsys):
    env = frozen_env()
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: FakeClient(env))
    registry = _write_registry(tmp_path, profile())
    pool = tmp_path / "verifiers.json"
    pool.write_text(json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1", "version": 1,
                                "verifiers": BOUND_POOL}), encoding="utf-8")
    rc = cli_mod.main(["--repo", REPO, "--registry", str(registry),
                       "--verifier-registry", str(pool), "--json",
                       "dispatch", "--pr", "10", "--agent", AGENT])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["result"]["ci"]["outcome"] == "DISPATCHED"
    assert out["result"]["iv"]["outcome"] == "REQUESTED"
    assert len(env.dispatched) == 1 and len(env.gh_calls) == 1


def test_cli_dispatch_unknown_agent_fails_closed(tmp_path, monkeypatch, capsys):
    env = frozen_env()
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: FakeClient(env))
    registry = _write_registry(tmp_path, profile())
    rc = cli_mod.main(["--repo", REPO, "--registry", str(registry),
                       "dispatch", "--pr", "10", "--agent", "ghost"])
    assert rc == 1
    assert "UNKNOWN_AGENT" in capsys.readouterr().err
    assert env.mutation_count == 0


def test_cli_dispatch_wrong_repo_identity_fails(tmp_path, monkeypatch, capsys):
    env = frozen_env()
    registry = _write_registry(tmp_path, profile())

    class _WrongRepoClient(FakeClient):
        def __init__(self, env):
            super().__init__(env)
            self.repo = "intruder/other-repo"

    monkeypatch.setattr(cli_mod, "GhClient",
                        lambda repo=None: _WrongRepoClient(env))
    rc = cli_mod.main(["--repo", "intruder/other-repo", "--registry",
                       str(registry), "dispatch", "--pr", "10",
                       "--agent", AGENT, "--expect-repo", REPO])
    assert rc == 1
    assert "WRONG_REPOSITORY_IDENTITY" in capsys.readouterr().err
    assert env.mutation_count == 0
