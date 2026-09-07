"""Offline adversarial tests for the atlas-dag coordinator.

Covers acceptance-matrix rows DAG/OWN/IV/CI/MG/EV with a fake `gh` runner —
no live network. Each scenario pins exact heads/trees; any evidence attached
to a different head must be demoted to predecessor (DAG-005).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import events as events_mod  # noqa: E402
from atlas_dag.gh import GhClient  # noqa: E402
from atlas_dag.model import build_snapshot  # noqa: E402

MAIN_SHA = "1" * 40
MAIN_TREE = "2" * 40
H1 = "a" * 40
T1 = "b" * 40
H2 = "c" * 40
T2 = "d" * 40
H3 = "e" * 40
T3 = "f" * 40

POOL_BODY = (
    "```json\n"
    + json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1", "verifiers": ["IV-A", "IV-B"]})
    + "\n```"
)


def make_event(event_id, event, *, ts="2026-09-01T00:00:00Z", pr=None, head=None,
               actor="agent-main", role="COORDINATOR", state="FROZEN", lane=None,
               dependencies=None):
    return {
        "schema": "ATLAS_EVENT_V1",
        "event_id": event_id,
        "timestamp_utc": ts,
        "actor": actor,
        "role": role,
        "session_id": f"sess-{actor}",
        "lane": lane or (f"pr/{pr}" if pr is not None else "main"),
        "pr": pr,
        "head": head,
        "event": event,
        "state": state,
        "dependencies": dependencies or [],
        "evidence": [],
        "invalidates": [],
        "next_actions": [],
    }


def make_receipt(receipt_id, *, pr=10, head=H1, tree=T1, verifier="IV-A",
                 session="sess-iv-a-1", author_conflict=False, writes=0,
                 result="PASS", p0=0, p1=0, p2=0, claim="PASS", independence="PASS",
                 ts="2026-09-01T01:00:00Z"):
    return {
        "schema": "ATLAS_IV_RECEIPT_V1",
        "receipt_id": receipt_id,
        "timestamp_utc": ts,
        "pr": pr,
        "head": head,
        "tree": tree,
        "verifier_id": verifier,
        "session_id": session,
        "candidate_author_conflict": author_conflict,
        "write_activity_count": writes,
        "result": result,
        "p0": p0,
        "p1": p1,
        "p2": p2,
        "claim_integrity": claim,
        "formal_independence": independence,
        "findings": [],
        "evidence": ["evidence://local"],
    }


def fenced(payload):
    return "```json\n" + json.dumps(payload) + "\n```"


def comments_with(*payloads):
    return [{"body": fenced(p)} for p in payloads]


class FakeEnv:
    """Recorded GitHub state keyed by the gh argument patterns GhClient emits."""

    def __init__(self):
        self.data = {
            "default_branch": "main",
            ("branch", "main"): {
                "commit": {"sha": MAIN_SHA, "commit": {"tree": {"sha": MAIN_TREE}}}
            },
            "prs": [],
            "dag_issue": None,
            "fail": set(),
        }
        self.commits = {}
        self.runs = {}
        self.reviews = {}
        self.issue_body = ""
        self.comments = []

    def add_pr(self, number, head, tree, *, mergeable="MERGEABLE"):
        self.data["prs"].append({
            "number": number, "title": f"PR {number}", "author": {"login": "someone"},
            "isDraft": False, "headRefName": f"branch-{number}", "headRefOid": head,
            "baseRefName": "main", "mergeable": mergeable, "url": f"https://example/{number}",
            "updatedAt": "2026-09-01T00:00:00Z",
        })
        self.commits[head] = {"sha": head, "commit": {"tree": {"sha": tree}}}

    def add_ci(self, head, run_id=101, conclusion="success", status="completed"):
        self.runs.setdefault(head, []).append({
            "id": run_id, "created_at": "2026-09-01T10:00:00Z",
            "status": status, "conclusion": conclusion,
        })

    def add_issue(self, number=1, body=POOL_BODY, comments=None):
        self.data["dag_issue"] = {"number": number, "title": "Atlas Autonomous DAG Control",
                                  "state": "OPEN"}
        self.issue_body = body
        self.comments = comments or []

    def key_for(self, args):
        if args[0] == "api" and args[1].startswith(f"repos/{REPO}"):
            rest = args[1][len(f"repos/{REPO}/"):]
            if not rest.startswith("branches") and not rest.startswith(("commits", "actions", "pulls", "issues")):
                return "default_branch"
            if rest.startswith("branches/"):
                return ("branch", rest.split("/", 1)[1])
            if rest.startswith("commits/"):
                return ("commit", rest.split("/", 1)[1])
            if rest.startswith("actions/runs"):
                sha = rest.split("head_sha=")[1].split("&")[0]
                return ("runs", sha)
            if rest.startswith("pulls/") and "comments" in rest:
                return ("reviews", int(rest.split("/")[1]))
            if rest.startswith("issues/") and "comments" in rest:
                return ("comments", int(rest.split("/")[1]))
            if rest.startswith("issues/"):
                return ("issue_body", int(rest.split("/")[1]))
            return "default_branch"
        if args[:2] == ["pr", "list"]:
            return "prs"
        if args[:2] == ["issue", "list"]:
            return "dag_issue"
        raise AssertionError(f"unexpected gh args: {args}")

    def runner(self):
        def _run(argv, **_kw):
            args = argv[1:]
            key = self.key_for(args)
            if key in self.data["fail"]:
                return _completed(argv, 1, "", "simulated gh failure")
            if key == "default_branch":
                if key in self.data["fail"]:
                    return _completed(argv, 1, "", "boom")
                return _completed(argv, 0, self.data.get("default_branch") or "", "")
            if key == "prs":
                return _completed(argv, 0, json.dumps(self.data["prs"]), "")
            if key == "dag_issue":
                issue = self.data["dag_issue"]
                return _completed(argv, 0, json.dumps([issue] if issue else []), "")
            if isinstance(key, tuple):
                kind, arg = key
                if kind == "branch":
                    val = self.data.get(key)
                elif kind == "commit":
                    val = self.commits.get(arg)
                elif kind == "runs":
                    val = {"workflow_runs": self.runs.get(arg, [])}
                elif kind == "reviews":
                    val = self.reviews.get(arg, [])
                elif kind == "comments":
                    val = self.comments
                elif kind == "issue_body":
                    return _completed(argv, 0, self.issue_body, "")
                else:
                    val = None
                if val is None:
                    return _completed(argv, 1, "", f"missing fixture for {key}")
                return _completed(argv, 0, json.dumps(val), "")
            raise AssertionError(f"unhandled key: {key}")

        return _run


def _completed(argv, code, stdout, stderr):
    import subprocess
    return subprocess.CompletedProcess(argv, code, stdout, stderr)


REPO = "B0LK13/project-atlas"


def make_client(env):
    return GhClient(repo=REPO, runner=env.runner())


def base_env(*, with_pool=True):
    env = FakeEnv()
    env.add_pr(10, H1, T1)
    env.add_pr(11, H2, T2)
    env.add_ci(H1)
    env.add_ci(H2)
    if with_pool:
        env.add_issue(body=POOL_BODY)
    return env


def node_for(snapshot, pr):
    return next(n for n in snapshot["nodes"] if n["pr"] == pr)


# -- event stream (EV-*) ---------------------------------------------------

def test_ev001_duplicate_event_id_is_idempotent():
    env = base_env()
    ev = make_event("evt-dup-001", "OWNER_CLAIMED", pr=10, actor="agent-x")
    env.comments = comments_with(ev, dict(ev))
    result = events_mod.ingest_comments(env.comments)
    assert len(result.events) == 1


def test_ev002_reordered_events_are_canonically_ordered():
    env = base_env()
    late = make_event("evt-b-long01", "OWNER_CLAIMED", ts="2026-09-02T00:00:00Z", pr=10)
    early = make_event("evt-a-long01", "OWNER_CLAIMED", ts="2026-09-01T00:00:00Z", pr=11)
    result = events_mod.ingest_comments(comments_with(late, early))
    assert [e["event_id"] for e in result.events] == ["evt-a-long01", "evt-b-long01"]


def test_ev003_stable_state_noise_rejected():
    env = base_env()
    noise = make_event("evt-noise01", "NO_CHANGE", pr=10, state="UNCHANGED")
    result = events_mod.ingest_comments(comments_with(noise))
    assert result.events == []
    # NO_CHANGE is not an allowed transition at all; either the schema enum or
    # the explicit noise filter rejects it.
    assert any("stable-state" in reason or "not one of" in reason
               for _m, reason in result.invalid)


def test_ev_invalid_schema_reported_not_fatal():
    env = base_env()
    bad = {"schema": "ATLAS_EVENT_V1", "event_id": "x"}  # missing required fields
    result = events_mod.ingest_comments(comments_with(bad))
    assert result.events == []
    assert len(result.invalid) == 1


# -- formal IV (IV-*) -------------------------------------------------------

def test_iv003_distinct_verifier_exact_head_eligible_and_gate_passes():
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-ok"))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["formal_iv"] == "rcpt-iv-ok"
    assert node["gate"]["merge_gate"] == "PASS"
    assert node["state"] == "MERGE_ELIGIBLE"


def test_iv001_author_conflict_rejected():
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-bad", author_conflict=True))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["formal_iv"] is None
    assert node["gate"]["merge_gate"] == "FAIL"
    assert any(r.startswith("FORMAL_IV_REJECTED") for r in node["gate"]["reasons"])


def test_iv002_same_session_fresh_worktree_rejected():
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-sess", independence="FAIL"))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["formal_iv"] is None
    assert node["gate"]["merge_gate"] == "FAIL"


def test_iv004_stale_head_receipt_rejected_and_marked_history():
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-old", head=H3, tree=T3))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["formal_iv"] is None
    assert node["gate"]["merge_gate"] == "FAIL"


def test_verifier_pool_undefined_fails_closed():
    env = base_env(with_pool=False)
    env.add_issue(body="no pool here")
    env.comments = comments_with(make_receipt("rcpt-iv-ok"))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["formal_iv"] is None
    assert node["gate"]["merge_gate"] == "FAIL"


def test_unapproved_verifier_rejected():
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-rogue", verifier="IV-ROGUE"))
    snapshot = build_snapshot(make_client(env))
    assert node_for(snapshot, 10)["formal_iv"] is None


# -- CI gate (CI-*) ----------------------------------------------------------

def test_ci001_ci_pass_iv_missing_gate_fail():
    env = base_env()
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["ci_status"] == "PASS"
    assert node["gate"]["merge_gate"] == "FAIL"
    assert "FORMAL_IV_MISSING" in node["gate"]["reasons"]


def test_ci002_claim_integrity_fail_gate_fail():
    env = base_env()
    env.comments = comments_with(
        make_receipt("rcpt-iv-ok"),
        make_event("evt-claim-fail", "CLAIM_INTEGRITY_CHANGED", pr=10, state="FAIL"),
    )
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["claim_integrity"] == "FAIL"
    assert node["gate"]["merge_gate"] == "FAIL"
    assert any(r.startswith("CLAIM_INTEGRITY_NOT_PASS") for r in node["gate"]["reasons"])


def test_ci003_p1_open_gate_fail():
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-p1", p1=1))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["gate"]["merge_gate"] == "FAIL"
    assert "P1_OPEN" in node["gate"]["reasons"]


def test_ci_fail_not_pass():
    env = base_env()
    env.runs[H1] = [{"id": 102, "created_at": "2026-09-01T11:00:00Z",
                     "status": "completed", "conclusion": "failure"}]
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["ci_status"] == "FAIL"
    assert node["gate"]["merge_gate"] == "FAIL"


# -- merge guardian (MG-*) ----------------------------------------------------

def test_mg001_prospective_merge_receipt_not_accepted():
    env = base_env()
    env.comments = comments_with(
        make_receipt("rcpt-iv-ok"),
        make_event("evt-merged-fake", "MERGED", pr=10, state="MERGED"),
    )
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["gate"]["merge_gate"] == "FAIL"
    assert any(r.startswith("MERGE_RECEIPT_UNPROVEN") for r in node["gate"]["reasons"])


def test_gate_fails_when_not_mergeable():
    env = base_env()
    env.data["prs"][0]["mergeable"] = "CONFLICTING"
    env.comments = comments_with(make_receipt("rcpt-iv-ok"))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["gate"]["merge_gate"] == "FAIL"
    assert any(r.startswith("MERGEABILITY") for r in node["gate"]["reasons"])


# -- frontier / lanes (DAG-*) --------------------------------------------------

def test_dag001_waiting_lane_does_not_block_runnable_lane():
    env = base_env()
    env.comments = comments_with(
        make_receipt("rcpt-iv-11-fail", pr=11, head=H2, tree=T2, result="FAIL"),
        make_event("evt-claim-11", "CLAIM_INTEGRITY_CHANGED", pr=11, state="FAIL"),
        make_event("evt-gate-11", "HUMAN_GATE_REQUIRED", pr=11, state="FROZEN"),
    )
    snapshot = build_snapshot(make_client(env))
    n10, n11 = node_for(snapshot, 10), node_for(snapshot, 11)
    assert n10["state"] in ("RUNNABLE_READONLY", "RUNNABLE_WRITE")
    assert n11["state"] == "FROZEN"
    assert "IV" in n11["waiting_on"]
    assert snapshot["safe_runnable_count"] >= 1


def test_dag005_head_move_invalidates_exact_head_evidence():
    env = base_env()
    # Candidate head moves H1 -> H3; old CI + old IV attach to H1 only.
    env.data["prs"][0]["headRefOid"] = H3
    env.commits[H3] = {"sha": H3, "commit": {"tree": {"sha": T3}}}
    env.comments = comments_with(make_receipt("rcpt-iv-old-head", head=H1, tree=T1))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["head"] == H3
    assert node["ci_status"] == "NONE"  # old-head CI demoted to predecessor
    assert node["formal_iv"] is None  # old-head IV demoted to predecessor
    assert "rcpt-iv-old-head" not in [node["formal_iv"]]
    assert node["gate"]["merge_gate"] == "FAIL"
    assert "evt" not in node["stale_events"]  # no events posted for pr 10 here
    assert node["gate"]["reasons"]  # deterministic non-empty reasons


def test_dag006_no_active_writer_inference_without_owner_event():
    env = base_env()
    snapshot = build_snapshot(make_client(env))
    for node in snapshot["nodes"]:
        assert node["owner"] is None  # worktree presence is not ownership evidence


def test_fail_closed_when_github_unavailable():
    env = base_env()
    env.data["fail"].add("default_branch")
    env.data["fail"].add(("branch", "main"))
    env.data["fail"].add("prs")
    env.data["dag_issue"] = None
    snapshot = build_snapshot(make_client(env))
    assert snapshot["main_head"] == "UNKNOWN"
    assert snapshot["nodes"] == []
    assert snapshot["safe_runnable_count"] == 0


# -- ownership (OWN-*) ----------------------------------------------------------

def test_own001_owner_claim_tracked_and_released():
    env = base_env()
    env.comments = comments_with(
        make_event("evt-claim", "OWNER_CLAIMED", pr=10, actor="agent-x"),
        make_event("evt-release", "OWNER_RELEASED", pr=10, actor="agent-x",
                   ts="2026-09-02T00:00:00Z"),
    )
    snapshot = build_snapshot(make_client(env))
    assert node_for(snapshot, 10)["owner"] is None


def test_own001b_active_owner_recorded():
    env = base_env()
    env.comments = comments_with(make_event("evt-claim", "OWNER_CLAIMED", pr=10, actor="agent-x"))
    snapshot = build_snapshot(make_client(env))
    assert node_for(snapshot, 10)["owner"] == "agent-x"
    assert node_for(snapshot, 10)["state"] == "RUNNABLE_WRITE"


def test_own002_unowned_node_is_claimable():
    env = base_env()
    snapshot = build_snapshot(make_client(env))
    assert node_for(snapshot, 10)["owner"] is None
    assert node_for(snapshot, 10)["state"] == "RUNNABLE_READONLY"


# -- determinism -----------------------------------------------------------------

def test_snapshot_deterministic_for_fixed_clock():
    env = base_env()
    env.comments = comments_with(
        make_event("evt-claim", "OWNER_CLAIMED", pr=10, actor="agent-x"),
        make_receipt("rcpt-iv-ok"),
    )
    client = make_client(env)
    clock = lambda: "2026-09-07T00:00:00Z"  # noqa: E731
    first = build_snapshot(client, clock=clock)
    second = build_snapshot(client, clock=clock)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_snapshot_conforms_to_dag_snapshot_schema():
    from atlas_dag.events import validator_for
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-ok"))
    snapshot = build_snapshot(make_client(env))
    validator = validator_for("dag_snapshot_v1.schema.json")
    errors = list(validator.iter_errors(snapshot))
    assert errors == [f"{e.message} at {'/'.join(map(str, e.path))}" for e in errors]


@pytest.mark.parametrize("status,conclusion,expected", [
    ("completed", "success", "PASS"),
    ("completed", "failure", "FAIL"),
    ("in_progress", None, "PENDING"),
])
def test_ci_status_reduction(status, conclusion, expected):
    from atlas_dag.model import ci_status_for_head
    result, _run_id = ci_status_for_head(
        [{"id": 1, "created_at": "2026-09-01T00:00:00Z", "status": status,
          "conclusion": conclusion}]
    )
    assert result == expected
