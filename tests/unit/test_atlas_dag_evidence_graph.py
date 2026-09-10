"""Adversarial tests for FEATURE_07: EVIDENCE_DEPENDENCY_AND_INVALIDATION_GRAPH.

Core invariant under test: EVIDENCE_REUSE = EXPLICITLY_PROVEN_NOT_INFERRED.
Candidate-wide exact-head CI / formal IV NEVER transfer across HEAD movement;
narrow evidence survives ONLY via an explicit, provenance-bound equivalence
proof for the exact transition. Every denial has a load-bearing positive
control — removing that one constraint flips the verdict. Hermetic: no
network; fake clients and local git repos only.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import cli as cli_mod  # noqa: E402
from atlas_dag import dispatch as dispatch_mod  # noqa: E402
from atlas_dag import evidence as evidence_mod  # noqa: E402
from atlas_dag import evidence_graph as graph_mod  # noqa: E402

H1 = "a" * 40
T1 = "b" * 40
H2 = "c" * 40
T2 = "d" * 40
H3 = "e" * 40
T3 = "f" * 40
PH1 = "9" * 40  # stack parent head at freeze time
MAIN0 = "1" * 40
MAIN1 = "2" * 40

PROVENANCE = {"author": "github:lead-verifier",
              "issued_at_utc": "2026-09-02T00:00:00Z",
              "evidence_ref": "evidence://iv-proof-1"}


def make_record(evidence_id: str, **kw) -> dict:
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


def make_proof(*, old_head=H1, new_head=H3, contract="contract:api",
               scope=None, provenance=None, result="PROVEN") -> dict:
    proof = {"result": result, "covered_contract": contract,
             "old_head": old_head, "new_head": new_head}
    if scope is not None:
        proof["scope"] = scope
    if provenance is not None:
        proof["provenance"] = provenance
    return proof


def ctx(**kw) -> dict:
    context = {
        "pr": 10,
        "current_head": H1,
        "current_tree": T1,
        "current_parent_head": None,
        "current_main_head": None,
        "changed_files": [],
        "current_platform": None,
        "current_test_set": None,
        "current_toolchain": None,
        "current_verifier_principal": None,
        "current_verifier_session": None,
        "equivalence_proofs": [],
    }
    context.update(kw)
    return context


# -- dependency derivation ----------------------------------------------------


def test_dependencies_derive_from_record_fields_only():
    record = make_record("ev-deps-0001", scope="SUBSYSTEM",
                         covered_files=["src/b.py", "src/a.py"],
                         parent_head=PH1, main_head=MAIN0, platform="linux",
                         test_set="unit", toolchain="py312",
                         verifier_principal="github:iv-a",
                         verifier_session="sess-1")
    deps = {(d["class"], str(d["value"]))
            for d in graph_mod.derive_dependencies(record)}
    assert ("HEAD", H1) in deps
    assert ("TREE", T1) in deps
    assert ("PARENT_HEAD", PH1) in deps
    assert ("MAIN_HEAD", MAIN0) in deps
    assert ("PATH_SET", str(["src/a.py", "src/b.py"])) in deps
    assert ("SUBSYSTEM", "contract:api") in deps
    assert ("PLATFORM", "linux") in deps
    assert ("TEST_SET", "unit") in deps
    assert ("TOOLCHAIN", "py312") in deps
    assert ("VERIFIER_PRINCIPAL", "github:iv-a") in deps
    assert ("VERIFIER_SESSION", "sess-1") in deps
    # Deterministic: same record, same bytes.
    assert graph_mod.derive_dependencies(record) == \
        graph_mod.derive_dependencies(dict(record))
    # Fields never declared never invent a dependency.
    minimal = make_record("ev-deps-0002")
    classes = {d["class"] for d in graph_mod.derive_dependencies(minimal)}
    assert classes == {"HEAD", "TREE", "PATH_SET", "SUBSYSTEM"}


def test_new_optional_fields_pass_schema_validation():
    record = make_record("ev-schema-ok1", evidence_class="subsystem_tests",
                         parent_head=PH1, main_head=MAIN0, platform="linux",
                         test_set="unit", toolchain="py312",
                         verifier_principal="github:iv-a",
                         verifier_session="sess-1")
    assert evidence_mod.validate_record(record) == []
    bad = make_record("ev-schema-bad1", evidence_class="made_up_class")
    assert evidence_mod.validate_record(bad)


# -- candidate-wide never transfers -------------------------------------------


def test_candidate_wide_head_move_is_predecessor_only():
    record = make_record("ev-ci-stale1", evidence_class="exact_head_ci")
    moved = graph_mod.evaluate(record, ctx(current_head=H3, current_tree=T3,
                                           changed_files=None))
    assert moved["state"] == graph_mod.PREDECESSOR_ONLY
    assert "HEAD_MOVED" in moved["reasons"]
    assert moved["reuse_proof"] is None
    # Positive control: at the exact live head it is current.
    exact = graph_mod.evaluate(record, ctx())
    assert exact["state"] == graph_mod.EXACT_CURRENT
    # formal_iv demotes identically.
    iv = graph_mod.evaluate(make_record("ev-iv-stale1", evidence_class="formal_iv"),
                            ctx(current_head=H3, current_tree=T3,
                                changed_files=None))
    assert iv["state"] == graph_mod.PREDECESSOR_ONLY


def test_main_movement_alone_does_not_transfer_candidate_wide():
    # Record WITHOUT a main_head dependency: main moving is irrelevant.
    record = make_record("ev-ci-nomain1", evidence_class="exact_head_ci")
    stayed = graph_mod.evaluate(record, ctx(current_main_head=MAIN1))
    assert stayed["state"] == graph_mod.EXACT_CURRENT
    # Positive control: a record that DECLARES the main_head dependency is
    # invalidated when main moves (and stays current when it does not).
    bound = make_record("ev-ci-mainb1", evidence_class="exact_head_ci",
                        main_head=MAIN0)
    invalidated = graph_mod.evaluate(bound, ctx(current_main_head=MAIN1))
    assert invalidated["state"] == graph_mod.INVALIDATED
    assert "MAIN_HEAD_MOVED" in invalidated["reasons"]
    ok = graph_mod.evaluate(bound, ctx(current_main_head=MAIN0))
    assert ok["state"] == graph_mod.EXACT_CURRENT


# -- narrow evidence: reuse requires explicit valid proof ----------------------


def test_narrow_head_move_without_proof_is_predecessor_only():
    record = make_record("ev-sub-stale1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"])
    moved = graph_mod.evaluate(record, ctx(current_head=H3, current_tree=T3,
                                           changed_files=["src/other.py"]))
    assert moved["state"] == graph_mod.PREDECESSOR_ONLY
    assert "SUBSYSTEM_REUSE_REQUIRES_EQUIVALENCE_PROOF" in moved["reasons"]
    # No detected overlap is NOT proof: the artifact stays history-only.
    assert moved["reuse_proof"] is None


def test_narrow_reuse_with_valid_provenance_bound_proof():
    record = make_record("ev-sub-proof1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"])
    proof = make_proof(scope=["src/sub/a.py"], provenance=PROVENANCE)
    reused = graph_mod.evaluate(record, ctx(current_head=H3, current_tree=T3,
                                            changed_files=["src/sub/a.py"],
                                            equivalence_proofs=[proof]))
    assert reused["state"] == graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE
    assert reused["reuse_proof"]["provenance"] == PROVENANCE
    assert reused["reuse_proof"]["old_head"] == H1
    assert reused["reuse_proof"]["new_head"] == H3
    # Positive control: disjoint change + valid proof is reusable too.
    disjoint = graph_mod.evaluate(record, ctx(
        current_head=H3, current_tree=T3, changed_files=["src/other.py"],
        equivalence_proofs=[make_proof(scope=["src/sub/a.py"],
                                       provenance=PROVENANCE)]))
    assert disjoint["state"] == graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE


def test_changed_scoped_file_invalidates_narrow_evidence():
    record = make_record("ev-sub-path1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py", "src/sub/b.py"])
    base = ctx(current_head=H3, current_tree=T3,
               changed_files=["src/sub/b.py"])
    no_proof = graph_mod.evaluate(record, base)
    assert no_proof["state"] == graph_mod.INVALIDATED
    assert "PATHS_CHANGED" in no_proof["reasons"]
    # Proof whose declared scope does not cover the changed covered file is
    # insufficient — even when bound to the right transition.
    narrow_proof = make_proof(scope=["src/sub/a.py"], provenance=PROVENANCE)
    insufficient = graph_mod.evaluate(
        record, {**base, "equivalence_proofs": [narrow_proof]})
    assert insufficient["state"] == graph_mod.INVALIDATED
    assert "EQUIVALENCE_PROOF_SCOPE_INSUFFICIENT" in insufficient["reasons"]
    # Positive control: a proof whose scope covers every changed covered file
    # authorizes reuse.
    covering = make_proof(scope=["src/sub/a.py", "src/sub/b.py"],
                          provenance=PROVENANCE)
    reused = graph_mod.evaluate(record, {**base, "equivalence_proofs": [covering]})
    assert reused["state"] == graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE


def test_missing_changed_file_truth_is_unknown():
    record = make_record("ev-sub-unkn1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"])
    outcome = graph_mod.evaluate(record, ctx(current_head=H3, current_tree=T3,
                                             changed_files=None))
    assert outcome["state"] == graph_mod.UNKNOWN
    assert outcome["reasons"] == ["CHANGED_FILES_UNAVAILABLE"]
    assert outcome["uncertainty"] == ["CHANGED_FILES_UNAVAILABLE"]
    # Positive control: with truth available the same record resolves.
    resolved = graph_mod.evaluate(record, ctx(current_head=H3, current_tree=T3,
                                              changed_files=["src/x.py"]))
    assert resolved["state"] == graph_mod.PREDECESSOR_ONLY


# -- proof binding: transition, contract, provenance ----------------------------


def test_stale_and_wrong_transition_proofs_fail():
    record = make_record("ev-sub-trans1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"])
    base = ctx(current_head=H3, current_tree=T3,
               changed_files=["src/sub/a.py"])
    # A proof for A->B presented at B->C: new_head must equal the live head.
    stale = make_proof(old_head=H2, new_head=H3, scope=["src/sub/a.py"],
                       provenance=PROVENANCE)
    outcome = graph_mod.evaluate(record, {**base, "equivalence_proofs": [stale]})
    assert outcome["state"] == graph_mod.INVALIDATED
    assert "EQUIVALENCE_PROOF_NOT_BOUND" in outcome["reasons"]
    # new_head pinned to a different head than live.
    wrong_new = make_proof(old_head=H1, new_head=H2, scope=["src/sub/a.py"],
                           provenance=PROVENANCE)
    outcome = graph_mod.evaluate(record, {**base, "equivalence_proofs": [wrong_new]})
    assert outcome["state"] == graph_mod.INVALIDATED
    assert "EQUIVALENCE_PROOF_NOT_BOUND" in outcome["reasons"]
    # old_head must name the record's stored head, not any other head.
    wrong_old = make_proof(old_head=H2, new_head=H3, scope=["src/sub/a.py"],
                           provenance=PROVENANCE)
    outcome = graph_mod.evaluate(record, {**base, "equivalence_proofs": [wrong_old]})
    assert outcome["state"] == graph_mod.INVALIDATED
    assert "EQUIVALENCE_PROOF_NOT_BOUND" in outcome["reasons"]
    # Wrong covered contract.
    wrong_contract = make_proof(scope=["src/sub/a.py"], contract="contract:OTHER",
                                provenance=PROVENANCE)
    outcome = graph_mod.evaluate(record, {**base, "equivalence_proofs": [wrong_contract]})
    assert outcome["state"] == graph_mod.INVALIDATED
    assert "EQUIVALENCE_PROOF_CONTRACT_MISMATCH" in outcome["reasons"]
    # Positive control: the correctly bound proof is accepted.
    good = make_proof(scope=["src/sub/a.py"], provenance=PROVENANCE)
    assert graph_mod.evaluate(record, {**base, "equivalence_proofs": [good]})["state"] \
        == graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE


def test_proof_without_provenance_is_rejected():
    record = make_record("ev-sub-noprov1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"])
    base = ctx(current_head=H3, current_tree=T3,
               changed_files=["src/sub/a.py"])
    unprovenanced = make_proof(scope=["src/sub/a.py"])  # no provenance block
    outcome = graph_mod.evaluate(record, {**base, "equivalence_proofs": [unprovenanced]})
    assert outcome["state"] == graph_mod.INVALIDATED
    assert "EQUIVALENCE_PROOF_NO_PROVENANCE" in outcome["reasons"]
    # Partial provenance (author + time, no evidence ref) is still rejected.
    partial = make_proof(scope=["src/sub/a.py"],
                         provenance={"author": "github:lead-verifier",
                                     "issued_at_utc": "2026-09-02T00:00:00Z"})
    outcome = graph_mod.evaluate(record, {**base, "equivalence_proofs": [partial]})
    assert outcome["state"] == graph_mod.INVALIDATED
    assert "EQUIVALENCE_PROOF_NO_PROVENANCE" in outcome["reasons"]
    # Positive control: full provenance (who/when/what evidence) is accepted.
    provenanced = make_proof(scope=["src/sub/a.py"], provenance=PROVENANCE)
    assert graph_mod.evaluate(record, {**base, "equivalence_proofs": [provenanced]})["state"] \
        == graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE


# -- environment dependencies ---------------------------------------------------


def test_parent_head_dependency_invalidates_on_parent_movement():
    # Narrow artifact stored against parent head PH1; the parent moved.
    record = make_record("ev-sub-par1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"], parent_head=PH1)
    moved = graph_mod.evaluate(record, ctx(current_parent_head=H3,
                                           changed_files=["src/x.py"]))
    assert moved["state"] == graph_mod.INVALIDATED
    assert "PARENT_HEAD_MOVED" in moved["reasons"]
    # Candidate-wide artifact with the same dependency demotes to INVALIDATED
    # too (dependency change dominates the HEAD-move demotion).
    wide = make_record("ev-ci-par001", evidence_class="exact_head_ci",
                       parent_head=PH1)
    wide_out = graph_mod.evaluate(wide, ctx(current_head=H3, current_tree=T3,
                                            current_parent_head=H3,
                                            changed_files=None))
    assert wide_out["state"] == graph_mod.INVALIDATED
    assert "PARENT_HEAD_MOVED" in wide_out["reasons"]
    # Positive controls: parent unchanged + head current is EXACT_CURRENT;
    # no declared parent dependency is unaffected by parent movement.
    ok = graph_mod.evaluate(record, ctx(current_parent_head=PH1,
                                        changed_files=["src/x.py"]))
    assert ok["state"] == graph_mod.EXACT_CURRENT
    no_dep = make_record("ev-sub-parnd1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"])
    unaffected = graph_mod.evaluate(no_dep, ctx(current_parent_head=H3,
                                                changed_files=["src/x.py"]))
    assert "PARENT_HEAD_MOVED" not in unaffected["reasons"]


def test_parent_head_unavailable_is_unknown_not_guessed():
    record = make_record("ev-sub-paru1", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"], parent_head=PH1)
    outcome = graph_mod.evaluate(record, ctx(current_parent_head=None,
                                             changed_files=["src/x.py"]))
    assert outcome["state"] == graph_mod.UNKNOWN
    assert outcome["uncertainty"] == ["PARENT_HEAD_UNAVAILABLE"]


def test_verifier_principal_and_session_change_invalidates():
    record = make_record("ev-iv-verif1", evidence_class="formal_iv",
                         verifier_principal="github:iv-a",
                         verifier_session="sess-1")
    principal_moved = graph_mod.evaluate(
        record, ctx(current_verifier_principal="github:iv-b"))
    assert principal_moved["state"] == graph_mod.INVALIDATED
    assert "VERIFIER_PRINCIPAL_CHANGED" in principal_moved["reasons"]
    session_moved = graph_mod.evaluate(
        record, ctx(current_verifier_session="sess-2"))
    assert session_moved["state"] == graph_mod.INVALIDATED
    assert "VERIFIER_SESSION_CHANGED" in session_moved["reasons"]
    # Positive controls: unchanged verifier context stays current.
    assert graph_mod.evaluate(record, ctx(current_verifier_principal="github:iv-a",
                                          current_verifier_session="sess-1"))["state"] \
        == graph_mod.EXACT_CURRENT
    assert graph_mod.evaluate(record, ctx())["state"] == graph_mod.EXACT_CURRENT


def test_platform_evidence_cannot_cross_platforms():
    record = make_record("ev-plat-lin1", evidence_class="platform_validation",
                         platform="linux")
    windows = graph_mod.evaluate(record, ctx(current_platform="windows"))
    assert windows["state"] == graph_mod.INVALIDATED
    assert "PLATFORM_MISMATCH" in windows["reasons"]
    assert windows["reuse_proof"] is None
    # Positive control: same platform stays current.
    linux = graph_mod.evaluate(record, ctx(current_platform="linux"))
    assert linux["state"] == graph_mod.EXACT_CURRENT
    # Unknown live platform does not invent an invalidation.
    unknown = graph_mod.evaluate(record, ctx(current_platform=None))
    assert unknown["state"] == graph_mod.EXACT_CURRENT


def test_test_set_and_toolchain_change_invalidates():
    record = make_record("ev-sub-env001", scope="SUBSYSTEM",
                         covered_files=["src/sub/a.py"], test_set="unit",
                         toolchain="py312")
    test_moved = graph_mod.evaluate(record, ctx(current_test_set="integration"))
    assert test_moved["state"] == graph_mod.INVALIDATED
    assert "TEST_SET_CHANGED" in test_moved["reasons"]
    tool_moved = graph_mod.evaluate(record, ctx(current_toolchain="py313"))
    assert tool_moved["state"] == graph_mod.INVALIDATED
    assert "TOOLCHAIN_CHANGED" in tool_moved["reasons"]
    # Positive control: unchanged environment stays current.
    ok = graph_mod.evaluate(record, ctx(current_test_set="unit",
                                        current_toolchain="py312"))
    assert ok["state"] == graph_mod.EXACT_CURRENT


# -- lane isolation: no inheritance between PRs ---------------------------------


def test_wrong_lane_evidence_is_invalidated_never_reusable():
    record = make_record("ev-sub-lane1", scope="SUBSYSTEM", pr=10,
                         covered_files=["src/sub/a.py"])
    # Sibling PR 11 presents pr/10's artifact: head even matches the sibling's
    # live head, and a generous proof is offered — still never reusable.
    proof = make_proof(new_head=H1, scope=["src/sub/a.py"],
                       provenance=PROVENANCE)
    sibling = graph_mod.evaluate(record, ctx(pr=11, current_head=H1,
                                             current_tree=T1,
                                             equivalence_proofs=[proof]))
    assert sibling["state"] == graph_mod.INVALIDATED
    assert any(r.startswith("WRONG_LANE") for r in sibling["reasons"])
    # Positive control: evaluated against its own lane it is current.
    own = graph_mod.evaluate(record, ctx(pr=10))
    assert own["state"] == graph_mod.EXACT_CURRENT


# -- live truth always comes from the caller ------------------------------------


def test_stale_cached_store_cannot_override_live_truth(tmp_path):
    store = evidence_mod.EvidenceStore(tmp_path / "evidence.json")
    store.ingest(make_record("ev-store-st1"))
    record = store.for_pr(10)[0]
    # The store says head H1; the caller's live context says H3: the artifact
    # is predecessor-only, no matter what the cache recorded.
    outcome = graph_mod.evaluate(record, ctx(current_head=H3, current_tree=T3,
                                             changed_files=None))
    assert outcome["state"] == graph_mod.PREDECESSOR_ONLY
    assert "HEAD_MOVED" in outcome["reasons"]
    impact = graph_mod.evidence_impact(store.for_pr(10), H1, H3,
                                       changed_files=["src/elsewhere.py"])
    assert impact["artifacts"][0]["state"] == graph_mod.PREDECESSOR_ONLY
    # evaluate() takes NO truth from the store: passing an empty-context
    # caller (no live head) yields UNKNOWN, never "current from cache".
    unknown = graph_mod.evaluate(record, {"pr": 10})
    assert unknown["state"] == graph_mod.UNKNOWN


# -- evidence_impact: hypothetical transitions -----------------------------------


def test_evidence_impact_is_deterministic_and_complete():
    records = [
        make_record("ev-imp-ci001", evidence_class="exact_head_ci"),
        make_record("ev-imp-sub01", scope="SUBSYSTEM",
                    covered_files=["src/sub/a.py"]),
        make_record("ev-imp-sub02", scope="SUBSYSTEM",
                    covered_files=["src/sub/b.py"]),
    ]
    changed = ["src/sub/a.py", "README.md"]
    first = graph_mod.evidence_impact(records, H1, H3, changed)
    second = graph_mod.evidence_impact(list(reversed(records)), H1, H3,
                                       list(reversed(changed)))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["changed_files"] == sorted(changed)
    by_id = {a["evidence_id"]: a for a in first["artifacts"]}
    assert by_id["ev-imp-ci001"]["state"] == graph_mod.PREDECESSOR_ONLY
    assert by_id["ev-imp-sub01"]["state"] == graph_mod.INVALIDATED
    assert "PATHS_CHANGED" in by_id["ev-imp-sub01"]["reasons"]
    assert by_id["ev-imp-sub02"]["state"] == graph_mod.PREDECESSOR_ONLY
    # Hypothetical means read-only: records are untouched.
    assert all(r["head"] == H1 for r in records)


def test_evidence_impact_unavailable_changed_files_fails_closed():
    records = [make_record("ev-imp-unkn1", scope="SUBSYSTEM",
                           covered_files=["src/sub/a.py"])]
    impact = graph_mod.evidence_impact(records, H1, H3, None)
    assert impact["changed_files_available"] is False
    assert impact["artifacts"][0]["state"] == graph_mod.UNKNOWN


def test_changed_files_between_uses_git_subprocess_fail_closed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "one"], cwd=repo, check=True)
    first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True, check=True).stdout.strip()
    (repo / "b.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "two"], cwd=repo, check=True)
    second = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout.strip()
    changed = graph_mod.changed_files_between(repo, first, second)
    assert changed == ["b.txt"]
    # Failure path: not a git repo / bad object -> None, never guessed.
    assert graph_mod.changed_files_between(tmp_path, first, second) is None
    assert graph_mod.changed_files_between(repo, first, "0" * 40) is None

    def _boom(*_a, **_kw):
        raise OSError("no git")

    assert graph_mod.changed_files_between(repo, first, second,
                                           runner=_boom) is None


# -- graph builder ---------------------------------------------------------------


def test_build_graph_exposes_nodes_edges_states_and_uncertainty():
    records = [
        make_record("ev-gr-ci001", evidence_class="exact_head_ci"),
        make_record("ev-gr-sub01", scope="SUBSYSTEM", parent_head=PH1,
                    covered_files=["src/sub/a.py"]),
    ]
    graph = graph_mod.build_graph(records, ctx(current_parent_head=H3,
                                               changed_files=["src/x.py"]))
    assert [n["evidence_id"] for n in graph["nodes"]] == \
        ["ev-gr-ci001", "ev-gr-sub01"]
    assert graph["states"]["ev-gr-ci001"] == graph_mod.EXACT_CURRENT
    assert graph["states"]["ev-gr-sub01"] == graph_mod.INVALIDATED
    assert "PARENT_HEAD_MOVED" in graph["nodes"][1]["reasons"]
    edge_keys = {(e["from"], e["to"]) for e in graph["edges"]}
    assert ("ev-gr-sub01", "PARENT_HEAD") in edge_keys
    assert ("ev-gr-sub01", "PATH_SET") in edge_keys
    assert graph["uncertainty"] == []
    # Deterministic across input order.
    again = graph_mod.build_graph(list(reversed(records)),
                                  ctx(current_parent_head=H3,
                                      changed_files=["src/x.py"]))
    assert json.dumps(graph, sort_keys=True) == json.dumps(again, sort_keys=True)


# -- dispatch integration (additive evidence view) --------------------------------

REPO = "B0LK13/project-atlas"


class _DispatchFakeClient:
    """Minimal GhClient surface for dispatch planner tests (no network)."""

    def __init__(self, prs, runs):
        self._prs = prs
        self._runs = runs
        self.repo = REPO

    def open_prs(self):
        return list(self._prs)

    def dag_issue(self):
        return None

    def commit(self, sha):
        for pr in self._prs:
            if pr["headRefOid"] == sha:
                return {"sha": sha, "tree": pr["_tree"]}
        return None

    def runs_for_head(self, sha):
        return list(self._runs.get(sha, []))


def _dispatch_pr(head, tree):
    return {"number": 10, "title": "PR 10",
            "author": {"login": "someone"}, "isDraft": False,
            "headRefName": "branch-10", "headRefOid": head,
            "baseRefName": "main", "mergeable": "MERGEABLE",
            "url": "https://example/10", "updatedAt": "2026-09-01T00:00:00Z",
            "_tree": tree}


def _dispatch_store(base, records):
    store = evidence_mod.EvidenceStore(Path(base) / "evidence" / "evidence.json")
    for record in records:
        store.ingest(record)
    return store


def test_dispatch_exact_head_complete_with_current_evidence_no_duplicate(tmp_path):
    prs = [_dispatch_pr(H1, T1)]
    runs = {H1: [{"id": 101, "created_at": "2026-09-01T10:00:00Z",
                  "status": "completed", "conclusion": "success"}]}
    store = _dispatch_store(tmp_path, [make_record("ev-disp-cur1")])
    plan = dispatch_mod.plan_dispatch({"pr": 10, "frozen": True},
                                      _DispatchFakeClient(prs, runs),
                                      None, None, None,
                                      evidence_store=store)
    assert plan["ci"]["lane_state"] == dispatch_mod.COMPLETE
    assert plan["evidence"]["current_exact_head_complete"] is True
    assert plan["evidence"]["predecessor_only"] == []
    assert plan["evidence"]["reusable_by_proof"] == []
    # The evidence view is informational: the lane state is unchanged by it.
    result = dispatch_mod.execute_dispatch(plan, _DispatchFakeClient(prs, runs),
                                           "agent", {}, dry_run=False)
    assert result["ci"]["outcome"] == dispatch_mod.COMPLETE


def test_dispatch_predecessor_only_evidence_leaves_successor_runnable(tmp_path):
    prs = [_dispatch_pr(H3, T3)]  # candidate moved; no runs at H3
    store = _dispatch_store(tmp_path, [make_record("ev-disp-old1",
                                                   evidence_class="exact_head_ci")])
    plan = dispatch_mod.plan_dispatch({"pr": 10, "frozen": True},
                                      _DispatchFakeClient(prs, {}),
                                      None, None, None,
                                      evidence_store=store)
    assert plan["ci"]["lane_state"] == dispatch_mod.RUNNABLE
    assert plan["evidence"]["current_exact_head_complete"] is False
    assert plan["evidence"]["predecessor_only"] == ["ev-disp-old1"]
    # Positive control: current evidence flips the view only.
    store_current = _dispatch_store(tmp_path / "cur", [make_record("ev-disp-cur2")])
    plan_current = dispatch_mod.plan_dispatch(
        {"pr": 10, "frozen": True}, _DispatchFakeClient(prs, {}),
        None, None, None, evidence_store=store_current)
    assert plan_current["evidence"]["current_exact_head_complete"] is False
    assert plan_current["evidence"]["predecessor_only"] == ["ev-disp-cur2"]


def test_dispatch_stale_proof_never_suppresses_required_validation(tmp_path):
    # A stale subsystem artifact (head moved, no live truth for paths) must
    # not satisfy — or even appear as reusable in — the dispatch evidence
    # view, and the CI lane stays runnable.
    prs = [_dispatch_pr(H3, T3)]
    store = _dispatch_store(tmp_path, [make_record(
        "ev-disp-sub1", scope="SUBSYSTEM", covered_files=["src/sub/a.py"])])
    client = _DispatchFakeClient(prs, {})
    plan = dispatch_mod.plan_dispatch({"pr": 10, "frozen": True}, client,
                                      None, None, None, evidence_store=store)
    assert plan["evidence"]["reusable_by_proof"] == []
    assert plan["evidence"]["current_exact_head_complete"] is False
    assert plan["ci"]["lane_state"] == dispatch_mod.RUNNABLE
    # REUSABLE_BY_PROVEN_EQUIVALENCE never feeds the lane state even when a
    # caller-side evaluation would mark it reusable: the planner passes no
    # proofs, so nothing transfers.
    proof = make_proof(scope=["src/sub/a.py"], provenance=PROVENANCE)
    direct = graph_mod.evaluate(store.for_pr(10)[0], ctx(
        current_head=H3, current_tree=T3, changed_files=["src/sub/a.py"],
        equivalence_proofs=[proof]))
    assert direct["state"] == graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE
    assert plan["ci"]["lane_state"] == dispatch_mod.RUNNABLE


def test_dispatch_plan_is_deterministic_with_evidence_view(tmp_path):
    prs = [_dispatch_pr(H1, T1)]
    store = _dispatch_store(
        tmp_path, [make_record("ev-disp-d01"), make_record("ev-disp-d02")])
    client = _DispatchFakeClient(prs, {})
    plan1 = dispatch_mod.plan_dispatch({"pr": 10, "frozen": True}, client,
                                       None, None, None, evidence_store=store)
    plan2 = dispatch_mod.plan_dispatch({"pr": 10, "frozen": True}, client,
                                       None, None, None, evidence_store=store)
    assert json.dumps(plan1, sort_keys=True) == json.dumps(plan2, sort_keys=True)
    # Without a store the view is the empty default and lanes are unaffected.
    bare = dispatch_mod.plan_dispatch({"pr": 10, "frozen": True}, client,
                                      None, None, None)
    assert bare["evidence"]["records"] == []
    assert bare["evidence"]["current_exact_head_complete"] is False
    assert bare["ci"]["lane_state"] == plan1["ci"]["lane_state"]


# -- CLI --------------------------------------------------------------------------


class _OfflineClient:
    @property
    def repo(self):
        return None

    def open_prs(self):
        return []

    def commit(self, _sha):
        return None


def test_cli_evidence_graph_json_is_deterministic(tmp_path, monkeypatch, capsys):
    _dispatch_store(tmp_path / "rt", [
        make_record("ev-cli-gr001", evidence_class="exact_head_ci"),
        make_record("ev-cli-gr002", scope="SUBSYSTEM", parent_head=PH1,
                    covered_files=["src/sub/a.py"]),
    ])
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: _OfflineClient())
    runtime = tmp_path / "rt"
    argv = ["--runtime-dir", str(runtime), "--json", "evidence-graph", "10"]
    assert cli_mod.main(argv) == 0
    first = capsys.readouterr().out
    assert cli_mod.main(argv) == 0
    assert capsys.readouterr().out == first  # byte-identical across calls
    graph = json.loads(first)
    assert graph["pr"] == 10
    assert graph["github_unavailable"] == "GITHUB_UNAVAILABLE"
    assert {n["evidence_id"] for n in graph["nodes"]} == \
        {"ev-cli-gr001", "ev-cli-gr002"}
    assert graph["states"]["ev-cli-gr001"] == graph_mod.UNKNOWN
    assert graph["uncertainty"] == ["CURRENT_HEAD_TREE_UNKNOWN"]


def test_cli_evidence_lists_graph_state_and_dependencies(tmp_path, monkeypatch,
                                                         capsys):
    _dispatch_store(tmp_path / "rt", [make_record("ev-cli-ev001")])
    monkeypatch.setattr(cli_mod, "GhClient", lambda repo=None: _OfflineClient())
    argv = ["--runtime-dir", str(tmp_path / "rt"), "--json", "evidence", "10"]
    assert cli_mod.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    row = out["records"][0]
    assert row["state"] == graph_mod.UNKNOWN
    assert row["reasons"] == ["GITHUB_UNAVAILABLE"]
    dep_classes = {d["class"] for d in row["dependencies"]}
    assert {"HEAD", "TREE", "PATH_SET", "SUBSYSTEM"} <= dep_classes
    assert row["reuse_proof"] is None
    assert row["uncertainty"] == ["GITHUB_UNAVAILABLE"]
    # D-009 classification fields are preserved alongside the graph state.
    assert row["reuse_class"] == evidence_mod.UNKNOWN


def test_cli_evidence_impact_with_real_git_repo(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "one"], cwd=repo, check=True)
    first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True, check=True).stdout.strip()
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "two"], cwd=repo, check=True)
    second = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout.strip()
    _dispatch_store(
        tmp_path / "rt", [make_record("ev-cli-imp1", scope="SUBSYSTEM",
                                      covered_files=["a.txt"])])
    argv = ["--runtime-dir", str(tmp_path / "rt"), "--json", "evidence-impact",
            "--pr", "10", "--from", first, "--to", second,
            "--repo-dir", str(repo)]
    assert cli_mod.main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["changed_files"] == ["a.txt"]
    assert out["changed_files_available"] is True
    assert out["artifacts"][0]["state"] == graph_mod.INVALIDATED
    assert "PATHS_CHANGED" in out["artifacts"][0]["reasons"]
    # Deterministic across calls.
    assert cli_mod.main(argv) == 0
    assert capsys.readouterr().out == json.dumps(out, indent=2, sort_keys=True) + "\n"


def test_cli_evidence_impact_git_failure_fails_closed(tmp_path, monkeypatch,
                                                      capsys):
    _dispatch_store(tmp_path / "rt", [make_record("ev-cli-imp2", scope="SUBSYSTEM",
                                                    covered_files=["a.txt"])])
    argv = ["--runtime-dir", str(tmp_path / "rt"), "--json", "evidence-impact",
            "--pr", "10", "--from", H1, "--to", H3, "--repo-dir", str(tmp_path)]
    assert cli_mod.main(argv) == 0  # read-only report; failure is data, not crash
    out = json.loads(capsys.readouterr().out)
    assert out["changed_files"] is None
    assert out["changed_files_available"] is False
    assert out["artifacts"][0]["state"] == graph_mod.UNKNOWN
    # The store is untouched: impact is hypothetical.
    assert evidence_mod.EvidenceStore(
        tmp_path / "rt" / "evidence" / "evidence.json").for_pr(10)[0]["head"] == H1
