"""Automatic parallel CI / formal-IV lane dispatch (FEATURE_06,
AUTOMATIC_PARALLEL_CI_IV_DISPATCH).

Once a candidate is frozen, CI and formal IV are INDEPENDENT SIBLING LANES:
`CI_RUNNABLE != IV_RUNNABLE`. A blocked IV lane never prevents CI and vice
versa; an unbound verifier pool is a fail-closed BLOCKED state, never idle
silence.

`plan_dispatch` is pure/read-only: it re-resolves the exact live HEAD/TREE
from repository truth and classifies each lane independently from the same
snapshot. Neither lane's state is computed from the other.

`execute_dispatch` performs only what the plan marks RUNNABLE, re-checks the
live HEAD before any mutation (a head move is HEAD_MOVED, never a stale
dispatch), and enforces registry permissions: CI needs the `ci_dispatch`
capability; the IV request is posted to the canonical #719 bus through the
FEATURE_04 emitter (permission-checked, deduplicated by deterministic event
id). `--dry-run` reports WOULD_DISPATCH / WOULD_REQUEST with zero mutation.

Dispatch grants no authority: an IV_REQUEST is a request, never an
ATLAS_IV_RECEIPT_V1 receipt, and a CI dispatch certifies nothing by itself.
"""
from __future__ import annotations

from . import agents as agents_mod
from . import emitter as emitter_mod
from . import events as events_mod
from . import evidence as evidence_mod
from . import evidence_graph as evidence_graph_mod
from . import verifiers as verifiers_mod

# Default CI workflow dispatched for a runnable frozen lane. Resolves in
# .github/workflows/ci.yml; the ref is the candidate head branch.
CI_WORKFLOW_ID = "ci.yml"

# Event type for a bounded IV request on the #719 bus (schema additive enum).
IV_REQUEST_EVENT = "IV_REQUEST"

# Lane states (controlled vocabulary).
RUNNABLE = "RUNNABLE"
ALREADY_RUNNING = "ALREADY_RUNNING"
COMPLETE = "COMPLETE"
BLOCKED = "BLOCKED"

# Executor outcomes (controlled vocabulary).
DISPATCHED = "DISPATCHED"
WOULD_DISPATCH = "WOULD_DISPATCH"
REQUESTED = "REQUESTED"
WOULD_REQUEST = "WOULD_REQUEST"
PERMISSION_DENIED = "PERMISSION_DENIED"
HEAD_MOVED = "HEAD_MOVED"
FAILED = "FAILED"

# Block reasons (controlled vocabulary).
CANDIDATE_NOT_FROZEN = "CANDIDATE_NOT_FROZEN"
HEAD_UNKNOWN = "HEAD_UNKNOWN"
TREE_UNKNOWN = "TREE_UNKNOWN"
VERIFIER_IDENTITY_UNBOUND = "VERIFIER_IDENTITY_UNBOUND"
VERIFIER_POOL_INVALID = "VERIFIER_POOL_INVALID"
VERIFIER_POOL_UNDEFINED = "VERIFIER_POOL_UNDEFINED"
INDEPENDENCE_CONFLICT = "INDEPENDENCE_CONFLICT"
PR_AUTHOR_UNKNOWN = "PR_AUTHOR_UNKNOWN"


def _blocked(reasons: list[str]) -> dict:
    return {"lane_state": BLOCKED, "reasons": sorted(reasons)}


def _live_pr(client, pr: int) -> dict | None:
    return next((p for p in client.open_prs() if p.get("number") == pr), None)


def _ingested_events(client) -> list[dict]:
    issue = client.dag_issue()
    if not issue:
        return []
    return events_mod.ingest_comments(client.issue_comments(issue["number"])).events


def _latest_live_event(events: list[dict], name: str, pr: int,
                       live_head: str | None) -> dict | None:
    matches = [
        e for e in events
        if e.get("event") == name and e.get("pr") == pr
        and (not e.get("head") or not live_head or e.get("head") == live_head)
    ]
    return matches[-1] if matches else None


