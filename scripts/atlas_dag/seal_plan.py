"""Automatic post-merge seal planning (FEATURE_09, AUTOMATIC_POST_MERGE_SEAL_PLANNING).

A seal plan answers, from repository truth only, what happened AFTER a merge:
what object was really merged, which pre-merge evidence still counts and for
what, what must be rerun on the merged object / current main, what
reconciliation remains, and when the lane can truthfully become SEALED.

Core invariants:

- MERGE_ELIGIBLE != MERGED != SEALED. A prospective merge SHA is never proof
  of a merge: only a MERGED-state PR whose mergeCommit resolves AND verifies
  against live repository history certifies the merge object.
- Planning only: this module never merges, never seals, never restacks, and
  grants no authority. READY_TO_SEAL is a claim about *plan* truth, not a seal.
- UNKNOWN preservation: ancestry, main advancement, evidence state, and claim
  consistency that cannot be resolved stay literal "UNKNOWN" with explicit
  uncertainty entries; UNKNOWN never becomes READY_TO_SEAL.
- Candidate-wide evidence (exact_head_ci / formal_iv / claim_integrity /
  freeze_validation / post_merge_seal) NEVER certifies the merged object:
  it transfers only as candidate history (requires_rerun) unless it is
  EXACT_CURRENT at the merged head itself. Narrow evidence survives only via
  an explicit, provenance-bound equivalence proof (FEATURE_07 rules reused
  verbatim; this module layers no new reuse semantics).
- Parent evidence is never inherited by children after a merge
  (stack_after_merge.parent_evidence_inherited is always false).
- Docs/WORKLOG/backlog reconciliation is listed as a requirement and is
  satisfiable only by stored ATLAS_EVIDENCE_V1 records (evidence_class
  post_merge_seal, covered_contract naming the reconciliation contract) that
  are EXACT_CURRENT at the verified merge commit. The check is never
  auto-performed and never self-certified.
- Determinism: plan_id is a sha256 over the material fields + pr (no wall
  clock); generated_at_utc is the only volatile field.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import events as events_mod
from . import evidence as evidence_mod
from . import evidence_graph as evidence_graph_mod
from .gh import is_ancestor as git_is_ancestor

SCHEMA_CONST = "ATLAS_POSTMERGE_PLAN_V1"
PLAN_SCHEMA = "atlas_postmerge_plan_v1.schema.json"

# Plan states (controlled vocabulary).
NOT_MERGED = "NOT_MERGED"
MERGE_OBJECT_UNRESOLVED = "MERGE_OBJECT_UNRESOLVED"
POSTMERGE_VALIDATION_REQUIRED = "POSTMERGE_VALIDATION_REQUIRED"
POSTMERGE_RECONCILIATION_REQUIRED = "POSTMERGE_RECONCILIATION_REQUIRED"
READY_TO_SEAL = "READY_TO_SEAL"
SEALED = "SEALED"
UNKNOWN = "UNKNOWN"
STATES = (NOT_MERGED, MERGE_OBJECT_UNRESOLVED, POSTMERGE_VALIDATION_REQUIRED,
          POSTMERGE_RECONCILIATION_REQUIRED, READY_TO_SEAL, SEALED, UNKNOWN)

# Seal projection states.
SEAL_STATE_SEALED = "SEALED"
SEAL_STATE_READY = "READY_TO_SEAL"
SEAL_STATE_NOT_READY = "NOT_READY"
SEAL_STATE_UNKNOWN = "UNKNOWN"

# Reconciliation contracts and their plan labels.
RECONCILIATION_ITEMS = (
    ("DOCS_RECONCILIATION", "contract:docs-reconciliation"),
    ("WORKLOG_RECONCILIATION", "contract:worklog-reconciliation"),
    ("BACKLOG_RECONCILIATION", "contract:backlog-reconciliation"),
)

# A valid exact-head CI run at the merged head satisfies the exact-head test
# requirement; any other candidate-wide CI state demands a rerun.
TEST_EXACT_HEAD_CI = "EXACT_HEAD_CI_ON_MERGE_COMMIT"
TEST_MAIN_COMPAT = "CURRENT_MAIN_COMPATIBILITY_VALIDATION"

_UNSET: Any = object()


class SealPlanError(RuntimeError):
    """Fail-closed: the plan cannot be built truthfully."""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_plan(plan: dict) -> list[str]:
    """Schema-validation error summaries for one plan ([] = valid)."""
    validator = events_mod.validator_for(PLAN_SCHEMA)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(plan)
    )


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _safe_call(fn: Callable[..., Any], *args: Any) -> Any:
    try:
        return fn(*args)
    except Exception:
        return None


def _ingested_events(client: Any) -> events_mod.IngestResult:
    issue = _safe_call(client.dag_issue)
    if not issue:
        return events_mod.IngestResult()
    comments = _safe_call(client.issue_comments, issue.get("number")) or []
    return events_mod.ingest_comments(comments)


def _main_head_tree(client: Any) -> tuple[str | None, str | None]:
    head_info = _safe_call(client.branch_head, "main")
    if not head_info:
        return None, None
    return head_info.get("sha"), head_info.get("tree")


def _candidate_tree(client: Any, head: str | None) -> str | None:
    if not head:
        return None
    commit = _safe_call(client.commit, head)
    return commit.get("tree") if commit else None


def _claim_consistency(events: list[dict], pr: int, merge_commit: str) -> str:
    """Latest CLAIM_INTEGRITY_CHANGED bound to the merge commit, else UNKNOWN."""
    matches = [e for e in events
               if e.get("event") == "CLAIM_INTEGRITY_CHANGED"
               and e.get("pr") == pr
               and e.get("head") == merge_commit]
    if not matches:
        return "UNKNOWN"
    state = str(matches[-1].get("state", "")).upper()
    if state == "FAIL":
        return "FAIL"
    if state == "PASS":
        return "PASS"
    return "UNKNOWN"


def _sealed_event_for(events: list[dict], pr: int, merge_commit: str) -> bool:
    """A SEALED event naming the EXACT merge commit object (idempotent seal)."""
    return any(e.get("event") == "SEALED" and e.get("pr") == pr
               and e.get("head") == merge_commit and e.get("state") == "SEALED"
               for e in events)


def _ownership_consistent(events: list[dict], pr: int, merge_commit: str) -> bool:
    """Ownership is consistent when it is not AMBIGUOUS (lane mutex truth)."""
    from . import model as model_mod  # local import: no truth dependency cycle
    status, _claimants = model_mod.ownership(events, pr, live_head=merge_commit)
    return status != "AMBIGUOUS"


def _build_context(pr: int, merged_head: str | None,
                   merged_tree: str | None, main_head: str | None,
                   main_tree: str | None, repo_dir: str | Path | None,
                   changed_files: Any, equivalence_proofs: list | None) -> dict:
    """Live FEATURE_07 context evaluated against the MERGED object, not the
    candidate: the object to certify is the merged head (or current main)."""
    current_head = merged_head
    current_tree = merged_tree
    resolved_changed: list[str] | None
    if changed_files is not _UNSET:
        resolved_changed = changed_files  # caller-supplied seam (may be None)
    else:
        resolved_changed = None
    return {
        "pr": pr,
        "current_head": current_head,
        "current_tree": current_tree,
        "current_parent_head": None,
        "current_main_head": main_head,
        "changed_files": resolved_changed,
        "current_platform": None,
        "current_test_set": None,
        "current_toolchain": None,
        "current_verifier_principal": None,
        "current_verifier_session": None,
        "equivalence_proofs": equivalence_proofs or [],
    }


def _classify_evidence(records: list[dict], context: dict,
                       advanced_since_merge: bool | str,
                       main_head: str | None) -> tuple[dict, list[dict], list[str]]:
    """Bucket every stored artifact for the merged-object context.

    Returns (classification, artifact summaries, uncertainty). Candidate-wide
    artifacts never certify the merged object unless EXACT_CURRENT at the
    merged head itself; INVALIDATED stays invalidated (never seal evidence);
    narrow reuse only via provenanced proof (FEATURE_07 rules unchanged).
    """
    buckets: dict[str, list[str]] = {
        "transferable_by_contract": [],
        "requires_rerun": [],
        "invalidated_by_merge": [],
        "invalidated_by_main_movement": [],
        "reusable_narrow": [],
        "unknown": [],
    }
    artifacts: list[dict] = []
    uncertainty: list[str] = []
    by_id = {str(r.get("evidence_id")): r for r in records}
    # Each artifact needs its own old-object -> target-object path delta.
    # A merge->main diff cannot prove candidate->merge equivalence.
    nodes = []
    graph_uncertainty = set()
    for record in records:
        ctx = dict(context)
        if context.get("repo_dir") and record.get("head") and context.get("current_head"):
            ctx["changed_files"] = _object_diff(
                context["repo_dir"], record["head"], context["current_head"])
        node = evidence_graph_mod.evaluate(record, ctx)
        if str(record.get("result", "")).upper() != "PASS":
            node.update(state=evidence_graph_mod.INVALIDATED,
                        reasons=["EVIDENCE_RESULT_NOT_PASS"], reuse_proof=None)
        nodes.append(node)
        graph_uncertainty.update(node["uncertainty"])
    graph = {"nodes": nodes, "uncertainty": sorted(graph_uncertainty)}
    for node in graph["nodes"]:
        record = by_id.get(str(node["evidence_id"])) or {}
        state = node["state"]
        evidence_id = str(node["evidence_id"])
        artifacts.append({
            "evidence_id": evidence_id,
            "evidence_class": node["evidence_class"],
            "state": state,
            "reasons": node["reasons"],
            "reuse_proof": node["reuse_proof"],
        })
        if state == evidence_graph_mod.UNKNOWN:
            buckets["unknown"].append(evidence_id)
        elif state == evidence_graph_mod.INVALIDATED:
            if "MAIN_HEAD_MOVED" in node["reasons"] or (
                    advanced_since_merge is True
                    and record.get("main_head") and main_head
                    and record.get("main_head") != main_head):
                buckets["invalidated_by_main_movement"].append(evidence_id)
            else:
                buckets["invalidated_by_merge"].append(evidence_id)
        elif state == evidence_graph_mod.EXACT_CURRENT:
            if evidence_graph_mod.is_candidate_wide(record):
                # Exact-current at the merged head: valid by contract for the
                # merged object (the only candidate-wide transfer allowed).
                buckets["transferable_by_contract"].append(evidence_id)
            else:
                buckets["reusable_narrow"].append(evidence_id)
        elif state == evidence_graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE:
            buckets["reusable_narrow"].append(evidence_id)
        else:  # PREDECESSOR_ONLY: history only, never post-merge certification
            buckets["requires_rerun"].append(evidence_id)
    uncertainty.extend(graph["uncertainty"])
    for key in buckets:
        buckets[key] = sorted(buckets[key])
    return buckets, artifacts, sorted(set(uncertainty))


def _stack_after_merge(client: Any, ancestry: Callable | None,
                       merged_branch: str | None, merge_commit: str | None,
                       base_branch: str | None) -> dict | None:
    """Children of the merged branch still pointing at it (planning only).

    retargetable: merge commit is IN the child's ancestry (child already
    contains the merged work; base retarget suffices).
    stale: base still names the merged branch but the merge commit is NOT in
    the child's ancestry (descendant predates/diverged from the merge).
    unknown: ancestry unverifiable — fail closed, never guessed.
    Parent evidence is NEVER inherited (explicit false field).
    """
    out: dict[str, Any] = {
        "merged_branch": merged_branch,
        "retargetable": [],
        "stale": [],
        "unknown": [],
        "parent_evidence_inherited": False,
        "parent_ownership_inherited": False,
        "truth_resolved": True,
    }
    if not merged_branch or merged_branch == base_branch:
        return out
    open_prs = _safe_call(getattr(client, "seal_open_prs", client.open_prs))
    if open_prs is None:
        out["truth_resolved"] = False
        return out
    children = sorted(
        (p for p in open_prs if p.get("baseRefName") == merged_branch),
        key=lambda p: p.get("number") or 0,
    )
    for child in children:
        number = child.get("number")
        child_head = child.get("headRefOid")
        if ancestry is None or not merge_commit or not child_head:
            out["unknown"].append(number)
            continue
        verdict = _safe_call(ancestry, merge_commit, child_head)
        if verdict is True:
            out["retargetable"].append(number)
        elif verdict is False:
            out["stale"].append(number)
        else:
            out["unknown"].append(number)
    return out


def _empty_plan(pr: int, repo: str | None, state: str, seal_state: str,
                clock: Callable[[], str]) -> dict:
    """Honest minimal packet for NOT_MERGED / UNKNOWN plan states."""
    plan = {
        "schema": SCHEMA_CONST,
        "plan_id": "",
        "generated_at_utc": clock(),
        "repo": repo,
        "pr": pr,
        "state": state,
        "merged": {
            "is_merged": False if state == NOT_MERGED else None,
            "method": None,
            "merge_commit": None,
            "verified": False,
            "evidence": [],
        },
        "candidate": {"head": None, "tree": None},
        "main": {
            "head_at_merge": None,
            "head_current": None,
            "tree_at_merge": None,
            "tree_current": None,
            "advanced_since_merge": "UNKNOWN",
        },
        "ancestry": {"candidate_in_main": "UNKNOWN", "via": None},
        "stack_after_merge": None,
        "evidence_classification": {
            "transferable_by_contract": [],
            "requires_rerun": [],
            "invalidated_by_merge": [],
            "invalidated_by_main_movement": [],
            "reusable_narrow": [],
            "unknown": [],
        },
        "post_merge_requirements": {
            "tests_required": [],
            "reconciliation_required": [],
            "freeze_seal_checks": [],
            "claim_consistency": "UNKNOWN",
            "ownership_release_eligible": False,
            "ownership_release_reasons": ["PR_NOT_MERGED"],
        },
        "blockers": [],
        "required_actions": ["AWAIT_MERGE_DECISION"],
        "seal_state": seal_state,
        "uncertainty": [],
        "provenance": {
            "generator": "atlas-dag seal-plan (FEATURE_09)",
            "projection_only": True,
            "grants_no_authority": True,
            "planning_only_no_seal_execution": True,
            "truth_sources": [
                "live GitHub PR/commit/branch truth",
                "FEATURE_07 evidence graph (merged-object context)",
                "#719 ATLAS_EVENT_V1 stream",
            ],
        },
    }
    material = {k: v for k, v in plan.items()
                if k not in ("plan_id", "generated_at_utc")}
    plan["plan_id"] = _plan_id(material, pr)
    return plan


def _plan_id(material: dict, pr: int) -> str:
    fingerprint = _canonical_sha256(material)
    return "sealplan-" + hashlib.sha256(
        f"{fingerprint}|{pr}".encode("utf-8")).hexdigest()[:16]


def build_seal_plan(
    pr_number: int,
    client: Any,
    *,
    evidence_store: evidence_mod.EvidenceStore | None = None,
    clock: Callable[[], str] = utcnow,
    ancestry: Callable[[str, str], bool | None] | None = None,
    repo_dir: str | Path | None = None,
    changed_files: Any = _UNSET,
    equivalence_proofs: list | None = None,
) -> dict:
    """Build one ATLAS_POSTMERGE_PLAN_V1 packet from live repository truth.

    `ancestry` is a (ancestor, descendant) -> bool|None seam; the default
    resolves repo-local ancestry via `git merge-base --is-ancestor` in
    `repo_dir` (None repo_dir => ancestry UNKNOWN, never guessed). Planning
    only: never merges, seals, or restacks.
    """
    if ancestry is None:
        if repo_dir is not None:
            ancestry = lambda a, d: git_is_ancestor(a, d, repo_dir)  # noqa: E731
        else:
            ancestry = getattr(client, "is_ancestor", None)

    repo = getattr(client, "repo", None)
    pr = _safe_call(getattr(client, "closed_pr", lambda _: None), pr_number)
    if pr is None:
        plan = _empty_plan(pr_number, repo, UNKNOWN, SEAL_STATE_UNKNOWN, clock)
        plan["required_actions"] = ["RESOLVE_PR_TRUTH"]
        plan["uncertainty"] = ["PR_TRUTH_UNRESOLVABLE"]
        plan["post_merge_requirements"]["ownership_release_reasons"] = \
            ["PR_TRUTH_UNRESOLVABLE"]
        return _finalize(plan)

    state = str(pr.get("state") or "").upper()
    candidate_head = pr.get("headRefOid")
    candidate_tree = _candidate_tree(client, candidate_head)

    if state in ("OPEN", "CLOSED"):
        # OPEN or CLOSED-unmerged: no merge has occurred. Any mergeCommit
        # shaped field on a non-merged PR is a prospective value and is never
        # merge proof: verified stays false, merge_commit stays null.
        plan = _empty_plan(pr_number, repo, NOT_MERGED, SEAL_STATE_NOT_READY,
                           clock)
        plan["candidate"] = {"head": candidate_head, "tree": candidate_tree}
        main_head, _main_tree = _main_head_tree(client)
        plan["main"]["head_current"] = main_head
        plan["main"]["tree_current"] = _candidate_tree(client, main_head)
        if not candidate_head:
            plan["uncertainty"].append("CANDIDATE_HEAD_UNKNOWN")
        if not candidate_tree:
            plan["uncertainty"].append("CANDIDATE_TREE_UNKNOWN")
        if not main_head:
            plan["uncertainty"].append("MAIN_HEAD_UNKNOWN")
        plan["uncertainty"] = sorted(plan["uncertainty"])
        material = {k: v for k, v in plan.items()
                    if k not in ("plan_id", "generated_at_utc")}
        plan["plan_id"] = _plan_id(material, pr_number)
        return _finalize(plan)

    if state != "MERGED":
        plan = _empty_plan(pr_number, repo, UNKNOWN, SEAL_STATE_UNKNOWN, clock)
        plan["uncertainty"] = ["PR_STATE_UNKNOWN"]
        plan["required_actions"] = ["RESOLVE_PR_TRUTH"]
        return _finalize(plan)

    # -- merged: resolve the actual merge object from live truth -------------
    merge_commit = None
    merge_info = pr.get("mergeCommit")
    if isinstance(merge_info, dict):
        merge_commit = merge_info.get("oid")
    if not merge_commit:
        merge_commit = pr.get("merge_commit_sha") if isinstance(
            pr.get("merge_commit_sha"), str) else None

    main_head, main_tree = _main_head_tree(client)
    events = _ingested_events(client).events
    uncertainty: set[str] = set()

    if not merge_commit:
        plan = _empty_plan(pr_number, repo, MERGE_OBJECT_UNRESOLVED,
                           SEAL_STATE_NOT_READY, clock)
        plan["merged"]["is_merged"] = True
        plan["candidate"] = {"head": candidate_head, "tree": candidate_tree}
        plan["main"]["head_current"] = main_head
        plan["main"]["tree_current"] = _candidate_tree(client, main_head)
        plan["blockers"] = ["MERGE_COMMIT_UNRESOLVED"]
        plan["required_actions"] = ["RESOLVE_MERGE_COMMIT_FROM_LIVE_HISTORY"]
        plan["post_merge_requirements"]["ownership_release_reasons"] = \
            ["MERGE_OBJECT_UNRESOLVED"]
        plan["uncertainty"] = ["MERGE_COMMIT_UNRESOLVED"]
        material = {k: v for k, v in plan.items()
                    if k not in ("plan_id", "generated_at_utc")}
        plan["plan_id"] = _plan_id(material, pr_number)
        return _finalize(plan)

    merge_object = _safe_call(client.commit, merge_commit)
    merge_tree = merge_object.get("tree") if merge_object else None
    exists = bool(merge_object and merge_object.get("sha") == merge_commit and merge_tree)
    merge_in_main = _safe_call(ancestry, merge_commit, main_head) if ancestry and main_head else None
    verified = bool(exists and pr.get("mergedAt") and merge_in_main is True
                    and pr.get("baseRefName") == "main")
    if not verified:
        uncertainty.add("MERGE_COMMIT_EXISTENCE_UNKNOWN" if exists is None
                        else "MERGE_COMMIT_NOT_IN_REPOSITORY")

    # -- ancestry of the candidate vs the merged object / current main -------
    via: str | None = None
    candidate_in_main: bool | str = "UNKNOWN"
    in_merge = _safe_call(ancestry, candidate_head, merge_commit) \
        if ancestry and candidate_head else None
    in_main = _safe_call(ancestry, candidate_head, main_head) \
        if ancestry and candidate_head and main_head else None
    if in_main is True:
        candidate_in_main, via = True, "CANDIDATE_ANCESTOR_OF_MAIN_HEAD"
    elif in_main is False and in_merge is not True:
        candidate_in_main, via = False, None
    elif in_merge is True and merge_in_main is True:
        # Candidate is inside the verified merge commit (merge-commit merge):
        # the merge object carries the candidate even when main has advanced.
        candidate_in_main, via = True, "CANDIDATE_ANCESTOR_OF_MERGE_COMMIT"
    elif in_main is False:
        candidate_in_main, via = False, None
    else:
        uncertainty.add("ANCESTRY_UNVERIFIABLE")
    if candidate_in_main == "UNKNOWN":
        uncertainty.add("CANDIDATE_IN_MAIN_UNKNOWN")

    # -- merge method requires actual commit parents, not ancestry alone ----
    parents = merge_object.get("parents", []) if merge_object else []
    method = "merge" if len(parents) >= 2 and candidate_head in parents[1:] else "UNKNOWN"
    # A single-parent result can be squash, rebase or fast-forward. The
    # GitHub merged record identifies the result, but does not prove method.
    if merge_in_main is True:
        advanced_since_merge = main_head != merge_commit
    else:
        advanced_since_merge = "UNKNOWN"
        uncertainty.add("MERGE_ANCESTRY_UNRESOLVED")
    head_at_merge = merge_commit if verified else None
    if not candidate_head or not candidate_tree or not main_tree or not merge_tree:
        uncertainty.add("OBJECT_HEAD_TREE_UNRESOLVED")

    # -- already sealed? (idempotent, exact merge commit object) --------------
    if _sealed_event_for(events, pr_number, merge_commit):
        sealed = True
    else:
        sealed = False

    # -- evidence classification against the merged-object context -----------
    records = evidence_store.for_pr(pr_number) if evidence_store is not None \
        else []
    context = _build_context(
        pr_number, merge_commit, merge_tree, main_head, main_tree,
        repo_dir, changed_files, equivalence_proofs)
    context["repo_dir"] = repo_dir
    classification, artifacts, evidence_uncertainty = _classify_evidence(
        records, context, advanced_since_merge, main_head)
    uncertainty.update(evidence_uncertainty)

    # -- post-merge requirements (deterministic, honest) ----------------------
    transferable = set(classification["transferable_by_contract"])
    exact_ci_ids = {str(r.get("evidence_id")) for r in records
                    if str(r.get("evidence_class")).strip().lower()
                    == "exact_head_ci"}
    tests_required: list[str] = []
    if not (transferable & exact_ci_ids):
        tests_required.append(TEST_EXACT_HEAD_CI)
    current_context = dict(context, current_head=main_head, current_tree=main_tree)
    main_classification, main_artifacts, main_uncertainty = _classify_evidence(
        records, current_context, advanced_since_merge, main_head)
    main_ci = set(main_classification["transferable_by_contract"]) & exact_ci_ids
    if advanced_since_merge is not False and not main_ci:
        tests_required.append(TEST_MAIN_COMPAT)

    satisfied_contracts = {
        str(r.get("covered_contract"))
        for r in records
        if str(r.get("evidence_id")) in transferable
        and str(r.get("evidence_class")).strip().lower() == "post_merge_seal"
    }
    reconciliation_required = sorted(
        label for label, contract in RECONCILIATION_ITEMS
        if contract not in satisfied_contracts)

    freeze_seal_checks: list[str] = []
    if any(e.get("event") == "HUMAN_GATE_REQUIRED" and e.get("pr") == pr_number
           for e in events):
        freeze_seal_checks.append("FREEZE_RESOLUTION_CONFIRMATION")

    claim_consistency = _claim_consistency(events, pr_number, merge_commit)
    if claim_consistency == "UNKNOWN":
        uncertainty.add("CLAIM_CONSISTENCY_UNKNOWN")

    stack_out = _stack_after_merge(
        client, ancestry, pr.get("headRefName"), merge_commit, pr.get("baseRefName"))
    children_pending = sorted(set(stack_out["stale"] + stack_out["retargetable"]
                                  + stack_out["unknown"]))
    if children_pending:
        reconciliation_required.append("STACK_TOPOLOGY_RECONCILIATION")
    if stack_out["unknown"] or not stack_out["truth_resolved"]:
        uncertainty.add("CHILD_ANCESTRY_UNKNOWN")

    # -- blockers -------------------------------------------------------------
    blockers: list[str] = []
    if not verified:
        blockers.append("MERGE_OBJECT_UNVERIFIED")
    if candidate_in_main == "UNKNOWN":
        blockers.append("ANCESTRY_UNKNOWN")
    if classification["unknown"]:
        blockers.append("EVIDENCE_UNKNOWN_PRESENT")
    if tests_required:
        blockers.append("POSTMERGE_TESTS_MISSING")
    blockers.extend(f"RECONCILIATION_PENDING:{item}"
                    for item in reconciliation_required)
    if claim_consistency != "PASS":
        blockers.append(f"CLAIM_INTEGRITY_NOT_PASS:{claim_consistency}")
    blockers.extend(f"FREEZE_PENDING:{item}" for item in freeze_seal_checks)
    if uncertainty:
        blockers.append("UNRESOLVED_TRUTH")
    if not _ownership_consistent(events, pr_number, merge_commit):
        blockers.append("OWNERSHIP_AMBIGUOUS")
    blockers = sorted(set(blockers))

    # -- plan state ------------------------------------------------------------
    if not verified:
        plan_state = MERGE_OBJECT_UNRESOLVED
    elif sealed:
        plan_state = SEALED
    elif tests_required:
        plan_state = POSTMERGE_VALIDATION_REQUIRED
    elif reconciliation_required:
        plan_state = POSTMERGE_RECONCILIATION_REQUIRED
    elif blockers:
        plan_state = POSTMERGE_VALIDATION_REQUIRED
    else:
        plan_state = READY_TO_SEAL

    seal_state = {
        SEALED: SEAL_STATE_SEALED,
        READY_TO_SEAL: SEAL_STATE_READY,
        UNKNOWN: SEAL_STATE_UNKNOWN,
    }.get(plan_state, SEAL_STATE_NOT_READY)

    # -- required actions ------------------------------------------------------
    required_actions: list[str] = []
    if plan_state == SEALED:
        required_actions.append("NONE_SEAL_IDEMPOTENT")
    else:
        required_actions.extend(
            f"RERUN_ON_MERGED_OBJECT:{eid}"
            for eid in classification["requires_rerun"])
        required_actions.extend(f"PERFORM_RECONCILIATION:{item}"
                                for item in reconciliation_required)
        if TEST_EXACT_HEAD_CI in tests_required:
            required_actions.append("RUN_EXACT_HEAD_CI_ON_MERGE_COMMIT")
        if TEST_MAIN_COMPAT in tests_required:
            required_actions.append("VALIDATE_CURRENT_MAIN_COMPATIBILITY")
        if plan_state == READY_TO_SEAL:
            required_actions.append("EMIT_SEALED_EVENT_FOR_MERGE_COMMIT")
    required_actions.extend(f"RECONCILE_STACK_CHILD:{n}" for n in children_pending)
    required_actions = sorted(required_actions)

    # -- ownership release eligibility -----------------------------------------
    ownership_consistent = _ownership_consistent(events, pr_number, merge_commit)
    release_reasons: list[str] = []
    if plan_state != SEALED:
        release_reasons.append("EXPLICIT_SEAL_REQUIRED")
    if blockers:
        release_reasons.append("BLOCKERS_PRESENT")
    if not ownership_consistent:
        release_reasons.append("OWNERSHIP_AMBIGUOUS")
    ownership_release_eligible = not release_reasons

    plan = {
        "schema": SCHEMA_CONST,
        "plan_id": "",
        "generated_at_utc": clock(),
        "repo": repo,
        "pr": pr_number,
        "state": plan_state,
        "merged": {
            "is_merged": True,
            "method": method,
            "merge_commit": merge_commit,
            "verified": verified,
            "evidence": artifacts,
        },
        "candidate": {"head": candidate_head, "tree": candidate_tree},
        "main": {
            "head_at_merge": head_at_merge,
            "head_current": main_head,
            "tree_at_merge": merge_tree,
            "tree_current": main_tree,
            "advanced_since_merge": advanced_since_merge,
        },
        "ancestry": {"candidate_in_main": candidate_in_main, "via": via},
        "stack_after_merge": stack_out,
        "evidence_classification": classification,
        "current_main_evidence": {"classification": main_classification,
                                  "artifacts": main_artifacts,
                                  "uncertainty": main_uncertainty},
        "post_merge_requirements": {
            "tests_required": sorted(tests_required),
            "reconciliation_required": reconciliation_required,
            "freeze_seal_checks": sorted(freeze_seal_checks),
            "claim_consistency": claim_consistency,
            "ownership_release_eligible": ownership_release_eligible,
            "ownership_release_reasons": sorted(release_reasons),
        },
        "blockers": blockers,
        "required_actions": required_actions,
        "seal_state": seal_state,
        "uncertainty": sorted(uncertainty),
        "provenance": {
            "generator": "atlas-dag seal-plan (FEATURE_09)",
            "projection_only": True,
            "grants_no_authority": True,
            "planning_only_no_seal_execution": True,
            "truth_sources": [
                "live GitHub PR/commit/branch truth",
                "FEATURE_07 evidence graph (merged-object context)",
                "#719 ATLAS_EVENT_V1 stream",
            ],
        },
    }
    material = {k: v for k, v in plan.items()
                if k not in ("plan_id", "generated_at_utc")}
    plan["plan_id"] = _plan_id(material, pr_number)
    return plan


def _finalize(plan: dict) -> dict:
    material = {k: v for k, v in plan.items() if k not in ("plan_id", "generated_at_utc")}
    plan["plan_id"] = _plan_id(material, plan["pr"])
    return plan


def _object_diff(repo_dir: Path | str, old: str, new: str) -> list[str] | None:
    """Endpoint tree delta (not merge-base delta), including deleted paths."""
    import subprocess
    try:
        result = subprocess.run(["git", "diff", "--name-only", "-z", old, new, "--"],
                                cwd=repo_dir, capture_output=True, text=True, timeout=60)
        return sorted(p for p in result.stdout.split("\0") if p) if result.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None
