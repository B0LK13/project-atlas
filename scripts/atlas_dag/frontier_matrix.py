"""Multidimensional runnable frontier (FEATURE_12).

FRONTIER != SINGLE_QUEUE
ACTION_RANK != ACTION_AUTHORITY
SAME_LANE_CAN_HAVE_MULTIPLE_INDEPENDENT_ACTIONS

Each frontier item is an ACTION (not a PR). Presence on the frontier never
grants execution authority. Ranking occurs only within comparable authorized
action classes. Feature 10 scores are one dimension among many.

Consumes (never duplicates): Feature 1 registry, Feature 2 router,
Feature 3 stack, Feature 6 dispatch plans, Feature 9 seal-plan projections,
Feature 10 scoring factors. Feature 11 steal consumes the WRITE /
OWNERSHIP_CLAIM projection via write_steal_candidates().
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from . import agents as agents_mod
from . import dispatch as dispatch_mod
from . import events as events_mod
from . import router as router_mod
from . import score as score_mod
from . import stack as stack_mod

SCHEMA_CONST = "ATLAS_MULTIDIMENSIONAL_FRONTIER_V1"
SCHEMA_FILE = "atlas_multidimensional_frontier_v1.schema.json"

# Action types (controlled vocabulary).
IMPLEMENT = "IMPLEMENT"
REMEDIATE = "REMEDIATE"
READONLY_ANALYZE = "READONLY_ANALYZE"
CI_DISPATCH = "CI_DISPATCH"
IV_REQUEST = "IV_REQUEST"
POSTMERGE_VALIDATE = "POSTMERGE_VALIDATE"
POSTMERGE_RECONCILE = "POSTMERGE_RECONCILE"
OWNERSHIP_CLAIM = "OWNERSHIP_CLAIM"
RESTACK_REQUIRED = "RESTACK_REQUIRED"
OWNER_DECISION = "OWNER_DECISION"

ACTION_TYPES = frozenset({
    IMPLEMENT, REMEDIATE, READONLY_ANALYZE, CI_DISPATCH, IV_REQUEST,
    POSTMERGE_VALIDATE, POSTMERGE_RECONCILE, OWNERSHIP_CLAIM,
    RESTACK_REQUIRED, OWNER_DECISION,
})

# Action classes.
CLASS_WRITE = "WRITE"
CLASS_READONLY = "READONLY"
CLASS_VALIDATION = "VALIDATION"
CLASS_HUMAN_GATE = "HUMAN_GATE"

# Runnable states.
RUNNABLE = "RUNNABLE"
BLOCKED = "BLOCKED"
INELIGIBLE = "INELIGIBLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
UNKNOWN_FAIL_CLOSED = "UNKNOWN_FAIL_CLOSED"

_CLAIM_CLEARED = frozenset({
    "LANE_UNOWNED_WRITE_REQUIRES_CLAIM",
    "SNAPSHOT_STATE_NOT_WRITABLE:RUNNABLE_READONLY",
})

_MERGED_PHASES = frozenset({"MERGED_UNSEALED", "MERGED", "SEALED"})


class FrontierMatrixError(RuntimeError):
    """Fail-closed multidimensional frontier failure."""


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_matrix(packet: dict) -> list[str]:
    validator = events_mod.validator_for(SCHEMA_FILE)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )


def action_id(pr: int, action_type: str, residual_id: str | None = None) -> str:
    if action_type not in ACTION_TYPES:
        raise FrontierMatrixError(f"UNKNOWN_ACTION_TYPE:{action_type}")
    base = f"pr/{int(pr)}:{action_type}"
    if residual_id:
        return f"{base}:{residual_id}"
    return base


def parse_action_id(aid: str) -> tuple[int, str, str | None]:
    if ":" not in aid or not aid.startswith("pr/"):
        raise FrontierMatrixError(f"MALFORMED_ACTION_ID:{aid}")
    parts = aid.split(":")
    if len(parts) < 2:
        raise FrontierMatrixError(f"MALFORMED_ACTION_ID:{aid}")
    lane, atype = parts[0], parts[1]
    residual_id = parts[2] if len(parts) >= 3 else None
    if atype not in ACTION_TYPES:
        raise FrontierMatrixError(f"UNKNOWN_ACTION_TYPE:{atype}")
    try:
        pr = int(lane.split("/", 1)[1])
    except (IndexError, ValueError) as exc:
        raise FrontierMatrixError(f"MALFORMED_ACTION_ID:{aid}") from exc
    return pr, atype, residual_id


def hypothesize_owned(node: dict, agent_id: str) -> dict:
    """Project node as owned WRITE by agent (eligibility only, not authority)."""
    projected = copy.deepcopy(node)
    projected["state"] = router_mod.ROUTE_WRITE
    projected["ownership"] = "OWNED"
    projected["owner"] = agent_id
    projected["claimants"] = [agent_id]
    return projected


def write_eligible_after_claim(profile: dict, node: dict,
                               stack: dict | None) -> tuple[bool, list[str]]:
    """Canonical WRITE-after-claim eligibility (FEATURE_11 consumes this)."""
    if node.get("ownership") != "UNOWNED" or node.get("owner") is not None:
        return False, ["LANE_NOT_UNOWNED"]
    if node.get("frozen"):
        return False, ["LANE_FROZEN_BY_REPOSITORY_TRUTH"]
    if str(node.get("state") or "") in _MERGED_PHASES:
        return False, ["LANE_MERGED_NOT_IMPLEMENTABLE"]
    live = router_mod.evaluate_lane(profile, node, stack)
    residual = [b for b in live.get("blockers") or [] if b not in _CLAIM_CLEARED]
    hypo = hypothesize_owned(node, str(profile.get("agent_id")))
    auth = router_mod.evaluate_lane(profile, hypo, stack)
    if auth["action_class"] != router_mod.ROUTE_WRITE or not auth["routable"]:
        return False, sorted(set(residual) | set(auth.get("blockers") or []))
    if residual:
        return False, sorted(residual)
    return True, []


def _lifecycle(node: dict) -> str:
    state = str(node.get("state") or "")
    if state:
        return state
    if node.get("frozen"):
        return "FROZEN"
    if node.get("ownership") == "OWNED":
        return "RUNNABLE_WRITE"
    return "RUNNABLE_READONLY"


def _base_action(node: dict, action_type: str, action_class: str,
                 stack: dict | None) -> dict:
    pr = int(node["pr"])
    lane = str(node.get("lane") or f"pr/{pr}")
    return {
        "action_id": action_id(pr, action_type),
        "pr": pr,
        "lane": lane,
        "head": node.get("head"),
        "tree": node.get("tree"),
        "lifecycle_phase": _lifecycle(node),
        "action_type": action_type,
        "action_class": action_class,
        "runnable_state": UNKNOWN_FAIL_CLOSED,
        "blocking_reasons": [],
        "agent_eligible": False,
        "capabilities_required": [],
        "platform_constraints": list(node.get("platform_requirements") or []),
        "ownership": node.get("ownership"),
        "owner": node.get("owner"),
        "frozen": bool(node.get("frozen")),
        "stack_state": (stack or {}).get("stack_state"),
        "restack_required": bool((stack or {}).get("restack_required")),
        "evidence_state": None,
        "ci_status": node.get("ci_status"),
        "iv_status": "PRESENT" if node.get("formal_iv") else "ABSENT",
        "postmerge_seal_state": node.get("seal_state"),
        "score_total": None,
        "expected_downstream_unblock": None,
        "concurrency_group": f"lane:{lane}",
        "truth_fingerprint": None,
    }


def _finalize(action: dict) -> dict:
    material = {
        "action_id": action["action_id"],
        "runnable_state": action["runnable_state"],
        "blocking_reasons": sorted(action.get("blocking_reasons") or []),
        "action_class": action["action_class"],
        "ownership": action.get("ownership"),
        "frozen": action.get("frozen"),
        "stack_state": action.get("stack_state"),
        "head": action.get("head"),
        "tree": action.get("tree"),
    }
    action["blocking_reasons"] = sorted(action.get("blocking_reasons") or [])
    action["truth_fingerprint"] = _canonical_sha256(material)
    return action


def _set_state(action: dict, state: str, reasons: list[str] | None = None,
               eligible: bool | None = None) -> dict:
    action["runnable_state"] = state
    action["blocking_reasons"] = list(reasons or [])
    if eligible is not None:
        action["agent_eligible"] = eligible
    elif state == RUNNABLE:
        action["agent_eligible"] = True
    elif state in (INELIGIBLE, NOT_APPLICABLE):
        action["agent_eligible"] = False
    else:
        action["agent_eligible"] = False
    return _finalize(action)


def _agent_inactive(profile: dict | None, agent_status: str) -> bool:
    if agent_status != "REGISTERED_ACTIVE" or profile is None:
        return True
    return not profile.get("active", False)


def _caps(profile: dict | None) -> set[str]:
    if profile is None:
        return set()
    return {str(c) for c in profile.get("capabilities", [])}


def _class_for_action_type(action_type: str) -> str:
    if action_type in (IMPLEMENT, REMEDIATE, OWNERSHIP_CLAIM, RESTACK_REQUIRED):
        return CLASS_WRITE
    if action_type in (READONLY_ANALYZE,):
        return CLASS_READONLY
    if action_type in (CI_DISPATCH, IV_REQUEST, POSTMERGE_VALIDATE,
                       POSTMERGE_RECONCILE):
        return CLASS_VALIDATION
    return CLASS_HUMAN_GATE


def _emit_residual_backed(residual_packet: dict | None,
                          nodes_by_pr: dict[int, dict],
                          stacks: dict | None,
                          profile: dict | None,
                          agent_status: str,
                          weights: dict) -> list[dict]:
    """FEATURE_13: project OPEN residuals into typed frontier actions."""
    if not residual_packet:
        return []
    from . import residuals as residuals_mod
    out: list[dict] = []
    for seed in residuals_mod.residual_frontier_actions(residual_packet):
        pr = seed.get("pr")
        if pr is None:
            # Targetless residual: synthetic node shell for lane-less research.
            node = {
                "pr": 0, "lane": seed.get("lane") or "residual/unbound",
                "head": None, "tree": None, "ownership": "UNOWNED",
                "owner": None, "frozen": False, "state": "RUNNABLE_READONLY",
                "claimants": [],
            }
            pr = 0
        else:
            pr = int(pr)
            node = nodes_by_pr.get(pr) or {
                "pr": pr, "lane": seed.get("lane") or f"pr/{pr}",
                "head": None, "tree": None, "ownership": "UNOWNED",
                "owner": None, "frozen": False, "state": "RUNNABLE_READONLY",
                "claimants": [],
            }
        lane = str(seed.get("lane") or node.get("lane") or f"pr/{pr}")
        stack = (stacks or {}).get(lane)
        atype = seed["action_type"]
        if atype not in ACTION_TYPES:
            continue
        action = _base_action(node, atype, _class_for_action_type(atype), stack)
        action["action_id"] = action_id(pr, atype, seed["residual_id"])
        action["residual_id"] = seed["residual_id"]
        action["residual_type"] = seed.get("residual_type")
        action["concurrency_group"] = f"residual:{seed['residual_id']}"
        derived = seed.get("derived_execution_state")
        reasons = list(seed.get("blocking_reasons") or [])
        # Score never converts blocked → runnable.
        if derived == residuals_mod.RUNNABLE:
            action = _set_state(action, RUNNABLE, [])
            _score_action(action, node, stack, profile, weights)
            # Mild residual severity boost as score dimension only.
            if action.get("score_total") is not None and seed.get("severity") == "P0":
                action["score_total"] = float(action["score_total"]) + 5.0
        elif derived == residuals_mod.INELIGIBLE:
            action = _set_state(action, INELIGIBLE, reasons)
        elif derived == residuals_mod.NOT_APPLICABLE:
            action = _set_state(action, NOT_APPLICABLE, reasons)
        else:
            action = _set_state(action, BLOCKED, reasons or ["RESIDUAL_BLOCKED"])
        out.append(action)
    return out


def _emit_readonly(profile: dict | None, node: dict, stack: dict | None,
                   agent_status: str) -> dict:
    action = _base_action(node, READONLY_ANALYZE, CLASS_READONLY, stack)
    action["capabilities_required"] = sorted(router_mod.READ_CAPABILITIES)
    action["concurrency_group"] = f"readonly:{action['lane']}"
    if _agent_inactive(profile, agent_status):
        return _set_state(action, INELIGIBLE, ["AGENT_INACTIVE"])
    if not (_caps(profile) & router_mod.READ_CAPABILITIES):
        return _set_state(action, INELIGIBLE, ["NO_READ_CAPABILITY"])
    assert profile is not None
    auth = router_mod.evaluate_lane(profile, node, stack)
    if auth["action_class"] in (router_mod.ROUTE_READONLY, router_mod.ROUTE_WRITE):
        return _set_state(action, RUNNABLE, [])
    # Foreign ownership still allows READONLY floor when read-capable.
    if auth["action_class"] == router_mod.NO_ROUTE:
        blockers = auth.get("blockers") or []
        write_only = all(
            b.startswith("OWNERSHIP_MUTEX_HELD_BY:")
            or b.startswith("LANE_UNOWNED")
            or b.startswith("SNAPSHOT_STATE_NOT_WRITABLE")
            or b == "LANE_FROZEN_BY_REPOSITORY_TRUTH"
            or b.startswith("STACK_")
            or b.startswith("NO_WRITE")
            or b.startswith("PLATFORM_REQUIRED")
            or b.startswith("SCOPE_")
            for b in blockers
        ) if blockers else False
        # Re-evaluate: router always grants READONLY floor when read-capable
        # unless completely denied. If NO_ROUTE with only write blockers,
        # still RUNNABLE readonly for diagnosis.
        if write_only or not blockers:
            return _set_state(action, RUNNABLE, [])
        return _set_state(action, BLOCKED, blockers)
    return _set_state(action, BLOCKED, auth.get("blockers") or ["NO_SAFE_ROUTE"])


def _emit_implement(profile: dict | None, node: dict, stack: dict | None,
                    agent_status: str, agent_id: str | None) -> dict:
    action = _base_action(node, IMPLEMENT, CLASS_WRITE, stack)
    action["capabilities_required"] = sorted(router_mod.WRITE_CAPABILITIES)
    phase = _lifecycle(node)
    if phase in _MERGED_PHASES or phase == "SEALED":
        return _set_state(action, NOT_APPLICABLE, ["LANE_MERGED_NOT_IMPLEMENTABLE"])
    if node.get("seal_state") == "SEALED":
        return _set_state(action, NOT_APPLICABLE, ["LANE_SEALED_NO_IMPLEMENT"])
    if _agent_inactive(profile, agent_status):
        return _set_state(action, INELIGIBLE, ["AGENT_INACTIVE"])
    if not (_caps(profile) & router_mod.WRITE_CAPABILITIES):
        return _set_state(action, INELIGIBLE, ["NO_WRITE_CAPABILITY"])
    if node.get("frozen"):
        return _set_state(action, BLOCKED, ["LANE_FROZEN_BY_REPOSITORY_TRUTH"])
    if (stack or {}).get("restack_required") or (
            (stack or {}).get("stack_state") == stack_mod.RESTACK_REQUIRED):
        return _set_state(action, BLOCKED, ["STACK_RESTACK_REQUIRED"])
    assert profile is not None
    auth = router_mod.evaluate_lane(profile, node, stack)
    if auth["action_class"] == router_mod.ROUTE_WRITE and auth["routable"]:
        return _set_state(action, RUNNABLE, [])
    return _set_state(action, BLOCKED, auth.get("blockers") or ["NO_SAFE_ROUTE"])


def _emit_ownership_claim(profile: dict | None, node: dict, stack: dict | None,
                          agent_status: str, agent_id: str | None) -> dict:
    action = _base_action(node, OWNERSHIP_CLAIM, CLASS_WRITE, stack)
    action["capabilities_required"] = sorted(router_mod.WRITE_CAPABILITIES)
    action["concurrency_group"] = f"claim:{action['lane']}"
    phase = _lifecycle(node)
    if phase in _MERGED_PHASES:
        return _set_state(action, NOT_APPLICABLE, ["LANE_MERGED_NOT_CLAIMABLE"])
    if node.get("ownership") == "OWNED" and node.get("owner") == agent_id:
        return _set_state(action, NOT_APPLICABLE, ["ALREADY_OWNED_BY_AGENT"])
    if node.get("ownership") == "OWNED" and node.get("owner") != agent_id:
        return _set_state(action, BLOCKED,
                          [f"OWNERSHIP_MUTEX_HELD_BY:{node.get('owner')}"])
    if node.get("ownership") == "AMBIGUOUS":
        return _set_state(action, BLOCKED, ["OWNERSHIP_AMBIGUOUS_FAIL_CLOSED"])
    if _agent_inactive(profile, agent_status):
        return _set_state(action, INELIGIBLE, ["AGENT_INACTIVE"])
    if not (_caps(profile) & router_mod.WRITE_CAPABILITIES):
        return _set_state(action, INELIGIBLE, ["NO_WRITE_CAPABILITY"])
    assert profile is not None
    ok, reasons = write_eligible_after_claim(profile, node, stack)
    if ok:
        return _set_state(action, RUNNABLE, [])
    return _set_state(action, BLOCKED, reasons)


def _emit_remediate(profile: dict | None, node: dict, stack: dict | None,
                    agent_status: str) -> dict:
    action = _base_action(node, REMEDIATE, CLASS_WRITE, stack)
    action["capabilities_required"] = sorted(router_mod.WRITE_CAPABILITIES)
    if _lifecycle(node) in _MERGED_PHASES:
        return _set_state(action, NOT_APPLICABLE, ["LANE_MERGED"])
    needs = node.get("ci_status") == "FAIL" or node.get("claim_integrity") == "FAIL"
    if not needs:
        return _set_state(action, NOT_APPLICABLE, ["NO_REMEDIATION_SIGNAL"])
    if _agent_inactive(profile, agent_status):
        return _set_state(action, INELIGIBLE, ["AGENT_INACTIVE"])
    if not (_caps(profile) & router_mod.WRITE_CAPABILITIES):
        return _set_state(action, INELIGIBLE, ["NO_WRITE_CAPABILITY"])
    if node.get("frozen"):
        return _set_state(action, BLOCKED, ["LANE_FROZEN_BY_REPOSITORY_TRUTH"])
    assert profile is not None
    auth = router_mod.evaluate_lane(profile, node, stack)
    if auth["action_class"] == router_mod.ROUTE_WRITE and auth["routable"]:
        return _set_state(action, RUNNABLE, ["REMEDIATION_SIGNAL"])
    return _set_state(action, BLOCKED, auth.get("blockers") or ["NO_SAFE_ROUTE"])


def _emit_restack(profile: dict | None, node: dict, stack: dict | None,
                  agent_status: str) -> dict:
    action = _base_action(node, RESTACK_REQUIRED, CLASS_WRITE, stack)
    action["capabilities_required"] = sorted(router_mod.WRITE_CAPABILITIES)
    needs = bool((stack or {}).get("restack_required")) or (
        (stack or {}).get("stack_state") == stack_mod.RESTACK_REQUIRED)
    if not needs:
        return _set_state(action, NOT_APPLICABLE, ["STACK_CURRENT"])
    if _agent_inactive(profile, agent_status):
        return _set_state(action, INELIGIBLE, ["AGENT_INACTIVE"])
    # Restack is visible but never auto-executed; writable restack still
    # requires ownership — expose as BLOCKED until owned+current policy.
    if node.get("ownership") != "OWNED":
        return _set_state(action, BLOCKED, ["RESTACK_REQUIRES_OWNER"])
    if node.get("frozen"):
        return _set_state(action, BLOCKED, ["LANE_FROZEN_BY_REPOSITORY_TRUTH"])
    return _set_state(action, BLOCKED, ["RESTACK_REQUIRED_MANUAL"])


def _emit_owner_decision(profile: dict | None, node: dict, stack: dict | None,
                         agent_status: str, agent_id: str | None) -> dict:
    action = _base_action(node, OWNER_DECISION, CLASS_HUMAN_GATE, stack)
    action["concurrency_group"] = f"owner-gate:{action['lane']}"
    gate = node.get("gate") or {}
    needs = (
        node.get("frozen")
        or "HUMAN_GATE_OPEN" in (gate.get("reasons") or [])
        or "OWNER" in (node.get("waiting_on") or [])
    )
    if not needs:
        return _set_state(action, NOT_APPLICABLE, ["NO_OWNER_GATE"])
    if node.get("owner") and node.get("owner") != agent_id:
        return _set_state(action, BLOCKED,
                          [f"OWNER_GATE_HELD_BY:{node.get('owner')}"])
    if _agent_inactive(profile, agent_status):
        return _set_state(action, INELIGIBLE, ["AGENT_INACTIVE"])
    if node.get("owner") == agent_id or node.get("ownership") == "UNOWNED":
        # Human/owner decision is never auto-executable by agents.
        return _set_state(action, BLOCKED, ["OWNER_DECISION_REQUIRES_HUMAN"])
    return _set_state(action, BLOCKED, ["OWNER_DECISION_REQUIRES_HUMAN"])


def _map_dispatch_lane(lane_plan: dict | None, default_reason: str) -> tuple[str, list[str]]:
    if not lane_plan:
        return BLOCKED, [default_reason]
    state = lane_plan.get("lane_state")
    reasons = list(lane_plan.get("reasons") or [])
    if state == dispatch_mod.RUNNABLE:
        return RUNNABLE, []
    if state == dispatch_mod.ALREADY_RUNNING:
        return BLOCKED, reasons or ["ALREADY_RUNNING"]
    if state == dispatch_mod.COMPLETE:
        return NOT_APPLICABLE, reasons or ["COMPLETE"]
    return BLOCKED, reasons or [default_reason]


def _emit_ci_iv(profile: dict | None, node: dict, stack: dict | None,
                agent_status: str, dispatch_plan: dict | None) -> list[dict]:
    out: list[dict] = []
    for atype, key, cls, group in (
        (CI_DISPATCH, "ci", CLASS_VALIDATION, "validation-ci"),
        (IV_REQUEST, "iv", CLASS_VALIDATION, "validation-iv"),
    ):
        action = _base_action(node, atype, cls, stack)
        action["concurrency_group"] = f"{group}:{action['lane']}"
        if atype == CI_DISPATCH:
            action["capabilities_required"] = ["ci_dispatch"]
        else:
            action["capabilities_required"] = ["POST_EVENTS"]
        if _lifecycle(node) in _MERGED_PHASES:
            out.append(_set_state(action, NOT_APPLICABLE, ["LANE_MERGED"]))
            continue
        if not node.get("frozen"):
            out.append(_set_state(action, BLOCKED,
                                  [dispatch_mod.CANDIDATE_NOT_FROZEN]))
            continue
        if _agent_inactive(profile, agent_status):
            out.append(_set_state(action, INELIGIBLE, ["AGENT_INACTIVE"]))
            continue
        caps = _caps(profile)
        required = set(action["capabilities_required"])
        # Planning observes RUNNABLE even without agent caps; agent view marks
        # INELIGIBLE when capability missing while lane itself may be ready.
        lane_state, reasons = _map_dispatch_lane(
            (dispatch_plan or {}).get(key), "DISPATCH_PLAN_UNAVAILABLE")
        evidence = (dispatch_plan or {}).get("evidence") or {}
        if evidence.get("predecessor_only"):
            action["evidence_state"] = "PREDECESSOR_ONLY"
            if atype == CI_DISPATCH and lane_state == RUNNABLE:
                # Predecessor evidence must never satisfy current validation.
                action["expected_downstream_unblock"] = "EXACT_HEAD_EVIDENCE"
        # Lane runnable_state is observation; agent_eligible is separate.
        if lane_state == RUNNABLE:
            action = _set_state(action, RUNNABLE, [])
            if not (caps & required):
                action["agent_eligible"] = False
                action["blocking_reasons"] = sorted(
                    set(action["blocking_reasons"])
                    | {f"CAPABILITY_MISSING:{sorted(required)}"})
                action = _finalize(action)
            out.append(action)
            continue
        if lane_state == NOT_APPLICABLE:
            out.append(_set_state(action, NOT_APPLICABLE, reasons))
        else:
            out.append(_set_state(action, BLOCKED, reasons))
    return out


def _emit_postmerge(profile: dict | None, node: dict, stack: dict | None,
                    agent_status: str, seal_plan: dict | None) -> list[dict]:
    out: list[dict] = []
    phase = _lifecycle(node)
    is_merged = phase in _MERGED_PHASES or bool(node.get("merged"))
    validate = _base_action(node, POSTMERGE_VALIDATE, CLASS_VALIDATION, stack)
    reconcile = _base_action(node, POSTMERGE_RECONCILE, CLASS_VALIDATION, stack)
    validate["concurrency_group"] = f"postmerge-validate:{validate['lane']}"
    reconcile["concurrency_group"] = f"postmerge-reconcile:{reconcile['lane']}"
    validate["capabilities_required"] = ["READ_REPO"]
    reconcile["capabilities_required"] = ["READ_REPO"]

    if not is_merged:
        out.append(_set_state(validate, NOT_APPLICABLE, ["PR_NOT_MERGED"]))
        out.append(_set_state(reconcile, NOT_APPLICABLE, ["PR_NOT_MERGED"]))
        return out

    seal_state = (seal_plan or {}).get("seal_state") or node.get("seal_state")
    validate["postmerge_seal_state"] = seal_state
    reconcile["postmerge_seal_state"] = seal_state
    if seal_state == "SEALED" or (seal_plan or {}).get("sealed") is True:
        out.append(_set_state(validate, NOT_APPLICABLE, ["ALREADY_SEALED"]))
        out.append(_set_state(reconcile, NOT_APPLICABLE, ["ALREADY_SEALED"]))
        return out

    if _agent_inactive(profile, agent_status):
        out.append(_set_state(validate, INELIGIBLE, ["AGENT_INACTIVE"]))
        out.append(_set_state(reconcile, INELIGIBLE, ["AGENT_INACTIVE"]))
        return out

    required = list((seal_plan or {}).get("required_actions") or [])
    reconcile_needed = any(
        str(a).startswith("RECONCILE") or str(a).startswith("PERFORM_RECONCILIATION")
        for a in required
    )
    validate_needed = bool(required) or seal_state in (
        None, "NOT_READY", "POSTMERGE_VALIDATION_REQUIRED", "UNSEALED")

    if validate_needed:
        out.append(_set_state(validate, RUNNABLE, []))
    else:
        out.append(_set_state(validate, NOT_APPLICABLE, ["NO_POSTMERGE_VALIDATE"]))

    if reconcile_needed:
        out.append(_set_state(reconcile, RUNNABLE, []))
    else:
        out.append(_set_state(reconcile, NOT_APPLICABLE, ["NO_RECONCILE_REQUIRED"]))
    return out


def _score_action(action: dict, node: dict, stack: dict | None,
                  profile: dict | None, weights: dict) -> None:
    if action["runnable_state"] != RUNNABLE:
        return
    factors = score_mod.compute_factors(node, stack, profile, weights)
    action["score_total"] = score_mod.factor_total(factors)
    action["score_factors"] = factors


def _parallel_sets(actions: list[dict]) -> list[list[str]]:
    """Independent RUNNABLE actions that may proceed concurrently.

    Sibling CI/IV on the same lane form a set. Distinct concurrency groups
    across lanes are also parallel when neither declares a hard dependency
    on the other action_id.
    """
    runnable = [a for a in actions if a["runnable_state"] == RUNNABLE]
    by_lane: dict[str, list[dict]] = {}
    for a in runnable:
        by_lane.setdefault(a["lane"], []).append(a)

    sets: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    for _lane, items in sorted(by_lane.items()):
        types = {i["action_type"] for i in items}
        if CI_DISPATCH in types and IV_REQUEST in types:
            pair = tuple(sorted(
                i["action_id"] for i in items
                if i["action_type"] in (CI_DISPATCH, IV_REQUEST)))
            if pair and pair not in seen:
                seen.add(pair)
                sets.append(list(pair))

    # Cross-lane: READONLY_ANALYZE never blocked by OWNER_DECISION elsewhere.
    readonly = sorted(
        a["action_id"] for a in runnable if a["action_type"] == READONLY_ANALYZE)
    owner_gates = [
        a for a in actions
        if a["action_type"] == OWNER_DECISION and a["runnable_state"] == BLOCKED
    ]
    if readonly and owner_gates:
        key = tuple(readonly[:5])
        if key and key not in seen:
            seen.add(key)
            sets.append(list(key))

    # Generic: all RUNNABLE with distinct concurrency_group prefixes.
    groups: dict[str, list[str]] = {}
    for a in runnable:
        prefix = a["concurrency_group"].split(":", 1)[0]
        groups.setdefault(prefix, []).append(a["action_id"])
    multi = sorted({aid for ids in groups.values() for aid in ids})
    if len(groups) >= 2 and len(multi) >= 2:
        key = tuple(sorted(multi)[:8])
        if key not in seen:
            seen.add(key)
            sets.append(list(key))

    return sorted(sets, key=lambda s: (len(s), s))


def _typed_rankings(actions: list[dict], weights: dict) -> dict[str, list[str]]:
    """Rank only within comparable authorized action classes."""
    tiebreak = list(weights.get("tiebreak") or score_mod.SAFE_DEFAULT_WEIGHTS["tiebreak"])
    rankings: dict[str, list[str]] = {}
    for cls in (CLASS_WRITE, CLASS_READONLY, CLASS_VALIDATION, CLASS_HUMAN_GATE):
        eligible = [
            a for a in actions
            if a["action_class"] == cls and a["runnable_state"] == RUNNABLE
            and a.get("agent_eligible")
        ]
        # Map WRITE→ROUTE_WRITE for shared tiebreak key helper.
        route = {
            CLASS_WRITE: score_mod.ROUTE_WRITE,
            CLASS_READONLY: score_mod.ROUTE_READONLY,
            CLASS_VALIDATION: score_mod.ROUTE_READONLY,
            CLASS_HUMAN_GATE: score_mod.ROUTE_READONLY,
        }[cls]

        def sort_key(a: dict, route: str = route) -> tuple:
            total = float(a.get("score_total") or 0.0)
            return tuple(score_mod.tiebreak_key(
                route, total, int(a["pr"]), a["lane"], tiebreak))

        eligible.sort(key=sort_key)
        rankings[f"best_{cls.lower()}"] = [a["action_id"] for a in eligible]

    # Highest-value blocker-removal: VALIDATION RUNNABLE + OWNERSHIP_CLAIM.
    blockers = [
        a for a in actions
        if a["runnable_state"] == RUNNABLE and a.get("agent_eligible")
        and a["action_type"] in (CI_DISPATCH, IV_REQUEST, OWNERSHIP_CLAIM,
                                 POSTMERGE_VALIDATE, POSTMERGE_RECONCILE)
    ]
    blockers.sort(key=lambda a: (
        -(float(a.get("score_total") or 0.0)), int(a["pr"]), a["action_id"]))
    rankings["highest_value_blocker_removal"] = [a["action_id"] for a in blockers]
    return rankings


def build_frontier_matrix(
    snapshot: dict,
    *,
    agent_id: str | None = None,
    registry: agents_mod.RegistryResult | None = None,
    stacks: dict | None = None,
    weights: dict | None = None,
    weights_source: str = "explicit",
    dispatch_by_pr: dict[int, dict] | None = None,
    seal_by_pr: dict[int, dict] | None = None,
    residual_registry: dict | None = None,
    events: list[dict] | None = None,
    extra_nodes: list[dict] | None = None,
    client: Any = None,
    pool: Any = None,
    clock: Callable[[], str] = utcnow,
) -> dict:
    """Build ATLAS_MULTIDIMENSIONAL_FRONTIER_V1 from live (or fixture) truth."""
    cfg = weights if weights is not None else score_mod.SAFE_DEFAULT_WEIGHTS
    profile: dict | None = None
    agent_status = "NONE"
    if agent_id is not None:
        if registry is None:
            raise FrontierMatrixError("REGISTRY_REQUIRED_FOR_AGENT_FRONTIER")
        resolved = agents_mod.resolve_agent(registry, agent_id)
        if resolved.status != "REGISTERED":
            agent_status = resolved.status
        elif not (resolved.profile or {}).get("active", False):
            agent_status = "REGISTERED_INACTIVE"
            profile = resolved.profile
        else:
            agent_status = "REGISTERED_ACTIVE"
            profile = resolved.profile

    nodes = list(snapshot.get("nodes") or [])
    if extra_nodes:
        nodes.extend(extra_nodes)
    # Deterministic lane order independent of source permutation.
    nodes = sorted(nodes, key=lambda n: (int(n["pr"]), str(n.get("lane") or "")))
    nodes_by_pr = {int(n["pr"]): n for n in nodes}

    # FEATURE_13 residual registry (event-derived + seal/stack projections).
    if residual_registry is None and (events is not None or seal_by_pr or stacks):
        from . import residuals as residuals_mod
        repo = (snapshot.get("repository")
                or (getattr(client, "repo", None) if client else None)
                or "UNKNOWN")
        residual_registry = residuals_mod.build_residual_registry(
            repository=str(repo), events=events or [], snapshot=snapshot,
            stacks=stacks, seal_by_pr=seal_by_pr, agent_id=agent_id,
            registry=registry, clock=clock)

    actions: list[dict] = []
    for node in nodes:
        lane = str(node.get("lane") or f"pr/{node['pr']}")
        stack = (stacks or {}).get(lane)
        pr = int(node["pr"])

        dispatch_plan = (dispatch_by_pr or {}).get(pr)
        if dispatch_plan is None and client is not None and node.get("frozen"):
            try:
                dispatch_plan = dispatch_mod.plan_dispatch(
                    node, client, agent_id, profile, pool)
            except Exception:
                dispatch_plan = None

        seal_plan = (seal_by_pr or {}).get(pr)

        actions.append(_emit_readonly(profile, node, stack, agent_status))
        actions.append(_emit_implement(profile, node, stack, agent_status, agent_id))
        actions.append(_emit_ownership_claim(
            profile, node, stack, agent_status, agent_id))
        actions.append(_emit_remediate(profile, node, stack, agent_status))
        actions.append(_emit_restack(profile, node, stack, agent_status))
        actions.append(_emit_owner_decision(
            profile, node, stack, agent_status, agent_id))
        actions.extend(_emit_ci_iv(
            profile, node, stack, agent_status, dispatch_plan))
        actions.extend(_emit_postmerge(
            profile, node, stack, agent_status, seal_plan))

        for action in actions:
            if action["pr"] == pr and action.get("score_total") is None:
                _score_action(action, node, stack, profile, cfg)

    actions.extend(_emit_residual_backed(
        residual_registry, nodes_by_pr, stacks, profile, agent_status, cfg))

    # Stable action order.
    actions.sort(key=lambda a: (int(a["pr"]), a["action_type"], a["action_id"]))

    eligible = [a["action_id"] for a in actions
                if a["runnable_state"] == RUNNABLE and a.get("agent_eligible")]
    ineligible = [a["action_id"] for a in actions
                  if a["runnable_state"] == INELIGIBLE]
    blocked = [a["action_id"] for a in actions
               if a["runnable_state"] == BLOCKED]
    by_class: dict[str, list[str]] = {
        CLASS_WRITE: [], CLASS_READONLY: [], CLASS_VALIDATION: [],
        CLASS_HUMAN_GATE: [],
    }
    for a in actions:
        if a["runnable_state"] == RUNNABLE and a.get("agent_eligible"):
            by_class.setdefault(a["action_class"], []).append(a["action_id"])

    fingerprint_material = [
        {
            "action_id": a["action_id"],
            "runnable_state": a["runnable_state"],
            "blocking_reasons": a["blocking_reasons"],
            "action_class": a["action_class"],
            "truth_fingerprint": a["truth_fingerprint"],
            "score_total": a.get("score_total"),
        }
        for a in actions
    ]
    packet = {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "agent": agent_id,
        "agent_status": agent_status,
        "weights_id": cfg.get("weights_id"),
        "weights_version": cfg.get("version"),
        "weights_source": weights_source,
        "actions": actions,
        "eligible_actions": eligible,
        "ineligible_actions": ineligible,
        "blocked_actions": blocked,
        "by_action_class": {k: v for k, v in sorted(by_class.items())},
        "parallel_runnable_set": _parallel_sets(actions),
        "typed_rankings": _typed_rankings(actions, cfg),
        "frontier_fingerprint": _canonical_sha256(fingerprint_material),
        "provenance": {
            "generator": "atlas-dag frontier-matrix (FEATURE_12)",
            "frontier_is_not_single_queue": True,
            "action_rank_is_not_authority": True,
            "presence_is_not_authority": True,
            "truth_sources": [
                "FEATURE_01 agent registry",
                "FEATURE_02 router",
                "FEATURE_03 stack topology",
                "FEATURE_06 dispatch plan",
                "FEATURE_09 seal plan",
                "FEATURE_10 frontier scoring (dimension only)",
                "FEATURE_13 residual registry (obligation projection)",
            ],
        },
        "residual_registry_fingerprint": (
            (residual_registry or {}).get("registry_fingerprint")),
        "open_residual_count": (residual_registry or {}).get("open_count"),
    }
    return packet


def explain_action(packet: dict, aid: str) -> dict:
    """Return one action with fail-closed unknown/malformed handling."""
    try:
        parse_action_id(aid)
    except FrontierMatrixError as exc:
        return {"found": False, "reason": str(exc), "action": None}
    for action in packet.get("actions") or []:
        if action.get("action_id") == aid:
            return {"found": True, "action": action, "reason": None}
    return {"found": False, "reason": f"UNKNOWN_ACTION_ID:{aid}", "action": None}


def write_steal_candidates(packet: dict) -> list[dict]:
    """FEATURE_11 projection: RUNNABLE OWNERSHIP_CLAIM actions only."""
    out: list[dict] = []
    for action in packet.get("actions") or []:
        if action.get("action_type") != OWNERSHIP_CLAIM:
            continue
        if action.get("runnable_state") != RUNNABLE:
            continue
        if not action.get("agent_eligible"):
            continue
        out.append({
            "pr": action["pr"],
            "lane": action["lane"],
            "head": action.get("head"),
            "tree": action.get("tree"),
            "total": float(action.get("score_total") or 0.0),
            "factors": action.get("score_factors") or {},
            "action_class_after_claim": router_mod.ROUTE_WRITE,
            "ownership": "UNOWNED",
            "action_id": action["action_id"],
            "tiebreak_key": score_mod.tiebreak_key(
                router_mod.ROUTE_WRITE,
                float(action.get("score_total") or 0.0),
                int(action["pr"]),
                action["lane"],
                list(score_mod.SAFE_DEFAULT_WEIGHTS["tiebreak"])),
        })
    out.sort(key=lambda e: tuple(e["tiebreak_key"]))
    return out


def validation_dispatch_projection(packet: dict) -> list[dict]:
    """FEATURE_06 projection: CI/IV validation actions from the matrix."""
    return [
        a for a in packet.get("actions") or []
        if a.get("action_type") in (CI_DISPATCH, IV_REQUEST)
    ]


def score_compat_projection(packet: dict, snapshot: dict) -> dict:
    """Compatibility ATLAS_FRONTIER_SCORE_V1-shaped view derived from matrix.

    Does not re-authorize: only RUNNABLE agent-eligible WRITE/READONLY actions
    appear as ranked executable entries.
    """
    ranked: list[dict] = []
    blocked: list[dict] = []
    seen_lanes: set[str] = set()
    for action in packet.get("actions") or []:
        lane = action["lane"]
        if action["action_type"] not in (IMPLEMENT, READONLY_ANALYZE, OWNERSHIP_CLAIM):
            continue
        if action["runnable_state"] == RUNNABLE and action.get("agent_eligible"):
            if lane in seen_lanes and action["action_type"] != IMPLEMENT:
                continue
            # Prefer IMPLEMENT over READONLY for the same lane in compat view.
            if action["action_type"] == READONLY_ANALYZE and any(
                    r["lane"] == lane and r["action_class"] == score_mod.ROUTE_WRITE
                    for r in ranked):
                continue
            cls = (score_mod.ROUTE_WRITE
                   if action["action_class"] == CLASS_WRITE
                   else score_mod.ROUTE_READONLY)
            if action["action_type"] == OWNERSHIP_CLAIM:
                # Compat frontier historically ranks live WRITE; claims stay
                # out of the flat score list (steal uses write_steal_candidates).
                continue
            entry = {
                "pr": action["pr"],
                "lane": lane,
                "action_class": cls,
                "executable": True,
                "total": float(action.get("score_total") or 0.0),
                "factors": action.get("score_factors") or {},
                "authorization": {
                    "action_class": cls,
                    "routable": True,
                    "blockers": [],
                    "reasons": ["DERIVED_FROM_MULTIDIM_FRONTIER"],
                },
            }
            # Replace weaker READONLY if IMPLEMENT arrives later.
            ranked = [r for r in ranked if r["lane"] != lane]
            ranked.append(entry)
            seen_lanes.add(lane)
        elif action["action_type"] == IMPLEMENT and action["runnable_state"] == BLOCKED:
            blocked.append({
                "pr": action["pr"],
                "lane": lane,
                "action_class": "BLOCKED",
                "executable": False,
                "nominal_total": float(action.get("score_total") or 0.0),
                "authorization": {
                    "action_class": score_mod.NO_ROUTE,
                    "routable": False,
                    "blockers": action.get("blocking_reasons") or [],
                    "reasons": action.get("blocking_reasons") or [],
                },
            })

    tiebreak = list(score_mod.SAFE_DEFAULT_WEIGHTS["tiebreak"])
    ranked.sort(key=lambda e: tuple(score_mod.tiebreak_key(
        e["action_class"], float(e["total"]), int(e["pr"]), e["lane"], tiebreak)))
    return {
        "schema": score_mod.SCHEMA_CONST,
        "generated_at_utc": packet.get("generated_at_utc"),
        "weights_id": packet.get("weights_id"),
        "weights_version": packet.get("weights_version"),
        "weights_source": packet.get("weights_source"),
        "agent": packet.get("agent"),
        "agent_status": packet.get("agent_status"),
        "ranked": ranked,
        "blocked": blocked,
        "ranking_fingerprint": _canonical_sha256(
            {"ranked": ranked, "blocked": [
                {"pr": b["pr"], "blockers": b["authorization"]["blockers"]}
                for b in blocked]}),
        "provenance": {
            "generator": "atlas-dag frontier-matrix compat projection (FEATURE_12)",
            "authorization_before_scoring": True,
            "priority_is_not_authority": True,
            "derived_from": SCHEMA_CONST,
        },
    }