def _plan_ci(client, head: str) -> dict:
    """CI lane from runs for the EXACT head only: predecessor-head runs can
    never satisfy a successor (DAG-005). Pure observation."""
    runs = client.runs_for_head(head)
    ordered = sorted(runs, key=lambda r: (r.get("created_at", ""),
                                          str(r.get("id", ""))))
    in_progress = [r for r in ordered if r.get("status") != "completed"]
    if in_progress:
        return {"lane_state": ALREADY_RUNNING, "reasons": [],
                "run_id": str(in_progress[-1].get("id"))}
    completed = [r for r in ordered if r.get("status") == "completed"]
    if completed:
        last = completed[-1]
        return {"lane_state": COMPLETE, "reasons": [],
                "run_id": str(last.get("id")),
                "conclusion": str(last.get("conclusion"))}
    return {"lane_state": RUNNABLE, "reasons": []}


def _plan_iv(client, pr: int, head: str, pr_author: str | None,
             pool: verifiers_mod.PoolResolution | None) -> dict:
    """IV lane: RUNNABLE only with an authenticated, independent verifier and
    no outstanding request for this exact head. Pool truth is FEATURE_05."""
    if pool is None or pool.pool_invalid:
        return _blocked([VERIFIER_POOL_INVALID])
    if not pool.present:
        return _blocked([VERIFIER_POOL_UNDEFINED])
    bindings = pool.bindings or {}
    if not bindings:
        # Pool present but no authenticated binding: the live state today.
        return _blocked([VERIFIER_IDENTITY_UNBOUND])
    if not pr_author:
        return _blocked([PR_AUTHOR_UNKNOWN])
    # Principal bindings are canonical `github:<login>` (receipts.py); the
    # PR author login is compared in the same form (no_self_iv).
    author_principal = f"github:{pr_author}"
    eligible = sorted(vid for vid, principal in bindings.items()
                      if principal != author_principal)
    if not eligible:
        return _blocked([INDEPENDENCE_CONFLICT])
    outstanding = _latest_live_event(_ingested_events(client), IV_REQUEST_EVENT,
                                     pr, head)
    if outstanding is not None:
        return {"lane_state": ALREADY_RUNNING, "reasons": [],
                "request_id": outstanding["event_id"]}
    return {"lane_state": RUNNABLE, "reasons": [], "verifiers": eligible}


def _plan_evidence(client, pr: int, head: str, tree: str | None,
                   store: evidence_mod.EvidenceStore | None) -> dict:
    """Additive FEATURE_07 evidence view: ingested artifacts for this PR
    resolved against the same live (head, tree) snapshot. Purely
    informational — it NEVER feeds the CI/IV lane states: lane truth comes
    only from exact-head runs and authenticated IV requests. A stale
    equivalence proof (REUSABLE_BY_PROVEN_EQUIVALENCE) therefore can never
    suppress required validation."""
    empty = {"records": [], "current_exact_head_complete": False,
             "predecessor_only": [], "reusable_by_proof": []}
    if store is None or not head:
        return empty
    try:
        records = store.for_pr(pr)
    except Exception:
        return empty  # unreadable cache must not disturb the lane plan
    evaluated = []
    for record in records:
        outcome = evidence_graph_mod.evaluate(record, {
            "pr": pr,
            "current_head": head,
            "current_tree": tree,
            "changed_files": None,  # unavailable: path reuse stays UNKNOWN
        })
        evaluated.append({
            "evidence_id": outcome["evidence_id"],
            "evidence_class": outcome["evidence_class"],
            "state": outcome["state"],
            "reasons": outcome["reasons"],
        })
    current_exact = [
        row["evidence_id"] for row in evaluated
        if row["state"] == evidence_graph_mod.EXACT_CURRENT
    ]
    return {
        "records": sorted(evaluated, key=lambda r: str(r["evidence_id"])),
        "current_exact_head_complete": bool(current_exact),
        "predecessor_only": sorted(
            row["evidence_id"] for row in evaluated
            if row["state"] == evidence_graph_mod.PREDECESSOR_ONLY),
        "reusable_by_proof": sorted(
            row["evidence_id"] for row in evaluated
            if row["state"] == evidence_graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE),
    }


