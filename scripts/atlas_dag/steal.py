"""Safe cross-agent work stealing (FEATURE_11).

WORK_STEALING != OWNERSHIP_BYPASS.

An idle eligible agent may claim the highest-value compatible *unowned*
runnable lane from the FEATURE_10 ranked frontier. Actively owned, frozen,
blocked, incompatible, verifier-only, policy-gated, or stale-stack lanes
are never stealable.

Pipeline:

  LIVE DAG
  → agent identity/capabilities
  → FEATURE_10 ranked authorized frontier
  → unowned candidates that WOULD be RUNNABLE_WRITE after claim
  → race-safe OWNER_CLAIMED via FEATURE_04

Stealing never modifies candidate code, dispatches CI, merges, restacks, or
releases another owner's claim. Forced reassignment of an actively owned
lane is out of scope.
"""
from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from . import agents as agents_mod
from . import emitter as emitter_mod
from . import events as events_mod
from . import model as model_mod
from . import router as router_mod
from . import score as score_mod
from . import stack as stack_mod

SCHEMA_CONST = "ATLAS_STEAL_PLAN_V1"
MAX_RACE_RETRIES = 3

STEAL_AVAILABLE = "STEAL_AVAILABLE"
NO_COMPATIBLE_WORK = "NO_COMPATIBLE_WORK"
ALL_COMPATIBLE_WORK_OWNED = "ALL_COMPATIBLE_WORK_OWNED"
BLOCKED_BY_PLATFORM = "BLOCKED_BY_PLATFORM"
BLOCKED_BY_CAPABILITY = "BLOCKED_BY_CAPABILITY"
NO_SAFE_STEAL = "NO_SAFE_STEAL"
STEAL_PLAN_STALE = "STEAL_PLAN_STALE"
ALREADY_OWNED = "ALREADY_OWNED"
CLAIMED = "CLAIMED"
WOULD_CLAIM = "WOULD_CLAIM"

# Ownership-related blockers that a successful claim itself clears.
_CLAIM_CLEARED = frozenset({
    "LANE_UNOWNED_WRITE_REQUIRES_CLAIM",
    "SNAPSHOT_STATE_NOT_WRITABLE:RUNNABLE_READONLY",
})


class StealError(RuntimeError):
    """Fail-closed steal planning/claim failure."""


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hypothesize_owned(node: dict, agent_id: str) -> dict:
    """Project the node as it would appear after this agent claims it."""
    projected = copy.deepcopy(node)
    projected["state"] = router_mod.ROUTE_WRITE
    projected["ownership"] = "OWNED"
    projected["owner"] = agent_id
    projected["claimants"] = [agent_id]
    return projected


def _is_unowned(node: dict) -> bool:
    return node.get("ownership") == "UNOWNED" and node.get("owner") is None


def write_eligible_after_claim(profile: dict, node: dict,
                               stack: dict | None) -> tuple[bool, list[str]]:
    """True when the lane would route WRITE after a successful claim.

    Uses router.evaluate_lane on a hypothesized owned node so we do not
    duplicate WRITE authorization. READONLY never becomes WRITE here without
    the ownership projection.
    """
    if not _is_unowned(node):
        return False, ["LANE_NOT_UNOWNED"]
    if node.get("frozen"):
        return False, ["LANE_FROZEN_BY_REPOSITORY_TRUTH"]
    # Pre-check live evaluate for non-ownership blockers while unowned.
    live = router_mod.evaluate_lane(profile, node, stack)
    residual = [b for b in live.get("blockers") or [] if b not in _CLAIM_CLEARED]
    # Platform/capability/stack/frozen must already be clean aside from claim.
    hypo = _hypothesize_owned(node, str(profile.get("agent_id")))
    auth = router_mod.evaluate_lane(profile, hypo, stack)
    if auth["action_class"] != router_mod.ROUTE_WRITE or not auth["routable"]:
        return False, sorted(set(residual) | set(auth.get("blockers") or []))
    if residual:
        # Hypo succeeded but live had non-claim blockers that hypo somehow
        # cleared — fail closed; claim must not paper over them.
        return False, sorted(residual)
    return True, []


def _utilization(agent_status: str, profile: dict | None,
                 stealable: list[dict], owned_compatible: int,
                 platform_blocked: int, capability_blocked: int) -> str:
    if agent_status != "REGISTERED_ACTIVE" or profile is None:
        return NO_SAFE_STEAL
    caps = {str(c) for c in profile.get("capabilities", [])}
    if not (caps & router_mod.WRITE_CAPABILITIES):
        return BLOCKED_BY_CAPABILITY
    if stealable:
        return STEAL_AVAILABLE
    # Prefer more specific codes when they dominate.
    if (capability_blocked and not platform_blocked
            and owned_compatible == 0):
        return BLOCKED_BY_CAPABILITY
    if platform_blocked and owned_compatible == 0:
        return BLOCKED_BY_PLATFORM
    if owned_compatible > 0:
        return ALL_COMPATIBLE_WORK_OWNED
    return NO_COMPATIBLE_WORK


