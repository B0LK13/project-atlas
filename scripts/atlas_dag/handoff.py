"""Automatic handoff packet generation (FEATURE_08, AUTOMATIC_HANDOFF_GENERATION).

A handoff packet is a PROJECTION of current DAG/repository/evidence truth —
never new authority. It is built exclusively by reusing the Features 1-7
resolvers (snapshot model, stack topology, verifier pool, dispatch planner,
evidence graph); this module adds no truth of its own.

Core rules:

- UNKNOWN preservation: any field whose truth cannot be resolved stays
  literal "UNKNOWN" (or null per field contract) with an explicit entry in
  the packet-level `uncertainty` list. UNKNOWN is never converted into
  PASS/FAIL by inference.
- TOCTOU guard: the candidate HEAD is re-resolved from live repository truth
  after the packet is built; any move => HandoffStale
  (HANDOFF_STALE_DURING_BUILD) and NO packet is emitted.
- Determinism: `truth_fingerprint` is a sha256 over the canonical JSON of
  the material identity/state fields only (generated_at_utc, handoff_id and
  the mode-specific `presentation` block are excluded), so equivalent
  snapshots yield identical fingerprints and identical handoff_ids.
- One canonical packet: mode (general / verifier / resume) only adds a
  `presentation` emphasis block; material fields are identical across modes.
- A prospective merge SHA never appears as a merge receipt: an open PR has
  merge_receipt.receipt = null with reason "PR_OPEN"; a MERGED lane keeps
  receipt null (schema) with reason "PR_MERGED" and projects actual merge
  identity only via the FEATURE_09 `post_merge` seal-plan summary.
- Post-merge seal state (FEATURE_09) is a `post_merge` summary projected from
  seal_plan.build_seal_plan on the same client — never a second truth model,
  never seal execution.
- CI state is exact-head only (model.ci_status_for_head semantics):
  predecessor-head runs can never surface as current CI.
- Invalidated / stale-proof evidence never appears in the reusable list;
  the evidence section exposes all five FEATURE_07 states per artifact.

Generation only: this module never posts, emails, or otherwise delivers.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import agents as agents_mod
from . import control_view as control_view_mod
from . import dispatch as dispatch_mod
from . import events as events_mod
from . import evidence as evidence_mod
from . import evidence_graph as evidence_graph_mod
from . import frontier_matrix as frontier_matrix_mod
from . import model as model_mod
from . import residuals as residuals_mod
from . import score as score_mod
from . import seal_plan as seal_plan_mod
from . import stack as stack_mod
from . import steal as steal_mod
from . import telemetry as telemetry_mod
from . import verifiers as verifiers_mod

SCHEMA_CONST = "ATLAS_HANDOFF_V1"
HANDOFF_SCHEMA = "atlas_handoff_v1.schema.json"

# Handoff modes (controlled vocabulary). Mode only shapes `presentation`.
MODES = ("general", "verifier", "resume")

# All five FEATURE_07 graph states, always present in the evidence summary.
GRAPH_STATES = (
    evidence_graph_mod.EXACT_CURRENT,
    evidence_graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE,
    evidence_graph_mod.PREDECESSOR_ONLY,
    evidence_graph_mod.INVALIDATED,
    evidence_graph_mod.UNKNOWN,
)

# Gate reasons that encode a validation requirement for a verifier audience.
_VALIDATION_PREFIXES = (
    "EXACT_HEAD_CI",
    "FORMAL_IV",
    "CLAIM_INTEGRITY",
    "MERGEABILITY",
    "P0_OPEN",
    "P1_OPEN",
)


class HandoffError(RuntimeError):
    """Fail-closed: the packet cannot be built truthfully."""


class HandoffStale(HandoffError):
    """HANDOFF_STALE_DURING_BUILD: live HEAD moved during packet build."""


class HandoffUnavailable(HandoffError):
    """The requested lane has no resolvable truth (e.g. UNKNOWN_PR)."""


def utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_packet(packet: dict) -> list[str]:
    """Schema-validation error summaries for one packet ([] = valid)."""
    validator = events_mod.validator_for(HANDOFF_SCHEMA)
    return sorted(
        f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
        for e in validator.iter_errors(packet)
    )


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _closed_pr(client: Any, pr: int) -> dict | None:
    """Merged/closed PR view when the open frontier no longer carries the lane."""
    closed_fn = getattr(client, "closed_pr", None)
    if not callable(closed_fn):
        return None
    try:
        data = closed_fn(pr)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _live_pr(client: Any, pr: int) -> dict | None:
    """Live PR identity for TOCTOU: open frontier first, else closed/merged view.

    Merged lanes leave the open frontier; FEATURE_09 handoff must still
    re-resolve headRefOid from repository truth, never invent stability."""
    open_hit = next((p for p in client.open_prs() if p.get("number") == pr), None)
    if open_hit is not None:
        return open_hit
    return _closed_pr(client, pr)


def _merged_frontier_node(pr_data: dict, client: Any) -> dict:
    """Sparse honest node for a MERGED PR absent from the open frontier.

    Open-frontier fields (CI / formal IV / mergeability / ownership gates) are
    not inventable after merge — they stay UNKNOWN. Material post-merge truth
    is projected only via the canonical seal planner (`post_merge`)."""
    number = int(pr_data["number"])
    head = pr_data.get("headRefOid")
    tree = None
    if isinstance(head, str) and head:
        try:
            commit = client.commit(head)
        except Exception:
            commit = None
        if isinstance(commit, dict):
            tree = commit.get("tree")
    return {
        "pr": number,
        "lane": f"pr/{number}",
        "head": head,
        "tree": tree,
        "base": pr_data.get("baseRefName"),
        "head_branch": pr_data.get("headRefName"),
        "owner": None,
        "ownership": "UNKNOWN",
        "claimants": [],
        "frozen": False,
        "ci_status": "UNKNOWN",
        "ci_run_id": None,
        "formal_iv": None,
        "claim_integrity": "UNKNOWN",
        "mergeable": "UNKNOWN",
        "gate": {
            "merge_gate": "MERGED",
            "reasons": ["PR_NOT_IN_OPEN_FRONTIER"],
        },
        "blockers": [],
        "next_actions": [],
        "dispatch": None,
    }


def _base_head(client: Any, base_branch: str | None) -> str | None:
    if not base_branch:
        return None
    try:
        base = client.branch_head(base_branch)
    except Exception:
        return None
    return base.get("sha") if base else None


def _receipt_verifier(client: Any, receipt_id: str) -> str | None:
    """Verifier id behind an eligible receipt id, from the #719 stream."""
    issue = client.dag_issue()
    if not issue:
        return None
    ingested = events_mod.ingest_comments(client.issue_comments(issue["number"]))
    for receipt in ingested.receipts:
        if receipt.get("receipt_id") == receipt_id:
            return receipt.get("verifier_id")
    return None


