"""Executable residual registry (FEATURE_13).

DISCOVERED_WORK != EPHEMERAL_PROSE
RESIDUAL_EXISTENCE != EXECUTION_AUTHORITY

Durable dispositions (OPEN / RESOLVED / SUPERSEDED / ACCEPTED_RISK) are
event-derived and append-only. Derived execution state (RUNNABLE / BLOCKED /
INELIGIBLE / UNKNOWN) is recomputed from live DAG truth and never stored as
permanent authority.

Sources (structured only — never prose scrape):
  NEW_FINDING / FINDING_RECLASSIFIED / RESIDUAL_* events on #719
  Feature-09 seal-plan required_actions (synthetic, deterministic IDs)
  Feature-03 restack_required (synthetic)

Feature-12 projects OPEN residuals into typed actions. Router / ownership /
freeze / stack / verifier / evidence remain the sole execution authorities.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from . import agents as agents_mod
from . import events as events_mod
from . import router as router_mod
from . import stack as stack_mod

SCHEMA_CONST = "ATLAS_RESIDUAL_V1"
REGISTRY_SCHEMA = "ATLAS_RESIDUAL_REGISTRY_V1"
RESIDUAL_SCHEMA_FILE = "atlas_residual_v1.schema.json"
REGISTRY_SCHEMA_FILE = "atlas_residual_registry_v1.schema.json"

# Mirror FEATURE_12 action types without importing frontier_matrix at load
# (frontier_matrix will consume this module).
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

# Durable disposition.
OPEN = "OPEN"
RESOLVED = "RESOLVED"
SUPERSEDED = "SUPERSEDED"
ACCEPTED_RISK = "ACCEPTED_RISK"
DISPOSITIONS = frozenset({OPEN, RESOLVED, SUPERSEDED, ACCEPTED_RISK})

# Derived execution state (never permanent truth).
RUNNABLE = "RUNNABLE"
BLOCKED = "BLOCKED"
INELIGIBLE = "INELIGIBLE"
UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "NOT_APPLICABLE"

# Residual types.
DEFECT = "DEFECT"
DEFERRED_REMEDIATION = "DEFERRED_REMEDIATION"
TECH_DEBT = "TECH_DEBT"
MISSING_VERIFICATION = "MISSING_VERIFICATION"
POSTMERGE_FOLLOWUP = "POSTMERGE_FOLLOWUP"
COMPATIBILITY = "COMPATIBILITY"
RESTACK = "RESTACK"
RESEARCH = "RESEARCH"
DOC_RECONCILE = "DOC_RECONCILE"
OWNER_DECISION = "OWNER_DECISION"
SECURITY_HARDENING = "SECURITY_HARDENING"
KNOWN_LIMITATION = "KNOWN_LIMITATION"

RESIDUAL_TYPES = frozenset({
    DEFECT, DEFERRED_REMEDIATION, TECH_DEBT, MISSING_VERIFICATION,
    POSTMERGE_FOLLOWUP, COMPATIBILITY, RESTACK, RESEARCH, DOC_RECONCILE,
    OWNER_DECISION, SECURITY_HARDENING, KNOWN_LIMITATION,
})

# Lifecycle events.
EVT_REGISTERED = "RESIDUAL_REGISTERED"
EVT_RESOLVED = "RESIDUAL_RESOLVED"
EVT_SUPERSEDED = "RESIDUAL_SUPERSEDED"
EVT_ACCEPTED = "RESIDUAL_ACCEPTED_RISK"
EVT_REOPENED = "RESIDUAL_REOPENED"
EVT_NEW_FINDING = "NEW_FINDING"
EVT_FINDING_RECLASSIFIED = "FINDING_RECLASSIFIED"

_TYPE_TO_ACTION = {
    DEFECT: REMEDIATE,
    DEFERRED_REMEDIATION: REMEDIATE,
    TECH_DEBT: REMEDIATE,
    SECURITY_HARDENING: REMEDIATE,
    MISSING_VERIFICATION: IV_REQUEST,
    POSTMERGE_FOLLOWUP: POSTMERGE_RECONCILE,
    COMPATIBILITY: POSTMERGE_VALIDATE,
    RESTACK: RESTACK_REQUIRED,
    RESEARCH: READONLY_ANALYZE,
    DOC_RECONCILE: READONLY_ANALYZE,
    OWNER_DECISION: OWNER_DECISION,
    KNOWN_LIMITATION: OWNER_DECISION,
}

_ID_SAFE = re.compile(r"[^a-z0-9._:-]+")


class ResidualError(RuntimeError):
    """Fail-closed residual registry failure."""


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_residual(record: dict) -> list[str]:
    validator = events_mod.validator_for(RESIDUAL_SCHEMA_FILE)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(record)
    )


def validate_registry(packet: dict) -> list[str]:
    validator = events_mod.validator_for(REGISTRY_SCHEMA_FILE)
    errors = sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )
    for residual in packet.get("residuals") or []:
        errors.extend(f"residual[{residual.get('residual_id')}]: {e}"
                      for e in validate_residual(residual))
    return errors


def make_residual_id(*parts: str) -> str:
    """Deterministic residual_id from identity parts (never wall-clock)."""
    digest = _canonical_sha256(list(parts))[:20]
    return f"res-{digest}"


def _slug(text: str, limit: int = 48) -> str:
    s = _ID_SAFE.sub("-", str(text).lower()).strip("-")
    return (s[:limit] or "item")


def _base_residual(*, residual_id: str, repository: str, residual_type: str,
                   description: str, required_action_type: str,
                   source_kind: str, **fields: Any) -> dict:
    if residual_type not in RESIDUAL_TYPES:
        raise ResidualError(f"UNKNOWN_RESIDUAL_TYPE:{residual_type}")
    if required_action_type not in ACTION_TYPES:
        raise ResidualError(f"UNKNOWN_ACTION_TYPE:{required_action_type}")
    record = {
        "schema": SCHEMA_CONST,
        "residual_id": residual_id,
        "repository": repository,
        "residual_type": residual_type,
        "disposition": OPEN,
        "derived_execution_state": UNKNOWN,
        "description": description,
        "severity": fields.pop("severity", "P2"),
        "priority_class": fields.pop("priority_class", None),
        "origin_event_id": fields.pop("origin_event_id", None),
        "originating_pr": fields.pop("originating_pr", None),
        "originating_lane": fields.pop("originating_lane", None),
        "originating_head": fields.pop("originating_head", None),
        "target_pr": fields.pop("target_pr", None),
        "target_lane": fields.pop("target_lane", None),
        "target_subsystem": fields.pop("target_subsystem", None),
        "required_action_type": required_action_type,
        "prerequisites": list(fields.pop("prerequisites", []) or []),
        "dependencies": list(fields.pop("dependencies", []) or []),
        "resolution_criteria": list(fields.pop("resolution_criteria", []) or []),
        "relationships": list(fields.pop("relationships", []) or []),
        "blocking_reasons": [],
        "evidence": list(fields.pop("evidence", []) or []),
        "policy_gates": list(fields.pop("policy_gates", []) or []),
        "created_at": fields.pop("created_at", None),
        "resolution_history": [],
        "provenance": {
            "source_kind": source_kind,
            "generator": "atlas-dag residuals (FEATURE_13)",
            "residual_existence_is_not_authority": True,
        },
    }
    if fields:
        raise ResidualError(f"UNKNOWN_RESIDUAL_FIELD:{sorted(fields)}")
    return record


def _apply_disposition_event(record: dict, event: dict) -> None:
    """Mutate disposition from lifecycle event; preserve history."""
    name = event.get("event")
    state = str(event.get("state") or "").upper()
    stamp = {
        "event_id": event.get("event_id"),
        "event": name,
        "state": state,
        "timestamp_utc": event.get("timestamp_utc"),
        "actor": event.get("actor"),
        "evidence": list(event.get("evidence") or []),
        "prior_disposition": record.get("disposition"),
    }
    record.setdefault("resolution_history", []).append(stamp)

    if name == EVT_RESOLVED or (
            name == EVT_FINDING_RECLASSIFIED and state in ("RESOLVED", "FIXED", "CLOSED")):
        record["disposition"] = RESOLVED
        record["evidence"] = sorted(set(record.get("evidence") or []) | set(
            event.get("evidence") or []))
    elif name == EVT_SUPERSEDED or (
            name == EVT_FINDING_RECLASSIFIED and state == "SUPERSEDED"):
        record["disposition"] = SUPERSEDED
        rel = event.get("residual_id_supersedes") or event.get("note")
        if isinstance(rel, str) and rel.startswith("res-"):
            record.setdefault("relationships", []).append(
                {"relation": "SUPERSEDES", "residual_id": rel})
    elif name == EVT_ACCEPTED or (
            name == EVT_FINDING_RECLASSIFIED and state == "ACCEPTED_RISK"):
        # Owner authority checked at emit time; registry records disposition.
        record["disposition"] = ACCEPTED_RISK
        record["evidence"] = sorted(set(record.get("evidence") or []) | set(
            event.get("evidence") or []))
    elif name == EVT_REOPENED or (
            name == EVT_FINDING_RECLASSIFIED and state in ("REOPENED", "OPEN")):
        record["disposition"] = OPEN
    elif name in (EVT_REGISTERED, EVT_NEW_FINDING):
        if record.get("disposition") not in (RESOLVED, SUPERSEDED, ACCEPTED_RISK):
            record["disposition"] = OPEN


def _finding_type(event: dict) -> str:
    """Map NEW_FINDING prose/state to residual_type without false substring hits.

    Fail closed toward DEFECT. Never treat accidental substrings (e.g. 'IV'
    inside 'Negative') as verification obligations.
    """
    blob = str(event.get("note") or event.get("state") or "")
    upper = blob.upper()
    if re.search(r"\b(SECURITY|CVE)\b", upper):
        return SECURITY_HARDENING
    # Explicit verification obligation phrasing only — bare "IV" in lists
    # like "CI/IV/freeze" must not reclassify a defect.
    if re.search(
            r"\b(MISSING[_\s-]?IV|IV[_\s-]?(?:MISSING|REQUIRED|ABSENT|GATE)|"
            r"AWAITING[_\s-]?IV|MISSING[_\s-]?VERIF\w*|"
            r"INDEPENDENT[_\s-]?VERIF\w*|VERIFIER[_\s-]?RECEIPT)\b",
            upper):
        return MISSING_VERIFICATION
    if re.search(r"\b(DOC(?:UMENTATION)?|WORKLOG|BACKLOG)\b", upper):
        return DOC_RECONCILE
    if re.search(r"\b(TECH(?:NICAL)?[_\s-]?DEBT|DEBT)\b", upper):
        return TECH_DEBT
    if re.search(r"\bRESEARCH\b", upper):
        return RESEARCH
    if re.search(r"\b(POST[_\s-]?MERGE|SEAL[_\s-]?PLAN)\b", upper):
        return POSTMERGE_FOLLOWUP
    if re.search(r"\bRESTACK\b", upper):
        return RESTACK
    return DEFECT


def residuals_from_events(events: list[dict], *, repository: str) -> dict[str, dict]:
    """Replay append-only events into residual records (deterministic)."""
    ordered = sorted(
        events,
        key=lambda e: (str(e.get("timestamp_utc") or ""), str(e.get("event_id") or "")))
    by_id: dict[str, dict] = {}
    # First pass: registrations / findings create identity.
    for event in ordered:
        name = event.get("event")
        if name not in (EVT_NEW_FINDING, EVT_REGISTERED, EVT_FINDING_RECLASSIFIED,
                        EVT_RESOLVED, EVT_SUPERSEDED, EVT_ACCEPTED, EVT_REOPENED):
            continue
        rid = event.get("residual_id")
        if not rid:
            if name == EVT_NEW_FINDING:
                rid = make_residual_id("finding", str(event.get("event_id")))
            elif name == EVT_REGISTERED:
                desc = str(event.get("note") or event.get("state") or "residual")
                rid = make_residual_id(
                    "register", str(event.get("event_id")), _slug(desc))
            else:
                # Lifecycle without residual_id cannot attach — fail closed skip.
                continue
        rid = str(rid)
        if not rid.startswith("res-"):
            raise ResidualError(f"MALFORMED_RESIDUAL_ID:{rid}")

        if rid not in by_id:
            if name not in (EVT_NEW_FINDING, EVT_REGISTERED, EVT_REOPENED):
                continue
            rtype = str(event.get("residual_type") or _finding_type(event))
            if rtype not in RESIDUAL_TYPES:
                raise ResidualError(f"UNKNOWN_RESIDUAL_TYPE:{rtype}")
            action = str(event.get("required_action_type")
                         or _TYPE_TO_ACTION.get(rtype)
                         or REMEDIATE)
            pr = event.get("pr")
            by_id[rid] = _base_residual(
                residual_id=rid,
                repository=repository,
                residual_type=rtype,
                description=str(event.get("note") or event.get("state")
                                or f"{name}:{event.get('event_id')}"),
                required_action_type=action,
                source_kind=f"event:{name}",
                origin_event_id=str(event.get("event_id")),
                originating_pr=pr,
                originating_lane=event.get("lane") or (f"pr/{pr}" if pr else None),
                originating_head=event.get("head"),
                target_pr=event.get("target_pr", pr),
                target_lane=event.get("target_lane") or event.get("lane")
                or (f"pr/{pr}" if pr else None),
                severity=str(event.get("severity") or "P2"),
                prerequisites=list(event.get("prerequisites") or []),
                dependencies=list(event.get("dependencies") or []),
                resolution_criteria=list(event.get("resolution_criteria") or [
                    "EXPLICIT_RESOLUTION_EVIDENCE"]),
                evidence=list(event.get("evidence") or []),
                created_at=event.get("timestamp_utc"),
            )
        _apply_disposition_event(by_id[rid], event)
        dup = event.get("duplicate_of")
        if dup:
            by_id[rid].setdefault("relationships", []).append(
                {"relation": "DUPLICATE_OF", "residual_id": str(dup)})
    return by_id


def residuals_from_seal(seal_by_pr: dict[int, dict] | None, *,
                        repository: str) -> dict[str, dict]:
    """Project Feature-09 required_actions as OPEN postmerge residuals.

    Placeholder pre-merge gates (AWAIT_MERGE_DECISION, RESOLVE_PR_TRUTH, …)
    are not residuals — they are seal-plan status, not durable obligations.
    """
    skip = frozenset({
        "AWAIT_MERGE_DECISION",
        "NONE_SEAL_IDEMPOTENT",
        "RESOLVE_PR_TRUTH",
        "RESOLVE_MERGE_COMMIT_FROM_LIVE_HISTORY",
    })
    out: dict[str, dict] = {}
    for pr, plan in sorted((seal_by_pr or {}).items()):
        if plan.get("sealed") is True or plan.get("seal_state") == "SEALED":
            continue
        for action in sorted(plan.get("required_actions") or []):
            action_s = str(action)
            if action_s in skip:
                continue
            rid = make_residual_id("seal", str(pr), action_s)
            if action_s.startswith("RECONCILE") or "RECONCILIATION" in action_s:
                rtype, req = POSTMERGE_FOLLOWUP, POSTMERGE_RECONCILE
            elif "COMPATIBILITY" in action_s or "VALIDATE" in action_s:
                rtype, req = COMPATIBILITY, POSTMERGE_VALIDATE
            elif "DOC" in action_s or "WORKLOG" in action_s or "BACKLOG" in action_s:
                rtype, req = DOC_RECONCILE, READONLY_ANALYZE
            else:
                rtype, req = POSTMERGE_FOLLOWUP, POSTMERGE_VALIDATE
            merged_info = plan.get("merged") or {}
            merged_ok = bool(
                merged_info.get("is_merged") and merged_info.get("verified"))
            prereqs = ["SEAL_NOT_COMPLETE"]
            if not merged_ok:
                prereqs.insert(0, "PR_MERGED")
            out[rid] = _base_residual(
                residual_id=rid,
                repository=repository,
                residual_type=rtype,
                description=f"Postmerge obligation: {action_s}",
                required_action_type=req,
                source_kind="feature09:seal_plan",
                originating_pr=pr,
                originating_lane=f"pr/{pr}",
                originating_head=(merged_info.get("merge_commit")
                                  or plan.get("head")),
                target_pr=pr,
                target_lane=f"pr/{pr}",
                severity="P1",
                prerequisites=prereqs,
                resolution_criteria=[
                    "SEALED_EVENT_FOR_MERGE_COMMIT",
                    f"REQUIRED_ACTION_SATISFIED:{action_s}",
                ],
                evidence=([f"merge_commit:{merged_info['merge_commit']}"]
                          if merged_info.get("merge_commit") else []),
            )
    return out


def residuals_from_stacks(stacks: dict | None, *,
                          repository: str) -> dict[str, dict]:
    """Project Feature-03 restack_required as OPEN restack residuals."""
    out: dict[str, dict] = {}
    for lane, rec in sorted((stacks or {}).items()):
        if not rec.get("restack_required"):
            continue
        pr = rec.get("pr") or (int(lane.split("/")[1]) if "/" in lane else None)
        rid = make_residual_id("restack", lane, str(rec.get("parent_pr")))
        out[rid] = _base_residual(
            residual_id=rid,
            repository=repository,
            residual_type=RESTACK,
            description=f"Restack required for {lane} "
                        f"(parent={rec.get('parent_pr')})",
            required_action_type=RESTACK_REQUIRED,
            source_kind="feature03:stack",
            originating_pr=pr,
            originating_lane=lane,
            target_pr=pr,
            target_lane=lane,
            severity="P1",
            prerequisites=["STACK_PARENT_CURRENT"],
            resolution_criteria=["PARENT_HEAD_IN_CHILD_ANCESTRY"],
            dependencies=[f"pr/{rec['parent_pr']}"] if rec.get("parent_pr") else [],
        )
    return out


def derive_execution_state(
    residual: dict,
    *,
    profile: dict | None,
    agent_status: str,
    node: dict | None,
    stack: dict | None,
) -> tuple[str, list[str]]:
    """Derive RUNNABLE/BLOCKED/INELIGIBLE from live truth — never stored."""
    if residual.get("disposition") != OPEN:
        return NOT_APPLICABLE, [f"DISPOSITION:{residual.get('disposition')}"]

    # Duplicates are visible but not independently executable.
    for rel in residual.get("relationships") or []:
        if rel.get("relation") == "DUPLICATE_OF":
            return BLOCKED, [f"DUPLICATE_OF:{rel.get('residual_id')}"]

    reasons: list[str] = []
    if agent_status != "REGISTERED_ACTIVE" or profile is None \
            or not profile.get("active", False):
        return INELIGIBLE, ["AGENT_INACTIVE"]

    action = residual.get("required_action_type")
    write_actions = {
        IMPLEMENT, REMEDIATE, OWNERSHIP_CLAIM, RESTACK_REQUIRED,
    }
    caps = {str(c) for c in profile.get("capabilities", [])}
    if action in write_actions and not (caps & router_mod.WRITE_CAPABILITIES):
        return INELIGIBLE, ["NO_WRITE_CAPABILITY"]
    if action == READONLY_ANALYZE and not (
            caps & router_mod.READ_CAPABILITIES):
        return INELIGIBLE, ["NO_READ_CAPABILITY"]

    # Prerequisites against live node/stack.
    for pre in residual.get("prerequisites") or []:
        if pre == "PR_MERGED":
            if node is None or (str(node.get("state") or "") not in (
                    "MERGED_UNSEALED", "MERGED", "SEALED") and not node.get("merged")):
                reasons.append("PREREQ_UNSATISFIED:PR_MERGED")
        elif pre == "SEAL_NOT_COMPLETE":
            if node is not None and (
                    node.get("seal_state") == "SEALED" or node.get("sealed")):
                reasons.append("PREREQ_UNSATISFIED:ALREADY_SEALED")
        elif pre == "STACK_PARENT_CURRENT":
            if stack is not None and (
                    stack.get("restack_required")
                    or stack.get("stack_state") == stack_mod.RESTACK_REQUIRED):
                reasons.append("PREREQ_UNSATISFIED:STACK_NOT_CURRENT")
        elif pre == "LANE_UNFROZEN":
            if node is not None and node.get("frozen"):
                reasons.append("PREREQ_UNSATISFIED:LANE_FROZEN")
        elif pre == "LANE_OWNED_BY_AGENT" and (
                node is None or node.get("owner") != profile.get("agent_id")):
            reasons.append("PREREQ_UNSATISFIED:NOT_OWNER")

    if node is not None and action in write_actions:
        if node.get("frozen"):
            reasons.append("LANE_FROZEN_BY_REPOSITORY_TRUTH")
        ownership = node.get("ownership")
        owner = node.get("owner")
        if ownership == "OWNED" and owner != profile.get("agent_id"):
            reasons.append(f"OWNERSHIP_MUTEX_HELD_BY:{owner}")
        elif ownership == "AMBIGUOUS":
            reasons.append("OWNERSHIP_AMBIGUOUS_FAIL_CLOSED")
        elif (action != OWNERSHIP_CLAIM and owner is None
              and action in (REMEDIATE, IMPLEMENT, RESTACK_REQUIRED)):
            reasons.append("LANE_UNOWNED_WRITE_REQUIRES_CLAIM")
        if (stack is not None
                and (stack.get("restack_required")
                     or stack.get("stack_state") in stack_mod.NOT_CURRENT_STATES)
                and action != RESTACK_REQUIRED):
            reasons.append(f"STACK_NOT_CURRENT:{stack.get('stack_state')}")

    # Policy gates listed on residual.
    for gate in residual.get("policy_gates") or []:
        reasons.append(f"POLICY_GATE:{gate}")

    if reasons:
        return BLOCKED, sorted(set(reasons))

    # For READONLY / OWNER_DECISION / postmerge without a live node, still
    # runnable when agent-eligible and no blockers.
    if action == OWNER_DECISION:
        return BLOCKED, ["OWNER_DECISION_REQUIRES_HUMAN"]
    if action == RESTACK_REQUIRED:
        return BLOCKED, ["RESTACK_REQUIRED_MANUAL"]
    if action == IV_REQUEST:
        return BLOCKED, ["VERIFIER_IDENTITY_OR_RECEIPT_REQUIRED"]

    return RUNNABLE, []


def build_residual_registry(
    *,
    repository: str,
    events: list[dict] | None = None,
    snapshot: dict | None = None,
    stacks: dict | None = None,
    seal_by_pr: dict[int, dict] | None = None,
    agent_id: str | None = None,
    registry: agents_mod.RegistryResult | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict:
    """Build ATLAS_RESIDUAL_REGISTRY_V1 with derived execution states."""
    by_id = residuals_from_events(events or [], repository=repository)
    # Synthetic sources fill gaps; explicit event residuals win on same id.
    for rid, rec in residuals_from_seal(seal_by_pr, repository=repository).items():
        by_id.setdefault(rid, rec)
    for rid, rec in residuals_from_stacks(stacks, repository=repository).items():
        by_id.setdefault(rid, rec)

    profile = None
    agent_status = "NONE"
    if agent_id is not None:
        if registry is None:
            raise ResidualError("REGISTRY_REQUIRED_FOR_AGENT_RESIDUALS")
        resolved = agents_mod.resolve_agent(registry, agent_id)
        if resolved.status != "REGISTERED":
            agent_status = resolved.status
        elif not (resolved.profile or {}).get("active", False):
            agent_status = "REGISTERED_INACTIVE"
            profile = resolved.profile
        else:
            agent_status = "REGISTERED_ACTIVE"
            profile = resolved.profile

    nodes_by_pr = {
        int(n["pr"]): n for n in (snapshot or {}).get("nodes") or []
        if n.get("pr") is not None
    }
    residuals: list[dict] = []
    for rid in sorted(by_id):
        rec = by_id[rid]
        target_pr = rec.get("target_pr")
        node = nodes_by_pr.get(int(target_pr)) if target_pr is not None else None
        lane = rec.get("target_lane") or (f"pr/{target_pr}" if target_pr else None)
        stack = (stacks or {}).get(lane) if lane else None
        state, reasons = derive_execution_state(
            rec, profile=profile, agent_status=agent_status, node=node, stack=stack)
        rec = dict(rec)
        rec["derived_execution_state"] = state
        rec["blocking_reasons"] = reasons
        residuals.append(rec)

    open_n = sum(1 for r in residuals if r["disposition"] == OPEN)
    runnable_n = sum(1 for r in residuals if r["derived_execution_state"] == RUNNABLE)
    blocked_n = sum(1 for r in residuals if r["derived_execution_state"] == BLOCKED)

    fingerprint = _canonical_sha256([
        {
            "residual_id": r["residual_id"],
            "disposition": r["disposition"],
            "derived_execution_state": r["derived_execution_state"],
            "blocking_reasons": r["blocking_reasons"],
            "relationships": r.get("relationships") or [],
            "resolution_history": [
                h.get("event_id") for h in (r.get("resolution_history") or [])
            ],
        }
        for r in residuals
    ])
    return {
        "schema": REGISTRY_SCHEMA,
        "generated_at_utc": clock(),
        "repository": repository,
        "agent": agent_id,
        "agent_status": agent_status,
        "residuals": residuals,
        "open_count": open_n,
        "runnable_count": runnable_n,
        "blocked_count": blocked_n,
        "registry_fingerprint": fingerprint,
        "provenance": {
            "generator": "atlas-dag residuals (FEATURE_13)",
            "discovered_work_is_not_ephemeral_prose": True,
            "residual_existence_is_not_execution_authority": True,
            "truth_sources": [
                "FEATURE_04 event bus (#719)",
                "FEATURE_03 stack restack projections",
                "FEATURE_09 seal-plan required_actions",
                "FEATURE_01/02 agent+router for derived eligibility",
            ],
        },
    }


def get_residual(packet: dict, residual_id: str) -> dict:
    for rec in packet.get("residuals") or []:
        if rec.get("residual_id") == residual_id:
            return {"found": True, "residual": rec}
    return {"found": False, "reason": f"UNKNOWN_RESIDUAL:{residual_id}",
            "residual": None}


def residual_frontier_actions(packet: dict) -> list[dict]:
    """Projection consumed by Feature-12: OPEN residuals as action seeds."""
    out: list[dict] = []
    for rec in packet.get("residuals") or []:
        if rec.get("disposition") != OPEN:
            continue
        out.append({
            "residual_id": rec["residual_id"],
            "action_type": rec["required_action_type"],
            "pr": rec.get("target_pr"),
            "lane": rec.get("target_lane"),
            "derived_execution_state": rec.get("derived_execution_state"),
            "blocking_reasons": list(rec.get("blocking_reasons") or []),
            "severity": rec.get("severity"),
            "residual_type": rec.get("residual_type"),
            "description": rec.get("description"),
            "agent_eligible": rec.get("derived_execution_state") == RUNNABLE,
        })
    out.sort(key=lambda a: (str(a.get("lane") or ""), a["residual_id"]))
    return out


def resolution_evidence_valid(residual: dict, evidence: list[str],
                              *, current_head: str | None = None,
                              allow_stale: bool = False) -> tuple[bool, list[str]]:
    """Fail-closed resolution contract check."""
    if not evidence:
        return False, ["RESOLUTION_REQUIRES_EVIDENCE"]
    criteria = list(residual.get("resolution_criteria") or [])
    if not criteria:
        return False, ["RESOLUTION_CRITERIA_MISSING"]
    reasons: list[str] = []
    for item in evidence:
        if (not allow_stale
                and (item.startswith("stale:") or item.startswith("predecessor:"))):
            reasons.append(f"STALE_EVIDENCE:{item}")
        if (current_head and item.startswith("head:")
                and item != f"head:{current_head}"):
            reasons.append(f"EVIDENCE_HEAD_MISMATCH:{item}")
    # PR closure alone is never enough.
    if evidence and all(
            e.startswith("pr_closed:") or e == "PR_CLOSED" for e in evidence):
        reasons.append("PR_CLOSURE_ALONE_CANNOT_RESOLVE")
    if reasons:
        return False, sorted(set(reasons))
    return True, []


def accepted_risk_authorized(profile: dict | None, residual: dict,
                             lane_owner: str | None) -> tuple[bool, list[str]]:
    """ACCEPTED_RISK requires explicit owner authority."""
    if profile is None:
        return False, ["AGENT_REQUIRED_FOR_ACCEPTED_RISK"]
    agent_id = str(profile.get("agent_id"))
    if lane_owner is None:
        return False, ["ACCEPTED_RISK_REQUIRES_LANE_OWNER"]
    if lane_owner != agent_id:
        return False, [f"ACCEPTED_RISK_REQUIRES_OWNER:{lane_owner}"]
    if "BYPASS_OWNER_GATE" in {str(p) for p in profile.get("prohibitions", [])}:
        # Prohibition means agent cannot bypass — still OK if they ARE owner.
        pass
    return True, []