def plan_steal(
    snapshot: dict,
    agent_id: str,
    registry: agents_mod.RegistryResult,
    *,
    stacks: dict | None = None,
    weights: dict | None = None,
    weights_source: str = "explicit",
    clock: Callable[[], str] = utcnow,
) -> dict:
    """Read-only steal plan: ranked unowned WRITE-after-claim candidates."""
    resolved = agents_mod.resolve_agent(registry, agent_id)
    if resolved.status != "REGISTERED":
        return {
            "schema": SCHEMA_CONST,
            "generated_at_utc": clock(),
            "agent": agent_id,
            "agent_status": resolved.status,
            "utilization": NO_SAFE_STEAL,
            "candidate": None,
            "candidates": [],
            "skipped": [],
            "ranking_fingerprint": None,
            "reasons": sorted(set(resolved.errors) or {resolved.status}),
        }
    profile = resolved.profile or {}
    if not profile.get("active", False):
        return {
            "schema": SCHEMA_CONST,
            "generated_at_utc": clock(),
            "agent": agent_id,
            "agent_status": "REGISTERED_INACTIVE",
            "utilization": NO_SAFE_STEAL,
            "candidate": None,
            "candidates": [],
            "skipped": [],
            "ranking_fingerprint": None,
            "reasons": ["AGENT_INACTIVE"],
        }

    cfg = weights
    source = weights_source
    if cfg is None:
        cfg, source = score_mod.load_weights()
    score_packet = score_mod.rank_frontier(
        snapshot, agent_id=agent_id, registry=registry, stacks=stacks,
        weights=cfg, weights_source=source, clock=clock)

    score_by_pr = {e["pr"]: e for e in score_packet.get("ranked", [])}
    # Also score unowned nodes that may only appear with low totals.
    stealable: list[dict] = []
    skipped: list[dict] = []
    owned_compatible = 0
    platform_blocked = 0
    capability_blocked = 0

    for node in snapshot.get("nodes") or []:
        pr = int(node["pr"])
        lane = str(node.get("lane") or f"pr/{pr}")
        stack = (stacks or {}).get(lane)
        scored = score_by_pr.get(pr)
        # Count owned-but-otherwise-compatible for utilization.
        if node.get("ownership") == "OWNED" and node.get("owner") != agent_id:
            hypo = _hypothesize_owned(node, agent_id)
            # Would this agent write if it owned it? (ignore foreign mutex)
            hypo_auth = router_mod.evaluate_lane(profile, hypo, stack)
            foreign_only = [
                b for b in (router_mod.evaluate_lane(profile, node, stack)
                            .get("blockers") or [])
                if not b.startswith("OWNERSHIP_MUTEX_HELD_BY:")
                and b not in _CLAIM_CLEARED
            ]
            if hypo_auth["action_class"] == router_mod.ROUTE_WRITE and not foreign_only:
                owned_compatible += 1
            continue

        if node.get("ownership") == "AMBIGUOUS":
            skipped.append({"pr": pr, "lane": lane, "reasons": ["OWNERSHIP_AMBIGUOUS"]})
            continue

        ok, reasons = write_eligible_after_claim(profile, node, stack)
        if not ok:
            if any(r.startswith("PLATFORM_REQUIRED:") for r in reasons):
                platform_blocked += 1
            if "NO_WRITE_CAPABILITY" in reasons:
                capability_blocked += 1
            if _is_unowned(node):
                skipped.append({"pr": pr, "lane": lane, "reasons": reasons})
            continue

        # Prefer FEATURE_10 total when present; otherwise compute factors.
        if scored is not None:
            total = float(scored["total"])
            factors = scored["factors"]
        else:
            factors = score_mod.compute_factors(node, stack, profile, cfg)
            total = score_mod.factor_total(factors)
        entry = {
            "pr": pr,
            "lane": lane,
            "head": node.get("head"),
            "tree": node.get("tree"),
            "total": total,
            "factors": factors,
            "action_class_after_claim": router_mod.ROUTE_WRITE,
            "ownership": "UNOWNED",
            "tiebreak_key": score_mod.tiebreak_key(
                router_mod.ROUTE_WRITE, total, pr, lane, list(cfg["tiebreak"])),
        }
        stealable.append(entry)

    stealable.sort(key=lambda e: tuple(e["tiebreak_key"]))
    utilization = _utilization(
        "REGISTERED_ACTIVE", profile, stealable, owned_compatible,
        platform_blocked, capability_blocked)
    candidate = stealable[0] if stealable else None
    return {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "agent": agent_id,
        "agent_status": "REGISTERED_ACTIVE",
        "utilization": utilization,
        "candidate": candidate,
        "candidates": stealable,
        "skipped": sorted(skipped, key=lambda s: (s["pr"], s["lane"])),
        "ranking_fingerprint": score_packet.get("ranking_fingerprint"),
        "weights_id": score_packet.get("weights_id"),
        "weights_version": score_packet.get("weights_version"),
        "owned_compatible_count": owned_compatible,
        "reasons": [] if candidate else [utilization],
        "provenance": {
            "generator": "atlas-dag steal (FEATURE_11)",
            "work_stealing_is_not_ownership_bypass": True,
            "authorization_before_claim": True,
            "truth_sources": [
                "FEATURE_01 agent registry",
                "FEATURE_02 router (hypothesized WRITE-after-claim)",
                "FEATURE_03 stack topology",
                "FEATURE_04 event emitter (claim path)",
                "FEATURE_10 ranked frontier",
            ],
        },
    }