def _evidence_section(client: Any, pr: int, head: str | None, tree: str | None,
                      record: dict | None,
                      store: evidence_mod.EvidenceStore | None) -> dict:
    """All five FEATURE_07 states, per-artifact reasons, and a reusable list
    that can never contain invalidated / stale-proof artifacts."""
    states: dict[str, list[str]] = {state: [] for state in GRAPH_STATES}
    artifacts: list[dict] = []
    uncertainty: list[str] = []
    if store is not None:
        records = store.for_pr(pr)
        parent_head = record.get("parent_head") if record else None
        context = {
            "pr": pr,
            "current_head": head,
            "current_tree": tree,
            "current_parent_head": parent_head,
            "current_main_head": _safe_main_head(client),
            "changed_files": None,  # live diff truth stays unresolved here
            "current_platform": None,
            "current_test_set": None,
            "current_toolchain": None,
            "current_verifier_principal": None,
            "current_verifier_session": None,
            "equivalence_proofs": [],
        }
        graph = evidence_graph_mod.build_graph(records, context)
        for node in graph["nodes"]:
            states.setdefault(node["state"], []).append(node["evidence_id"])
            artifacts.append({
                "evidence_id": node["evidence_id"],
                "evidence_class": node["evidence_class"],
                "state": node["state"],
                "reasons": node["reasons"],
                "reuse_proof": node["reuse_proof"],
                "uncertainty": node["uncertainty"],
            })
        for state in states:
            states[state] = sorted(states[state])
        uncertainty.extend(graph["uncertainty"])
    reusable = sorted(
        states[evidence_graph_mod.EXACT_CURRENT]
        + states[evidence_graph_mod.REUSABLE_BY_PROVEN_EQUIVALENCE]
    )
    return {"states": states, "artifacts": artifacts, "reusable": reusable,
            "uncertainty": sorted(set(uncertainty))}


def _safe_main_head(client: Any) -> str | None:
    try:
        main_branch = client.default_branch()
        main = client.branch_head(main_branch) if main_branch else None
    except Exception:
        return None
    return main.get("sha") if main else None