def plan_dispatch(node: dict, client, agent_id: str | None,
                  agent_profile: dict | None,
                  pool_views_result: verifiers_mod.PoolResolution | None,
                  evidence_store: evidence_mod.EvidenceStore | None = None) -> dict:
    """Pure/read-only sibling-lane plan for one frozen-candidate node.

    agent_id / agent_profile are accepted for call-site symmetry with
    execute_dispatch; planning is agent-independent observation and never
    consults them. Reasons are sorted; output is deterministic for an
    unchanged snapshot.
    """
    pr = int(node["pr"])
    plan: dict = {"pr": pr, "head": None, "tree": None, "frozen": False,
                  "ci": _blocked([HEAD_UNKNOWN]), "iv": _blocked([HEAD_UNKNOWN])}

    live = _live_pr(client, pr)
    if live is None:
        return plan
    head = live.get("headRefOid")
    if not head:
        return plan
    plan["head"] = head
    commit = client.commit(head)
    if not commit or not commit.get("tree"):
        plan["ci"] = _blocked([TREE_UNKNOWN])
        plan["iv"] = _blocked([TREE_UNKNOWN])
        return plan
    plan["tree"] = commit["tree"]

    frozen = bool(node.get("frozen"))  # FEATURE_06 reuses node freeze truth
    plan["frozen"] = frozen
    if not frozen:
        plan["ci"] = _blocked([CANDIDATE_NOT_FROZEN])
        plan["iv"] = _blocked([CANDIDATE_NOT_FROZEN])
        return plan

    # Sibling independence is structural: both lanes are evaluated here, from
    # the same resolved snapshot; neither reads the other's state.
    plan["ci"] = _plan_ci(client, head)
    author_info = live.get("author") or {}
    plan["iv"] = _plan_iv(client, pr, head, author_info.get("login"),
                          pool_views_result)
    # FEATURE_07: additive informational evidence view. It never feeds the
    # lane states above: predecessor-only evidence leaves the successor
    # runnable (CI-lane semantics unchanged), and REUSABLE_BY_PROVEN_
    # EQUIVALENCE is never a substitute for exact-head validation.
    plan["evidence"] = _plan_evidence(client, pr, head, plan["tree"],
                                      evidence_store)
    return plan


def _lane_owner(client, pr: int) -> tuple[str | None, list[str]]:
    """(single owner, denial reasons). AMBIGUOUS is fail-closed."""
    from .model import ownership  # lazy: model imports dispatch at module level

    events = _ingested_events(client)
    status, claimants = ownership(events, pr)
    if status == "AMBIGUOUS":
        return None, ["OWNERSHIP_AMBIGUOUS_FAIL_CLOSED"]
    if status == "OWNED":
        return claimants[0], []
    return None, []


def _ci_permission(profile: dict | None) -> list[str]:
    """Why CI dispatch is denied (empty = permitted)."""
    if not profile or not profile.get("active", False):
        return ["AGENT_INACTIVE"]
    capabilities = {str(c) for c in profile.get("capabilities", [])}
    if "ci_dispatch" not in capabilities:
        return ["CAPABILITY_MISSING:ci_dispatch"]
    return []


def _iv_permission(profile: dict | None, agent_id: str,
                   lane_owner: str | None) -> list[str]:
    """IV request permission via the FEATURE_04 emitter checks, reusing a
    single-profile registry view (dispatch is lane-owner work)."""
    if not profile:
        return ["AGENT_NOT_REGISTERED:UNKNOWN_AGENT"]
    registry = agents_mod.RegistryResult(registry={"agents": [profile]})
    checks = emitter_mod.check_emit_permission(
        registry, agent_id, IV_REQUEST_EVENT, lane_owner)
    return sorted(checks.reasons)


def _iv_request_note(plan: dict, eligible: list[str]) -> str:
    head = str(plan.get("head") or "")[:12]
    return (f"IV_REQUEST: formal independent verification requested for "
            f"pr/{plan['pr']} @ {head}. Candidate is FROZEN; eligible "
            f"authenticated verifiers: {', '.join(eligible)}. This is a "
            f"REQUEST for IV — NOT an ATLAS_IV_RECEIPT_V1 receipt; it "
            f"certifies nothing and grants no authority.")