def _live_events(client: Any) -> list[dict]:
    issue = client.dag_issue()
    if not issue:
        return []
    ingested = events_mod.ingest_comments(client.issue_comments(issue["number"]))
    return list(ingested.events)


def _live_ownership(client: Any, pr: int,
                    events: list[dict] | None = None) -> tuple[str, list[str]]:
    if events is None:
        events = _live_events(client)
    if not events:
        return "UNOWNED", []
    return model_mod.ownership(events, pr)


def _live_frozen(events: list[dict], pr: int, head: str | None) -> bool:
    """Same freeze signal as model._is_frozen (explicit HUMAN_GATE FROZEN)."""
    for ev in reversed(events):
        if ev.get("pr") != pr:
            continue
        if ev.get("event") != "HUMAN_GATE_REQUIRED":
            continue
        if head and ev.get("head") and ev.get("head") != head:
            continue
        if str(ev.get("state", "")).upper() == "FROZEN":
            return True
    return False


def _revalidate_candidate(client: Any, profile: dict, candidate: dict,
                          stacks: dict | None,
                          expected_repo: str | None) -> list[str]:
    """TOCTOU re-check immediately before claim mutation."""
    reasons: list[str] = []
    if expected_repo is not None and client.repo != expected_repo:
        reasons.append(f"WRONG_REPOSITORY_IDENTITY:{client.repo}")
    if not profile.get("active", False):
        reasons.append("AGENT_INACTIVE")
        return reasons
    live = next((p for p in client.open_prs()
                 if p.get("number") == candidate["pr"]), None)
    if live is None:
        reasons.append("PR_NO_LONGER_OPEN")
        return reasons
    head = live.get("headRefOid")
    if head != candidate.get("head"):
        reasons.append(f"STEAL_PLAN_STALE:head:{candidate.get('head')}->{head}")
    commit = client.commit(head) if head else None
    tree = commit.get("tree") if commit else None
    if tree != candidate.get("tree"):
        reasons.append(f"STEAL_PLAN_STALE:tree:{candidate.get('tree')}->{tree}")
    events = _live_events(client)
    status, claimants = _live_ownership(client, candidate["pr"], events=events)
    if status == "OWNED" and claimants and claimants[0] != profile["agent_id"]:
        reasons.append(f"OWNERSHIP_MUTEX_HELD_BY:{claimants[0]}")
    elif status == "AMBIGUOUS":
        reasons.append("OWNERSHIP_AMBIGUOUS_FAIL_CLOSED")
    elif status == "OWNED" and claimants == [profile["agent_id"]]:
        reasons.append(ALREADY_OWNED)
    frozen = _live_frozen(events, candidate["pr"], head)
    if frozen:
        reasons.append("LANE_FROZEN_BY_REPOSITORY_TRUTH")
    # Rebuild minimal node for freeze/stack/capability re-check.
    node = {
        "lane": candidate["lane"], "pr": candidate["pr"], "head": head,
        "tree": tree, "state": "RUNNABLE_READONLY", "ownership": status,
        "owner": claimants[0] if status == "OWNED" and claimants else None,
        "frozen": frozen, "claimants": claimants,
    }
    stack = (stacks or {}).get(candidate["lane"])
    if status == "UNOWNED" and not frozen:
        ok, elig = write_eligible_after_claim(profile, node, stack)
        if not ok:
            reasons.extend(elig)
    return reasons


