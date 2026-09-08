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
    + json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1", "verifiers": [
        {"verifier_id": "IV-A", "principal": "github:iv-a-user"},
        {"verifier_id": "IV-B", "principal": "github:iv-b-user"},
    ]})
    + "\n```"
)

BARE_POOL_BODY = (
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


def comments_with(*payloads, author="iv-a-user"):
    return [
        {"body": fenced(p), "id": 1000 + i,
         "user": {"login": author}, "html_url": f"https://example/comment/{1000 + i}"}
        for i, p in enumerate(payloads)
    ]


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
        if "--paginate" in args:
            args = [a for a in args if a != "--paginate"]
        if args[0] == "api" and args[1].startswith(f"repos/{REPO}"):
            rest = args[1][len(f"repos/{REPO}/"):]
            kinds = ("branches", "commits", "actions", "pulls", "issues")
            if not rest.startswith(kinds):
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
    late = make_event("evt-b-long01", "OWNER_CLAIMED", ts="2026-09-02T00:00:00Z", pr=10)
    early = make_event("evt-a-long01", "OWNER_CLAIMED", ts="2026-09-01T00:00:00Z", pr=11)
    result = events_mod.ingest_comments(comments_with(late, early))
    assert [e["event_id"] for e in result.events] == ["evt-a-long01", "evt-b-long01"]


def test_ev003_stable_state_noise_rejected():
    noise = make_event("evt-noise01", "NO_CHANGE", pr=10, state="UNCHANGED")
    result = events_mod.ingest_comments(comments_with(noise))
    assert result.events == []
    # NO_CHANGE is not an allowed transition at all; either the schema enum or
    # the explicit noise filter rejects it.
    assert any("stable-state" in reason or "not one of" in reason
               for _m, reason in result.invalid)


def test_ev_invalid_schema_reported_not_fatal():
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
    assert "VERIFIER_POOL_UNDEFINED" in node["rejected_receipts"]["rcpt-iv-ok"]


def test_unapproved_verifier_rejected():
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-rogue", verifier="IV-ROGUE"))
    snapshot = build_snapshot(make_client(env))
    assert node_for(snapshot, 10)["formal_iv"] is None


# -- trusted identity (D-PR720 §3/§4) -----------------------------------------

def test_bare_label_pool_is_unbound_and_fails_closed():
    # Bare-string pool entries are DECLARED_BUT_UNBOUND: parseable, never formal IV.
    env = base_env()
    env.add_issue(body=BARE_POOL_BODY)
    env.comments = comments_with(make_receipt("rcpt-iv-bare"))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["formal_iv"] is None
    assert "VERIFIER_IDENTITY_UNBOUND" in node["rejected_receipts"]["rcpt-iv-bare"]


def test_receipt_from_untrusted_principal_rejected():
    # Schema-valid receipt posted by a GitHub login that is not the bound
    # principal must not impersonate the verifier.
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-iv-mallory"), author="mallory")
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["formal_iv"] is None
    assert "PRINCIPAL_MISMATCH" in node["rejected_receipts"]["rcpt-iv-mallory"]


def test_unknown_candidate_tree_fails_closed():
    # Transient commit-lookup failure => tree None => receipt must be rejected,
    # never eligible via head-only identity.
    env = base_env()
    env.data["fail"].add(("commit", H1))
    env.comments = comments_with(make_receipt("rcpt-iv-ok"))
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["tree"] is None
    assert node["formal_iv"] is None
    assert "CANDIDATE_TREE_UNKNOWN" in node["rejected_receipts"]["rcpt-iv-ok"]
    assert node["gate"]["merge_gate"] == "FAIL"


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


def test_dag002_ci_pending_lane_still_runnable_for_readonly_diagnosis():
    env = base_env()
    env.runs[H1] = [{"id": 102, "created_at": "2026-09-01T10:05:00Z",
                     "status": "in_progress", "conclusion": None}]
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["state"] == "RUNNABLE_READONLY"  # read-only diagnosis stays safe
    assert "CI" in node["waiting_on"]  # waiting is lane-local annotation
    assert node["gate"]["merge_gate"] == "FAIL"
    assert any(r.startswith("EXACT_HEAD_CI_NOT_PASS") for r in node["gate"]["reasons"])


def test_dag003_owner_gated_lane_does_not_block_unrelated_lane():
    env = base_env()
    env.comments = comments_with(
        make_event("evt-claim-10", "OWNER_CLAIMED", pr=10, actor="agent-x"),
    )
    snapshot = build_snapshot(make_client(env))
    n10, n11 = node_for(snapshot, 10), node_for(snapshot, 11)
    assert n10["owner"] == "agent-x"
    assert n10["state"] == "RUNNABLE_WRITE"
    assert "OWNER" not in n10["waiting_on"]
    assert n11["owner"] is None
    assert n11["state"] == "RUNNABLE_READONLY"


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
    assert snapshot["main_head"] is None
    assert snapshot["nodes"] == []
    assert snapshot["safe_runnable_count"] == 0


def test_fail_closed_snapshot_still_validates_against_schema():
    from atlas_dag.events import validator_for
    env = base_env()
    env.data["fail"].add(("branch", "main"))
    snapshot = build_snapshot(make_client(env))
    errors = list(validator_for("dag_snapshot_v1.schema.json").iter_errors(snapshot))
    assert errors == [], "; ".join(
        f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors
    )


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
    errors = list(validator_for("dag_snapshot_v1.schema.json").iter_errors(snapshot))
    assert errors == [], "; ".join(
        f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors
    )


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


def test_ci_hidden_failing_run_cannot_be_laundered_by_newer_pass():
    # Adversarial: newer passing workflow run must not hide an older failure
    # on the same exact head (live #720 scenario).
    from atlas_dag.model import ci_status_for_head
    runs = [
        {"id": 1, "created_at": "2026-09-01T10:00:00Z", "status": "completed",
         "conclusion": "failure"},
        {"id": 2, "created_at": "2026-09-01T11:00:00Z", "status": "completed",
         "conclusion": "success"},
    ]
    assert ci_status_for_head(runs)[0] == "FAIL"


def test_ci_pending_run_blocks_pass():
    from atlas_dag.model import ci_status_for_head
    runs = [
        {"id": 1, "created_at": "2026-09-01T10:00:00Z", "status": "completed",
         "conclusion": "success"},
        {"id": 2, "created_at": "2026-09-01T11:00:00Z", "status": "queued",
         "conclusion": None},
    ]
    assert ci_status_for_head(runs)[0] == "PENDING"


# -- stale-head events are history only (D-PR720 §5) ----------------------------

def test_stale_old_head_claim_pass_cannot_launder_new_candidate():
    env = base_env()
    # Head moves H1 -> H3; an old-head PASS claim and old-head freeze are history.
    env.data["prs"][0]["headRefOid"] = H3
    env.commits[H3] = {"sha": H3, "commit": {"tree": {"sha": T3}}}
    env.comments = comments_with(
        make_event("evt-old-claim-pass", "CLAIM_INTEGRITY_CHANGED", pr=10,
                   head=H1, state="PASS", ts="2026-09-01T00:00:00Z"),
        make_event("evt-old-freeze", "HUMAN_GATE_REQUIRED", pr=10,
                   head=H1, state="FROZEN", ts="2026-09-01T00:01:00Z"),
    )
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["claim_integrity"] != "PASS"  # stale PASS is history only
    assert node["frozen"] is False  # stale freeze is history only
    assert node["gate"]["merge_gate"] == "FAIL"


def test_live_head_claim_event_applies_normally():
    env = base_env()
    env.comments = comments_with(
        make_event("evt-live-claim-pass", "CLAIM_INTEGRITY_CHANGED", pr=10,
                   head=H1, state="PASS"),
        make_receipt("rcpt-iv-ok"),
    )
    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["claim_integrity"] == "PASS"
    assert node["gate"]["merge_gate"] == "PASS"


# -- event bus pagination (D-PR720 §6) -------------------------------------------

def test_issue_comments_paginate_beyond_100():
    # 101 comments; the material OWNER_RELEASED arrives as comment 101.
    # gh api --paginate concatenates pages; all comments must be consumed.
    from atlas_dag.gh import GhClient
    from atlas_dag.model import ownership
    claim = make_event("evt-claim-p1", "OWNER_CLAIMED", pr=10, actor="agent-x")
    release = make_event("evt-release-p1", "OWNER_RELEASED", pr=10, actor="agent-x",
                         ts="2026-09-02T00:00:00Z")
    page1 = comments_with(*[dict(claim, event_id=f"evt-fill-{i:03d}") for i in range(100)])
    page2 = comments_with(release)
    all_comments = page1 + page2
    assert len(all_comments) == 101

    def paged_runner(argv, **_kw):
        args = [a for a in argv[1:] if a != "--paginate"]
        assert "--paginate" in argv[1:], "client must request pagination"
        if args[0] == "api" and "issues/1/comments" in args[1]:
            # simulate gh --paginate: concatenated JSON array pages
            pages = json.dumps(all_comments[:100]) + json.dumps(all_comments[100:])
            return _completed(argv, 0, pages, "")
        raise AssertionError(f"unexpected: {argv}")

    client = GhClient(repo=REPO, runner=paged_runner)
    fetched = client.issue_comments(1)
    assert len(fetched) == 101
    ingested = events_mod.ingest_comments(fetched)
    status, _actors = ownership(ingested.events, 10)
    assert status == "UNOWNED"  # the release after comment 100 was consumed


# -- ownership mutex (D-PR720 §7) --------------------------------------------------

def test_competing_owner_claims_fail_closed_and_commands_agree():
    from atlas_dag.model import ownership
    env = base_env()
    env.comments = comments_with(
        make_event("evt-claim-a", "OWNER_CLAIMED", pr=10, actor="AGENT_A"),
        make_event("evt-claim-b", "OWNER_CLAIMED", pr=10, actor="AGENT_B"),
    )
    events = events_mod.ingest_comments(env.comments).events
    status, actors = ownership(events, 10)
    assert status == "AMBIGUOUS"
    assert actors == ["AGENT_A", "AGENT_B"]

    snapshot = build_snapshot(make_client(env))
    node = node_for(snapshot, 10)
    assert node["ownership"] == "AMBIGUOUS"  # snapshot agrees with owners logic
    assert node["owner"] is None
    assert node["state"] != "RUNNABLE_WRITE"
    assert node["state"] == "RUNNABLE_READONLY"


# -- conservative evidence cache (D-009) ------------------------------------------

from atlas_dag import evidence as evidence_mod  # noqa: E402


def make_evidence(evidence_id, *, pr=10, head=H1, tree=T1, scope="CANDIDATE_WIDE",
                  producer="ci", result="PASS", negative_control="NONE",
                  covered_files=None, covered_contract="contract:api",
                  ts="2026-09-01T00:00:00Z"):
    return {
        "schema": "ATLAS_EVIDENCE_V1",
        "evidence_id": evidence_id,
        "producer": producer,
        "pr": pr,
        "head": head,
        "tree": tree,
        "environment": "linux-python3.12",
        "covered_files": covered_files if covered_files is not None else ["src/a.py"],
        "covered_contract": covered_contract,
        "result": result,
        "negative_control": negative_control,
        "scope": scope,
        "created_at_utc": ts,
    }


def store_at(tmp_path):
    return evidence_mod.EvidenceStore(tmp_path / ".atlas-runtime" / "evidence"
                                      / "evidence.json")


def test_d009_exact_head_tree_match_is_exact_head_only():
    record = make_evidence("ev-ci-exact01")
    reuse_class, reasons = evidence_mod.classify(record, H1, T1)
    assert reuse_class == "EXACT_HEAD_ONLY"
    assert reasons == ["HEAD_AND_TREE_MATCH"]


def test_d009_head_move_demotes_candidate_wide_to_predecessor():
    # Candidate-wide exact-head CI at H1; the candidate moved to H3/T3.
    record = make_evidence("ev-ci-stale01", producer="ci")
    reuse_class, reasons = evidence_mod.classify(record, H3, T3)
    assert reuse_class == "PREDECESSOR_SUPPORTING"  # history, never certification
    assert reuse_class != "EXACT_HEAD_ONLY"
    assert "HEAD_MISMATCH" in reasons


def test_d009_stale_exact_head_ci_cannot_satisfy_gate_equivalent_check():
    # Classification-only guard: a stale PASS-shaped CI record classifies as
    # predecessor supporting, so it can never stand in for the D-008 gate's
    # exact-head CI requirement (gate.py itself is untouched by D-009).
    record = make_evidence("ev-ci-pass-old", producer="ci", result="PASS")
    reuse_class, _reasons = evidence_mod.classify(record, H3, T3)
    assert reuse_class != "EXACT_HEAD_ONLY"
    import inspect as _inspect

    from atlas_dag import gate as gate_mod
    assert "ci_status" in _inspect.signature(gate_mod.evaluate).parameters


def test_d009_subsystem_reuse_after_head_move_requires_equivalence_proof():
    record = make_evidence("ev-sub-01", scope="SUBSYSTEM",
                           covered_files=["src/sub/a.py"])
    reuse_class, reasons = evidence_mod.classify(record, H3, T3)
    assert reuse_class == "PREDECESSOR_SUPPORTING"
    assert "SUBSYSTEM_REUSE_REQUIRES_EQUIVALENCE_PROOF" in reasons
    # Absence of file overlap is NOT proof: a no-op proof must not qualify.
    reuse_class, _ = evidence_mod.classify(record, H3, T3, equivalence_proof=None)
    assert reuse_class == "PREDECESSOR_SUPPORTING"


def test_d009_subsystem_with_valid_equivalence_proof_is_reusable():
    record = make_evidence("ev-sub-02", scope="SUBSYSTEM",
                           covered_files=["src/sub/a.py"])
    proof = {"covered_contract": "contract:api", "result": "PROVEN",
             "old_head": H1, "new_head": H3}
    reuse_class, reasons = evidence_mod.classify(record, H3, T3,
                                                 equivalence_proof=proof)
    assert reuse_class == "REUSABLE_SUBSYSTEM"
    assert "EQUIVALENCE_PROOF_ACCEPTED" in reasons


def test_d009_subsystem_with_callable_proof_and_wrong_contract_proof():
    record = make_evidence("ev-sub-03", scope="SUBSYSTEM")
    callable_proof = lambda _r, _h, _t: True  # noqa: E731
    assert evidence_mod.classify(record, H3, T3,
                                 equivalence_proof=callable_proof)[0] == "REUSABLE_SUBSYSTEM"
    crashing = lambda *_a: 1 / 0  # noqa: E731
    assert evidence_mod.classify(record, H3, T3,
                                 equivalence_proof=crashing)[0] == "PREDECESSOR_SUPPORTING"
    wrong_contract = {"covered_contract": "contract:OTHER", "result": "PROVEN"}
    assert evidence_mod.classify(record, H3, T3,
                                 equivalence_proof=wrong_contract)[0] == "PREDECESSOR_SUPPORTING"
    unproven = {"covered_contract": "contract:api", "result": "UNKNOWN"}
    assert evidence_mod.classify(record, H3, T3,
                                 equivalence_proof=unproven)[0] == "PREDECESSOR_SUPPORTING"


def test_d009_negative_control_failed_is_invalid():
    record = make_evidence("ev-nc-fail01", negative_control="FAIL")
    reuse_class, reasons = evidence_mod.classify(record, H1, T1)  # even at exact head
    assert reuse_class == "INVALID"
    assert reasons == ["NEGATIVE_CONTROL_FAILED"]


def test_d009_malformed_record_is_invalid_fail_closed():
    for field in ("head", "tree", "producer"):
        record = make_evidence("ev-bad-0001")
        del record[field]
        reuse_class, reasons = evidence_mod.classify(record, H1, T1)
        assert reuse_class == "INVALID"
        assert any(r == f"MISSING_FIELD:{field}" for r in reasons)
    reuse_class, reasons = evidence_mod.classify(["not", "a record"], H1, T1)
    assert reuse_class == "INVALID"
    assert reasons == ["MALFORMED_RECORD:not-an-object"]


def test_d009_unknown_scope_and_unknown_current_head_fail_closed():
    record = make_evidence("ev-scope-bad", scope="REPO_WIDE")
    reuse_class, reasons = evidence_mod.classify(record, H1, T1)
    assert reuse_class == "INVALID"
    assert any(r.startswith("UNKNOWN_SCOPE") for r in reasons)
    record = make_evidence("ev-good-0001")
    reuse_class, reasons = evidence_mod.classify(record, None, None)
    assert reuse_class == "UNKNOWN"
    assert reasons == ["CURRENT_HEAD_TREE_UNKNOWN"]


def test_d009_schema_validation_rejects_malformed_records():
    errors = evidence_mod.validate_record(make_evidence("ev-schema-ok"))
    assert errors == []
    missing_head = make_evidence("ev-schema-bad")
    del missing_head["head"]
    assert evidence_mod.validate_record(missing_head)
    bad_scope = make_evidence("ev-scope-bad2", scope="REPO_WIDE")
    assert evidence_mod.validate_record(bad_scope)


def test_d009_duplicate_evidence_id_ingestion_is_idempotent(tmp_path):
    store = store_at(tmp_path)
    first = dict(make_evidence("ev-dup-00001"), covered_files=["b.py", "a.py", "a.py"])
    added, records = store.ingest(first)
    assert added and len(records) == 1
    assert records[0]["covered_files"] == ["a.py", "b.py"]  # normalized
    again, records = store.ingest(make_evidence("ev-dup-00001", result="FAIL"))
    assert not again and len(records) == 1  # first record wins
    assert records[0]["result"] == "PASS"


def test_d009_store_output_is_deterministic_and_byte_identical(tmp_path):
    store_a, store_b = store_at(tmp_path / "a"), store_at(tmp_path / "b")
    rec_a = make_evidence("ev-det-a001", ts="2026-09-01T00:00:00Z")
    rec_b = make_evidence("ev-det-b001", ts="2026-09-02T00:00:00Z")
    for rec in (rec_a, rec_b):
        store_a.ingest(rec)
    for rec in (rec_b, rec_a):  # reversed order must not change bytes
        store_b.ingest(rec)
    assert store_a.path.read_bytes() == store_b.path.read_bytes()
    first = evidence_mod.classify(rec_a, H3, T3)
    second = evidence_mod.classify(dict(rec_a), H3, T3)
    assert first == second


class _FakeLiveClient:
    """Stand-in for GhClient in CLI evidence tests (no network)."""

    def __init__(self, env):
        self._env = env

    @property
    def repo(self):
        return REPO

    def open_prs(self):
        return self._env.data["prs"]

    def commit(self, sha):
        data = self._env.commits.get(sha)
        if not data:
            return None
        return {"sha": data["sha"], "tree": data["commit"]["tree"]["sha"]}


def test_d009_cli_evidence_classifies_against_live_head(tmp_path, monkeypatch, capsys):
    from atlas_dag import cli as cli_mod

    env = base_env()
    env.data["prs"][0]["headRefOid"] = H3
    env.commits[H3] = {"sha": H3, "commit": {"tree": {"sha": T3}}}
    store_at(tmp_path).ingest(make_evidence("ev-cli-0001"))
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: _FakeLiveClient(env))
    rc = cli_mod.main(["--runtime-dir", str(tmp_path / ".atlas-runtime"),
                       "--json", "evidence", "10"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["current_head"] == H3
    assert out["records"][0]["reuse_class"] == "PREDECESSOR_SUPPORTING"
    assert "HEAD_MISMATCH" in out["records"][0]["reasons"]


def test_d009_cli_evidence_fails_closed_when_github_unavailable(tmp_path, monkeypatch,
                                                              capsys):
    from atlas_dag import cli as cli_mod

    class _OfflineClient:
        @property
        def repo(self):
            return None

        def open_prs(self):
            return []

        def commit(self, _sha):
            return None

    store_at(tmp_path).ingest(make_evidence("ev-cli-0002"))
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: _OfflineClient())
    rc = cli_mod.main(["--runtime-dir", str(tmp_path / ".atlas-runtime"),
                       "--json", "evidence", "10"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["current_head"] is None
    assert out["records"][0]["reuse_class"] == "UNKNOWN"
    assert out["records"][0]["reasons"] == ["GITHUB_UNAVAILABLE"]


def test_d009_cli_evidence_ingest_validates_schema(tmp_path, capsys):
    from atlas_dag import cli as cli_mod

    good = tmp_path / "good.json"
    good.write_text(json.dumps(make_evidence("ev-cli-good1")), encoding="utf-8")
    rc = cli_mod.main(["--runtime-dir", str(tmp_path / ".atlas-runtime"),
                       "evidence-ingest", str(good)])
    assert rc == 0
    assert "stored" in capsys.readouterr().out

    bad = tmp_path / "bad.json"
    malformed = make_evidence("ev-cli-bad01")
    del malformed["head"]
    bad.write_text(json.dumps(malformed), encoding="utf-8")
    rc = cli_mod.main(["--runtime-dir", str(tmp_path / ".atlas-runtime"),
                       "evidence-ingest", str(bad)])
    assert rc == 1
    assert "SCHEMA" in capsys.readouterr().err
    store = store_at(tmp_path)
    assert [r["evidence_id"] for r in store.load()] == ["ev-cli-good1"]


# -- D-009 review finding set: trust-boundary remediation (PR #723) ---------------

def test_d009_dict_proof_must_be_bound_to_candidate_transition():
    record = make_evidence("ev-sub-bound1", scope="SUBSYSTEM")
    bound_proof = {"result": "PROVEN", "covered_contract": "contract:api",
                   "old_head": H1, "new_head": H3}
    # Missing old_head/new_head: accepted before the fix, must not be reusable.
    unbound = {"result": "PROVEN", "covered_contract": "contract:api"}
    reuse_class, reasons = evidence_mod.classify(record, H3, T3, equivalence_proof=unbound)
    assert reuse_class == "PREDECESSOR_SUPPORTING"
    assert "EQUIVALENCE_PROOF_NOT_BOUND" in reasons
    # old_head must name the record's stored head, not any other head.
    wrong_old = dict(bound_proof, old_head=H2)
    reuse_class, reasons = evidence_mod.classify(record, H3, T3, equivalence_proof=wrong_old)
    assert reuse_class == "PREDECESSOR_SUPPORTING"
    assert "EQUIVALENCE_PROOF_NOT_BOUND" in reasons
    # new_head must name the current candidate head being classified against.
    wrong_new = dict(bound_proof, new_head=H2)
    reuse_class, reasons = evidence_mod.classify(record, H3, T3, equivalence_proof=wrong_new)
    assert reuse_class == "PREDECESSOR_SUPPORTING"
    assert "EQUIVALENCE_PROOF_NOT_BOUND" in reasons
    # A correctly bound proof bridges the record head -> current head.
    reuse_class, reasons = evidence_mod.classify(record, H3, T3,
                                                 equivalence_proof=bound_proof)
    assert reuse_class == "REUSABLE_SUBSYSTEM"
    assert "EQUIVALENCE_PROOF_ACCEPTED" in reasons
    # Bound to the wrong covered contract is still not bound to THIS record.
    wrong_contract = dict(bound_proof, covered_contract="contract:OTHER")
    reuse_class, _reasons = evidence_mod.classify(record, H3, T3,
                                                  equivalence_proof=wrong_contract)
    assert reuse_class == "PREDECESSOR_SUPPORTING"


def test_d009_classification_validates_schema_constant_and_field_shapes():
    wrong_schema = make_evidence("ev-bad-schema1")
    wrong_schema["schema"] = "ATLAS_EVIDENCE_V9"
    reuse_class, reasons = evidence_mod.classify(wrong_schema, H1, T1)
    assert reuse_class == "INVALID"
    assert any(r.startswith("SCHEMA_MISMATCH") for r in reasons)

    bad_control = make_evidence("ev-bad-ncctl1", negative_control="MAYBE")
    reuse_class, reasons = evidence_mod.classify(bad_control, H1, T1)
    assert reuse_class == "INVALID"
    assert any(r.startswith("UNKNOWN_NEGATIVE_CONTROL") for r in reasons)

    for field in ("head", "tree"):
        malformed = make_evidence(f"ev-bad-{field}01")
        malformed[field] = "not-a-40-hex-sha"
        reuse_class, reasons = evidence_mod.classify(malformed, H1, T1)
        assert reuse_class == "INVALID"
        assert any(r == f"MALFORMED_{field.upper()}:not-a-40-hex-sha" for r in reasons)

    string_pr = make_evidence("ev-bad-prnum1")
    string_pr["pr"] = "10"  # schema requires an integer
    reuse_class, reasons = evidence_mod.classify(string_pr, H1, T1)
    assert reuse_class == "INVALID"
    assert any(r.startswith("PR_NOT_INTEGER") for r in reasons)


def test_d009_concurrent_ingest_serializes_read_modify_write(tmp_path):
    import threading

    store_path = tmp_path / ".atlas-runtime" / "evidence" / "evidence.json"
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def ingest_one(evidence_id: str) -> None:
        try:
            barrier.wait(timeout=10)
            added, _records = evidence_mod.EvidenceStore(store_path).ingest(
                make_evidence(evidence_id))
            assert added
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=ingest_one, args=(f"ev-conc-{i:02d}",))
               for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert not errors, errors
    stored = evidence_mod.EvidenceStore(store_path).load()
    assert len(stored) == 2  # no last-writer-wins record loss
    assert sorted(r["evidence_id"] for r in stored) == ["ev-conc-00", "ev-conc-01"]


def test_d009_cli_evidence_json_empty_store_returns_json(tmp_path, monkeypatch,
                                                         capsys):
    from atlas_dag import cli as cli_mod

    class _OfflineClient:
        @property
        def repo(self):
            return None

        def open_prs(self):
            return []

        def commit(self, _sha):
            return None

    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: _OfflineClient())
    argv = ["--runtime-dir", str(tmp_path / ".atlas-runtime"), "--json", "evidence", "10"]
    assert cli_mod.main(argv) == 0
    out = json.loads(capsys.readouterr().out)  # must be parseable JSON
    assert out["records"] == []
    assert out["pr"] == 10
    # Non-JSON mode output is unchanged: plain text, no JSON envelope.
    assert cli_mod.main(["--runtime-dir", str(tmp_path / ".atlas-runtime"),
                         "evidence", "10"]) == 0
    captured = capsys.readouterr()
    assert "no stored evidence for PR #10" in captured.out
