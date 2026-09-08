"""FEATURE_09 exact-object and closure adversarial controls."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from atlas_dag import seal_plan as sp
from test_atlas_dag_evidence_graph import PROVENANCE, make_proof, make_record
from test_atlas_dag_handoff import make_event

C, M, N, T = [x * 40 for x in "acdb"]


class Client:
    repo = "B0LK13/project-atlas"

    def __init__(self):
        self.pr = dict(number=10, state="MERGED", mergedAt="2026-09-08T00:00:00Z",
                       mergeCommit={"oid": M}, headRefOid=C,
                       headRefName="feature", baseRefName="main")
        self.main = M
        self.parents = [N, C]
        self.events = []
        self.children = []
        self.ancestry = {(C, M): True, (C, N): True, (M, N): True}

    def closed_pr(self, number):
        return self.pr

    def default_branch(self):
        return "main"

    def branch_head(self, branch):
        return {"sha": self.main, "tree": T}

    def commit(self, sha):
        return {"sha": sha, "tree": T, "parents": self.parents if sha == M else []}

    def merge_commit_exists(self, sha):
        return True

    def is_ancestor(self, a, b):
        return True if a == b else self.ancestry.get((a, b), False)

    def dag_issue(self):
        return {"number": 719}

    def issue_comments(self, number):
        return [{"body": "```json\n" + json.dumps(e) + "\n```"} for e in self.events]

    def open_prs(self):
        return self.children


class Store:
    def __init__(self, records):
        self.records = records

    def for_pr(self, pr):
        return self.records


def record(eid, head=M, cls="exact_head_ci", **kw):
    return make_record(eid, head=head, tree=T, evidence_class=cls, **kw)


def complete(client):
    client.events = [make_event("evt-claim-pass", "CLAIM_INTEGRITY_CHANGED",
                                pr=10, head=M, state="PASS")]
    return [record("ev-merge-ci"), *[
        record("ev-" + label.lower(), cls="post_merge_seal", covered_contract=contract)
        for label, contract in sp.RECONCILIATION_ITEMS]]


def plan(client=None, records=(), **kw):
    client = client or Client()
    result = sp.build_seal_plan(10, client, evidence_store=Store(records),
                               clock=lambda: "2026-09-08T00:00:00Z", **kw)
    assert sp.validate_plan(result) == []
    return result


def test_open_rejects_prospective_merge_sha():
    client = Client()
    client.pr["state"] = "OPEN"
    p = plan(client)
    assert p["state"] == "NOT_MERGED"
    assert p["merged"]["merge_commit"] is None
    assert not p["merged"]["verified"]


def test_real_merge_object_and_missing_validation():
    p = plan()
    assert p["merged"]["verified"]
    assert p["merged"]["method"] == "merge"
    assert p["main"]["head_at_merge"] == M
    assert p["main"]["tree_at_merge"] == T
    assert p["state"] == "POSTMERGE_VALIDATION_REQUIRED"


@pytest.mark.parametrize("mutation", ["no_object", "off_main", "no_merged_at"])
def test_unresolved_merge_identity(mutation):
    c = Client()
    if mutation == "no_object":
        c.pr["mergeCommit"] = None
    elif mutation == "off_main":
        c.main = N
        c.ancestry[(M, N)] = False
    else:
        c.pr["mergedAt"] = None
    p = plan(c)
    assert p["state"] == "MERGE_OBJECT_UNRESOLVED"
    assert not p["post_merge_requirements"]["ownership_release_eligible"]


@pytest.mark.parametrize("in_candidate", [True, False])
def test_single_parent_does_not_prove_merge_method(in_candidate):
    c = Client()
    c.parents = [N]
    c.ancestry[(C, M)] = in_candidate
    p = plan(c)
    assert p["merged"]["verified"]
    assert p["merged"]["method"] == "UNKNOWN"


def test_candidate_ci_and_iv_never_certify_merge():
    p = plan(records=[record("ev-ci", C), record("ev-iv", C, "formal_iv")])
    assert p["evidence_classification"]["requires_rerun"] == ["ev-ci", "ev-iv"]
    assert sp.TEST_EXACT_HEAD_CI in p["post_merge_requirements"]["tests_required"]


def test_reconciliation_gap_and_ready_without_release():
    c = Client()
    records = complete(c)
    assert plan(c, records[:1])["state"] == "POSTMERGE_RECONCILIATION_REQUIRED"
    p = plan(c, records)
    assert p["state"] == "READY_TO_SEAL"
    assert not p["post_merge_requirements"]["ownership_release_eligible"]


def test_main_advancement_requires_separate_compatibility():
    c = Client()
    records = complete(c)
    c.main = N
    p = plan(c, records)
    assert p["main"]["advanced_since_merge"] is True
    assert p["main"]["head_at_merge"] == M
    assert p["post_merge_requirements"]["tests_required"] == [sp.TEST_MAIN_COMPAT]
    records.append(record("ev-main-ci", N))
    assert plan(c, records)["state"] == "READY_TO_SEAL"


def test_failed_evidence_never_satisfies_validation():
    c = Client()
    records = complete(c)
    records[0]["result"] = "FAIL"
    assert plan(c, records)["state"] == "POSTMERGE_VALIDATION_REQUIRED"


def test_stale_equivalence_proof_and_explicit_reuse():
    r = record("ev-narrow", C, "subsystem_tests", scope="SUBSYSTEM")
    proof = make_proof(old_head=C, new_head=N, scope=["src/a.py"], provenance=PROVENANCE)
    assert not plan(records=[r], changed_files=["src/a.py"],
                    equivalence_proofs=[proof])["evidence_classification"]["reusable_narrow"]
    proof["new_head"] = M
    p = plan(records=[r], changed_files=["src/a.py"], equivalence_proofs=[proof])
    assert p["evidence_classification"]["reusable_narrow"] == ["ev-narrow"]


def test_stack_child_after_parent_merge_blocks_reconciliation():
    c = Client()
    records = complete(c)
    c.children = [{"number": 11, "headRefOid": C, "baseRefName": "feature"}]
    p = plan(c, records)
    assert p["stack_after_merge"]["stale"] == [11]
    assert not p["stack_after_merge"]["parent_evidence_inherited"]
    assert p["state"] == "POSTMERGE_RECONCILIATION_REQUIRED"
    assert "RECONCILE_STACK_CHILD:11" in p["required_actions"]


def test_sealed_explicit_and_idempotent():
    c = Client()
    records = complete(c)
    c.events.append(make_event("evt-sealed", "SEALED", pr=10, head=M, state="SEALED"))
    p = plan(c, records)
    assert p["state"] == "SEALED"
    assert p["post_merge_requirements"]["ownership_release_eligible"]
    assert p == plan(c, records)


@pytest.mark.parametrize("unknown", ["pr", "tree", "ancestry", "claim", "freeze"])
def test_unknown_or_gate_never_ready(unknown):
    c = Client()
    records = complete(c)
    if unknown == "pr":
        c.pr = None
    elif unknown == "tree":
        c.commit = lambda sha: None
    elif unknown == "ancestry":
        c.is_ancestor = lambda a, b: None
    elif unknown == "claim":
        c.events[0]["state"] = "NOT_PASS"
    else:
        c.events.append(make_event("evt-frozen", "HUMAN_GATE_REQUIRED", pr=10, head=M))
    assert plan(c, records)["state"] != "READY_TO_SEAL"


def test_handoff_projects_same_evidence_store():
    from atlas_dag.handoff import _post_merge_summary
    c = Client()
    records = complete(c)
    summary = _post_merge_summary(c, 10, lambda: "2026-09-08T00:00:00Z", Store(records))
    assert summary["state"] == plan(c, records)["state"] == "READY_TO_SEAL"


def test_cli_accepts_documented_json_position():
    from atlas_dag.cli import build_parser
    args = build_parser().parse_args(["seal-plan", "--pr", "10", "--json"])
    assert args.json


def test_main_movement_invalidates_main_bound_evidence():
    c = Client()
    c.main = N
    r = record("ev-main-bound", main_head=M)
    p = plan(c, [r])
    assert p["evidence_classification"]["invalidated_by_main_movement"] == ["ev-main-bound"]


def test_unknown_state_is_unknown_not_unmerged():
    c = Client()
    c.pr["state"] = "UNAVAILABLE"
    assert plan(c)["state"] == "UNKNOWN"


def test_claim_failure_cannot_be_overridden_by_seal_for_release():
    c = Client()
    records = complete(c)
    c.events[0]["state"] = "FAIL"
    c.events.append(make_event("evt-sealed", "SEALED", pr=10, head=M, state="SEALED"))
    assert not plan(c, records)["post_merge_requirements"]["ownership_release_eligible"]


def test_seal_for_candidate_is_not_merge_closure():
    c = Client()
    records = complete(c)
    c.events.append(make_event("evt-sealed", "SEALED", pr=10, head=C, state="SEALED"))
    assert plan(c, records)["state"] == "READY_TO_SEAL"


def test_unavailable_children_never_ready():
    c = Client()
    records = complete(c)
    def unavailable():
        raise RuntimeError("offline")
    c.open_prs = unavailable
    assert plan(c, records)["state"] != "READY_TO_SEAL"


def test_schema_rejects_ready_with_blockers():
    c = Client()
    p = plan(c, complete(c))
    p["blockers"] = ["UNKNOWN"]
    assert sp.validate_plan(p)


def test_merged_lane_handoff_uses_planner(monkeypatch):
    from atlas_dag import handoff
    c = Client()
    records = complete(c)
    monkeypatch.setattr(handoff.model_mod, "build_snapshot", lambda *a, **kw: {"nodes": []})
    packet = handoff.build_handoff(10, "resume", c, evidence_store=Store(records))
    assert handoff.validate_packet(packet) == []
    assert packet["post_merge"]["state"] == "READY_TO_SEAL"
    assert packet["post_merge"]["plan_id"] == plan(c, records)["plan_id"]