def _post_merge_summary(client: Any, pr: int, clock: Callable[[], str],
                        evidence_store: evidence_mod.EvidenceStore | None = None) -> dict:
    """FEATURE_09 seal-plan state summary (never a duplicated truth model).

    Built by reusing seal_plan.build_seal_plan on the same client; any
    failure degrades to an explicit UNKNOWN marker — post-merge truth is
    never invented inside a handoff packet."""
    try:
        plan = seal_plan_mod.build_seal_plan(
            pr, client, clock=clock, evidence_store=evidence_store)
    except Exception:
        return {"state": "UNKNOWN", "seal_state": "UNKNOWN",
                "reason": "POST_MERGE_TRUTH_UNRESOLVABLE"}
    return {
        "state": plan["state"],
        "seal_state": plan["seal_state"],
        "plan_id": plan["plan_id"],
        "merged": {
            "is_merged": plan["merged"]["is_merged"],
            "method": plan["merged"]["method"],
            "merge_commit": plan["merged"]["merge_commit"],
            "verified": plan["merged"]["verified"],
        },
    }


def _pool_prohibitions(pool_path: Path) -> list[str]:
    """Sorted union of declared verifier prohibitions (the honest boundary of
    what a verifier must not do, from the pool file itself — never invented).
    An unavailable/invalid pool yields no prohibitions, never invented ones."""
    loaded = verifiers_mod.load_pool(pool_path)
    if not loaded.valid or loaded.pool is None:
        return []
    prohibitions: set[str] = set()
    for entry in loaded.pool.get("verifiers", []):
        prohibitions.update(str(p) for p in entry.get("prohibitions", []))
    return sorted(prohibitions)


def _presentation(mode: str, node: dict, stack_record: dict | None,
                  evidence_section: dict, gate_reasons: list[str],
                  prohibitions: list[str],
                  priority: dict | None = None,
                  steal_info: dict | None = None,
                  matrix_info: dict | None = None,
                  residual_info: dict | None = None,
                  telemetry_info: dict | None = None,
                  control_view_info: dict | None = None,
                  e2e_hardening_info: dict | None = None) -> dict:
    """Mode-specific emphasis block. Presentation ONLY: every value here is
    derived from material truth already in the packet, never contradictory
    with it, and always excluded from the truth fingerprint."""
    if mode == "verifier":
        outstanding = sorted(
            artifact["evidence_id"]
            for artifact in evidence_section["artifacts"]
            if artifact["state"] in (evidence_graph_mod.PREDECESSOR_ONLY,
                                     evidence_graph_mod.INVALIDATED)
        )
        return {
            "audience": "verifier",
            "changed_scope_summary": outstanding,
            "outstanding_claims": sorted(gate_reasons),
            "validation_requirements": sorted(
                reason for reason in gate_reasons
                if reason.startswith(_VALIDATION_PREFIXES)
            ),
            "prohibited_verifier_actions": prohibitions,
        }
    if mode == "resume":
        next_actions = list(node.get("next_actions") or [])
        out = {
            "audience": "resuming-agent",
            "next_safe_action": next_actions[0] if next_actions else "UNKNOWN",
            "topology": {
                "lane": node.get("lane"),
                "stack_state": (stack_record or {}).get("stack_state"),
                "depth": (stack_record or {}).get("depth"),
                "parent_pr": (stack_record or {}).get("parent_pr"),
            },
            "invalidated_evidence": sorted(
                evidence_section["states"][evidence_graph_mod.INVALIDATED]),
            "reusable_evidence": list(evidence_section["reusable"]),
        }
        if priority is not None:
            # Ranked authorized actions only — scoring never grants write.
            out["ranked_next_safe_actions"] = priority
        if steal_info is not None:
            out["steal_candidate"] = steal_info
        if matrix_info is not None:
            out["multidim_frontier"] = matrix_info
        if residual_info is not None:
            out["residuals"] = residual_info
        if telemetry_info is not None:
            out["coordination_telemetry"] = telemetry_info
        if control_view_info is not None:
            out["control_view"] = control_view_info
        if e2e_hardening_info is not None:
            out["e2e_hardening_status"] = e2e_hardening_info
        return out
    return {"audience": "general"}


def _resume_e2e_hardening(mode: str) -> dict | None:
    """FEATURE_16 e2e hardening status for resume presentation only.

    Fixture suite is deterministic and side-effect free; presentation never
    grants authority from the packet.
    """
    if mode != "resume":
        return None
    try:
        from . import e2e_harden as e2e_harden_mod
        packet = e2e_harden_mod.run_e2e_hardening(live=False)
        return e2e_harden_mod.e2e_hardening_status(packet)
    except Exception:
        return {
            "overall_status": "UNKNOWN",
            "failed_scenario_ids": [],
            "reason": "E2E_HARDENING_UNRESOLVABLE",
            "e2e_ne_authority": True,
        }


