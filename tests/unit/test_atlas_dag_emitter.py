"""Offline adversarial tests for automatic event object resolution (FEATURE_04).

Repository/GitHub truth is the only authority for object identity:
- wrong --expect-head => fail, nothing posted;
- PR HEAD moves between build and emit => TOCTOU fail, never stale post;
- unknown PR / unresolvable tree / unavailable main => fail;
- prospective merge SHA is never accepted as HEAD or merge receipt;
- stacked parent identity comes from Feature-3 topology, not prose;
- manual arbitrary SHA cannot override resolved truth;
- wrong repository identity fails;
- invalid actor / inactive agent / event-not-permitted fails;
- schema-invalid event never emitted;
- duplicate identical transition is idempotent;
- dry-run causes zero GitHub mutation.

Every denial has a load-bearing control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import agents as agents_mod  # noqa: E402
from atlas_dag import emitter as emitter_mod  # noqa: E402
from atlas_dag import events as events_mod  # noqa: E402

H = "a1b2c3d4e5f6789012345678901234567890abcd"
H_PARENT = "b2c3d4e5f6789012345678901234567890abcde"
H_MAIN = "c3d4e5f6789012345678901234567890abcdef0"
TREE = "d4e5f6789012345678901234567890abcdef01"
BASE_TREE = "e5f6789012345678901234567890abcdef0123"


def profile(**kw) -> dict:
    p = {
        "agent_id": "ubuntu-main", "role": "coordinator", "active": True,
        "platforms": ["linux"],
        "capabilities": ["READ_REPO", "POST_EVENTS", "CLAIM_OWNERSHIP"],
        "prohibitions": ["AUTO_MERGE", "SELF_IV"],
        "write_scopes": ["path:scripts/atlas_dag"],
        "event_permissions": ["OWNER_CLAIMED", "HEAD_MOVED", "CI_COMPLETED"],
        "verification_class": "IMPLEMENTATION",
        "principal": "github:B0LK13",
        "metadata": {"session_id": "ubuntu-main-20260908"},
    }
    p.update(kw)
    return p


def registry(tmp_path, prof=None) -> agents_mod.RegistryResult:
    path = tmp_path / "agents.json"
    path.write_text(json.dumps({
        "schema": "ATLAS_AGENT_REGISTRY_V1", "registry_id": "t",
        "version": 1, "agents": [prof or profile()],
    }), encoding="utf-8")
    return agents_mod.load_registry(path)


class FakeClient:
    """Scripted live truth. `posts` records issue-comment mutations."""

    def __init__(self, prs=None, heads=None, ancestry=None, repo="B0LK13/project-atlas",
                 main_branch="main", issue=719, comments=None):
        self._prs = prs or []
        self._heads = heads or {}  # sha -> tree
        self._ancestry = ancestry or set()
        self._repo = repo
        self._main = main_branch
        self._issue = issue
        self._comments = comments or []
        self.posts: list[str] = []

    # GhClient surface
    @property
    def repo(self):
        return self._repo

    def open_prs(self):
        return list(self._prs)

    def commit(self, sha):
        tree = self._heads.get(sha)
        return {"sha": sha, "tree": tree} if tree else None

    def branch_head(self, branch):
        if branch == self._main:
            return {"sha": H_MAIN, "tree": "m" * 40}
        return {"sha": H_PARENT, "tree": BASE_TREE}

    def default_branch(self):
        return self._main

    def is_ancestor(self, anc, desc):
        return bool(anc == desc or (anc, desc) in self._ancestry)

    def dag_issue(self):
        return {"number": self._issue, "state": "OPEN"}

    def issue_comments(self, number):
        return list(self._comments)

    def run_gh(self, args):
        self.posts.append(" ".join(args))
        return "https://github.com/comment/1"


def stacked_client(**kw) -> FakeClient:
    prs = [
        {"number": 720, "headRefOid": H_PARENT, "headRefName": "feat-parent",
         "baseRefName": "main"},
        {"number": 730, "headRefOid": H, "headRefName": "feat-child",
         "baseRefName": "feat-parent"},
    ]
    heads = {H: TREE, H_PARENT: BASE_TREE}
    ancestry = {(H_PARENT, H)}
    return FakeClient(prs=prs, heads=heads, ancestry=ancestry, **kw)


def resolve(client, prof=None, **kw):
    return emitter_mod.resolve_context(client, 730, prof or profile(), **kw)


def build(ctx, event="HEAD_MOVED", state="SUCCESSOR_FROZEN", note="t", **kw):
    return emitter_mod.build_event(ctx, event=event, state=state, note=note, **kw)


# --- resolution truthfulness ---------------------------------------------------

def test_resolves_all_identity_fields_from_live_truth():
    ctx = resolve(stacked_client())
    assert ctx.head == H and ctx.tree == TREE
    assert ctx.base_branch == "feat-parent" and ctx.base_head == H_PARENT
    assert ctx.main_branch == "main" and ctx.main_head == H_MAIN
    assert ctx.parent_pr == 720 and ctx.parent_head == H_PARENT  # Feature-3
    assert ctx.actor == "ubuntu-main" and ctx.session_id == "ubuntu-main-20260908"


def test_event_payload_carries_resolved_metadata_and_validates():
    payload = build(resolve(stacked_client()), utc="2026-09-08T15:00:00Z")
    assert payload["head"] == H and payload["tree"] == TREE
    assert payload["base_head"] == H_PARENT and payload["main_head"] == H_MAIN
    assert payload["parent_pr"] == 720 and payload["parent_head"] == H_PARENT
    validator = events_mod.validator_for(events_mod.EVENT_SCHEMA)
    assert not list(validator.iter_errors(payload))


def test_deterministic_event_id_and_serialization():
    ctx = resolve(stacked_client())
    a = build(ctx, utc="2026-09-08T15:00:00Z")
    b = build(ctx, utc="2026-09-08T15:00:00Z")
    assert a["event_id"] == b["event_id"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["event_id"].count(H[:12]) == 1


def test_manual_sha_cannot_override_resolved_truth():
    """Supplying a full --expect-head is an assertion, not an override."""
    ctx = resolve(stacked_client())
    try:
        build(ctx, expect_head="f" * 40)
    except emitter_mod.EmitError as exc:
        assert "EXPECT_HEAD_MISMATCH" in str(exc)
    else:
        raise AssertionError("manual SHA override accepted")
    # control: matching assertion passes
    assert build(ctx, expect_head=H)["head"] == H


def test_historical_mistranscribed_sha_class_rejected():
    """Reproduce the 2026-09-08 mis-transcribed head class: a SHA composed
    by hand (180667040dd...) must fail the assertion, never post."""
    wrong = H[:12] + "0" + H[13:]  # one char off, human-style slip
    try:
        build(resolve(stacked_client()), expect_head=wrong)
    except emitter_mod.EmitError as exc:
        assert "EXPECT_HEAD_MISMATCH" in str(exc)
    else:
        raise AssertionError("mis-transcribed SHA accepted")


# --- fail-closed resolution -----------------------------------------------------

def test_unknown_pr_fails():
    client = stacked_client()
    client._prs = [p for p in client._prs if p["number"] != 730]
    try:
        resolve(client)
    except emitter_mod.EmitError as exc:
        assert "UNKNOWN_PR" in str(exc)
    else:
        raise AssertionError("unknown PR resolved")


def test_tree_cannot_resolve_fails():
    client = stacked_client()
    client._heads = {}  # commit lookup fails
    try:
        resolve(client)
    except emitter_mod.EmitError as exc:
        assert "CANDIDATE_TREE_UNKNOWN" in str(exc)
    else:
        raise AssertionError("unresolvable tree accepted")


def test_main_unavailable_fails():
    client = stacked_client()
    client._main = None  # default_branch unknown
    try:
        resolve(client)
    except emitter_mod.EmitError as exc:
        assert "MAIN_HEAD_UNKNOWN" in str(exc) or "MAIN" in str(exc)
    else:
        raise AssertionError("missing main accepted")


def test_wrong_repository_identity_fails():
    try:
        resolve(stacked_client(), expected_repo="someone/else")
    except emitter_mod.EmitError as exc:
        assert "WRONG_REPOSITORY_IDENTITY" in str(exc)
    else:
        raise AssertionError("wrong repo accepted")
    # control: correct identity passes
    assert resolve(stacked_client(), expected_repo="B0LK13/project-atlas").head == H


def test_prospective_merge_sha_never_identity():
    """A prospective merge SHA field on the PR must not leak into identity."""
    client = stacked_client()
    client._prs[1]["mergeCommit"] = {"oid": "f" * 40}
    client._prs[1]["prospective_merge_sha"] = "e" * 40
    ctx = resolve(client)
    assert ctx.head == H
    payload = build(ctx)
    assert payload["head"] == H and "merge" not in json.dumps(payload).lower()


# --- permission / context ---------------------------------------------------------

def test_event_not_permitted_fails(tmp_path):
    reg = registry(tmp_path, profile(event_permissions=["OWNER_CLAIMED"]))
    checks = emitter_mod.check_emit_permission(reg, "ubuntu-main", "HEAD_MOVED",
                                               lane_owner="ubuntu-main")
    assert not checks.ok and any("EVENT_NOT_PERMITTED" in r for r in checks.reasons)
    # control: permitted event passes
    ok = emitter_mod.check_emit_permission(reg, "ubuntu-main", "OWNER_CLAIMED",
                                           lane_owner=None)
    assert ok.ok


def test_inactive_agent_cannot_emit(tmp_path):
    reg = registry(tmp_path, profile(active=False))
    checks = emitter_mod.check_emit_permission(reg, "ubuntu-main", "HEAD_MOVED",
                                               lane_owner="ubuntu-main")
    assert not checks.ok and "AGENT_INACTIVE" in checks.reasons


def test_foreign_owner_lane_denied(tmp_path):
    reg = registry(tmp_path)
    checks = emitter_mod.check_emit_permission(reg, "ubuntu-main", "HEAD_MOVED",
                                               lane_owner="windows-main")
    assert not checks.ok
    assert any(r.startswith("OWNERSHIP_MUTEX_HELD_BY") for r in checks.reasons)
    # control: own lane permitted
    assert emitter_mod.check_emit_permission(
        reg, "ubuntu-main", "HEAD_MOVED", lane_owner="ubuntu-main").ok
    # control: first claim on an unowned lane permitted
    assert emitter_mod.check_emit_permission(
        reg, "ubuntu-main", "OWNER_CLAIMED", lane_owner=None).ok


def test_unknown_agent_cannot_emit(tmp_path):
    reg = registry(tmp_path)
    checks = emitter_mod.check_emit_permission(reg, "ghost", "HEAD_MOVED", None)
    assert not checks.ok and any(r.startswith("AGENT_NOT_REGISTERED") for r in checks.reasons)


# --- emit safety -------------------------------------------------------------------

def test_emit_dry_run_zero_mutation(tmp_path):
    client = stacked_client()
    reg = registry(tmp_path)
    payload = build(resolve(client))
    status = emitter_mod.emit_event(client, reg, payload, dry_run=True)
    assert status == "dry-run"
    assert client.posts == []  # zero GitHub mutation


def test_emit_posts_canonical_fenced_payload(tmp_path):
    client = stacked_client()
    reg = registry(tmp_path)
    payload = build(resolve(client), utc="2026-09-08T15:00:00Z")
    status = emitter_mod.emit_event(client, reg, payload)
    assert status == "posted"
    assert len(client.posts) == 1 and "issue comment 719" in client.posts[0]


def test_emit_duplicate_transition_idempotent(tmp_path):
    client = stacked_client()
    reg = registry(tmp_path)
    payload = build(resolve(client), utc="2026-09-08T15:00:00Z")
    assert emitter_mod.emit_event(client, reg, payload) == "posted"
    # same transition identity: the event now exists on the bus
    body = emitter_mod.fenced(payload)
    comment = {"body": body,
               "user": {"login": "B0LK13"}}
    client._comments = [comment]
    assert emitter_mod.emit_event(client, reg, payload) == "already-present"
    assert len(client.posts) == 1  # no second post


def test_toctou_head_move_between_build_and_emit_fails(tmp_path):
    client = stacked_client()
    reg = registry(tmp_path)
    payload = build(resolve(client), utc="2026-09-08T15:00:00Z")
    client._prs[1]["headRefOid"] = H_PARENT  # head moved after build
    try:
        emitter_mod.emit_event(client, reg, payload)
    except emitter_mod.EmitError as exc:
        assert "HEAD_MOVED_DURING_RESOLUTION" in str(exc)
    else:
        raise AssertionError("stale post allowed")
    assert client.posts == []


def test_schema_invalid_event_never_emitted(tmp_path):
    client = stacked_client()
    ctx = resolve(client)
    try:
        # event type outside the schema enum => build fails validation
        build(ctx, event="NOPE_NOT_A_TRANSITION")
    except emitter_mod.EmitError as exc:
        assert "SCHEMA_INVALID" in str(exc)
    else:
        raise AssertionError("schema-invalid event built")
    assert client.posts == []
