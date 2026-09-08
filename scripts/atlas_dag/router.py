"""Agent-aware work router (FEATURE_02, D-ATLAS-DAG-FEATURE-02).

Answers: given current repository truth (the DAG snapshot) and this agent's
registered capabilities (ATLAS_AGENT_REGISTRY_V1), what is the next safe
action this agent may perform?

Routing != authorization. This module RECOMMENDS only:

* it never claims a lane, posts events, modifies branches/files, dispatches
  CI, requests or performs IV, merges, or overrides an owner/freeze/gate;
* the snapshot remains the authority for lane state (RUNNABLE_WRITE exists
  only for lanes the snapshot itself classified as owned-and-unfrozen);
* the registry remains advisory context — it can only shrink the route set,
  never enlarge it, and it never converts an OWNER/IV/POLICY-gated node
  into writable work.

Selection semantics (no scoring yet): permitted RUNNABLE_WRITE first, then
permitted RUNNABLE_READONLY, otherwise NO_SAFE_ROUTE; ties break by
canonical lane identity. Output is deterministic for equivalent snapshots.

Platform/scope honesty: the live snapshot currently carries no per-lane
platform-requirement or required-scope field (no open PR carries such
labels), so the router cannot truthfully infer them from repository data.
When a node DOES declare `platform_requirements` or `required_scopes`, they
are enforced fail-closed. Live Windows-native gating therefore rides on
ownership/freeze frontier state plus the registry prohibition
EMULATE_WINDOWS_VALIDATION — never on invented lane attributes.

Formal verifier routing is NOT implemented (verifier principal
authentication is a later feature).
"""
from __future__ import annotations

from . import agents as agents_mod
from . import stack as stack_mod

ROUTE_WRITE = "RUNNABLE_WRITE"
ROUTE_READONLY = "RUNNABLE_READONLY"
NO_ROUTE = "NO_SAFE_ROUTE"

# Deterministic preference order for action classes.
_CLASS_RANK = {ROUTE_WRITE: 0, ROUTE_READONLY: 1, NO_ROUTE: 2}

WRITE_CAPABILITIES = frozenset({"WRITE_CODE", "WRITE_TESTS", "WRITE_DOCS"})
READ_CAPABILITIES = frozenset({"READ_REPO", "READ_GITHUB"})


def _platform_compatible(profile: dict, node: dict) -> tuple[bool, list[str]]:
    """Optional node-declared platform requirements, enforced fail-closed."""
    requirements = node.get("platform_requirements")
    if not requirements:
        return True, []
    platforms = {str(p) for p in profile.get("platforms", [])}
    covered = set(map(str, requirements)) & (platforms | {"any"})
    if covered:
        return True, []
    return False, sorted({f"PLATFORM_REQUIRED:{r}" for r in map(str, requirements)})


def _scopes_covered(profile: dict, node: dict) -> tuple[bool, list[str]]:
    """Optional node-declared required write scopes, enforced fail-closed."""
    required = node.get("required_scopes")
    if not required:
        if any(str(s).startswith("path:") for s in profile.get("write_scopes", [])):
            return True, []
        return False, ["NO_PATH_WRITE_SCOPE_DECLARED"]
    missing = [s for s in required if not agents_mod.scope_covers(profile, s)]
    if missing:
        return False, sorted({f"SCOPE_NOT_COVERED:{s}" for s in missing})
    return True, []