def _resume_control_view(mode: str, snapshot: dict, stacks: dict,
                         registry: Any, agent_id: str | None,
                         client: Any, clock: Callable[[], str],
                         verifier_pool: str | Path | None = None) -> dict | None:
    """FEATURE_15 global control-view summary for resume presentation."""
    if mode != "resume":
        return None
    try:
        if registry is None:
            registry = agents_mod.load_registry()
        elif not hasattr(registry, "status"):
            registry = agents_mod.load_registry(registry)
        issue = client.dag_issue() if client is not None else None
        events: list[dict] = []
        if issue is not None:
            events = events_mod.ingest_comments(
                client.issue_comments(issue["number"])).events
        residual_registry = residuals_mod.build_residual_registry(
            repository=getattr(client, "repo", "UNKNOWN"),
            events=events, snapshot=snapshot, stacks=stacks,
            seal_by_pr=None, agent_id=agent_id, registry=registry,
            clock=clock)
        matrix = None
        steal_plan = None
        if agent_id is not None:
            weights, source = score_mod.load_weights()
            matrix = frontier_matrix_mod.build_frontier_matrix(
                snapshot, agent_id=agent_id, registry=registry, stacks=stacks,
                weights=weights, weights_source=source,
                residual_registry=residual_registry, events=events,
                seal_by_pr=None, clock=clock)
            steal_plan = steal_mod.plan_steal(
                snapshot, agent_id, registry, stacks=stacks,
                weights=weights, weights_source=source, clock=clock)
        packet = control_view_mod.build_global_control_view(
            repository=getattr(client, "repo", "UNKNOWN"),
            snapshot=snapshot, stacks=stacks, events=events,
            matrix=matrix, residual_registry=residual_registry,
            steal_plan=steal_plan, agent_id=agent_id, registry=registry,
            verifier_pool_path=verifier_pool, clock=clock,
            seal_scan="skipped_for_latency")
        panels = packet.get("panels") or {}
        return {
            "view_fingerprint": packet.get("view_fingerprint"),
            "agent_status": packet.get("agent_status"),
            "panel_status": {
                name: (panels.get(name) or {}).get("status")
                for name in control_view_mod.PANEL_KEYS
            },
            "honesty": packet.get("honesty"),
            "seal_scan": (packet.get("provenance") or {}).get("seal_scan"),
        }
    except Exception:
        return {"view_fingerprint": None, "reason": "CONTROL_VIEW_UNRESOLVABLE"}


def _resume_telemetry(mode: str, snapshot: dict, stacks: dict,
                      registry: Any, agent_id: str | None,
                      client: Any, clock: Callable[[], str]) -> dict | None:
    """FEATURE_14 coordination telemetry summary for resume presentation."""
    if mode != "resume":
        return None
    try:
        if registry is None:
            registry = agents_mod.load_registry()
        elif not hasattr(registry, "status"):
            registry = agents_mod.load_registry(registry)
        issue = client.dag_issue() if client is not None else None
        events: list[dict] = []
        if issue is not None:
            events = events_mod.ingest_comments(
                client.issue_comments(issue["number"])).events
        # Speed path: events+stacks only — no full seal scan.
        residual_registry = residuals_mod.build_residual_registry(
            repository=getattr(client, "repo", "UNKNOWN"),
            events=events, snapshot=snapshot, stacks=stacks,
            seal_by_pr=None, agent_id=agent_id, registry=registry,
            clock=clock)
        matrix = None
        steal_plan = None
        if agent_id is not None:
            weights, source = score_mod.load_weights()
            matrix = frontier_matrix_mod.build_frontier_matrix(
                snapshot, agent_id=agent_id, registry=registry, stacks=stacks,
                weights=weights, weights_source=source,
                residual_registry=residual_registry, events=events,
                seal_by_pr=None, clock=clock)
            steal_plan = steal_mod.plan_steal(
                snapshot, agent_id, registry, stacks=stacks,
                weights=weights, weights_source=source, clock=clock)
        packet = telemetry_mod.build_coordination_telemetry(
            repository=getattr(client, "repo", "UNKNOWN"),
            snapshot=snapshot, stacks=stacks, events=events,
            matrix=matrix, residual_registry=residual_registry,
            steal_plan=steal_plan, agent_id=agent_id, registry=registry,
            clock=clock, seal_projection="deferred_or_skipped")
        cats = packet.get("categories") or {}
        return {
            "telemetry_fingerprint": packet.get("telemetry_fingerprint"),
            "agent_status": packet.get("agent_status"),
            "category_status": {
                name: (cats.get(name) or {}).get("status")
                for name in sorted(cats)
            },
            "summary_slice": {
                "residual_open": ((cats.get("residual_backlog") or {})
                                  .get("metrics") or {}).get("open_count"),
                "utilization": ((cats.get("utilization") or {})
                                .get("metrics") or {}).get("utilization"),
                "ambiguous_count": ((cats.get("ownership_contention") or {})
                                    .get("metrics") or {}).get("ambiguous_count"),
                "event_count": ((cats.get("event_bus_health") or {})
                                .get("metrics") or {}).get("event_count"),
            },
            "honesty": packet.get("honesty"),
            "seal_projection": (packet.get("provenance") or {}).get(
                "seal_projection"),
        }
    except Exception:
        return {"telemetry_fingerprint": None, "reason": "TELEMETRY_UNRESOLVABLE"}


