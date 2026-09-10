"""Adversarial tests for FEATURE_05: ATLAS_VERIFIER_POOL_V1 registry + principal
authentication (VERIFIER_ROLE != AUTHENTICATED_FORMAL_VERIFIER).

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
from atlas_dag import gate as gate_mod  # noqa: E402
from atlas_dag import receipts as receipts_mod  # noqa: E402
from atlas_dag import router as router_mod  # noqa: E402
from atlas_dag import verifiers as verifiers_mod  # noqa: E402
from atlas_dag.events import validator_for  # noqa: E402
from atlas_dag.model import build_snapshot  # noqa: E402

REPO = "B0LK13/project-atlas"
H1 = "a" * 40
T1 = "b" * 40
H3 = "e" * 40
T3 = "f" * 40

DEFAULT_POOL_PATH = verifiers_mod.default_pool_path()


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


def make_receipt(receipt_id, *, pr=10, head=H1, tree=T1, verifier="IV-A",
                 session="sess-iv-a", implementer_session=None, author_conflict=False,
                 writes=0, result="PASS", independence="PASS"):
    receipt = {
        "schema": "ATLAS_IV_RECEIPT_V1",
        "receipt_id": receipt_id,
        "timestamp_utc": "2026-09-01T01:00:00Z",
        "pr": pr, "head": head, "tree": tree,
        "verifier_id": verifier, "session_id": session,
        "candidate_author_conflict": author_conflict,
        "write_activity_count": writes, "result": result,
        "p0": 0, "p1": 0, "p2": 0,
        "claim_integrity": "PASS", "formal_independence": independence,
        "findings": [], "evidence": ["evidence://local"],
    }
    if implementer_session is not None:
        receipt["implementer_session_id"] = implementer_session
    return receipt


def evaluate(receipt, *, head=H1, tree=T1, author="iv-a-user",
             bindings=None, declared=None, present=True,
             status_map=None, pool_invalid=False, pr_author="someone"):
    if bindings is None:
        bindings = {"IV-A": "github:iv-a-user", "IV-B": "github:iv-b-user"}
    if declared is None:
        declared = []
    return receipts_mod.formal_iv_status(
        receipt, head, tree, bindings, declared, present, author,
        status_map=status_map, pool_invalid=pool_invalid, pr_author=pr_author,
    )


def bound_status_map(**overrides: str) -> dict[str, str]:
    status_map = {"IV-A": "AUTHENTICATED", "IV-B": "AUTHENTICATED"}
    status_map.update(overrides)
    return status_map


# -- registry load: distinct failure classes ------------------------------------


def test_committed_registry_is_valid_and_unbound():
    result = verifiers_mod.load_pool(DEFAULT_POOL_PATH)
    assert result.valid, result.errors
    ids = {e["verifier_id"]: e for e in result.pool["verifiers"]}
    assert sorted(ids) == ["IV-A", "IV-B"]
    # No fabricated principals: bare labels stay DECLARED_BUT_UNBOUND forever.
    assert ids["IV-A"]["principal"] is None
    assert ids["IV-B"]["principal"] is None


def test_load_pool_missing_file_is_distinct_failure(tmp_path):
    result = verifiers_mod.load_pool(tmp_path / "nope.json")
    assert not result.valid
    assert any(e.startswith(verifiers_mod.POOL_MISSING) for e in result.errors)
    assert not any(e.startswith(verifiers_mod.POOL_UNREADABLE) for e in result.errors)


def test_load_pool_malformed_json_is_unreadable(tmp_path):
    path = tmp_path / "verifiers.json"
    path.write_text("{not json", encoding="utf-8")
    result = verifiers_mod.load_pool(path)
    assert not result.valid
    assert any(e.startswith(verifiers_mod.POOL_UNREADABLE) for e in result.errors)


def test_load_pool_schema_violations(tmp_path):
    bad_principal = make_pool_file(tmp_path, [
        bound_entry("IV-A", "not-a-github-principal")], name="bad-principal.json")
    result = verifiers_mod.load_pool(bad_principal)
    assert not result.valid
    assert any(e.startswith(verifiers_mod.POOL_SCHEMA_VIOLATION) for e in result.errors)

    empty_repos = make_pool_file(tmp_path, [
        dict(bound_entry("IV-A", "github:iv-a-user"), allowed_repositories=[])],
        name="empty-repos.json")
    result = verifiers_mod.load_pool(empty_repos)
    assert not result.valid
    assert any(e.startswith(verifiers_mod.POOL_SCHEMA_VIOLATION) for e in result.errors)


def test_load_pool_duplicate_verifier_id(tmp_path):
    path = make_pool_file(tmp_path, [bound_entry("IV-A", "github:iv-a-user"),
                                     bound_entry("IV-A", "github:other")])
    result = verifiers_mod.load_pool(path)
    assert not result.valid
    assert any(e.startswith(verifiers_mod.POOL_DUPLICATE_VERIFIER_ID) for e in result.errors)


def test_load_pool_wrong_version_const_fails(tmp_path):
    path = tmp_path / "verifiers.json"
    path.write_text(json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1", "version": 2,
                                "verifiers": []}), encoding="utf-8")
    result = verifiers_mod.load_pool(path)
    assert not result.valid
    assert any(e.startswith(verifiers_mod.POOL_SCHEMA_VIOLATION) for e in result.errors)


# -- authentication_status / pool_views ------------------------------------------


def test_authentication_status_precedence():
    auth = verifiers_mod.authentication_status
    assert auth(None, REPO) == verifiers_mod.VERIFIER_UNKNOWN
    assert auth(bound_entry("IV-A", None), REPO) == verifiers_mod.DECLARED_BUT_UNBOUND
    assert auth(bound_entry("IV-A", "  "), REPO) == verifiers_mod.DECLARED_BUT_UNBOUND
    assert auth(bound_entry("IV-A", "github:x", active=False), REPO) \
        == verifiers_mod.VERIFIER_INACTIVE
    assert auth(bound_entry("IV-A", "github:x", repos=["other/repo"]), REPO) \
        == verifiers_mod.VERIFIER_REPO_NOT_ALLOWED
    assert auth(bound_entry("IV-A", "github:x"), REPO) == verifiers_mod.AUTHENTICATED
    # Unknown repo context must not authenticate more than a known one.
    assert auth(bound_entry("IV-A", "github:x"), None) == verifiers_mod.AUTHENTICATED


def test_pool_views_bindings_only_for_authenticated():
    pool = {"verifiers": [
        bound_entry("IV-A", "github:iv-a-user"),
        bound_entry("IV-B", None),                              # unbound
        bound_entry("IV-C", "github:iv-c-user", active=False),  # inactive
        bound_entry("IV-D", "github:iv-d-user", repos=["other/repo"]),  # wrong repo
    ]}
    bindings, declared, status_map = verifiers_mod.pool_views(pool, REPO)
    assert bindings == {"IV-A": "github:iv-a-user"}
    assert declared == ["IV-B", "IV-C", "IV-D"]  # sorted, never satisfies IV
    assert status_map == {
        "IV-A": "AUTHENTICATED", "IV-B": "DECLARED_BUT_UNBOUND",
        "IV-C": "VERIFIER_INACTIVE", "IV-D": "VERIFIER_REPO_NOT_ALLOWED",
    }


# -- resolve_pool: canonical file, fail-closed fallback ---------------------------


def test_resolve_pool_registry_file_is_canonical(tmp_path):
    path = make_pool_file(tmp_path, BOUND_POOL)
    resolution = verifiers_mod.resolve_pool("ignored body", path=path, repo=REPO)
    assert resolution.source == "registry"
    assert resolution.present
    assert not resolution.pool_invalid
    assert resolution.bindings == {"IV-A": "github:iv-a-user",
                                    "IV-B": "github:iv-b-user"}


def test_resolve_pool_absent_file_falls_back_to_issue_body(tmp_path):
    body = ("```json\n" + json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1",
                                      "verifiers": ["IV-A",
                                                    {"verifier_id": "IV-B",
                                                     "principal": "github:iv-b-user"}]})
            + "\n```")
    resolution = verifiers_mod.resolve_pool(body, path=tmp_path / "absent.json",
                                            repo=REPO)
    assert resolution.source == "issue_body"
    assert resolution.present
    assert resolution.status_map is None  # legacy path, no registry statuses
    assert resolution.bindings == {"IV-B": "github:iv-b-user"}
    assert resolution.declared == ["IV-A"]


def test_resolve_pool_invalid_registry_never_falls_back(tmp_path):
    path = tmp_path / "verifiers.json"
    path.write_text("{broken", encoding="utf-8")
    body = ("```json\n" + json.dumps({"schema": "ATLAS_VERIFIER_POOL_V1",
                                      "verifiers": [{"verifier_id": "IV-A",
                                                     "principal": "github:iv-a-user"}]})
            + "\n```")
    resolution = verifiers_mod.resolve_pool(body, path=path, repo=REPO)
    assert resolution.pool_invalid  # fail closed, no fallback bindings
    assert resolution.bindings == {}
    assert not resolution.present
    assert resolution.status_map == {}


def test_resolve_pool_missing_without_fallback_is_invalid(tmp_path):
    resolution = verifiers_mod.resolve_pool(None, path=tmp_path / "absent.json",
                                            repo=REPO, allow_issue_fallback=False)
    assert resolution.pool_invalid
    assert not resolution.present


# -- formal_iv_status: adversarial denials with positive controls -----------------

GOOD = make_receipt("rcpt-good")


def test_unknown_verifier_rejected_and_binding_fixes_it():
    receipt = make_receipt("rcpt-ghost", verifier="IV-GHOST")
    ok, reasons = evaluate(receipt, status_map=bound_status_map())
    assert not ok and "VERIFIER_UNKNOWN" in reasons
    # Positive control: bind IV-GHOST in the registry and it becomes acceptable.
    ok, reasons = evaluate(
        receipt, author="iv-a-user",
        bindings={"IV-GHOST": "github:iv-a-user"},
        status_map=bound_status_map(**{"IV-GHOST": "AUTHENTICATED"}))
    assert ok, reasons


def test_unbound_verifier_rejected_with_identity_unbound():
    ok, reasons = evaluate(GOOD, status_map=bound_status_map(**{"IV-A": "DECLARED_BUT_UNBOUND"}),
                           bindings={"IV-B": "github:iv-b-user"})
    assert not ok and "VERIFIER_IDENTITY_UNBOUND" in reasons
    # Positive control: owner binds a principal => AUTHENTICATED.
    ok, reasons = evaluate(GOOD, status_map=bound_status_map())
    assert ok, reasons


def test_inactive_verifier_rejected():
    ok, reasons = evaluate(GOOD, status_map=bound_status_map(**{"IV-A": "VERIFIER_INACTIVE"}),
                           bindings={"IV-B": "github:iv-b-user"})
    assert not ok and "VERIFIER_INACTIVE" in reasons
    ok, reasons = evaluate(GOOD, status_map=bound_status_map())
    assert ok, reasons


def test_repo_not_allowed_rejected():
    ok, reasons = evaluate(
        GOOD, status_map=bound_status_map(**{"IV-A": "VERIFIER_REPO_NOT_ALLOWED"}),
        bindings={"IV-B": "github:iv-b-user"})
    assert not ok and "VERIFIER_REPO_NOT_ALLOWED" in reasons
    ok, reasons = evaluate(GOOD, status_map=bound_status_map())
    assert ok, reasons


def test_principal_mismatch_rejected_and_matching_principal_accepted():
    ok, reasons = evaluate(GOOD, author="mallory", status_map=bound_status_map())
    assert not ok and "PRINCIPAL_MISMATCH" in reasons
    ok, reasons = evaluate(GOOD, author="iv-a-user", status_map=bound_status_map())
    assert ok, reasons


def test_bound_verifier_cannot_impersonate_another_bound_verifier():
    # Receipt claims IV-B's id but is posted by IV-A's principal.
    receipt = make_receipt("rcpt-impostor", verifier="IV-B")
    ok, reasons = evaluate(receipt, author="iv-a-user", status_map=bound_status_map())
    assert not ok and "PRINCIPAL_MISMATCH" in reasons
    ok, reasons = evaluate(receipt, author="iv-b-user", status_map=bound_status_map())
    assert ok, reasons


def test_candidate_author_equal_to_bound_principal_is_blocked():
    ok, reasons = evaluate(GOOD, pr_author="iv-a-user", status_map=bound_status_map())
    assert not ok and "AUTHOR_CONFLICT_BLOCKED" in reasons
    ok, reasons = evaluate(GOOD, pr_author="someone", status_map=bound_status_map())
    assert ok, reasons


def test_same_session_rejected_and_distinct_session_accepted():
    ok, reasons = evaluate(make_receipt("rcpt-sess", implementer_session="sess-iv-a"),
                           status_map=bound_status_map())
    assert not ok and "SESSION_CONFLICT" in reasons
    ok, reasons = evaluate(
        make_receipt("rcpt-sess2", implementer_session="sess-impl-1"),
        status_map=bound_status_map())
    assert ok, reasons
    ok, reasons = evaluate(make_receipt("rcpt-sess3"), status_map=bound_status_map())
    assert ok, reasons  # field absent: nothing to conflict


def test_write_activity_nonzero_rejected():
    ok, reasons = evaluate(make_receipt("rcpt-wr", writes=1),
                           status_map=bound_status_map())
    assert not ok and "WRITE_ACTIVITY_NONZERO" in reasons
    ok, reasons = evaluate(GOOD, status_map=bound_status_map())
    assert ok, reasons


def test_wrong_head_and_tree_rejected():
    ok, reasons = evaluate(GOOD, head=H3, tree=T3, status_map=bound_status_map())
    assert not ok and "HEAD_MISMATCH" in reasons and "TREE_MISMATCH" in reasons
    ok, reasons = evaluate(GOOD, status_map=bound_status_map())
    assert ok, reasons


def test_stale_receipt_after_head_move_rejected():
    # Receipt certified H1; candidate moved to H3. Exact-head identity only.
    ok, reasons = evaluate(GOOD, head=H3, tree=T3, status_map=bound_status_map())
    assert not ok and "HEAD_MISMATCH" in reasons


def test_copied_receipt_by_different_commenter_rejected():
    # A byte-identical receipt copied into another comment by a different
    # GitHub login is not authenticated identity.
    ok, reasons = evaluate(GOOD, author="iv-a-user", status_map=bound_status_map())
    assert ok, reasons
    ok, reasons = evaluate(GOOD, author="copycat", status_map=bound_status_map())
    assert not ok and "PRINCIPAL_MISMATCH" in reasons


def test_pool_invalid_rejects_everything_and_never_permissive():
    ok, reasons = evaluate(GOOD, status_map=bound_status_map(), pool_invalid=True)
    assert not ok and "VERIFIER_POOL_INVALID" in reasons
    # Even a perfect receipt under a perfect status map: still rejected.
    ok, reasons = evaluate(GOOD, pool_invalid=True)
    assert not ok and "VERIFIER_POOL_INVALID" in reasons
    ok, reasons = evaluate(GOOD, status_map=bound_status_map())
    assert ok, reasons


def test_existing_reasons_unchanged():
    _ok, reasons = evaluate(make_receipt("r1", author_conflict=True),
                           status_map=bound_status_map())
    assert "AUTHOR_CONFLICT" in reasons
    _ok, reasons = evaluate(make_receipt("r2", independence="FAIL"),
                           status_map=bound_status_map())
    assert "FORMAL_INDEPENDENCE_NOT_PASS" in reasons
    _ok, reasons = evaluate(make_receipt("r3", result="FAIL"),
                           status_map=bound_status_map())
    assert any(r.startswith("RESULT_NOT_PASS_SHAPED") for r in reasons)
    _ok, reasons = evaluate(make_receipt("r4", writes=0), present=False,
                           status_map=None)
    assert "VERIFIER_POOL_UNDEFINED" in reasons


def test_registry_status_path_keeps_source_identity_check():
    # AUTHENTICATED via status_map but no source author at all: fail closed.
    ok, reasons = evaluate(GOOD, author=None, status_map=bound_status_map())
    assert not ok and "SOURCE_IDENTITY_MISSING" in reasons


# -- registry membership grants no merge/write authority --------------------------


def test_pool_never_consulted_for_write_or_merge_decisions():
    import inspect

    assert "pool" not in inspect.signature(gate_mod.evaluate).parameters
    assert "bindings" not in inspect.signature(gate_mod.evaluate).parameters
    assert "pool" not in inspect.signature(router_mod.route).parameters
    assert "bindings" not in inspect.signature(router_mod.route).parameters
    # The merge guardian fails without a receipt even when the pool is valid
    # and the verifier bound: membership alone satisfies nothing.
    gate = gate_mod.evaluate(
        head=H1, ci_status="PASS", receipt=None, rejected_receipts={},
        claim_integrity="PASS", mergeable="MERGEABLE", pr_open=True,
        events=[], pr=10,
    )
    assert gate["merge_gate"] == "FAIL"
    assert "FORMAL_IV_MISSING" in gate["reasons"]


# -- snapshot-level tests with the fake gh harness --------------------------------


class FakeEnv:
    def __init__(self):
        self.prs = []
        self.commits = {}
        self.runs = {}
        self.reviews = {}
        self.issue = None
        self.issue_body = ""
        self.comments = []

    def add_pr(self, number, head, tree, *, author="someone", mergeable="MERGEABLE"):
        self.prs.append({
            "number": number, "title": f"PR {number}",
            "author": {"login": author}, "isDraft": False,
            "headRefName": f"branch-{number}", "headRefOid": head,
            "baseRefName": "main", "mergeable": mergeable,
            "url": f"https://example/{number}", "updatedAt": "2026-09-01T00:00:00Z",
        })
        self.commits[head] = {"sha": head, "commit": {"tree": {"sha": tree}}}
        self.runs[head] = [{"id": 101, "created_at": "2026-09-01T10:00:00Z",
                            "status": "completed", "conclusion": "success"}]

    def add_issue(self, comments=None, body=""):
        self.issue = {"number": 1, "title": "Atlas Autonomous DAG Control",
                      "state": "OPEN"}
        self.issue_body = body
        self.comments = comments or []


class FakeClient:
    def __init__(self, env: FakeEnv):
        self._env = env
        self.repo = REPO

    def default_branch(self):
        return "main"

    def branch_head(self, branch):
        return {"sha": "1" * 40, "tree": "2" * 40}

    def dag_issue(self):
        return self._env.issue

    def issue_body(self, number):
        return self._env.issue_body

    def issue_comments(self, number):
        return self._env.comments

    def open_prs(self):
        return self._env.prs

    def commit(self, sha):
        data = self._env.commits.get(sha)
        if not data:
            return None
        return {"sha": data["sha"], "tree": data["commit"]["tree"]["sha"]}

    def runs_for_head(self, sha):
        return self._env.runs.get(sha, [])

    def review_comments(self, pr):
        return self._env.reviews.get(pr, [])


def comments_with(*payloads, author="iv-a-user"):
    return [
        {"body": "```json\n" + json.dumps(p) + "\n```", "id": 1000 + i,
         "user": {"login": author}, "html_url": f"https://example/comment/{1000 + i}"}
        for i, p in enumerate(payloads)
    ]


def env_with_receipt(*, receipt_author="iv-a-user", pr_author="someone"):
    env = FakeEnv()
    env.add_pr(10, H1, T1, author=pr_author)
    env.add_issue(comments=comments_with(make_receipt("rcpt-live"),
                                         author=receipt_author))
    return env


def test_snapshot_committed_registry_unbound_pool_rejects_receipt():
    env = env_with_receipt()
    snapshot = build_snapshot(FakeClient(env))  # default pool = committed registry
    node = snapshot["nodes"][0]
    assert node["verifier_pool"]["source"] == "registry"
    assert node["verifier_pool"]["total"] == 2
    assert node["verifier_pool"]["authenticated"] == 0
    assert node["verifier_pool"]["unbound"] == 2
    assert node["formal_iv"] is None
    assert node["gate"]["merge_gate"] == "FAIL"
    assert any(r.startswith("FORMAL_IV_REJECTED") for r in node["gate"]["reasons"])
    assert "VERIFIER_IDENTITY_UNBOUND" in node["rejected_receipts"]["rcpt-live"]


def test_snapshot_invalid_registry_rejects_all_receipts(tmp_path):
    path = tmp_path / "verifiers.json"
    path.write_text("{broken", encoding="utf-8")
    env = env_with_receipt()
    snapshot = build_snapshot(FakeClient(env), pool_path=path)
    node = snapshot["nodes"][0]
    assert node["verifier_pool"]["invalid"] is True
    assert node["formal_iv"] is None
    assert "VERIFIER_POOL_INVALID" in node["rejected_receipts"]["rcpt-live"]
    assert node["gate"]["merge_gate"] == "FAIL"


def test_snapshot_missing_registry_without_issue_pool_is_fail_closed(tmp_path):
    env = env_with_receipt()
    env.issue_body = "no pool block"
    snapshot = build_snapshot(FakeClient(env), pool_path=tmp_path / "absent.json")
    node = snapshot["nodes"][0]
    assert node["formal_iv"] is None
    assert "VERIFIER_POOL_UNDEFINED" in node["rejected_receipts"]["rcpt-live"]


def test_snapshot_bound_pool_acceptes_exact_receipt(tmp_path):
    path = make_pool_file(tmp_path, BOUND_POOL)
    env = env_with_receipt()
    snapshot = build_snapshot(FakeClient(env), pool_path=path)
    node = snapshot["nodes"][0]
    assert node["verifier_pool"]["authenticated"] == 2
    assert node["formal_iv"] == "rcpt-live"
    assert node["gate"]["merge_gate"] == "PASS"


def test_snapshot_receipt_from_candidate_author_blocked_even_when_bound(tmp_path):
    path = make_pool_file(tmp_path, BOUND_POOL)
    env = env_with_receipt(pr_author="iv-a-user")  # candidate author IS the verifier
    snapshot = build_snapshot(FakeClient(env), pool_path=path)
    node = snapshot["nodes"][0]
    assert node["formal_iv"] is None
    assert "AUTHOR_CONFLICT_BLOCKED" in node["rejected_receipts"]["rcpt-live"]


def test_snapshot_conforms_to_dag_snapshot_schema_with_registry_pool(tmp_path):
    path = make_pool_file(tmp_path, BOUND_POOL)
    env = env_with_receipt()
    snapshot = build_snapshot(FakeClient(env), pool_path=path)
    errors = list(validator_for("dag_snapshot_v1.schema.json").iter_errors(snapshot))
    assert errors == [], "; ".join(
        f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors)


# -- CLI: read-only, deterministic -------------------------------------------------


def _fake_client_class(env):
    class _Cls:
        def __init__(self, repo=None):
            self.repo = REPO
            self._env = env

        def open_prs(self):
            return self._env.prs

        def commit(self, sha):
            data = self._env.commits.get(sha)
            if not data:
                return None
            return {"sha": data["sha"], "tree": data["commit"]["tree"]["sha"]}

        def dag_issue(self):
            return self._env.issue

        def issue_comments(self, number):
            return self._env.comments

    return _Cls


def test_cli_verifiers_json_deterministic_and_resolved_status(monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "GhClient", _fake_client_class(FakeEnv()))
    argv = ["--repo", REPO, "--json", "verifiers"]
    assert cli_mod.main(argv) == 0
    first = capsys.readouterr().out
    assert cli_mod.main(argv) == 0
    second = capsys.readouterr().out
    assert first == second  # byte-identical across calls
    out = json.loads(first)
    rows = {row["verifier_id"]: row for row in out["verifiers"]}
    assert rows["IV-A"]["status"] == "DECLARED_BUT_UNBOUND"
    assert rows["IV-A"]["principal"] is None


def test_cli_verifiers_invalid_registry_fails_closed(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "verifiers.json"
    bad.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(cli_mod, "GhClient", _fake_client_class(FakeEnv()))
    assert cli_mod.main(["--verifier-registry", str(bad), "--json", "verifiers"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["valid"] is False and out["verifiers"] == []


def test_cli_verifier_unknown_id_fails_closed(monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "GhClient", _fake_client_class(FakeEnv()))
    assert cli_mod.main(["--repo", REPO, "--json", "verifier", "ghost"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["registered"] is False
    assert out["status"] == "VERIFIER_UNKNOWN"


def test_cli_verifier_known_id_shows_unbound(monkeypatch, capsys):
    monkeypatch.setattr(cli_mod, "GhClient", _fake_client_class(FakeEnv()))
    assert cli_mod.main(["--repo", REPO, "--json", "verifier", "IV-A"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["registered"] is True
    assert out["status"] == "DECLARED_BUT_UNBOUND"


def test_cli_iv_eligibility_unbound_verifier_reports_reason(monkeypatch, capsys):
    env = env_with_receipt()
    monkeypatch.setattr(cli_mod, "GhClient", _fake_client_class(env))
    rc = cli_mod.main(["--repo", REPO, "--json", "iv-eligibility", "--pr", "10",
                       "--verifier", "IV-A"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["verifier_status"] == "DECLARED_BUT_UNBOUND"
    assert out["could_satisfy_gate"] is False
    assert "VERIFIER_IDENTITY_UNBOUND" in out["reasons"]
    assert out["candidate_head"] == H1 and out["candidate_tree"] == T1


def test_cli_iv_eligibility_bound_verifier_could_satisfy(tmp_path, monkeypatch, capsys):
    path = make_pool_file(tmp_path, BOUND_POOL)
    env = env_with_receipt()
    monkeypatch.setattr(cli_mod, "GhClient", _fake_client_class(env))
    rc = cli_mod.main(["--repo", REPO, "--verifier-registry", str(path),
                       "--json", "iv-eligibility", "--pr", "10", "--verifier", "IV-A"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verifier_status"] == "AUTHENTICATED"
    assert out["could_satisfy_gate"] is True
    assert out["receipts"][0]["eligible"] is True


def test_cli_iv_eligibility_deterministic(monkeypatch, capsys):
    env = env_with_receipt()
    monkeypatch.setattr(cli_mod, "GhClient", _fake_client_class(env))
    argv = ["--repo", REPO, "--json", "iv-eligibility", "--pr", "10",
            "--verifier", "IV-A"]
    assert cli_mod.main(argv) == 1
    first = capsys.readouterr().out
    assert cli_mod.main(argv) == 1
    assert capsys.readouterr().out == first
