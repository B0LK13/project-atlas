"""Autonomous Coordination Dashboard / Global Control View (FEATURE_15).

CONTROL_VIEW != AUTHORITY
UI != CANONICAL TRUTH
TELEMETRY != AUTHORITY

Read-only aggregate of Features 1-14 into one machine-readable packet.
Presentation only: never grants claim / dispatch / merge / IV / write.
UNKNOWN when live truth is missing; fail closed on malformed schema.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import agents as agents_mod
from . import events as events_mod
from . import verifiers as verifiers_mod

SCHEMA_CONST = "ATLAS_GLOBAL_CONTROL_VIEW_V1"
SCHEMA_FILE = "atlas_global_control_view_v1.schema.json"

OK = "OK"
DEGRADED = "DEGRADED"
UNKNOWN = "UNKNOWN"

PANEL_KEYS = (
    "agents",
    "ownership",
    "stacks",
    "frontier",
    "residuals",
    "telemetry",
    "steal",
    "dispatch_gates",
    "evidence_health",
    "postmerge",
    "event_bus",
    "system_honesty",
)


class ControlViewError(RuntimeError):
    """Fail-closed control-view failure (prefer UNKNOWN panels)."""


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _honesty() -> dict:
    return {
        "control_view_ne_authority": True,
        "ui_ne_canonical_truth": True,
        "grants_no_write_claim_dispatch_merge_iv": True,
        "aggregates_live_dag_only": True,
    }


def validate_control_view(packet: dict) -> list[str]:
    validator = events_mod.validator_for(SCHEMA_FILE)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )


def _panel(status: str, summary: dict | None = None, *,
           notes: list[str] | None = None,
           details: dict | None = None) -> dict:
    out: dict[str, Any] = {
        "status": status,
        "summary": dict(summary or {}),
        "notes": list(notes or []),
    }
    if details is not None:
        out["details"] = dict(details)
    return out


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


def _maybe_build_deps(
    *,
    snapshot: dict | None,
    stacks: dict | None,
    events: list[dict] | None,
    matrix: dict | None,
    residual_registry: dict | None,
    steal_plan: dict | None,
    telemetry_packet: dict | None,
    agent_id: str | None,
    registry: agents_mod.RegistryResult | None,
    repository: str,
    clock: Callable[[], str],
) -> tuple[dict | None, dict | None, dict | None, dict | None]:
    """Prefer injected packets; build lazily for residuals always, others with agent."""
    if snapshot is None:
        return matrix, residual_registry, steal_plan, telemetry_packet

    if residual_registry is None and registry is not None:
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

    if agent_id is not None and registry is not None:
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

    if telemetry_packet is None:
        from . import telemetry as telemetry_mod
        telemetry_packet = telemetry_mod.build_coordination_telemetry(
            repository=repository,
            snapshot=snapshot,
            stacks=stacks or {},
            events=events or [],
            matrix=matrix,
            residual_registry=residual_registry,
            steal_plan=steal_plan,
            agent_id=agent_id,
            registry=registry,
            clock=clock,
            seal_projection="deferred_or_skipped",
        )

    return matrix, residual_registry, steal_plan, telemetry_packet


def _panel_agents(
    registry: agents_mod.RegistryResult | None,
    agent_status: str,
    agent_id: str | None,
) -> dict:
    if registry is None or not registry.valid:
        return _panel(
            UNKNOWN,
            {"active_count": None, "inactive_count": None, "agent_status": agent_status},
            notes=["REGISTRY_ABSENT_OR_INVALID"],
        )
    agents = list((registry.registry or {}).get("agents") or [])
    active = sum(1 for a in agents if a.get("active", False))
    inactive = len(agents) - active
    notes: list[str] = []
    status = OK
    if agent_id is not None and agent_status not in (
            "REGISTERED_ACTIVE", "NONE"):
        status = DEGRADED
        notes.append(f"AGENT_STATUS:{agent_status}")
    return _panel(
        status,
        {
            "active_count": active,
            "inactive_count": inactive,
            "total_count": len(agents),
            "agent_status": agent_status,
            "agent": agent_id,
        },
        notes=notes,
    )


def _panel_ownership(snapshot: dict | None) -> dict:
    nodes = list((snapshot or {}).get("nodes") or [])
    if not nodes:
        return _panel(UNKNOWN, {
            "owned_count": 0, "unowned_count": 0, "ambiguous_count": 0,
        }, notes=["NO_SNAPSHOT_NODES"])
    owned = unowned = ambiguous = 0
    for node in nodes:
        ownership = node.get("ownership")
        if ownership == "OWNED":
            owned += 1
        elif ownership == "UNOWNED":
            unowned += 1
        elif ownership == "AMBIGUOUS":
            ambiguous += 1
    notes: list[str] = []
    status = OK
    if ambiguous:
        status = DEGRADED
        notes.append("AMBIGUOUS_OWNERSHIP_PRESENT")
    return _panel(status, {
        "owned_count": owned,
        "unowned_count": unowned,
        "ambiguous_count": ambiguous,
        "node_count": len(nodes),
    }, notes=notes)


def _panel_stacks(stacks: dict | None) -> dict:
    if stacks is None:
        return _panel(UNKNOWN, {
            "stack_record_count": None,
            "restack_required_count": None,
            "max_depth": None,
        }, notes=["STACKS_ABSENT"])
    records = list(stacks.values()) if isinstance(stacks, dict) else []
    restack = sum(1 for r in records if r.get("restack_required"))
    depths = [
        int(r["depth"]) for r in records
        if isinstance(r.get("depth"), int)
    ]
    max_depth = max(depths) if depths else None
    notes: list[str] = []
    status = OK if records else UNKNOWN
    if restack:
        status = DEGRADED
        notes.append("RESTACK_REQUIRED_PRESENT")
    return _panel(status, {
        "stack_record_count": len(records),
        "restack_required_count": restack,
        "max_depth": max_depth,
    }, notes=notes)


def _panel_frontier(matrix: dict | None) -> dict:
    if matrix is None or not isinstance(matrix, dict):
        return _panel(UNKNOWN, {
            "eligible_count": None,
            "blocked_count": None,
            "ineligible_count": None,
            "parallel_set_size": None,
        }, notes=["MATRIX_ABSENT"])
    eligible = len(matrix.get("eligible_actions") or [])
    blocked = len(matrix.get("blocked_actions") or [])
    ineligible = len(matrix.get("ineligible_actions") or [])
    parallel = matrix.get("parallel_runnable_set") or []
    parallel_size = sum(len(g) for g in parallel) if parallel else 0
    # Never invent runnable upgrades from blocked counts.
    return _panel(
        OK if matrix.get("frontier_fingerprint") else DEGRADED,
        {
            "eligible_count": eligible,
            "blocked_count": blocked,
            "ineligible_count": ineligible,
            "parallel_set_size": parallel_size,
            "frontier_fingerprint": matrix.get("frontier_fingerprint"),
        },
        notes=["PRESENTATION_ONLY"],
    )


def _panel_residuals(residual_registry: dict | None) -> dict:
    if residual_registry is None or not isinstance(residual_registry, dict):
        return _panel(UNKNOWN, {
            "open_count": None,
            "runnable_count": None,
            "blocked_count": None,
        }, notes=["RESIDUAL_REGISTRY_ABSENT", "seal_projection:deferred"])
    open_count = residual_registry.get("open_count")
    runnable_count = residual_registry.get("runnable_count")
    blocked_count = residual_registry.get("blocked_count")
    if open_count is None:
        open_n = runnable_n = blocked_n = 0
        for rec in residual_registry.get("residuals") or []:
            if rec.get("disposition") == "OPEN":
                open_n += 1
                state = rec.get("derived_execution_state")
                if state == "RUNNABLE":
                    runnable_n += 1
                elif state == "BLOCKED":
                    blocked_n += 1
        open_count, runnable_count, blocked_count = open_n, runnable_n, blocked_n
    return _panel(OK, {
        "open_count": open_count,
        "runnable_count": runnable_count,
        "blocked_count": blocked_count,
        "registry_fingerprint": residual_registry.get("registry_fingerprint"),
    }, notes=["seal_projection:deferred", "PRESENTATION_ONLY"])


def _panel_telemetry(telemetry_packet: dict | None) -> dict:
    if telemetry_packet is None or not isinstance(telemetry_packet, dict):
        return _panel(UNKNOWN, {
            "telemetry_fingerprint": None,
            "efficiency_summary": {},
        }, notes=["TELEMETRY_ABSENT"])
    from . import telemetry as telemetry_mod
    metrics = telemetry_mod.build_efficiency_metrics(telemetry_packet)
    summary = metrics.get("summary") or {}
    # Compact slice — fingerprints + a few counters only.
    slice_summary = {
        "telemetry_fingerprint": telemetry_packet.get("telemetry_fingerprint"),
        "truth_fingerprint": telemetry_packet.get("truth_fingerprint"),
        "residual_open": summary.get("residual_open"),
        "owned_count": summary.get("owned_count"),
        "unowned_count": summary.get("unowned_count"),
        "ambiguous_count": summary.get("ambiguous_count"),
        "event_count": summary.get("event_count"),
        "eligible_action_count": summary.get("eligible_action_count"),
        "steal_candidate_count": summary.get("steal_candidate_count"),
    }
    return _panel(OK, slice_summary, notes=["TELEMETRY_NE_AUTHORITY", "PRESENTATION_ONLY"])


def _panel_steal(steal_plan: dict | None, agent_status: str) -> dict:
    if steal_plan is None:
        if agent_status == "NONE":
            return _panel(OK, {
                "utilization": "PORTFOLIO",
                "candidate_present": False,
            }, notes=["PORTFOLIO_STEAL_NO_AGENT", "PRESENTATION_ONLY"])
        return _panel(UNKNOWN, {
            "utilization": None,
            "candidate_present": False,
        }, notes=["STEAL_PLAN_ABSENT"])
    cand = steal_plan.get("candidate")
    return _panel(OK, {
        "utilization": steal_plan.get("utilization"),
        "candidate_present": cand is not None,
        "owned_compatible_count": steal_plan.get("owned_compatible_count"),
        "ranking_fingerprint": steal_plan.get("ranking_fingerprint"),
    }, notes=["PRESENTATION_ONLY"], details={
        "candidate_pr": (cand or {}).get("pr") if cand else None,
    })


def _panel_dispatch_gates(snapshot: dict | None) -> dict:
    nodes = list((snapshot or {}).get("nodes") or [])
    if not nodes:
        return _panel(UNKNOWN, {
            "frozen_lane_count": 0,
            "waiting_ci": 0,
            "waiting_iv": 0,
        }, notes=["NO_SNAPSHOT_NODES"])
    frozen_n = sum(1 for n in nodes if n.get("frozen"))
    waiting_ci = waiting_iv = 0
    for node in nodes:
        for wait in node.get("waiting_on") or []:
            key = str(wait).upper()
            if key == "CI" or "CI" in key:
                waiting_ci += 1
            elif key == "IV" or "IV" in key:
                waiting_iv += 1
    notes: list[str] = []
    status = OK
    if frozen_n:
        notes.append("FROZEN_LANES_PRESENT")
        status = DEGRADED
    return _panel(status, {
        "frozen_lane_count": frozen_n,
        "waiting_ci": waiting_ci,
        "waiting_iv": waiting_iv,
        "node_count": len(nodes),
    }, notes=notes)


def _panel_evidence_health(
    evidence_records: list[dict] | None,
    evidence_store: Any | None,
) -> dict:
    records: list[dict] | None = evidence_records
    if records is None and evidence_store is not None:
        try:
            records = list(evidence_store.load())
        except Exception:
            return _panel(UNKNOWN, {"record_count": None},
                          notes=["EVIDENCE_STORE_UNREADABLE"])
    if records is None:
        return _panel(UNKNOWN, {"record_count": None},
                      notes=["EVIDENCE_STORE_ABSENT"])
    by_kind: Counter[str] = Counter(
        str(r.get("kind") or r.get("evidence_kind") or "UNKNOWN") for r in records
    )
    return _panel(OK, {
        "record_count": len(records),
        "by_kind": dict(sorted(by_kind.items())),
    })


def _panel_postmerge(seal_by_pr: dict[int, dict] | None) -> dict:
    if not seal_by_pr:
        return _panel(UNKNOWN, {
            "seal_plan_count": None,
            "not_ready_count": None,
        }, notes=["SEAL_SCAN_DEFERRED", "skipped_for_latency", "PRESENTATION_ONLY"])
    not_ready = 0
    for plan in seal_by_pr.values():
        if not isinstance(plan, dict):
            continue
        if plan.get("seal_state") == "NOT_READY":
            not_ready += 1
    return _panel(OK if seal_by_pr else UNKNOWN, {
        "seal_plan_count": len(seal_by_pr),
        "not_ready_count": not_ready,
    }, notes=["PRESENTATION_ONLY"])


def _panel_event_bus(
    events: list[dict] | None,
    invalid_events: list | None,
) -> dict:
    evs = list(events or [])
    invalid = list(invalid_events or [])
    by_type: Counter[str] = Counter(str(e.get("event") or "UNKNOWN") for e in evs)
    top = [
        {"event": name, "count": count}
        for name, count in sorted(by_type.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    ]
    notes: list[str] = []
    status = OK
    if invalid:
        status = DEGRADED
        notes.append(f"INVALID_EVENTS:{len(invalid)}")
    if not evs and not invalid:
        status = UNKNOWN
        notes.append("NO_EVENTS")
    return _panel(status, {
        "event_count": len(evs),
        "invalid_events": len(invalid),
        "by_type_top": top,
    }, notes=notes, details={"by_type": dict(sorted(by_type.items()))})


def _panel_system_honesty(
    honesty: dict,
    *,
    repository: str,
    verifier_pool_path: Path | str | None,
) -> dict:
    notes = [
        "CONTROL_VIEW_NE_AUTHORITY",
        "UI_NE_CANONICAL_TRUTH",
        "PRESENTATION_ONLY",
    ]
    unbound = False
    pool_source = "none"
    authenticated_count = 0
    declared_count = 0
    path = Path(verifier_pool_path) if verifier_pool_path is not None \
        else verifiers_mod.default_pool_path()
    if path.exists():
        resolved = verifiers_mod.resolve_pool(
            path=path, repo=repository, allow_issue_fallback=False)
        pool_source = resolved.source
        authenticated_count = len(resolved.bindings)
        declared_count = len(resolved.declared)
        # Any unbound/declared role with zero authenticated bindings => gated.
        if (
            (authenticated_count == 0 and (
                declared_count > 0 or resolved.present))
            or any(
                status == verifiers_mod.DECLARED_BUT_UNBOUND
                for status in (resolved.status_map or {}).values()
            )
        ):
            unbound = True
            notes.append("EXTERNAL_IV_GATED")
    else:
        notes.append("VERIFIER_POOL_ABSENT")
        unbound = True
        notes.append("EXTERNAL_IV_GATED")
    status = DEGRADED if unbound else OK
    return _panel(status, {
        "honesty": dict(honesty),
        "external_iv_gated": unbound,
        "authenticated_verifier_count": authenticated_count,
        "declared_verifier_count": declared_count,
        "pool_source": pool_source,
    }, notes=notes)


def build_global_control_view(
    *,
    repository: str,
    snapshot: dict | None = None,
    stacks: dict | None = None,
    events: list[dict] | None = None,
    invalid_events: list | None = None,
    matrix: dict | None = None,
    residual_registry: dict | None = None,
    steal_plan: dict | None = None,
    telemetry_packet: dict | None = None,
    seal_by_pr: dict[int, dict] | None = None,
    evidence_records: list[dict] | None = None,
    evidence_store: Any | None = None,
    agent_id: str | None = None,
    registry: agents_mod.RegistryResult | None = None,
    verifier_pool_path: Path | str | None = None,
    clock: Callable[[], str] = utcnow,
    seal_scan: str = "skipped_for_latency",
) -> dict:
    """Build ATLAS_GLOBAL_CONTROL_VIEW_V1 from live (or injected) DAG truth.

    Never mutates ``snapshot``. Never invents executable authority
    recommendations without PRESENTATION_ONLY labeling.
    """
    agent_status, _profile = _resolve_agent(agent_id, registry)
    matrix, residual_registry, steal_plan, telemetry_packet = _maybe_build_deps(
        snapshot=snapshot,
        stacks=stacks,
        events=events,
        matrix=matrix,
        residual_registry=residual_registry,
        steal_plan=steal_plan,
        telemetry_packet=telemetry_packet,
        agent_id=agent_id,
        registry=registry,
        repository=repository,
        clock=clock,
    )

    honesty = _honesty()
    panels = {
        "agents": _panel_agents(registry, agent_status, agent_id),
        "ownership": _panel_ownership(snapshot),
        "stacks": _panel_stacks(stacks),
        "frontier": _panel_frontier(matrix),
        "residuals": _panel_residuals(residual_registry),
        "telemetry": _panel_telemetry(telemetry_packet),
        "steal": _panel_steal(steal_plan, agent_status),
        "dispatch_gates": _panel_dispatch_gates(snapshot),
        "evidence_health": _panel_evidence_health(evidence_records, evidence_store),
        "postmerge": _panel_postmerge(seal_by_pr),
        "event_bus": _panel_event_bus(events, invalid_events),
        "system_honesty": _panel_system_honesty(
            honesty, repository=repository,
            verifier_pool_path=verifier_pool_path),
    }

    view_fp = _canonical_sha256({"panels": panels, "honesty": honesty})
    notes_prov = [
        f"seal_scan: {seal_scan}",
        "PRESENTATION_ONLY",
        "CONTROL_VIEW_NE_AUTHORITY",
    ]

    return {
        "schema": SCHEMA_CONST,
        "generated_at_utc": clock(),
        "repository": repository,
        "agent": agent_id,
        "agent_status": agent_status,
        "view_fingerprint": view_fp,
        "honesty": honesty,
        "panels": panels,
        "provenance": {
            "generator": "atlas-dag control-view (FEATURE_15)",
            **honesty,
            "seal_scan": seal_scan,
            "seal_projection": "deferred_or_skipped",
            "presentation_only": True,
            "notes": notes_prov,
            "truth_sources": [
                "ATLAS_DAG_SNAPSHOT_V1 (Features 1-5)",
                "FEATURE_03 stack topology",
                "FEATURE_04 event bus",
                "FEATURE_05 verifier pool (honesty only)",
                "FEATURE_11 steal plan (presentation)",
                "FEATURE_12 multidimensional frontier (presentation)",
                "FEATURE_13 residual registry (events+stacks; seals deferred)",
                "FEATURE_14 coordination telemetry (presentation)",
                "FEATURE_15 global control view (presentation only)",
            ],
        },
    }
