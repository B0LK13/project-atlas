"""Efficiency metrics & coordination telemetry (FEATURE_14).

TELEMETRY != AUTHORITY

Presentation-only derived counters over live DAG truth. Telemetry never
grants claim / dispatch / merge / IV / write authority. Efficiency metrics
are a pure projection of a telemetry packet and inherit the same honesty
boundary.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from . import agents as agents_mod
from . import events as events_mod

SCHEMA_CONST = "ATLAS_COORDINATION_TELEMETRY_V1"
METRICS_SCHEMA_CONST = "ATLAS_EFFICIENCY_METRICS_V1"
TELEMETRY_SCHEMA_FILE = "atlas_coordination_telemetry_v1.schema.json"
METRICS_SCHEMA_FILE = "atlas_efficiency_metrics_v1.schema.json"

OK = "OK"
DEGRADED = "DEGRADED"
UNKNOWN = "UNKNOWN"

WAIT_KINDS = ("CI", "IV", "OWNER", "HUMAN", "CLAIM_INTEGRITY")

CATEGORY_KEYS = (
    "utilization",
    "wait_time",
    "blocked_reasons",
    "residual_backlog",
    "steal_success",
    "ci_iv_latency_proxy",
    "frontier_depth",
    "ownership_contention",
    "event_bus_health",
)


class TelemetryError(RuntimeError):
    """Fail-closed telemetry failure (rare — prefer UNKNOWN categories)."""


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _honesty() -> dict:
    return {
        "telemetry_ne_authority": True,
        "metrics_ne_authorization": True,
        "derived_from_live_dag_only": True,
        "grants_no_write_claim_dispatch_merge_iv": True,
    }


def validate_telemetry(packet: dict) -> list[str]:
    validator = events_mod.validator_for(TELEMETRY_SCHEMA_FILE)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )


def validate_metrics(packet: dict) -> list[str]:
    validator = events_mod.validator_for(METRICS_SCHEMA_FILE)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )


def _cat(status: str, notes: list[str] | None = None,
         **metrics: Any) -> dict:
    return {
        "status": status,
        "notes": list(notes or []),
        "metrics": dict(metrics),
    }


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _resolve_agent(agent_id: str | None,
                   registry: agents_mod.RegistryResult | None) -> tuple[str, dict | None]:
    if agent_id is None:
        return "NONE", None
    if registry is None:
        return "REGISTRY_REQUIRED", None
    resolved = agents_mod.resolve_agent(registry, agent_id)
    if resolved.status != "REGISTERED":
        return resolved.status, None
    profile = resolved.profile or {}
    if not profile.get("active", False):
        return "REGISTERED_INACTIVE", profile
    return "REGISTERED_ACTIVE", profile


def _maybe_build_inputs(
    *,
    snapshot: dict | None,
    stacks: dict | None,
    events: list[dict] | None,
    matrix: dict | None,
    residual_registry: dict | None,
    steal_plan: dict | None,
    agent_id: str | None,
    registry: agents_mod.RegistryResult | None,
    repository: str,
    clock: Callable[[], str],
) -> tuple[dict | None, dict | None, dict | None]:
    """Prefer injected packets; build lazily when agent_id is set."""
    if agent_id is None or registry is None or snapshot is None:
        return matrix, residual_registry, steal_plan

    if residual_registry is None:
        from . import residuals as residuals_mod
        residual_registry = residuals_mod.build_residual_registry(
            repository=repository,
            events=events or [],
            snapshot=snapshot,
            stacks=stacks or {},
            seal_by_pr=None,
            agent_id=agent_id,
            registry=registry,
            clock=clock,
        )

    if matrix is None:
        from . import frontier_matrix as frontier_matrix_mod
        from . import score as score_mod
        weights, source = score_mod.load_weights()
        matrix = frontier_matrix_mod.build_frontier_matrix(
            snapshot,
            agent_id=agent_id,
            registry=registry,
            stacks=stacks or {},
            weights=weights,
            weights_source=source,
            residual_registry=residual_registry,
            events=events or [],
            seal_by_pr=None,
            clock=clock,
        )

    if steal_plan is None:
        from . import score as score_mod
        from . import steal as steal_mod
        weights, source = score_mod.load_weights()
        steal_plan = steal_mod.plan_steal(
            snapshot, agent_id, registry, stacks=stacks or {},
            weights=weights, weights_source=source, clock=clock,
        )

    return matrix, residual_registry, steal_plan


def _category_utilization(
    steal_plan: dict | None,
    snapshot: dict | None,
    agent_status: str,
) -> dict:
    nodes = list((snapshot or {}).get("nodes") or [])
    owned = sum(1 for n in nodes if n.get("ownership") == "OWNED")
    unowned = sum(1 for n in nodes if n.get("ownership") == "UNOWNED")
    if steal_plan is None:
        if agent_status == "NONE":
            return _cat(
                OK if nodes else UNKNOWN,
                ["PORTFOLIO_UTILIZATION_NO_AGENT"],
                utilization="PORTFOLIO",
                owned_lane_count=owned,
                unowned_lane_count=unowned,
                owned_compatible_count=None,
                steal_candidate_present=False,
            )
        return _cat(
            UNKNOWN,
            ["STEAL_PLAN_ABSENT"],
            utilization=None,
            owned_lane_count=owned,
            unowned_lane_count=unowned,
            owned_compatible_count=None,
            steal_candidate_present=False,
        )
    util = steal_plan.get("utilization")
    notes: list[str] = []
    status = OK
    if util not in ("STEAL_AVAILABLE", "ALL_COMPATIBLE_WORK_OWNED"):
        status = DEGRADED if util else UNKNOWN
        if util:
            notes.append(f"UTILIZATION:{util}")
    return _cat(
        status,
        notes,
        utilization=util,
        owned_lane_count=owned,
        unowned_lane_count=unowned,
        owned_compatible_count=steal_plan.get("owned_compatible_count"),
        steal_candidate_present=steal_plan.get("candidate") is not None,
        candidate_count=len(steal_plan.get("candidates") or []),
    )


def _category_wait_time(snapshot: dict | None, now: datetime | None) -> dict:
    nodes = list((snapshot or {}).get("nodes") or [])
    if not nodes:
        return _cat(UNKNOWN, ["NO_SNAPSHOT_NODES"],
                    waiting_counts={k: 0 for k in WAIT_KINDS},
                    age_hours_known=0, age_hours_unknown=0,
                    max_age_hours=None)
    counts = {k: 0 for k in WAIT_KINDS}
    age_known = 0
    age_unknown = 0
    max_age: float | None = None
    notes: list[str] = []
    for node in nodes:
        for wait in node.get("waiting_on") or []:
            key = str(wait).upper()
            if key in counts:
                counts[key] += 1
            elif "CI" in key:
                counts["CI"] += 1
            elif "IV" in key:
                counts["IV"] += 1
            elif "OWNER" in key:
                counts["OWNER"] += 1
            elif "HUMAN" in key or "POLICY" in key:
                counts["HUMAN"] += 1
            elif "CLAIM" in key:
                counts["CLAIM_INTEGRITY"] += 1
        opened = _parse_iso(node.get("opened_at_utc"))
        if opened is None or now is None:
            age_unknown += 1
        else:
            age_known += 1
            hours = max(0.0, (now - opened).total_seconds() / 3600.0)
            max_age = hours if max_age is None else max(max_age, hours)
    if age_unknown:
        notes.append("UNKNOWN_AGE")
    status = OK if any(counts.values()) or age_known else DEGRADED
    return _cat(
        status, notes,
        waiting_counts=counts,
        age_hours_known=age_known,
        age_hours_unknown=age_unknown,
        max_age_hours=None if max_age is None else round(max_age, 4),
    )


def _category_blocked_reasons(matrix: dict | None) -> dict:
    if matrix is None or not isinstance(matrix, dict):
        return _cat(UNKNOWN, ["MATRIX_ABSENT_OR_INVALID"],
                    histogram=[], top_reason=None, blocked_action_count=0)
    actions = matrix.get("actions")
    if not isinstance(actions, list):
        return _cat(UNKNOWN, ["MATRIX_ACTIONS_INVALID"],
                    histogram=[], top_reason=None, blocked_action_count=0)
    counter: Counter[str] = Counter()
    blocked_n = 0
    for action in actions:
        if not isinstance(action, dict):
            continue
        reasons = action.get("blocking_reasons") or []
        if reasons or action.get("runnable_state") == "BLOCKED":
            blocked_n += 1
        for reason in reasons:
            counter[str(reason)] += 1
    # Deterministic: sort by count desc, then reason asc.
    histogram = [
        {"reason": reason, "count": count}
        for reason, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return _cat(
        OK if matrix.get("frontier_fingerprint") else DEGRADED,
        [],
        histogram=histogram,
        top_reason=histogram[0]["reason"] if histogram else None,
        blocked_action_count=blocked_n,
        distinct_reasons=len(histogram),
    )


def _category_residual_backlog(residual_registry: dict | None) -> dict:
    if residual_registry is None or not isinstance(residual_registry, dict):
        return _cat(UNKNOWN, ["RESIDUAL_REGISTRY_ABSENT"],
                    open_count=None, runnable_count=None, blocked_count=None,
                    by_type={})
    residuals = residual_registry.get("residuals") or []
    by_type: Counter[str] = Counter()
    open_n = 0
    runnable_n = 0
    blocked_n = 0
    for rec in residuals:
        if rec.get("disposition") == "OPEN":
            open_n += 1
            by_type[str(rec.get("residual_type") or "UNKNOWN")] += 1
            state = rec.get("derived_execution_state")
            if state == "RUNNABLE":
                runnable_n += 1
            elif state == "BLOCKED":
                blocked_n += 1
    # Prefer packet counters when present (may include agent derivation).
    open_count = residual_registry.get("open_count", open_n)
    runnable_count = residual_registry.get("runnable_count", runnable_n)
    blocked_count = residual_registry.get("blocked_count", blocked_n)
    status = OK if open_count is not None else UNKNOWN
    return _cat(
        status,
        [],
        open_count=open_count,
        runnable_count=runnable_count,
        blocked_count=blocked_count,
        by_type=dict(sorted(by_type.items())),
        registry_fingerprint=residual_registry.get("registry_fingerprint"),
    )


def _category_steal_success(
    steal_plan: dict | None,
    events: list[dict] | None,
) -> dict:
    claimed = sum(
        1 for e in (events or [])
        if e.get("event") == "OWNER_CLAIMED"
    )
    released = sum(
        1 for e in (events or [])
        if e.get("event") == "OWNER_RELEASED"
    )
    plan_only = claimed == 0 and released == 0
    notes: list[str] = []
    if plan_only:
        notes.append("PLAN_ONLY_NO_CLAIM_HISTORY")
    util = (steal_plan or {}).get("utilization")
    # Never invent a success rate from plan alone.
    success_rate = None if plan_only else (
        round(claimed / max(claimed + released, 1), 6) if (claimed or released) else None
    )
    if steal_plan is None and plan_only:
        return _cat(UNKNOWN, [*notes, "STEAL_PLAN_ABSENT"],
                    plan_only=True, owner_claimed_count=0,
                    owner_released_count=0, success_rate=None,
                    utilization=None)
    status = OK if steal_plan is not None else DEGRADED
    return _cat(
        status,
        notes,
        plan_only=plan_only,
        owner_claimed_count=claimed,
        owner_released_count=released,
        success_rate=success_rate,
        utilization=util,
        steal_available=util == "STEAL_AVAILABLE",
    )


def _category_ci_iv_latency(dispatch_by_pr: dict[int, dict] | None) -> dict:
    if not dispatch_by_pr:
        return _cat(
            UNKNOWN,
            ["DISPATCH_BY_PR_ABSENT"],
            lane_state_counts={},
            ci_duration_hours=None,
            iv_duration_hours=None,
            pr_count=0,
        )
    states: Counter[str] = Counter()
    for plan in dispatch_by_pr.values():
        if not isinstance(plan, dict):
            continue
        # plan may be full dispatch packet with ci/iv sublanes or a lane dict.
        for key in ("ci", "iv", "lane"):
            sub = plan.get(key) if key != "lane" else plan
            if isinstance(sub, dict) and sub.get("lane_state"):
                states[str(sub["lane_state"])] += 1
        if plan.get("lane_state"):
            states[str(plan["lane_state"])] += 1
        for lane_name, lane in (plan.get("lanes") or {}).items():
            if isinstance(lane, dict) and lane.get("lane_state"):
                states[str(lane["lane_state"])] += 1
            _ = lane_name
    # Durations stay null without timestamps — honest proxy only.
    return _cat(
        OK,
        ["DURATION_NULL_WITHOUT_TIMESTAMPS"],
        lane_state_counts=dict(sorted(states.items())),
        ci_duration_hours=None,
        iv_duration_hours=None,
        pr_count=len(dispatch_by_pr),
    )


def _category_frontier_depth(
    snapshot: dict | None,
    matrix: dict | None,
    stacks: dict | None,
) -> dict:
    nodes = list((snapshot or {}).get("nodes") or [])
    state_counts: Counter[str] = Counter(
        str(n.get("state") or "UNKNOWN") for n in nodes)
    restack_n = sum(
        1 for rec in (stacks or {}).values()
        if rec.get("restack_required")
    )
    notes: list[str] = []
    status = OK if nodes else UNKNOWN
    eligible = blocked = ineligible = parallel_size = None
    if matrix is None:
        notes.append("MATRIX_ABSENT")
        status = DEGRADED if nodes else UNKNOWN
    else:
        eligible = len(matrix.get("eligible_actions") or [])
        blocked = len(matrix.get("blocked_actions") or [])
        ineligible = len(matrix.get("ineligible_actions") or [])
        parallel = matrix.get("parallel_runnable_set") or []
        parallel_size = sum(len(g) for g in parallel) if parallel else 0
    return _cat(
        status,
        notes,
        state_counts=dict(sorted(state_counts.items())),
        safe_runnable_count=(snapshot or {}).get("safe_runnable_count"),
        eligible_action_count=eligible,
        blocked_action_count=blocked,
        ineligible_action_count=ineligible,
        parallel_set_size=parallel_size,
        restack_required_count=restack_n,
        node_count=len(nodes),
    )


def _category_ownership_contention(
    snapshot: dict | None,
    events: list[dict] | None,
) -> dict:
    nodes = list((snapshot or {}).get("nodes") or [])
    owned = ambiguous = unowned = 0
    for node in nodes:
        ownership = node.get("ownership")
        if ownership == "OWNED":
            owned += 1
        elif ownership == "AMBIGUOUS":
            ambiguous += 1
        elif ownership == "UNOWNED":
            unowned += 1
    claim_churn = sum(
        1 for e in (events or [])
        if e.get("event") in ("OWNER_CLAIMED", "OWNER_RELEASED")
    )
    notes: list[str] = []
    status = OK if nodes else UNKNOWN
    if ambiguous:
        notes.append("AMBIGUOUS_OWNERSHIP_PRESENT")
        status = DEGRADED
    return _cat(
        status,
        notes,
        owned_count=owned,
        unowned_count=unowned,
        ambiguous_count=ambiguous,
        claim_churn=claim_churn,
    )


def _category_event_bus_health(
    events: list[dict] | None,
    invalid_events: list | None,
) -> dict:
    evs = list(events or [])
    invalid = list(invalid_events or [])
    by_type: Counter[str] = Counter(str(e.get("event") or "UNKNOWN") for e in evs)
    status = OK
    notes: list[str] = []
    if invalid:
        status = DEGRADED
        notes.append(f"INVALID_EVENTS:{len(invalid)}")
    if not evs and not invalid:
        status = UNKNOWN
        notes.append("NO_EVENTS")
    return _cat(
        status,
        notes,
        event_count=len(evs),
        by_type=dict(sorted(by_type.items())),
        invalid_events=len(invalid),
    )


def _truth_fingerprint(
    snapshot: dict | None,
    events: list[dict] | None,
    matrix: dict | None,
    residual_registry: dict | None,
    steal_plan: dict | None,
) -> str:
    nodes_material = [
        {
            "pr": n.get("pr"),
            "state": n.get("state"),
            "owner": n.get("owner"),
            "ownership": n.get("ownership"),
        }
        for n in sorted((snapshot or {}).get("nodes") or [],
                        key=lambda x: int(x.get("pr") or 0))
    ]
    event_ids = sorted(
        str(e.get("event_id")) for e in (events or []) if e.get("event_id")
    )
    material = {
        "nodes": nodes_material,
        "event_ids": event_ids,
        "matrix_fingerprint": (matrix or {}).get("frontier_fingerprint"),
        "residual_fingerprint": (residual_registry or {}).get("registry_fingerprint"),
        "steal_ranking_fingerprint": (steal_plan or {}).get("ranking_fingerprint")
        or (steal_plan or {}).get("multidim_frontier_fingerprint"),
    }
    return _canonical_sha256(material)


def build_coordination_telemetry(
    *,
    repository: str,
    snapshot: dict | None = None,
    stacks: dict | None = None,
    events: list[dict] | None = None,
    invalid_events: list | None = None,
    matrix: dict | None = None,
    residual_registry: dict | None = None,
    steal_plan: dict | None = None,
    dispatch_by_pr: dict[int, dict] | None = None,
    agent_id: str | None = None,
    registry: agents_mod.RegistryResult | None = None,
    clock: Callable[[], str] = utcnow,
    seal_projection: str = "deferred_or_skipped",
) -> dict:
    """Build ATLAS_COORDINATION_TELEMETRY_V1 from live (or injected) DAG truth."""
    agent_status, _profile = _resolve_agent(agent_id, registry)
    matrix, residual_registry, steal_plan = _maybe_build_inputs(
        snapshot=snapshot,
        stacks=stacks,
        events=events,
        matrix=matrix,
        residual_registry=residual_registry,
        steal_plan=steal_plan,
        agent_id=agent_id,
        registry=registry,
        repository=repository,
        clock=clock,
    )

    now = _parse_iso(clock())
    categories = {
        "utilization": _category_utilization(steal_plan, snapshot, agent_status),
        "wait_time": _category_wait_time(snapshot, now),
        "blocked_reasons": _category_blocked_reasons(matrix),
        "residual_backlog": _category_residual_backlog(residual_registry),
        "steal_success": _category_steal_success(steal_plan, events),
        "ci_iv_latency_proxy": _category_ci_iv_latency(dispatch_by_pr),
        "frontier_depth": _category_frontier_depth(snapshot, matrix, stacks),
        "ownership_contention": _category_ownership_contention(snapshot, events),
        "event_bus_health": _category_event_bus_health(events, invalid_events),
    }

    honesty = _honesty()
    truth_fp = _truth_fingerprint(
        snapshot, events, matrix, residual_registry, steal_plan)
    telemetry_fp = _canonical_sha256(categories)

    notes_prov: list[str] = []
    if seal_projection in ("deferred_or_skipped", "SEAL_SCAN_SKIPPED"):
        notes_prov.append("SEAL_SCAN_SKIPPED")

    return {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "repository": repository,
        "agent": agent_id,
        "agent_status": agent_status,
        "truth_fingerprint": truth_fp,
        "telemetry_fingerprint": telemetry_fp,
        "honesty": honesty,
        "categories": categories,
        "provenance": {
            "generator": "atlas-dag telemetry (FEATURE_14)",
            **honesty,
            "seal_projection": seal_projection,
            "notes": notes_prov,
            "truth_sources": [
                "ATLAS_DAG_SNAPSHOT_V1",
                "FEATURE_03 stack topology",
                "FEATURE_04 event bus",
                "FEATURE_11 steal plan (presentation)",
                "FEATURE_12 multidimensional frontier (presentation)",
                "FEATURE_13 residual registry (events+stacks; seals deferred)",
            ],
        },
    }


def build_efficiency_metrics(telemetry_packet: dict,
                             *,
                             clock: Callable[[], str] | None = None) -> dict:
    """Pure rollup projection of ATLAS_COORDINATION_TELEMETRY_V1."""
    cats = telemetry_packet.get("categories") or {}
    util = (cats.get("utilization") or {}).get("metrics") or {}
    wait = (cats.get("wait_time") or {}).get("metrics") or {}
    blocked = (cats.get("blocked_reasons") or {}).get("metrics") or {}
    residual = (cats.get("residual_backlog") or {}).get("metrics") or {}
    steal = (cats.get("steal_success") or {}).get("metrics") or {}
    latency = (cats.get("ci_iv_latency_proxy") or {}).get("metrics") or {}
    frontier = (cats.get("frontier_depth") or {}).get("metrics") or {}
    ownership = (cats.get("ownership_contention") or {}).get("metrics") or {}
    bus = (cats.get("event_bus_health") or {}).get("metrics") or {}

    waiting_counts = wait.get("waiting_counts") or {}
    summary = {
        "owned_lane_count": util.get("owned_lane_count"),
        "unowned_lane_count": util.get("unowned_lane_count"),
        "steal_candidate_count": util.get("candidate_count"),
        "waiting_ci": waiting_counts.get("CI"),
        "waiting_iv": waiting_counts.get("IV"),
        "waiting_owner": waiting_counts.get("OWNER"),
        "waiting_human": waiting_counts.get("HUMAN"),
        "waiting_claim_integrity": waiting_counts.get("CLAIM_INTEGRITY"),
        "blocked_reason_distinct": blocked.get("distinct_reasons"),
        "blocked_action_count": blocked.get("blocked_action_count"),
        "residual_open": residual.get("open_count"),
        "residual_runnable": residual.get("runnable_count"),
        "residual_blocked": residual.get("blocked_count"),
        "owner_claimed_count": steal.get("owner_claimed_count"),
        "steal_success_rate": steal.get("success_rate"),
        "ci_duration_hours": latency.get("ci_duration_hours"),
        "iv_duration_hours": latency.get("iv_duration_hours"),
        "safe_runnable_count": frontier.get("safe_runnable_count"),
        "eligible_action_count": frontier.get("eligible_action_count"),
        "parallel_set_size": frontier.get("parallel_set_size"),
        "restack_required_count": frontier.get("restack_required_count"),
        "owned_count": ownership.get("owned_count"),
        "unowned_count": ownership.get("unowned_count"),
        "ambiguous_count": ownership.get("ambiguous_count"),
        "claim_churn": ownership.get("claim_churn"),
        "event_count": bus.get("event_count"),
        "invalid_event_count": bus.get("invalid_events"),
    }

    stamp = clock() if clock is not None else telemetry_packet.get(
        "generated_at_utc") or utcnow()
    honesty = _honesty()
    return {
        "schema": METRICS_SCHEMA_CONST,
        "generated_at_utc": stamp,
        "repository": telemetry_packet.get("repository"),
        "agent": telemetry_packet.get("agent"),
        "summary": summary,
        "honesty": honesty,
        "source_telemetry_fingerprint": telemetry_packet.get(
            "telemetry_fingerprint"),
        "provenance": {
            "generator": "atlas-dag efficiency-metrics (FEATURE_14)",
            **honesty,
            "projection_of": SCHEMA_CONST,
        },
    }