def execute_steal(
    client: Any,
    agent_id: str,
    registry: agents_mod.RegistryResult,
    *,
    stacks: dict | None = None,
    weights: dict | None = None,
    weights_source: str = "explicit",
    dry_run: bool = False,
    expected_repo: str | None = None,
    clock: Callable[[], str] = utcnow,
    max_retries: int = MAX_RACE_RETRIES,
    snapshot: dict | None = None,
) -> dict:
    """Plan and optionally claim. dry_run => zero GitHub mutation."""
    for attempt in range(max(1, int(max_retries))):
        snap = snapshot if snapshot is not None and attempt == 0 \
            else model_mod.build_snapshot(client)
        live_stacks = stacks if stacks is not None and attempt == 0 else \
            stack_mod.build_stacks(
                snap["nodes"], client, snap.get("main_branch") or "main")
        plan = plan_steal(
            snap, agent_id, registry, stacks=live_stacks,
            weights=weights, weights_source=weights_source, clock=clock)
        if plan["utilization"] != STEAL_AVAILABLE or plan["candidate"] is None:
            return {
                **plan,
                "outcome": plan["utilization"],
                "mutated": False,
                "attempt": attempt + 1,
                "event_id": None,
            }
        candidate = plan["candidate"]
        resolved = agents_mod.resolve_agent(registry, agent_id)
        profile = resolved.profile or {}

        if dry_run:
            return {
                **plan,
                "outcome": WOULD_CLAIM,
                "mutated": False,
                "attempt": attempt + 1,
                "event_id": None,
                "dry_run": True,
            }

        # TOCTOU re-validation immediately before mutation.
        stale = _revalidate_candidate(
            client, profile, candidate, live_stacks, expected_repo)
        if ALREADY_OWNED in stale:
            return {
                **plan,
                "outcome": ALREADY_OWNED,
                "mutated": False,
                "attempt": attempt + 1,
                "event_id": None,
                "reasons": [ALREADY_OWNED],
            }
        if stale:
            if attempt + 1 >= max_retries:
                return {
                    **plan,
                    "outcome": STEAL_PLAN_STALE,
                    "mutated": False,
                    "attempt": attempt + 1,
                    "event_id": None,
                    "reasons": stale,
                }
            snapshot = None  # force rebuild
            stacks = None
            continue

        owner = None
        status, claimants = _live_ownership(client, candidate["pr"])
        if status == "OWNED" and claimants:
            owner = claimants[0]
        checks = emitter_mod.check_emit_permission(
            registry, agent_id, "OWNER_CLAIMED", owner)
        if not checks.ok:
            return {
                **plan,
                "outcome": NO_SAFE_STEAL,
                "mutated": False,
                "attempt": attempt + 1,
                "event_id": None,
                "reasons": list(checks.reasons),
            }
        try:
            ctx = emitter_mod.resolve_context(
                client, candidate["pr"], profile, expected_repo=expected_repo)
            if ctx.head != candidate["head"]:
                if attempt + 1 >= max_retries:
                    return {
                        **plan, "outcome": STEAL_PLAN_STALE, "mutated": False,
                        "attempt": attempt + 1, "event_id": None,
                        "reasons": [f"STEAL_PLAN_STALE:head:{candidate['head']}->{ctx.head}"],
                    }
                snapshot = None
                stacks = None
                continue
            payload = emitter_mod.build_event(
                ctx, event="OWNER_CLAIMED", state="CLAIMED",
                note=f"FEATURE_11 safe steal by {agent_id}",
                next_actions=["ci"],
                expect_head=candidate["head"])
            status_s = emitter_mod.emit_event(
                client, registry, payload, dry_run=False)
        except emitter_mod.EmitError as exc:
            if attempt + 1 >= max_retries:
                return {
                    **plan, "outcome": NO_SAFE_STEAL, "mutated": False,
                    "attempt": attempt + 1, "event_id": None,
                    "reasons": [str(exc)],
                }
            snapshot = None
            stacks = None
            continue
        return {
            **plan,
            "outcome": CLAIMED if status_s in ("posted", "already-present") else status_s,
            "mutated": status_s == "posted",
            "attempt": attempt + 1,
            "event_id": payload["event_id"],
            "emit_status": status_s,
            "claimed_owner": agent_id,
        }

    return {
        "schema": SCHEMA_CONST,
        "agent": agent_id,
        "utilization": NO_SAFE_STEAL,
        "candidate": None,
        "outcome": NO_SAFE_STEAL,
        "mutated": False,
        "attempt": max_retries,
        "event_id": None,
        "reasons": ["STEAL_RETRIES_EXHAUSTED"],
    }