def _resume_residuals(mode: str, snapshot: dict, stacks: dict,
                      registry: Any, agent_id: str | None,
                      client: Any, clock: Callable[[], str]) -> dict | None:
    """FEATURE_13 residual summary for resume presentation."""
    if mode != "resume":
        return None
    try:
        if registry is None:
            registry = agents_mod.load_registry()
        elif not hasattr(registry, "status"):
            registry = agents_mod.load_registry(registry)
        issue = client.dag_issue() if client is not None else None
        events = []
        if issue is not None:
            from . import events as events_mod
            events = events_mod.ingest_comments(
                client.issue_comments(issue["number"])).events
        seal_by_pr: dict[int, dict] = {}
        for node in sorted(snapshot.get("nodes") or [],
                           key=lambda n: int(n["pr"])):
            pr = int(node["pr"])
            try:
                if clock is None:
                    seal_by_pr[pr] = seal_plan_mod.build_seal_plan(pr, client)
                else:
                    seal_by_pr[pr] = seal_plan_mod.build_seal_plan(
                        pr, client, clock=clock)
            except Exception:
                continue
        packet = residuals_mod.build_residual_registry(
            repository=getattr(client, "repo", "UNKNOWN"),
            events=events, snapshot=snapshot, stacks=stacks,
            seal_by_pr=seal_by_pr, agent_id=agent_id, registry=registry,
            clock=clock)
        open_rows = [r for r in packet["residuals"] if r["disposition"] == "OPEN"]
        runnable = [r for r in open_rows
                    if r["derived_execution_state"] == residuals_mod.RUNNABLE]
        blocked = [r for r in open_rows
                   if r["derived_execution_state"] == residuals_mod.BLOCKED]
        # Highest priority unresolved: sort by severity then id.
        sev_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        top = sorted(
            open_rows,
            key=lambda r: (sev_rank.get(str(r.get("severity")), 9),
                           r["residual_id"]))[:10]
        return {
            "open_count": packet["open_count"],
            "runnable_count": len(runnable),
            "blocked_count": len(blocked),
            "highest_priority": [
                {"residual_id": r["residual_id"], "severity": r.get("severity"),
                 "type": r["residual_type"],
                 "derived": r["derived_execution_state"]}
                for r in top
            ],
            "blocked_gates": sorted({
                reason for r in blocked
                for reason in (r.get("blocking_reasons") or [])
            })[:20],
            "registry_fingerprint": packet["registry_fingerprint"],
        }
    except Exception:
        return {"open_count": None, "reason": "RESIDUAL_REGISTRY_UNRESOLVABLE"}


def _resume_matrix(mode: str, snapshot: dict, stacks: dict,
                   registry: Any, agent_id: str | None,
                   clock: Callable[[], str]) -> dict | None:
    """FEATURE_12 top actions / parallel set for resume presentation."""
    if mode != "resume" or agent_id is None:
        return None
    try:
        if registry is None:
            registry = agents_mod.load_registry()
        elif not hasattr(registry, "status"):
            registry = agents_mod.load_registry(registry)
        weights, source = score_mod.load_weights()
        packet = frontier_matrix_mod.build_frontier_matrix(
            snapshot, agent_id=agent_id, registry=registry, stacks=stacks,
            weights=weights, weights_source=source, clock=clock)
        rankings = packet.get("typed_rankings") or {}
        return {
            "frontier_fingerprint": packet.get("frontier_fingerprint"),
            "top_actions_by_class": {
                k: v[:5] for k, v in rankings.items() if k.startswith("best_")
            },
            "parallel_runnable_set": packet.get("parallel_runnable_set") or [],
            "blocked_human_verifier_platform": [
                a["action_id"] for a in packet.get("actions") or []
                if a["runnable_state"] == frontier_matrix_mod.BLOCKED
                and (
                    a["action_class"] == frontier_matrix_mod.CLASS_HUMAN_GATE
                    or a["action_type"] == frontier_matrix_mod.IV_REQUEST
                    or any(r.startswith("PLATFORM_")
                           for r in (a.get("blocking_reasons") or []))
                )
            ][:20],
        }
    except Exception:
        return {"frontier_fingerprint": None, "reason": "MATRIX_UNRESOLVABLE"}


