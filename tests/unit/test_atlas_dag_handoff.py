"""Adversarial tests for FEATURE_08: AUTOMATIC_HANDOFF_GENERATION.

Core invariants under test:

- A handoff is a PROJECTION of Features 1-7 truth, never new authority.
- TOCTOU: a candidate-HEAD move during packet build => HandoffStale
  (HANDOFF_STALE_DURING_BUILD) and NO packet; a stable head emits one.
- UNKNOWN preservation: unresolved tree/base/main/owner/verifier fields stay
  UNKNOWN/null with explicit uncertainty entries — never guessed.
- Predecessor CI never surfaces as current CI; invalidated / stale-proof
  evidence never appears in reusable lists; a broken stack never appears
  STACK_CURRENT; a prospective merge SHA is never a merge receipt.
- Determinism: equivalent truth reordered or rebuilt yields byte-identical
  JSON and an identical truth_fingerprint; mode changes only `presentation`.

Every denial has a load-bearing positive control. Hermetic: fake `gh`
runner, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import cli as cli_mod  # noqa: E402
from atlas_dag import evidence as evidence_mod  # noqa: E402
from atlas_dag import handoff as handoff_mod  # noqa: E402
from atlas_dag import stack as stack_mod  # noqa: E402
from atlas_dag import verifiers as verifiers_mod  # noqa: E402
from atlas_dag.gh import GhClient  # noqa: E402

REPO = "B0LK13/project-atlas"
MAIN_SHA = "1" * 40
MAIN_TREE = "2" * 40
H1 = "a" * 40
T1 = "b" * 40
H2 = "c" * 40
T2 = "d" * 40
H3 = "e" * 40
T3 = "f" * 40

FIXED_CLOCK = "2026-09-08T00:00:00Z"


def fixed_clock() -> str:
    return FIXED_CLOCK

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


@pytest.fixture(autouse=True)
def _registry_file_absent(monkeypatch, tmp_path):
    """Force the registry file absent so pool truth comes from the explicit
    `verifier_pool` parameter or the legacy issue-body fallback — the
    committed registry (principal:null) must not shadow these tests."""
    monkeypatch.setattr(verifiers_mod, "default_pool_path",
                        lambda: tmp_path / "absent-verifiers.json")


def make_event(event_id, event, *, ts="2026-09-01T00:00:00Z", pr=None, head=None,
               actor="agent-main", state="FROZEN", dependencies=None):
    return {
        "schema": "ATLAS_EVENT_V1",
        "event_id": event_id,
        "timestamp_utc": ts,
        "actor": actor,
        "role": "COORDINATOR",
        "session_id": f"sess-{actor}",
        "lane": f"pr/{pr}" if pr is not None else "main",
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
                 result="PASS", claim="PASS"):
    return {
        "schema": "ATLAS_IV_RECEIPT_V1",
        "receipt_id": receipt_id,
        "timestamp_utc": "2026-09-01T01:00:00Z",
        "pr": pr,
        "head": head,
        "tree": tree,
        "verifier_id": verifier,
        "session_id": f"sess-{verifier.lower()}",
        "candidate_author_conflict": False,
        "write_activity_count": 0,
        "result": result,
        "p0": 0,
        "p1": 0,
        "p2": 0,
        "claim_integrity": claim,
        "formal_independence": "PASS",
        "findings": [],
        "evidence": ["evidence://local"],
    }


def make_record(evidence_id, **kw) -> dict:
    record = {
        "schema": "ATLAS_EVIDENCE_V1",
        "evidence_id": evidence_id,
        "producer": "ci",
        "pr": 10,
        "head": H1,
        "tree": T1,
        "environment": "linux-python3.12",
        "covered_files": ["src/a.py"],
        "covered_contract": "contract:api",
        "result": "PASS",
        "negative_control": "NONE",
        "scope": "CANDIDATE_WIDE",
        "created_at_utc": "2026-09-01T00:00:00Z",
    }
    record.update(kw)
    return record


def fenced(payload):
    return "```json\n" + json.dumps(payload) + "\n```"


def comments_with(*payloads, author="iv-a-user"):
    return [
        {"body": fenced(p), "id": 1000 + i,
         "user": {"login": author}, "html_url": f"https://example/comment/{1000 + i}"}
        for i, p in enumerate(payloads)
    ]


def make_pool_file(dir_path: Path, verifiers: list[dict],
                   name: str = "verifiers.json") -> Path:
    path = Path(dir_path) / name
    path.write_text(json.dumps({
        "schema": "ATLAS_VERIFIER_POOL_V1", "version": 1, "verifiers": verifiers,
    }), encoding="utf-8")
    return path


def bound_entry(verifier_id: str, principal: str, *,
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
        self.ancestry = {}
        self.issue_body = ""
        self.comments = []

    def add_pr(self, number, head, tree, *, mergeable="MERGEABLE", base="main"):
        self.data["prs"].append({
            "number": number, "title": f"PR {number}", "author": {"login": "someone"},
            "isDraft": False, "headRefName": f"branch-{number}", "headRefOid": head,
            "baseRefName": base, "mergeable": mergeable, "url": f"https://example/{number}",
            "updatedAt": "2026-09-01T00:00:00Z",
        })
        self.commits[head] = {"sha": head, "commit": {"tree": {"sha": tree}}}

    def move_pr_head(self, number, new_head, tree=T2):
        for pr in self.data["prs"]:
            if pr["number"] == number:
                pr["headRefOid"] = new_head
        self.commits[new_head] = {"sha": new_head,
                                  "commit": {"tree": {"sha": tree}}}

    def add_ci(self, head, run_id=101, conclusion="success", status="completed"):
        self.runs.setdefault(head, []).append({
            "id": run_id, "created_at": "2026-09-01T10:00:00Z",
            "status": status, "conclusion": conclusion,
        })

    def set_ancestry(self, ancestor, descendant, status):
        self.ancestry[f"{ancestor}...{descendant}"] = status

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
            if rest.startswith("compare/"):
                return ("compare", rest[len("compare/"):])
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
            import subprocess
            args = argv[1:]
            key = self.key_for(args)
            if key in self.data["fail"]:
                return subprocess.CompletedProcess(argv, 1, "", "simulated gh failure")
            if key == "default_branch":
                branch = self.data.get("default_branch") or ""
                return subprocess.CompletedProcess(argv, 0, branch, "")
            if key == "prs":
                return subprocess.CompletedProcess(argv, 0, json.dumps(self.data["prs"]), "")
            if key == "dag_issue":
                issue = self.data["dag_issue"]
                return subprocess.CompletedProcess(
                    argv, 0, json.dumps([issue] if issue else []), "")
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
                    return subprocess.CompletedProcess(argv, 0, self.issue_body, "")
                elif kind == "compare":
                    return subprocess.CompletedProcess(
                        argv, 0, json.dumps({"status": self.ancestry.get(arg, "diverged")}), "")
                else:
                    val = None
                if val is None:
                    return subprocess.CompletedProcess(argv, 1, "", f"missing fixture for {key}")
                return subprocess.CompletedProcess(argv, 0, json.dumps(val), "")
            raise AssertionError(f"unhandled key: {key}")

        return _run


def make_client(env) -> GhClient:
    return GhClient(repo=REPO, runner=env.runner())


def base_env(*, with_issue=True):
    env = FakeEnv()
    env.add_pr(10, H1, T1)
    env.add_ci(H1)
    if with_issue:
        env.add_issue(body=POOL_BODY)
    return env


def build(env, pr=10, mode="general", *, store=None, pool=None):
    kwargs = {"clock": fixed_clock}
    if store is not None:
        kwargs["evidence_store"] = store
    if pool is not None:
        kwargs["verifier_pool"] = pool
    return handoff_mod.build_handoff(pr, mode, make_client(env), **kwargs)


def dumps(packet) -> str:
    return json.dumps(packet, indent=2, sort_keys=True)


# -- TOCTOU guard -------------------------------------------------------------


class MutatingClient:
    """Wraps a real client; flips pr/10's head after `flip_after` open_prs
    calls, so the final TOCTOU re-resolution observes a moved head."""

    def __init__(self, inner: GhClient, env: FakeEnv, new_head: str, flip_after: int):
        self._inner = inner
        self._env = env
        self._new_head = new_head
        self._flip_after = flip_after
        self.calls = 0
        self.repo = inner.repo

    def open_prs(self):
        self.calls += 1
        if self.calls > self._flip_after:
            self._env.move_pr_head(10, self._new_head)
        return self._inner.open_prs()

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_tocotu_head_move_fails_closed_no_packet():
    env = base_env()
    client = MutatingClient(make_client(env), env, H3, flip_after=1)
    with pytest.raises(handoff_mod.HandoffStale) as excinfo:
        handoff_mod.build_handoff(10, "general", client, clock=fixed_clock)
    assert "HANDOFF_STALE_DURING_BUILD" in str(excinfo.value)
    # Positive control: head stable across build and re-resolution => packet.
    env2 = base_env()
    packet = build(env2)
    assert packet["head"] == H1


def test_tocotu_stable_head_emits_schema_valid_packet():
    env = base_env()
    client = MutatingClient(make_client(env), env, H3, flip_after=99)
    packet = handoff_mod.build_handoff(10, "general", client, clock=fixed_clock)
    assert client.calls == 2  # snapshot build + TOCTOU re-resolution
    assert packet["head"] == H1
    assert handoff_mod.validate_packet(packet) == []


# -- resolvability ------------------------------------------------------------


def test_unknown_pr_fails():
    env = base_env()
    with pytest.raises(handoff_mod.HandoffUnavailable) as excinfo:
        build(env, pr=99)
    assert "UNKNOWN_PR:99" in str(excinfo.value)
    # Positive control: a PR in the open frontier resolves.
    assert build(env)["pr"] == 10


def test_unresolved_tree_base_main_stay_unknown_with_uncertainty():
    env = base_env()
    env.data["fail"].add(("commit", H1))       # candidate tree unresolvable
    env.data["fail"].add(("branch", "main"))   # main/base head unresolvable
    packet = build(env)
    assert packet["head"] == H1            # head itself still resolved
    assert packet["tree"] is None
    assert packet["main_head"] is None
    assert packet["base_head"] is None
    for marker in ("TREE_UNKNOWN", "MAIN_HEAD_UNKNOWN", "BASE_HEAD_UNKNOWN"):
        assert marker in packet["uncertainty"]
    assert handoff_mod.validate_packet(packet) == []
    # Positive control: full resolution leaves none of those markers.
    resolved = build(base_env())
    assert resolved["tree"] == T1
    assert resolved["main_head"] == MAIN_SHA
    assert resolved["base_head"] == MAIN_SHA
    assert not {"TREE_UNKNOWN", "MAIN_HEAD_UNKNOWN", "BASE_HEAD_UNKNOWN"} \
        & set(resolved["uncertainty"])


def test_ambiguous_ownership_stays_ambiguous_no_owner_invented():
    env = base_env()
    env.comments = comments_with(
        make_event("evt-own-a1", "OWNER_CLAIMED", pr=10, actor="agent-x"),
        make_event("evt-own-b1", "OWNER_CLAIMED", pr=10, actor="agent-y"))
    packet = build(env)
    assert packet["ownership"] == "AMBIGUOUS"
    assert packet["owner"] is None
    assert packet["claimants"] == ["agent-x", "agent-y"]
    assert packet["gates"]["owner"] == "AMBIGUOUS"
    assert "OWNER_UNKNOWN" in packet["uncertainty"]
    # Positive control: a single claimant resolves to exactly one owner.
    solo = base_env()
    solo.comments = comments_with(
        make_event("evt-own-s1", "OWNER_CLAIMED", pr=10, actor="agent-x"))
    packet_solo = build(solo)
    assert packet_solo["ownership"] == "OWNED"
    assert packet_solo["owner"] == "agent-x"


def test_missing_formal_iv_stays_missing_unbound_verifier_stays_unbound(tmp_path):
    # Pool present (bare declarations, no authenticated binding): the unbound
    # state must surface verbatim, never an inferred PASS/FAIL.
    env = base_env()
    env.add_issue(body=BARE_POOL_BODY)
    packet = build(env)
    assert packet["formal_iv"]["state"] == "MISSING"
    assert packet["formal_iv"]["receipt_id"] is None
    assert packet["formal_iv"]["verifier_binding"] is None
    assert packet["gates"]["verifier"] == "VERIFIER_IDENTITY_UNBOUND"
    # Positive control: authenticated binding + eligible receipt SATISFIES IV
    # with the pool principal as the binding — nothing inferred.
    env2 = base_env()
    env2.comments = comments_with(make_receipt("rcpt-ho-ok1"))
    pool = make_pool_file(tmp_path, BOUND_POOL)
    packet2 = build(env2, pool=pool)
    assert packet2["formal_iv"]["state"] == "SATISFIED"
    assert packet2["formal_iv"]["receipt_id"] == "rcpt-ho-ok1"
    assert packet2["formal_iv"]["verifier_id"] == "IV-A"
    assert packet2["formal_iv"]["verifier_binding"] == "github:iv-a-user"
    assert packet2["gates"]["verifier"] == "SATISFIED"


# -- exact-head CI ------------------------------------------------------------


def test_predecessor_ci_run_never_appears_as_current():
    env = base_env(with_issue=False)
    env.runs = {}                       # no runs at the live head H1
    env.add_ci(H2, run_id=777)          # a run exists, but for an older head
    packet = build(env)
    assert packet["ci"]["status"] == "NONE"
    assert packet["ci"]["run_id"] is None
    assert "777" not in dumps(packet)   # predecessor run id never leaks in
    # Positive control: a concluded run at the EXACT head is current CI.
    env2 = base_env(with_issue=False)
    env2.add_ci(H1, run_id=888)
    packet2 = build(env2)
    assert packet2["ci"]["status"] == "PASS"
    assert packet2["ci"]["run_id"] == "888"
    assert packet2["ci"]["head"] == H1


# -- evidence graph projection ------------------------------------------------


def _store(tmp_path, name, records):
    store = evidence_mod.EvidenceStore(Path(tmp_path) / name / "evidence.json")
    for record in records:
        store.ingest(record)
    return store


def test_invalidated_and_stale_evidence_never_reusable(tmp_path):
    current = make_record("ev-ho-cur1", evidence_class="exact_head_ci")
    stale = make_record("ev-ho-old1", evidence_class="exact_head_ci",
                        head=H2, tree=T2)          # head moved => predecessor
    invalidated = make_record("ev-ho-bad1", evidence_class="exact_head_ci",
                              negative_control="FAIL")
    store = _store(tmp_path, "s1", [current, stale, invalidated])
    packet = build(base_env(), store=store)
    states = packet["evidence"]["states"]
    assert states["EXACT_CURRENT"] == ["ev-ho-cur1"]
    assert states["PREDECESSOR_ONLY"] == ["ev-ho-old1"]
    assert states["INVALIDATED"] == ["ev-ho-bad1"]
    assert states["REUSABLE_BY_PROVEN_EQUIVALENCE"] == []
    assert states["UNKNOWN"] == []
    # Only the exact-current artifact is reusable — never invalidated/stale.
    assert packet["evidence"]["reusable"] == ["ev-ho-cur1"]
    # Positive control: without the stale/invalidated records the reusable
    # list is unchanged (current artifact still reusable).
    store2 = _store(tmp_path, "s2", [make_record("ev-ho-cur1", evidence_class="exact_head_ci")])
    packet2 = build(base_env(), store=store2)
    assert packet2["evidence"]["reusable"] == ["ev-ho-cur1"]


def test_all_five_evidence_states_exposed_with_per_artifact_reasons(tmp_path):
    narrow_stale = make_record("ev-ho-sub1", scope="SUBSYSTEM", head=H2, tree=T2,
                               covered_files=["src/a.py"])
    env = base_env()
    store = _store(tmp_path, "s3", [
        make_record("ev-ho-c1", evidence_class="exact_head_ci"),
        narrow_stale,
        make_record("ev-ho-i1", evidence_class="exact_head_ci", negative_control="FAIL"),
    ])
    packet = build(env, store=store)
    states = packet["evidence"]["states"]
    assert set(states) == {"EXACT_CURRENT", "REUSABLE_BY_PROVEN_EQUIVALENCE",
                           "PREDECESSOR_ONLY", "INVALIDATED", "UNKNOWN"}
    assert states["EXACT_CURRENT"] == ["ev-ho-c1"]
    assert states["INVALIDATED"] == ["ev-ho-i1"]
    # Narrow artifact at an older head with no live path truth is UNKNOWN
    # (fail closed), never laundered into reusable.
    assert states["UNKNOWN"] == ["ev-ho-sub1"]
    assert states["REUSABLE_BY_PROVEN_EQUIVALENCE"] == []
    by_id = {a["evidence_id"]: a for a in packet["evidence"]["artifacts"]}
    assert by_id["ev-ho-i1"]["reasons"] == ["NEGATIVE_CONTROL_FAILED"]
    assert by_id["ev-ho-sub1"]["state"] == "UNKNOWN"
    assert "CHANGED_FILES_UNAVAILABLE" in by_id["ev-ho-sub1"]["uncertainty"]
    # Positive control: the narrow artifact at its EXACT live head is current.
    store2 = _store(tmp_path, "s3b", [
        make_record("ev-ho-sub2", scope="SUBSYSTEM", covered_files=["src/a.py"])])
    packet2 = build(base_env(), store=store2)
    assert packet2["evidence"]["states"]["EXACT_CURRENT"] == ["ev-ho-sub2"]
    assert packet2["evidence"]["reusable"] == ["ev-ho-sub2"]


def test_parent_child_evidence_is_never_inherited(tmp_path):
    child_only = make_record("ev-ho-child1", pr=11, head=H2, tree=T2,
                             evidence_class="exact_head_ci")
    store = _store(tmp_path, "s5", [child_only])
    env = base_env()
    env.add_pr(11, H2, T2)
    packet_parent = build(env, pr=10, store=store)
    assert packet_parent["evidence"]["artifacts"] == []
    assert packet_parent["evidence"]["reusable"] == []
    # Positive control: the same artifact IS visible on its own lane.
    packet_child = build(env, pr=11, store=store)
    assert [a["evidence_id"] for a in packet_child["evidence"]["artifacts"]] \
        == ["ev-ho-child1"]
    assert packet_child["evidence"]["reusable"] == ["ev-ho-child1"]


# -- stack topology projection ------------------------------------------------


def _stack_env(ancestry_status):
    env = base_env()
    env.add_pr(11, H2, T2, base="branch-10")
    env.set_ancestry(H1, H2, ancestry_status)
    return env


def test_broken_stack_never_appears_stack_current():
    env = _stack_env("diverged")  # parent head not in child ancestry
    packet = build(env, pr=11)
    assert packet["stack"]["stack_state"] == stack_mod.PARENT_MOVED
    assert packet["stack"]["restack_required"] is True
    assert packet["stack"]["stack_state"] != "STACK_CURRENT"
    # Positive control: verified ancestry => STACK_CURRENT with real depth.
    env2 = _stack_env("ahead")
    packet2 = build(env2, pr=11)
    assert packet2["stack"]["stack_state"] == "STACK_CURRENT"
    assert packet2["stack"]["depth"] == 1
    assert packet2["stack"]["parent_pr"] == 10


def test_stack_root_depth_and_parent_head_projected():
    env = _stack_env("ahead")
    packet = build(env, pr=11)
    assert packet["stack"]["root"] == "pr/10"
    assert packet["stack"]["parent_head"] == H1
    assert packet["stack"]["target_branch"] == "branch-10"
    # Positive control: the root lane itself has no parent.
    root_packet = build(env, pr=10)
    assert root_packet["stack"]["stack_state"] == stack_mod.ROOT
    assert root_packet["stack"]["parent_pr"] is None
    assert root_packet["stack"]["depth"] == 0


# -- merge receipt boundary ---------------------------------------------------


def test_prospective_merge_sha_never_a_merge_receipt(tmp_path):
    env = base_env()
    packet = build(env)
    # PR is open: no merge receipt can exist, and none is synthesized.
    assert packet["merge_receipt"] == {"receipt": None, "reason": "PR_OPEN"}
    assert packet["merge_receipt"]["receipt"] is None
    # Positive control: even a fully merge-eligible lane keeps the boundary.
    env2 = base_env()
    env2.comments = comments_with(make_receipt("rcpt-ho-el1"))
    pool = make_pool_file(tmp_path, BOUND_POOL)
    packet2 = build(env2, pool=pool)
    assert packet2["merge_receipt"]["receipt"] is None
    assert packet2["merge_receipt"]["reason"] == "PR_OPEN"


# -- determinism --------------------------------------------------------------


def test_main_advance_between_builds_changes_main_head_and_fingerprint():
    env = base_env()
    first = build(env)
    assert first["main_head"] == MAIN_SHA
    new_main = "3" * 40
    env.data[("branch", "main")] = {
        "commit": {"sha": new_main, "commit": {"tree": {"sha": "4" * 40}}}}
    second = build(env)
    assert second["main_head"] == new_main
    assert second["truth_fingerprint"] != first["truth_fingerprint"]
    assert second["handoff_id"] != first["handoff_id"]
    # Positive control: an unchanged rebuild is fingerprint-identical.
    assert build(env, mode="verifier")["truth_fingerprint"] \
        == second["truth_fingerprint"]


def test_reordered_equivalent_source_data_yields_byte_identical_packet(tmp_path):
    events_a = [
        make_event("evt-ro-a01", "OWNER_CLAIMED", pr=10, actor="agent-x",
                   ts="2026-09-01T00:00:00Z"),
        make_event("evt-ro-b01", "OWNER_CLAIMED", pr=11, actor="agent-y",
                   ts="2026-09-01T01:00:00Z"),
    ]
    env_a = base_env()
    env_a.add_pr(11, H2, T2)
    env_a.comments = comments_with(*events_a)
    env_b = base_env()
    env_b.add_pr(11, H2, T2)
    env_b.data["prs"].reverse()          # PR list order is semantically unordered
    env_b.comments = comments_with(*reversed(events_a))  # comment order unordered
    # Evidence covered_files list order is normalized by the store.
    store_a = _store(tmp_path, "ra", [
        make_record("ev-ho-ro1", covered_files=["src/a.py", "src/b.py"])])
    store_b = _store(tmp_path, "rb", [
        make_record("ev-ho-ro1", covered_files=["src/b.py", "src/a.py"])])
    packet_a = build(env_a, store=store_a)
    packet_b = build(env_b, store=store_b)
    assert packet_a["truth_fingerprint"] == packet_b["truth_fingerprint"]
    assert dumps(packet_a) == dumps(packet_b)


def test_two_calls_on_same_snapshot_are_byte_identical():
    env = base_env()
    assert dumps(build(env)) == dumps(build(env))


# -- schema validation --------------------------------------------------------


def test_malformed_packet_fails_schema_validation():
    env = base_env()
    packet = build(env)
    assert handoff_mod.validate_packet(packet) == []
    corrupted = dict(packet)
    del corrupted["head"]
    assert handoff_mod.validate_packet(corrupted)
    corrupted = dict(packet, schema="ATLAS_HANDOFF_V2")
    assert handoff_mod.validate_packet(corrupted)
    corrupted = dict(packet, mode="bogus")
    assert handoff_mod.validate_packet(corrupted)
    corrupted = dict(packet, handoff_id="handoff-not-hex!")
    assert handoff_mod.validate_packet(corrupted)
    corrupted = dict(packet, truth_fingerprint="zz" * 32)
    assert handoff_mod.validate_packet(corrupted)
    # Positive control: the untouched packet validates cleanly again.
    assert handoff_mod.validate_packet(packet) == []


# -- modes --------------------------------------------------------------------


def _material(packet) -> dict:
    volatile = {"handoff_id", "generated_at_utc", "presentation", "mode"}
    return {k: v for k, v in packet.items() if k not in volatile}


def test_modes_share_material_truth_only_presentation_differs(tmp_path):
    env = base_env()
    env.comments = comments_with(make_receipt("rcpt-ho-md1"))
    pool = make_pool_file(tmp_path, BOUND_POOL)
    packets = {mode: build(env, mode=mode, pool=pool)
               for mode in ("general", "verifier", "resume")}
    fingerprints = {p["truth_fingerprint"] for p in packets.values()}
    assert len(fingerprints) == 1
    material = [_material(p) for p in packets.values()]
    assert material[0] == material[1] == material[2]
    # handoff_id is derived from fingerprint+pr+mode: stable per mode, and
    # identical across rebuilds of the same mode.
    assert packets["verifier"]["handoff_id"] == build(env, mode="verifier", pool=pool)["handoff_id"]
    # VERIFIER mode carries prohibitions + validation requirements.
    verifier_pres = packets["verifier"]["presentation"]
    assert "no_self_iv" in verifier_pres["prohibited_verifier_actions"]
    assert "no_merge_authority" in verifier_pres["prohibited_verifier_actions"]
    assert verifier_pres["validation_requirements"] == sorted(
        r for r in packets["verifier"]["merge_guardian"]["reasons"]
        if r.startswith(handoff_mod._VALIDATION_PREFIXES))
    # RESUME mode carries the next safe action from node truth.
    resume_pres = packets["resume"]["presentation"]
    assert resume_pres["next_safe_action"] in packets["resume"]["next_actions"] \
        or resume_pres["next_safe_action"] == "UNKNOWN"
    assert resume_pres["topology"]["lane"] == "pr/10"
    # GENERAL mode: no verifier/resume emphasis leaked in.
    assert packets["general"]["presentation"] == {"audience": "general"}


def test_frozen_lane_dispatch_plan_projected_unfrozen_is_none():
    env = base_env()
    env.add_issue(body=BARE_POOL_BODY)  # declared but unbound verifier pool
    freeze = make_event("evt-ho-frz1", "HUMAN_GATE_REQUIRED", pr=10, head=H1,
                        state="FROZEN")
    env.comments = comments_with(freeze)
    packet = build(env)
    assert packet["frozen"] is True
    assert packet["dispatch"] is not None
    assert packet["dispatch"]["ci"]["lane_state"] in (
        "RUNNABLE", "ALREADY_RUNNING", "COMPLETE", "BLOCKED")
    # IV lane is blocked by the unbound pool — verbatim, not laundered.
    assert packet["dispatch"]["iv"]["lane_state"] == "BLOCKED"
    assert "VERIFIER_IDENTITY_UNBOUND" in packet["dispatch"]["iv"]["reasons"]
    # Positive control: without the freeze event there is no dispatch plan.
    unfrozen = build(base_env())
    assert unfrozen["frozen"] is False
    assert unfrozen["dispatch"] is None


# -- CLI -----------------------------------------------------------------------


def _cli_client(monkeypatch, env):
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: make_client(env))


def test_cli_handoff_json_is_schema_valid(tmp_path, monkeypatch, capsys):
    env = base_env()
    _cli_client(monkeypatch, env)
    rc = cli_mod.main(["--runtime-dir", str(tmp_path), "--json",
                       "handoff", "--pr", "10"])
    assert rc == 0
    packet = json.loads(capsys.readouterr().out)
    assert packet["schema"] == "ATLAS_HANDOFF_V1"
    assert handoff_mod.validate_packet(packet) == []


def test_cli_handoff_text_summary(tmp_path, monkeypatch, capsys):
    env = base_env()
    _cli_client(monkeypatch, env)
    rc = cli_mod.main(["--runtime-dir", str(tmp_path), "handoff", "--pr", "10"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "handoff handoff-" in out
    assert "pr/10" in out and "gate=" in out


def test_cli_handoff_unknown_pr_fails_closed(tmp_path, monkeypatch, capsys):
    env = base_env()
    _cli_client(monkeypatch, env)
    rc = cli_mod.main(["--runtime-dir", str(tmp_path), "--json",
                       "handoff", "--pr", "99"])
    assert rc == 2
    assert "UNKNOWN_PR:99" in capsys.readouterr().err


def test_cli_handoff_tocotu_fails_closed(tmp_path, monkeypatch, capsys):
    env = base_env()
    mutating = MutatingClient(make_client(env), env, H3, flip_after=1)
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: mutating)
    rc = cli_mod.main(["--runtime-dir", str(tmp_path), "--json",
                       "handoff", "--pr", "10"])
    assert rc == 2
    assert "HANDOFF_STALE_DURING_BUILD" in capsys.readouterr().err


def test_cli_handoff_schema_invalid_packet_never_printed(tmp_path, monkeypatch, capsys):
    env = base_env()
    _cli_client(monkeypatch, env)

    def _corrupt(*_a, **_kw):
        return {"schema": "ATLAS_HANDOFF_V1"}  # missing every required field

    monkeypatch.setattr(handoff_mod, "build_handoff", _corrupt)
    rc = cli_mod.main(["--runtime-dir", str(tmp_path), "--json",
                       "handoff", "--pr", "10"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "SCHEMA:" in captured.err
    assert captured.out == ""  # fail closed: nothing emitted