def evaluate_lane(profile: dict, node: dict,
                  stack: dict | None = None) -> dict:
    """One lane vs one agent: the maximal permitted action class.

    Read-only diagnosis is safe for any lane the snapshot exposes (even
    foreign-platform, frozen, or ambiguously-owned: reading changes
    nothing), so READONLY is the floor; WRITE additionally requires the
    snapshot's own RUNNABLE_WRITE state, the ownership mutex, platform and
    scope fit, a write capability, and — when stack truth is supplied — a
    current stack relation. Stack membership never grants write authority;
    a stacked child is never independent mergeable-to-main work.
    """
    agent_id = str(profile.get("agent_id", "?"))
    lane = str(node.get("lane", "?"))
    capabilities = {str(c) for c in profile.get("capabilities", [])}
    read_capable = bool(capabilities & READ_CAPABILITIES)
    write_capable = bool(capabilities & WRITE_CAPABILITIES)
    blockers: list[str] = []

    if not read_capable:
        blockers.append("NO_READ_CAPABILITY")
        return {"lane": lane, "action_class": NO_ROUTE, "routable": False,
                "reasons": [], "blockers": sorted(blockers)}

    write_blockers: list[str] = []
    if node.get("state") != ROUTE_WRITE:
        write_blockers.append(f"SNAPSHOT_STATE_NOT_WRITABLE:{node.get('state')}")
    if node.get("frozen"):
        write_blockers.append("LANE_FROZEN_BY_REPOSITORY_TRUTH")
    ownership = node.get("ownership")
    owner = node.get("owner")
    if ownership == "AMBIGUOUS":
        write_blockers.append("OWNERSHIP_AMBIGUOUS_FAIL_CLOSED")
    elif owner is not None and owner != agent_id:
        write_blockers.append(f"OWNERSHIP_MUTEX_HELD_BY:{owner}")
    elif owner is None:
        write_blockers.append("LANE_UNOWNED_WRITE_REQUIRES_CLAIM")
    if not write_capable:
        write_blockers.append("NO_WRITE_CAPABILITY")
    platform_ok, platform_reasons = _platform_compatible(profile, node)
    if not platform_ok:
        write_blockers.extend(platform_reasons)
    scopes_ok, scope_reasons = _scopes_covered(profile, node)
    if not scopes_ok:
        write_blockers.extend(scope_reasons)
    if stack is not None:
        stack_state = stack.get("stack_state")
        if stack_state in stack_mod.NOT_CURRENT_STATES or \
                stack.get("restack_required"):
            write_blockers.append(f"STACK_NOT_CURRENT:{stack_state}")

    if not write_blockers:
        reasons = {"OWNED_BY_AGENT" if owner == agent_id else "LANE_WRITABLE",
                   "WRITE_CAPABILITY_PRESENT"}
        if stack is not None and stack.get("parent_pr") is not None:
            # Stacked child: writable, but never independent
            # mergeable-to-main work — annotate for consumers.
            reasons.add(f"STACK_CHILD_OF:pr/{stack['parent_pr']}")
        return {"lane": lane, "action_class": ROUTE_WRITE, "routable": True,
                "reasons": sorted(reasons),
                "blockers": []}
    blockers.extend(write_blockers)
    return {"lane": lane, "action_class": ROUTE_READONLY, "routable": True,
            "reasons": sorted({"READ_CAPABILITY_PRESENT", "READONLY_DIAGNOSIS_SAFE"}),
            "blockers": sorted(blockers)}


def route(agent_id: str, snapshot: dict, registry: agents_mod.RegistryResult,
          stacks: dict | None = None) -> dict:
    """Deterministic recommendation for one agent over the whole frontier.

    stacks: optional lane -> stack record (FEATURE_03). When supplied, a
    lane with a non-current stack relation can never route as write; when
    absent, stack filtering is skipped (callers with live GitHub access
    should always supply it).
    """
    resolved = agents_mod.resolve_agent(registry, agent_id)
    if resolved.status != "REGISTERED":
        return {
            "schema": "ATLAS_DAG_ROUTE_V1",
            "agent": agent_id,
            "agent_status": resolved.status,
            "action_class": NO_ROUTE,
            "routable": False,
            "lane": None,
            "reasons": [],
            "blockers": sorted(set(resolved.errors)
                               or {resolved.status, "NO_SAFE_ROUTE"}),
            "routes": [],
        }
    profile = resolved.profile or {}
    if not profile.get("active", False):
        return {
            "schema": "ATLAS_DAG_ROUTE_V1",
            "agent": agent_id,
            "agent_status": "REGISTERED_INACTIVE",
            "action_class": NO_ROUTE,
            "routable": False,
            "lane": None,
            "reasons": [],
            "blockers": sorted({"AGENT_INACTIVE", "NO_CURRENT_SESSION"}),
            "routes": [],
        }

    nodes = sorted(snapshot.get("nodes", []), key=lambda n: str(n.get("lane", "")))
    routes = [evaluate_lane(profile, n, (stacks or {}).get(str(n.get("lane"))))
              for n in nodes]
    routes.sort(key=lambda r: (_CLASS_RANK[r["action_class"]], r["lane"]))

    if not routes or all(not r["routable"] for r in routes):
        return {
            "schema": "ATLAS_DAG_ROUTE_V1",
            "agent": agent_id,
            "agent_status": "REGISTERED_ACTIVE",
            "action_class": NO_ROUTE,
            "routable": False,
            "lane": None,
            "reasons": [],
            "blockers": sorted({"NO_SAFE_ROUTE"}),
            "routes": routes,
        }
    best = routes[0]
    return {
        "schema": "ATLAS_DAG_ROUTE_V1",
        "agent": agent_id,
        "agent_status": "REGISTERED_ACTIVE",
        "action_class": best["action_class"],
        "routable": True,
        "lane": best["lane"],
        "reasons": best["reasons"],
        "blockers": [f"{r['lane']}: {reason}"
                     for r in routes[1:] for reason in r["blockers"]][:10],
        "routes": routes,
    }


def route_summary(result: dict) -> str:
    """Human-readable one-liner (deterministic)."""
    if not result["routable"]:
        return (f"{result['agent']}: {NO_ROUTE} "
                f"({', '.join(result['blockers'])})")
    return (f"{result['agent']}: {result['action_class']} -> {result['lane']} "
            f"({', '.join(result['reasons'])})")