def _resume_steal(mode: str, snapshot: dict, stacks: dict,
                  registry: Any, agent_id: str | None,
                  clock: Callable[[], str]) -> dict | None:
    """FEATURE_11 utilization / steal candidate for resume presentation."""
    if mode != "resume" or agent_id is None:
        return None
    try:
        if registry is None:
            registry = agents_mod.load_registry()
        elif not hasattr(registry, "status"):
            registry = agents_mod.load_registry(registry)
        weights, source = score_mod.load_weights()
        plan = steal_mod.plan_steal(
            snapshot, agent_id, registry, stacks=stacks,
            weights=weights, weights_source=source, clock=clock)
        cand = plan.get("candidate")
        return {
            "utilization": plan["utilization"],
            "candidate": (
                {"pr": cand["pr"], "lane": cand["lane"], "total": cand["total"]}
                if cand else None
            ),
            "ranking_fingerprint": plan.get("ranking_fingerprint"),
        }
    except Exception:
        return {"utilization": steal_mod.NO_SAFE_STEAL,
                "candidate": None, "reason": "STEAL_PLAN_UNRESOLVABLE"}


def _resume_priority(mode: str, snapshot: dict, stacks: dict,
                     registry: Any, agent_id: str | None,
                     clock: Callable[[], str]) -> dict | None:
    """FEATURE_10 ranked view derived from FEATURE_12 matrix (presentation)."""
    if mode != "resume" or agent_id is None:
        return None
    try:
        if registry is None:
            registry = agents_mod.load_registry()
        elif not hasattr(registry, "status"):
            registry = agents_mod.load_registry(registry)
        weights, source = score_mod.load_weights()
        matrix = frontier_matrix_mod.build_frontier_matrix(
            snapshot, agent_id=agent_id, registry=registry, stacks=stacks,
            weights=weights, weights_source=source, clock=clock)
        packet = frontier_matrix_mod.score_compat_projection(matrix, snapshot)
        return {
            "ranking_fingerprint": packet["ranking_fingerprint"],
            "weights_id": packet["weights_id"],
            "weights_version": packet["weights_version"],
            "ranked": [
                {"lane": e["lane"], "action_class": e["action_class"],
                 "total": e["total"], "pr": e["pr"]}
                for e in packet["ranked"][:10]
            ],
            "derived_from": frontier_matrix_mod.SCHEMA_CONST,
        }
    except Exception:
        return {"ranking_fingerprint": None, "ranked": [],
                "reason": "PRIORITY_UNRESOLVABLE"}