def _execute_ci(plan: dict, client, live: dict | None, live_head: str | None,
                agent_profile: dict | None, dry_run: bool, head_moved: bool,
                deny_reasons: list[str]) -> dict:
    lane = plan.get("ci") or {}
    if lane.get("lane_state") != RUNNABLE:
        return {"outcome": lane.get("lane_state", BLOCKED),
                "reasons": sorted(lane.get("reasons") or [])}
    if deny_reasons:
        return {"outcome": PERMISSION_DENIED, "reasons": sorted(deny_reasons)}
    if head_moved:
        return {"outcome": HEAD_MOVED,
                "reasons": ["LIVE_HEAD_MISMATCHES_PLAN"]}
    if dry_run:
        ref = (live or {}).get("headRefName") or live_head
        return {"outcome": WOULD_DISPATCH, "reasons": [],
                "workflow_id": CI_WORKFLOW_ID, "ref": ref}
    try:
        ref = (live or {}).get("headRefName") or live_head
        client.dispatch_workflow(CI_WORKFLOW_ID, ref)
    except Exception as exc:  # GhError from gh; fake clients raise alike
        return {"outcome": FAILED, "reasons": [f"CI_DISPATCH_FAILED:{exc}"]}
    return {"outcome": DISPATCHED, "reasons": [],
            "workflow_id": CI_WORKFLOW_ID, "ref": ref}


def _execute_iv(plan: dict, client, agent_id: str, agent_profile: dict | None,
                dry_run: bool, head_moved: bool, deny_reasons: list[str],
                emitter) -> dict:
    lane = plan.get("iv") or {}
    if lane.get("lane_state") != RUNNABLE:
        return {"outcome": lane.get("lane_state", BLOCKED),
                "reasons": sorted(lane.get("reasons") or [])}
    # The planner guarantees an authenticated verifier here; never fabricate
    # a request target when that guarantee does not hold.
    eligible = sorted(lane.get("verifiers") or [])
    if not eligible:
        return {"outcome": BLOCKED, "reasons": [VERIFIER_IDENTITY_UNBOUND]}
    if deny_reasons:
        return {"outcome": PERMISSION_DENIED, "reasons": sorted(deny_reasons)}
    if head_moved:
        return {"outcome": HEAD_MOVED, "reasons": ["LIVE_HEAD_MISMATCHES_PLAN"]}
    note = _iv_request_note(plan, eligible)
    if dry_run:
        return {"outcome": WOULD_REQUEST, "reasons": [],
                "verifiers": eligible}
    try:
        ctx = emitter.resolve_context(client, int(plan["pr"]),
                                      agent_profile or {},
                                      expected_repo=client.repo)
        payload = emitter.build_event(ctx, IV_REQUEST_EVENT, "REQUESTED", note)
        registry = agents_mod.RegistryResult(registry={"agents": [agent_profile]})
        status = emitter.emit_event(client, registry, payload, dry_run=False)
    except emitter_mod.EmitError as exc:
        return {"outcome": FAILED, "reasons": [f"IV_REQUEST_FAILED:{exc}"]}
    outcome = REQUESTED if status == "posted" else ALREADY_RUNNING
    return {"outcome": outcome, "reasons": [], "event_id": payload["event_id"],
            "verifiers": eligible}


def execute_dispatch(plan: dict, client, agent_id: str,
                     agent_profile: dict | None, *, dry_run: bool = True,
                     emitter=None) -> dict:
    """Execute a plan_dispatch plan with permission checks and a live-HEAD
    guard. Only RUNNABLE lanes mutate; every denial is explicit; executing
    twice for the same exact head cannot duplicate dispatches/requests (the
    second call observes ALREADY_RUNNING)."""
    em = emitter if emitter is not None else emitter_mod
    pr = int(plan["pr"])
    live = _live_pr(client, pr)
    live_head = live.get("headRefOid") if live else None
    plan_head = plan.get("head")
    head_moved = not live_head or live_head != plan_head

    lane_owner, ownership_denials = _lane_owner(client, pr)
    if not ownership_denials and lane_owner is not None \
            and lane_owner != agent_id:
        ownership_denials = [f"OWNERSHIP_MUTEX_HELD_BY:{lane_owner}"]
    ci_denials = sorted(set(ownership_denials)
                        | set(_ci_permission(agent_profile)))
    iv_denials = sorted(set(ownership_denials)
                        | set(_iv_permission(agent_profile, agent_id,
                                             lane_owner)))

    result = {"pr": pr, "head": plan_head, "dry_run": bool(dry_run),
              "ci": _execute_ci(plan, client, live, live_head, agent_profile,
                                dry_run, head_moved, ci_denials),
              "iv": _execute_iv(plan, client, agent_id, agent_profile, dry_run,
                                head_moved, iv_denials, em)}
    return result