def build_handoff(
    pr_number: int,
    mode: str,
    client: Any,
    *,
    evidence_store: evidence_mod.EvidenceStore | None = None,
    registry: Any = None,
    agent_id: str | None = None,
    verifier_pool: str | Path | None = None,
    clock: Callable[[], str] = utcnow,
) -> dict:
    """Build one ATLAS_HANDOFF_V1 packet from live Features 1-7 truth.

    Raises HandoffUnavailable when the lane is not truthfully resolvable and
    HandoffStale (HANDOFF_STALE_DURING_BUILD) when the candidate HEAD moves
    between the initial resolution and the final TOCTOU re-resolution; in
    both cases NO packet is emitted. `registry`/`agent_id` optionally enrich
    resume presentation with FEATURE_10 ranked authorized actions; they never
    grant write authority inside the handoff.
    """
    if mode not in MODES:
        raise HandoffError(f"UNKNOWN_MODE:{mode}")

    pool_path = Path(verifier_pool) if verifier_pool is not None \
        else verifiers_mod.default_pool_path()
    snapshot = model_mod.build_snapshot(client, pool_path=pool_path)
    node = next((n for n in snapshot["nodes"] if n["pr"] == pr_number), None)
    merged_lane = False
    if node is None:
        # FEATURE_09: a genuinely MERGED lane leaves the open frontier. Resolve
        # via closed_pr and project a sparse node; never invent open-frontier
        # CI/IV/ownership. Non-merged absence remains UNKNOWN_PR.
        closed = _closed_pr(client, pr_number)
        if closed and str(closed.get("state") or "").upper() == "MERGED":
            node = _merged_frontier_node(closed, client)
            merged_lane = True
            if not snapshot.get("main_head"):
                try:
                    main_branch = (
                        snapshot.get("main_branch")
                        or client.default_branch()
                        or "main"
                    )
                except Exception:
                    main_branch = snapshot.get("main_branch") or "main"
                snapshot = {
                    **snapshot,
                    "main_head": _safe_main_head(client),
                    "main_branch": main_branch,
                }
        else:
            raise HandoffUnavailable(f"UNKNOWN_PR:{pr_number}")
    head = node.get("head")
    if not head:
        raise HandoffUnavailable(f"PR_HEAD_UNRESOLVED:{pr_number}")

    stacks = stack_mod.build_stacks(
        snapshot["nodes"], client, snapshot.get("main_branch") or "main")
    stack_record = stacks.get(node["lane"]) or None

    issue = None
    try:
        issue = client.dag_issue()
    except Exception:
        issue = None
    issue_body = None
    if issue is not None:
        try:
            issue_body = client.issue_body(issue["number"])
        except Exception:
            issue_body = None
    pool = verifiers_mod.resolve_pool(
        issue_body, path=pool_path, repo=client.repo)

    gate = node["gate"]
    gate_reasons = list(gate.get("reasons") or [])

    # Formal IV: satisfied only by the snapshot's eligible receipt; the
    # verifier binding comes from the authenticated pool, never inferred.
    # Merged sparse nodes carry no inventable formal_iv.
    receipt_id = node.get("formal_iv")
    verifier_id: str | None = None
    verifier_binding: str | None = None
    if receipt_id:
        verifier_id = _receipt_verifier(client, receipt_id)
        if verifier_id is not None:
            verifier_binding = pool.bindings.get(verifier_id)

    base_branch = node.get("base")
    base_head = _base_head(client, base_branch)
    main_head = snapshot.get("main_head")

    ci = {"status": node["ci_status"], "run_id": node["ci_run_id"], "head": head}
    formal_iv = {
        "state": "SATISFIED" if receipt_id else "MISSING",
        "receipt_id": receipt_id,
        "verifier_id": verifier_id,
        "verifier_binding": verifier_binding,
    }
    mergeable = node.get("mergeable") or "UNKNOWN"
    merge_guardian = {"merge_gate": gate["merge_gate"], "reasons": gate_reasons}
    # A prospective merge SHA is never a merge receipt. Open PRs stay PR_OPEN;
    # merged lanes keep receipt=null (schema) and point at post_merge truth.
    merge_receipt = (
        {"receipt": None, "reason": "PR_MERGED"} if merged_lane
        else {"receipt": None, "reason": "PR_OPEN"}
    )

    dispatch_plan: dict | None
    if node.get("frozen"):
        dispatch_plan = dispatch_mod.plan_dispatch(
            node, client, None, None, pool, evidence_store=evidence_store)
    else:
        dispatch_plan = node.get("dispatch")

    evidence_section = _evidence_section(
        client, pr_number, head, node.get("tree"), stack_record, evidence_store)

    # Gates: verbatim truth states, never an inferred PASS/FAIL conversion.
    if pool.pool_invalid:
        verifier_gate = "VERIFIER_POOL_INVALID"
    elif receipt_id:
        verifier_gate = "SATISFIED"
    elif pool.present and not pool.bindings:
        verifier_gate = "VERIFIER_IDENTITY_UNBOUND"
    else:
        verifier_gate = "MISSING"
    gates = {
        "owner": node["ownership"],
        "verifier": verifier_gate,
        "platform": str(mergeable),
        "policy": gate["merge_gate"],
    }

    blockers = list(node.get("blockers") or [])
    next_actions = list(node.get("next_actions") or [])

    stack_out: dict[str, Any] = {
        "root": None, "parent_pr": None, "parent_head": None,
        "depth": None, "stack_state": stack_mod.PARENT_MISSING,
        "restack_required": False, "target_branch": base_branch,
    }
    if stack_record is not None:
        stack_out.update({
            "root": stack_record.get("stack_root"),
            "parent_pr": stack_record.get("parent_pr"),
            "parent_head": stack_record.get("parent_head"),
            "depth": stack_record.get("depth"),
            "stack_state": stack_record.get("stack_state"),
            "restack_required": bool(stack_record.get("restack_required")),
            "target_branch": stack_record.get("target_branch"),
        })

    # UNKNOWN preservation: explicit uncertainty for everything unresolved.
    uncertainty: set[str] = set(evidence_section["uncertainty"])
    if not node.get("tree"):
        uncertainty.add("TREE_UNKNOWN")
    if not base_head:
        uncertainty.add("BASE_HEAD_UNKNOWN")
    if not main_head:
        uncertainty.add("MAIN_HEAD_UNKNOWN")
    if node.get("owner") is None:
        uncertainty.add("OWNER_UNKNOWN")
    if receipt_id and verifier_binding is None:
        uncertainty.add("VERIFIER_BINDING_UNKNOWN")
    if mergeable == "UNKNOWN":
        uncertainty.add("MERGEABILITY_UNKNOWN")

    # FEATURE_09: post-merge seal-plan state summary (projection only; built
    # by reusing seal_plan truth, never a second truth model). For an open
    # PR this is the honest NOT_MERGED marker.
    post_merge = _post_merge_summary(client, pr_number, clock, evidence_store)

    material = {
        "pr": pr_number,
        "head": head,
        "tree": node.get("tree"),
        "base_branch": base_branch,
        "base_head": base_head,
        "main_head": main_head,
        "stack": stack_out,
        "owner": node.get("owner"),
        "ownership": node["ownership"],
        "claimants": sorted(node.get("claimants") or []),
        "frozen": bool(node.get("frozen")),
        "ci": ci,
        "formal_iv": formal_iv,
        "claim_integrity": node.get("claim_integrity"),
        "mergeable": mergeable,
        "merge_guardian": merge_guardian,
        "merge_receipt": merge_receipt,
        "blockers": blockers,
        "dispatch": dispatch_plan,
        "evidence": evidence_section,
        "next_actions": next_actions,
        "gates": gates,
        "post_merge": post_merge,
    }
    fingerprint = _canonical_sha256(material)
    handoff_id = "handoff-" + hashlib.sha256(
        f"{fingerprint}|{pr_number}|{mode}".encode()).hexdigest()[:16]

    packet = {
        "schema": SCHEMA_CONST,
        "handoff_id": handoff_id,
        "generated_at_utc": clock(),
        "mode": mode,
        "repo": client.repo or model_mod.UNKNOWN,
        "pr": pr_number,
        "head": head,
        "tree": node.get("tree"),
        "truth_fingerprint": fingerprint,
        "base_branch": base_branch,
        "base_head": base_head,
        "main_head": main_head,
        "stack": stack_out,
        "owner": node.get("owner"),
        "ownership": node["ownership"],
        "claimants": sorted(node.get("claimants") or []),
        "frozen": bool(node.get("frozen")),
        "ci": ci,
        "formal_iv": formal_iv,
        "claim_integrity": node.get("claim_integrity"),
        "mergeable": mergeable,
        "merge_guardian": merge_guardian,
        "merge_receipt": merge_receipt,
        "blockers": blockers,
        "dispatch": dispatch_plan,
        "evidence": evidence_section,
        "next_actions": next_actions,
        "gates": gates,
        "post_merge": post_merge,
        "uncertainty": sorted(uncertainty),
        "provenance": {
            "generator": "atlas-dag handoff (FEATURE_08)",
            "projection_only": True,
            "grants_no_authority": True,
            "truth_sources": [
                "ATLAS_DAG_SNAPSHOT_V1 (Features 1-5)",
                "FEATURE_03 stack topology",
                "FEATURE_06 dispatch plan",
                "FEATURE_07 evidence graph",
                "FEATURE_09 post-merge seal plan",
                "FEATURE_10 frontier prioritization (presentation only)",
                "FEATURE_11 safe work stealing (presentation only)",
                "FEATURE_12 multidimensional frontier (presentation only)",
                "FEATURE_13 residual registry (presentation only)",
                "FEATURE_14 coordination telemetry (presentation only)",
                "FEATURE_15 global control view (presentation only)",
                "FEATURE_16 e2e hardening status (presentation only)",
            ],
        },
        "presentation": _presentation(
            mode, node, stack_record, evidence_section, gate_reasons,
            _pool_prohibitions(pool_path),
            priority=_resume_priority(
                mode, snapshot, stacks, registry, agent_id, clock),
            steal_info=_resume_steal(
                mode, snapshot, stacks, registry, agent_id, clock),
            matrix_info=_resume_matrix(
                mode, snapshot, stacks, registry, agent_id, clock),
            residual_info=_resume_residuals(
                mode, snapshot, stacks, registry, agent_id, client, clock),
            telemetry_info=_resume_telemetry(
                mode, snapshot, stacks, registry, agent_id, client, clock),
            control_view_info=_resume_control_view(
                mode, snapshot, stacks, registry, agent_id, client, clock,
                verifier_pool=pool_path),
            e2e_hardening_info=_resume_e2e_hardening(mode)),
    }

    # TOCTOU guard: re-resolve the candidate HEAD from live truth before any
    # packet is emitted. A move => stale, fail closed, no packet.
    live = _live_pr(client, pr_number)
    live_head = live.get("headRefOid") if live else None
    if live_head != head:
        raise HandoffStale(
            f"HANDOFF_STALE_DURING_BUILD:pr={pr_number}:"
            f"built={head}:live={live_head or 'UNKNOWN'}")
    return packet
