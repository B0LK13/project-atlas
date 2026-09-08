"""atlas-dag command-line interface (D-006). Read-only coordinator; no merge mutation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import agents as agents_mod
from . import dispatch as dispatch_mod
from . import emitter as emitter_mod
from . import events as events_mod
from . import evidence as evidence_mod
from . import evidence_graph as evidence_graph_mod
from . import frontier_matrix as frontier_matrix_mod
from . import handoff as handoff_mod
from . import receipts as receipts_mod
from . import residuals as residuals_mod
from . import router as router_mod
from . import score as score_mod
from . import seal_plan as seal_plan_mod
from . import stack as stack_mod
from . import steal as steal_mod
from . import verifiers as verifiers_mod
from .gh import GhClient
from .model import build_snapshot, ownership

RUNTIME_DIR = ".atlas-runtime"


def _client(args) -> GhClient:
    return GhClient(repo=args.repo)


def _runtime_path(args) -> Path:
    return Path(args.runtime_dir) / "dag.json"


def _evidence_store(args) -> evidence_mod.EvidenceStore:
    return evidence_mod.EvidenceStore(Path(args.runtime_dir) / "evidence" / "evidence.json")


def cmd_snapshot(args) -> int:
    client = _client(args)
    snapshot = build_snapshot(client)
    registry = agents_mod.load_registry(args.registry)
    snapshot["agent_registry"] = {
        "schema": agents_mod.REGISTRY_SCHEMA_CONST,
        "valid": registry.valid,
        "agent_ids": sorted(
            a["agent_id"] for a in registry.registry["agents"]
        ) if registry.registry else [],
        "errors": registry.errors,
    }
    path = _runtime_path(args)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(snapshot, indent=2, sort_keys=True))
    else:
        print(f"main={snapshot['main_head']} nodes={len(snapshot['nodes'])} "
              f"safe_runnable={snapshot['safe_runnable_count']} "
              f"events={snapshot['event_count']} invalid={snapshot['invalid_events']}")
        print(f"snapshot written: {path}")
    return 0


def cmd_frontier(args) -> int:
    """Frontier listing; with --agent, FEATURE_12 matrix → FEATURE_10 compat view."""
    client = _client(args)
    snapshot = build_snapshot(client, pool_path=_pool_path(args))
    if getattr(args, "agent", None):
        registry = agents_mod.load_registry(args.registry)
        stacks = stack_mod.build_stacks(
            snapshot["nodes"], client, snapshot.get("main_branch") or "main")
        weights, source = score_mod.load_weights(
            getattr(args, "weights", None))
        pool = _resolve_pool(args, client)
        matrix = frontier_matrix_mod.build_frontier_matrix(
            snapshot, agent_id=args.agent, registry=registry, stacks=stacks,
            weights=weights, weights_source=source, client=client, pool=pool)
        packet = frontier_matrix_mod.score_compat_projection(matrix, snapshot)
        errors = score_mod.validate_score(packet)
        if errors:
            print("frontier: FAIL ATLAS_FRONTIER_SCORE_V1 schema:", file=sys.stderr)
            for error in errors:
                print(f"  SCHEMA: {error}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(packet, indent=2, sort_keys=True))
            return 0
        print(f"frontier-score agent={packet['agent']} "
              f"status={packet['agent_status']} "
              f"weights={packet['weights_id']}@v{packet['weights_version']} "
              f"source={packet.get('weights_source')} "
              f"(derived-from={frontier_matrix_mod.SCHEMA_CONST})")
        print(f"{'RANK':<5} {'CLASS':<18} {'TOTAL':>8} {'LANE':<12} HEAD")
        for idx, entry in enumerate(packet["ranked"], start=1):
            node = next((n for n in snapshot["nodes"] if n["pr"] == entry["pr"]), {})
            print(f"{idx:<5} {entry['action_class']:<18} {entry['total']:>8.3f} "
                  f"{entry['lane']:<12} {str(node.get('head') or 'UNKNOWN')[:12]}")
        for entry in packet["blocked"]:
            print(f"{'-':<5} {'BLOCKED':<18} {entry['nominal_total']:>8.3f} "
                  f"{entry['lane']:<12} blockers={','.join(entry['authorization']['blockers'][:3])}")
        print(f"RANKING_FINGERPRINT={packet['ranking_fingerprint']}")
        return 0 if packet["ranked"] or packet["agent_status"] == "REGISTERED_ACTIVE" else 1
    if args.json:
        print(json.dumps(snapshot["nodes"], indent=2, sort_keys=True))
        return 0
    print(f"{'LANE':<10} {'STATE':<18} {'WAITING_ON':<28} HEAD")
    for node in snapshot["nodes"]:
        print(f"{node['lane']:<10} {node['state']:<18} "
              f"{','.join(node['waiting_on']) or '-':<28} {node['head'] or 'UNKNOWN'}")
    print(f"SAFE_RUNNABLE_COUNT={snapshot['safe_runnable_count']}")
    return 0


def _build_live_matrix(args):
    client = _client(args)
    snapshot = build_snapshot(client, pool_path=_pool_path(args))
    registry = agents_mod.load_registry(args.registry)
    stacks = stack_mod.build_stacks(
        snapshot["nodes"], client, snapshot.get("main_branch") or "main")
    weights, source = score_mod.load_weights(getattr(args, "weights", None))
    pool = _resolve_pool(args, client)
    events = _live_events(client)
    seal_by_pr = _collect_seal_by_pr(client, snapshot)
    return frontier_matrix_mod.build_frontier_matrix(
        snapshot, agent_id=getattr(args, "agent", None), registry=registry,
        stacks=stacks, weights=weights, weights_source=source,
        client=client, pool=pool, events=events, seal_by_pr=seal_by_pr), snapshot


def cmd_frontier_matrix(args) -> int:
    """Full ATLAS_MULTIDIMENSIONAL_FRONTIER_V1 packet (FEATURE_12)."""
    packet, _snapshot = _build_live_matrix(args)
    errors = frontier_matrix_mod.validate_matrix(packet)
    if errors:
        print("frontier-matrix: FAIL schema:", file=sys.stderr)
        for error in errors:
            print(f"  SCHEMA: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 0
    print(f"frontier-matrix agent={packet.get('agent')} "
          f"status={packet.get('agent_status')} "
          f"actions={len(packet['actions'])} "
          f"eligible={len(packet['eligible_actions'])}")
    print(f"{'STATE':<14} {'CLASS':<12} {'TYPE':<20} {'LANE':<12} REASONS")
    for action in packet["actions"]:
        if action["runnable_state"] == frontier_matrix_mod.NOT_APPLICABLE:
            continue
        print(f"{action['runnable_state']:<14} {action['action_class']:<12} "
              f"{action['action_type']:<20} {action['lane']:<12} "
              f"{','.join(action['blocking_reasons'][:2]) or '-'}")
    for group in packet.get("parallel_runnable_set") or []:
        print(f"PARALLEL_SET={' '.join(group)}")
    print(f"FRONTIER_FINGERPRINT={packet['frontier_fingerprint']}")
    return 0


def cmd_frontier_actions(args) -> int:
    """Agent-specific eligible/ineligible/blocked action lists (FEATURE_12)."""
    if not args.agent:
        print("frontier-actions: --agent required", file=sys.stderr)
        return 2
    packet, _ = _build_live_matrix(args)
    view = {
        "schema": frontier_matrix_mod.SCHEMA_CONST,
        "agent": packet.get("agent"),
        "agent_status": packet.get("agent_status"),
        "eligible_actions": packet.get("eligible_actions"),
        "ineligible_actions": packet.get("ineligible_actions"),
        "blocked_actions": packet.get("blocked_actions"),
        "by_action_class": packet.get("by_action_class"),
        "typed_rankings": packet.get("typed_rankings"),
        "parallel_runnable_set": packet.get("parallel_runnable_set"),
        "frontier_fingerprint": packet.get("frontier_fingerprint"),
    }
    if args.json:
        print(json.dumps(view, indent=2, sort_keys=True))
        return 0
    print(f"frontier-actions agent={view['agent']} status={view['agent_status']}")
    print(f"ELIGIBLE={len(view['eligible_actions'])} "
          f"INELIGIBLE={len(view['ineligible_actions'])} "
          f"BLOCKED={len(view['blocked_actions'])}")
    for aid in view["eligible_actions"][:20]:
        print(f"  ELIGIBLE {aid}")
    for aid in (view.get("typed_rankings") or {}).get("best_write", [])[:5]:
        print(f"  BEST_WRITE {aid}")
    return 0 if view["agent_status"] == "REGISTERED_ACTIVE" else 1


def cmd_explain_action(args) -> int:
    """Explain one action_id from the live multidimensional frontier."""
    packet, _ = _build_live_matrix(args)
    explained = frontier_matrix_mod.explain_action(packet, args.action_id)
    if args.json:
        print(json.dumps(explained, indent=2, sort_keys=True))
        return 0 if explained.get("found") else 2
    if not explained.get("found"):
        print(f"explain-action: FAIL {explained.get('reason')}", file=sys.stderr)
        return 2
    action = explained["action"]
    print(f"{action['action_id']} class={action['action_class']} "
          f"state={action['runnable_state']} eligible={action['agent_eligible']}")
    for reason in action.get("blocking_reasons") or []:
        print(f"  BLOCKER: {reason}")
    if action.get("score_total") is not None:
        print(f"  score_total={action['score_total']}")
    print(f"  concurrency_group={action.get('concurrency_group')}")
    print(f"  truth_fingerprint={action.get('truth_fingerprint')}")
    return 0


def _live_events(client) -> list[dict]:
    issue = client.dag_issue()
    if not issue:
        return []
    return events_mod.ingest_comments(client.issue_comments(issue["number"])).events


def _collect_seal_by_pr(client, snapshot, clock=None) -> dict[int, dict]:
    """Build Feature-09 seal plans for snapshot + recently merged PRs.

    Open snapshot lanes alone miss postmerge obligations on already-merged
    PRs (e.g. #740). Recently merged candidates are included so Feature-13
    can project durable seal residuals without inventing obligations.
    """
    out: dict[int, dict] = {}
    prs = {int(n["pr"]) for n in (snapshot.get("nodes") or []) if n.get("pr")}
    try:
        repo = client.repo
        if repo:
            merged = client.gh_json([
                "pr", "list", "--repo", repo, "--state", "merged",
                "--limit", "25", "--json", "number",
            ]) or []
            for item in merged:
                if item.get("number") is not None:
                    prs.add(int(item["number"]))
    except Exception:
        pass
    for pr in sorted(prs):
        try:
            if clock is None:
                plan = seal_plan_mod.build_seal_plan(pr, client)
            else:
                plan = seal_plan_mod.build_seal_plan(pr, client, clock=clock)
        except Exception:
            continue
        out[pr] = plan
    return out


def _build_residual_registry(args, client=None, snapshot=None, stacks=None,
                             seal_by_pr=None):
    client = client or _client(args)
    snapshot = snapshot or build_snapshot(client, pool_path=_pool_path(args))
    stacks = stacks or stack_mod.build_stacks(
        snapshot["nodes"], client, snapshot.get("main_branch") or "main")
    if seal_by_pr is None:
        seal_by_pr = _collect_seal_by_pr(client, snapshot)
    registry = agents_mod.load_registry(args.registry)
    events = _live_events(client)
    return residuals_mod.build_residual_registry(
        repository=client.repo, events=events, snapshot=snapshot, stacks=stacks,
        seal_by_pr=seal_by_pr, agent_id=getattr(args, "agent", None),
        registry=registry), snapshot, stacks


def cmd_residuals(args) -> int:
    """List durable residuals (FEATURE_13)."""
    packet, _, _ = _build_residual_registry(args)
    errors = residuals_mod.validate_registry(packet)
    if errors:
        print("residuals: FAIL schema:", file=sys.stderr)
        for error in errors[:20]:
            print(f"  SCHEMA: {error}", file=sys.stderr)
        return 1
    state_filter = getattr(args, "state", None)
    rows = packet["residuals"]
    if state_filter:
        rows = [r for r in rows
                if r["disposition"] == state_filter
                or r["derived_execution_state"] == state_filter]
    view = {**packet, "residuals": rows}
    if args.json:
        print(json.dumps(view, indent=2, sort_keys=True))
        return 0
    print(f"residuals open={packet['open_count']} runnable={packet['runnable_count']} "
          f"blocked={packet['blocked_count']} fingerprint={packet['registry_fingerprint'][:12]}")
    for rec in rows[:40]:
        print(f"  {rec['residual_id']:<28} {rec['disposition']:<14} "
              f"{rec['derived_execution_state']:<12} {rec['residual_type']:<20} "
              f"{rec.get('target_lane') or '-'}")
    return 0


def cmd_residual(args) -> int:
    """Inspect one residual by id (FEATURE_13)."""
    packet, _, _ = _build_residual_registry(args)
    found = residuals_mod.get_residual(packet, args.residual_id)
    if args.json:
        print(json.dumps(found, indent=2, sort_keys=True))
        return 0 if found.get("found") else 2
    if not found.get("found"):
        print(f"residual: FAIL {found.get('reason')}", file=sys.stderr)
        return 2
    rec = found["residual"]
    print(f"{rec['residual_id']} disposition={rec['disposition']} "
          f"derived={rec['derived_execution_state']} type={rec['residual_type']}")
    print(f"  action={rec['required_action_type']} lane={rec.get('target_lane')}")
    print(f"  {rec['description']}")
    for reason in rec.get("blocking_reasons") or []:
        print(f"  BLOCKER: {reason}")
    for hist in rec.get("resolution_history") or []:
        print(f"  HISTORY: {hist.get('event')} {hist.get('state')} "
              f"evt={hist.get('event_id')}")
    return 0


def cmd_residual_register(args) -> int:
    """Register a structured residual via FEATURE_04 event emit."""
    client = _client(args)
    registry = agents_mod.load_registry(args.registry)
    rid = args.residual_id or residuals_mod.make_residual_id(
        "register", args.description, str(args.pr or ""), args.residual_type)
    note = args.description
    profile = agents_mod.resolve_agent(registry, args.agent).profile or {}
    try:
        ctx = emitter_mod.resolve_context(
            client, args.pr, profile, expected_repo=getattr(args, "expect_repo", None))
        payload = emitter_mod.build_event(
            ctx, event=residuals_mod.EVT_REGISTERED, state="OPEN",
            note=note, next_actions=["residual"])
        payload["residual_id"] = rid
        payload["residual_type"] = args.residual_type
        payload["required_action_type"] = args.action_type
        payload["severity"] = args.severity
        if args.prerequisite:
            payload["prerequisites"] = list(args.prerequisite)
        if args.criterion:
            payload["resolution_criteria"] = list(args.criterion)
        status = emitter_mod.emit_event(
            client, registry, payload, dry_run=bool(args.dry_run))
    except emitter_mod.EmitError as exc:
        print(f"residual-register: FAIL {exc}", file=sys.stderr)
        return 1
    out = {"residual_id": rid, "emit_status": status, "event_id": payload["event_id"],
           "dry_run": bool(args.dry_run)}
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(f"residual-register {rid} status={status} event={payload['event_id']}")
    return 0 if status in ("posted", "already-present", "would-post") else 1


def cmd_residual_resolve(args) -> int:
    """Resolve / accept-risk / reopen a residual via FEATURE_04 emit."""
    client = _client(args)
    registry = agents_mod.load_registry(args.registry)
    packet, snapshot, _ = _build_residual_registry(args, client=client)
    found = residuals_mod.get_residual(packet, args.residual_id)
    if not found.get("found"):
        print(f"residual-resolve: FAIL {found.get('reason')}", file=sys.stderr)
        return 2
    rec = found["residual"]
    evidence = list(args.evidence or [])
    event = {
        "RESOLVED": residuals_mod.EVT_RESOLVED,
        "ACCEPTED_RISK": residuals_mod.EVT_ACCEPTED,
        "REOPENED": residuals_mod.EVT_REOPENED,
        "SUPERSEDED": residuals_mod.EVT_SUPERSEDED,
    }[args.disposition]
    pr = rec.get("target_pr") or args.pr
    if pr is None:
        print("residual-resolve: FAIL TARGET_PR_REQUIRED", file=sys.stderr)
        return 2
    node = next((n for n in snapshot["nodes"] if n.get("pr") == pr), {})
    if args.disposition == "RESOLVED":
        ok, reasons = residuals_mod.resolution_evidence_valid(
            rec, evidence, current_head=node.get("head"))
        if not ok:
            print(f"residual-resolve: FAIL {','.join(reasons)}", file=sys.stderr)
            return 1
    if args.disposition == "ACCEPTED_RISK":
        profile = agents_mod.resolve_agent(registry, args.agent).profile
        ok, reasons = residuals_mod.accepted_risk_authorized(
            profile, rec, node.get("owner"))
        if not ok:
            print(f"residual-resolve: FAIL {','.join(reasons)}", file=sys.stderr)
            return 1
    profile = agents_mod.resolve_agent(registry, args.agent).profile or {}
    try:
        ctx = emitter_mod.resolve_context(client, int(pr), profile)
        payload = emitter_mod.build_event(
            ctx, event=event, state=args.disposition,
            note=args.note or f"{args.disposition} {args.residual_id}",
            evidence=evidence, next_actions=[])
        payload["residual_id"] = args.residual_id
        status = emitter_mod.emit_event(
            client, registry, payload, dry_run=bool(args.dry_run))
    except emitter_mod.EmitError as exc:
        print(f"residual-resolve: FAIL {exc}", file=sys.stderr)
        return 1
    out = {"residual_id": args.residual_id, "disposition": args.disposition,
           "emit_status": status, "event_id": payload["event_id"]}
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(f"residual-resolve {args.residual_id} → {args.disposition} "
              f"status={status}")
    return 0 if status in ("posted", "already-present", "would-post") else 1


def cmd_residual_frontier(args) -> int:
    """Residual-backed actions in the Feature-12 frontier (FEATURE_13)."""
    client = _client(args)
    packet, snapshot, stacks = _build_residual_registry(args, client=client)
    registry = agents_mod.load_registry(args.registry)
    weights, source = score_mod.load_weights(getattr(args, "weights", None))
    events = _live_events(client)
    seal_by_pr = _collect_seal_by_pr(client, snapshot)
    matrix = frontier_matrix_mod.build_frontier_matrix(
        snapshot, agent_id=args.agent, registry=registry, stacks=stacks,
        weights=weights, weights_source=source, residual_registry=packet,
        events=events, client=client, seal_by_pr=seal_by_pr)
    residual_actions = [
        a for a in matrix["actions"] if a.get("residual_id")
    ]
    view = {
        "schema": residuals_mod.REGISTRY_SCHEMA,
        "agent": args.agent,
        "registry_fingerprint": packet["registry_fingerprint"],
        "frontier_fingerprint": matrix["frontier_fingerprint"],
        "residual_actions": residual_actions,
        "runnable": [a for a in residual_actions
                     if a["runnable_state"] == frontier_matrix_mod.RUNNABLE],
        "blocked": [a for a in residual_actions
                    if a["runnable_state"] == frontier_matrix_mod.BLOCKED],
    }
    if args.json:
        print(json.dumps(view, indent=2, sort_keys=True))
        return 0
    print(f"residual-frontier agent={args.agent} "
          f"residual_actions={len(residual_actions)} "
          f"runnable={len(view['runnable'])} blocked={len(view['blocked'])}")
    for action in residual_actions[:30]:
        print(f"  {action['runnable_state']:<12} {action['action_id']}")
    return 0


def cmd_score(args) -> int:
    """Score one PR after authorization (FEATURE_10)."""
    client = _client(args)
    snapshot = build_snapshot(client, pool_path=_pool_path(args))
    node = _find_node(snapshot, args.pr)
    if node is None:
        print(f"score: FAIL UNKNOWN_PR:{args.pr}", file=sys.stderr)
        return 2
    registry = agents_mod.load_registry(args.registry) if args.agent else None
    stacks = stack_mod.build_stacks(
        snapshot["nodes"], client, snapshot.get("main_branch") or "main")
    weights, source = score_mod.load_weights(getattr(args, "weights", None))
    explained = score_mod.explain_priority(
        snapshot, args.pr, agent_id=args.agent, registry=registry,
        stacks=stacks, weights=weights, weights_source=source)
    if args.json:
        print(json.dumps(explained, indent=2, sort_keys=True))
        return 0 if explained.get("found") else 2
    if not explained.get("found"):
        print(f"score: FAIL {explained.get('reason')}", file=sys.stderr)
        return 2
    entry = explained["entry"]
    print(f"score pr/{entry['pr']} class={entry['action_class']} "
          f"executable={entry['executable']}")
    if entry["executable"]:
        print(f"  total={entry['total']}")
    else:
        print(f"  nominal_total={entry['nominal_total']} (NOT executable)")
        for blocker in entry["authorization"]["blockers"]:
            print(f"  BLOCKER: {blocker}")
    for name, contrib in entry["factors"].items():
        print(f"  {name}: raw={contrib['raw']} weight={contrib['weight']} "
              f"weighted={contrib['weighted']} ({contrib['rationale']})")
    return 0


def cmd_explain_priority(args) -> int:
    """Alias surface for score --json factor dump (FEATURE_10)."""
    args.json = True
    return cmd_score(args)


def cmd_steal_status(args) -> int:
    """Read-only steal plan for one agent (FEATURE_11)."""
    client = _client(args)
    snapshot = build_snapshot(client, pool_path=_pool_path(args))
    registry = agents_mod.load_registry(args.registry)
    stacks = stack_mod.build_stacks(
        snapshot["nodes"], client, snapshot.get("main_branch") or "main")
    weights, source = score_mod.load_weights(getattr(args, "weights", None))
    plan = steal_mod.plan_steal(
        snapshot, args.agent, registry, stacks=stacks,
        weights=weights, weights_source=source)
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(f"steal-status agent={plan['agent']} "
              f"status={plan['agent_status']} utilization={plan['utilization']}")
        if plan.get("candidate"):
            c = plan["candidate"]
            print(f"  candidate: {c['lane']} total={c['total']:.3f} "
                  f"head={str(c.get('head') or '')[:12]}")
        for skip in plan.get("skipped", [])[:10]:
            print(f"  SKIP {skip['lane']}: {','.join(skip['reasons'][:3])}")
        for reason in plan.get("reasons") or []:
            print(f"  REASON: {reason}")
    return 0 if plan["utilization"] == steal_mod.STEAL_AVAILABLE else 1


def cmd_steal(args) -> int:
    """Safe claim of highest-value compatible unowned lane (FEATURE_11)."""
    client = _client(args)
    registry = agents_mod.load_registry(args.registry)
    weights, source = score_mod.load_weights(getattr(args, "weights", None))
    result = steal_mod.execute_steal(
        client, args.agent, registry,
        weights=weights, weights_source=source,
        dry_run=bool(getattr(args, "dry_run", False)),
        expected_repo=getattr(args, "expect_repo", None))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"steal agent={result.get('agent')} outcome={result.get('outcome')} "
              f"mutated={result.get('mutated')} attempt={result.get('attempt')}")
        cand = result.get("candidate")
        if cand:
            print(f"  candidate: {cand['lane']} total={cand['total']:.3f}")
        if result.get("event_id"):
            print(f"  event_id: {result['event_id']}")
        for reason in result.get("reasons") or []:
            print(f"  REASON: {reason}")
    ok = result.get("outcome") in (
        steal_mod.CLAIMED, steal_mod.WOULD_CLAIM, steal_mod.ALREADY_OWNED)
    return 0 if ok else 1


def _find_node(snapshot, pr: int) -> dict | None:
    for node in snapshot["nodes"]:
        if node["pr"] == pr:
            return node
    return None


def cmd_inspect(args) -> int:
    snapshot = build_snapshot(_client(args))
    node = _find_node(snapshot, args.pr)
    if node is None:
        print(f"PR #{args.pr} not in open-PR frontier", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(node, indent=2, sort_keys=True))
        return 0
    print(f"PR #{node['pr']} — {node.get('title')}")
    for key in ("state", "owner", "head", "tree", "base", "ci_status", "ci_run_id",
                "mergeable", "claim_integrity", "frozen", "formal_iv", "waiting_on",
                "stale_events", "review_comment_count"):
        print(f"  {key}: {node.get(key)}")
    print(f"  gate: {node['gate']['merge_gate']}")
    for reason in node["gate"]["reasons"]:
        print(f"    - {reason}")
    return 0


def cmd_events(args) -> int:
    client = _client(args)
    issue = client.dag_issue()
    if not issue:
        print("DAG Control issue not found (event bus not established)")
        return 1
    ingested = events_mod.ingest_comments(client.issue_comments(issue["number"]))
    if args.json:
        print(json.dumps({
            "issue": issue["number"],
            "events": ingested.events,
            "receipts": ingested.receipts,
            "invalid": ingested.invalid,
        }, indent=2, sort_keys=True))
        return 0
    print(f"DAG Control issue #{issue['number']} ({issue.get('state', '?')})")
    for event in ingested.events:
        print(f"  {event['timestamp_utc']} {event['event_id']} {event['event']} "
              f"pr={event.get('pr')} actor={event.get('actor')}")
    for receipt in ingested.receipts:
        print(f"  {receipt['timestamp_utc']} RECEIPT {receipt['receipt_id']} "
              f"pr={receipt['pr']} result={receipt['result']} by={receipt['verifier_id']}")
    for marker, reason in ingested.invalid:
        print(f"  INVALID {marker}: {reason}")
    return 0


def cmd_owners(args) -> int:
    from .model import ownership
    client = _client(args)
    issue = client.dag_issue()
    ingested = events_mod.ingest_comments(client.issue_comments(issue["number"])) if issue \
        else events_mod.IngestResult()
    result: dict[int, dict] = {}
    prs = {e["pr"] for e in ingested.events if e.get("pr") is not None}
    for pr in sorted(prs):
        status, actors = ownership(ingested.events, pr)
        result[pr] = {"status": status, "claimants": actors}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    for pr, info in result.items():
        if info["status"] == "OWNED":
            print(f"pr/{pr}: {info['claimants'][0]}")
        elif info["status"] == "AMBIGUOUS":
            print(f"pr/{pr}: AMBIGUOUS {info['claimants']}")
        else:
            print(f"pr/{pr}: UNOWNED")
    if not result:
        print("no active owner claims")
    return 0


def cmd_agents(args) -> int:
    result = agents_mod.load_registry(args.registry)
    if not result.valid:
        if args.json:
            print(json.dumps({"schema": agents_mod.REGISTRY_SCHEMA_CONST,
                              "valid": False, "errors": result.errors,
                              "agents": []}, indent=2, sort_keys=True))
        else:
            print("REGISTRY INVALID — failing closed (no inferred authority):")
            for error in result.errors:
                print(f"  {error}")
        return 1
    agents = sorted(result.registry["agents"], key=lambda a: a["agent_id"])
    if args.json:
        print(json.dumps({"schema": agents_mod.REGISTRY_SCHEMA_CONST,
                          "valid": True, "errors": [],
                          "agents": agents}, indent=2, sort_keys=True))
        return 0
    print(f"ATLAS_AGENT_REGISTRY_V1 — {len(agents)} registered profiles")
    for profile in agents:
        active = "ACTIVE" if profile.get("active") else "inactive"
        platforms = ",".join(profile.get("platforms", []))
        print(f"  {profile['agent_id']:<22} {active:<8} [{platforms:<12}] "
              f"role={profile.get('role')} "
              f"verification_class={profile.get('verification_class')}")
    return 0


def cmd_agent(args) -> int:
    result = agents_mod.load_registry(args.registry)
    resolved = agents_mod.resolve_agent(result, args.agent_id)
    if args.json:
        payload = {"agent_id": args.agent_id, "status": resolved.status,
                   "errors": resolved.errors}
        if resolved.profile is not None:
            payload["profile"] = resolved.profile
        if args.eval is not None and resolved.profile is not None:
            request = agents_mod.AgentRequest(
                action=args.eval,
                platform=args.platform,
                scope=args.scope,
                lane_owner=args.lane_owner,
                lane_frozen=args.frozen,
                event_type=args.event_type,
            )
            allowed, reasons = agents_mod.evaluate(resolved.profile, request)
            payload["evaluation"] = {"action": args.eval, "allowed": allowed,
                                     "reasons": reasons}
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if resolved.status != "REGISTERED":
            print(f"{args.agent_id}: {resolved.status} — failing closed, "
                  "no authority inferred", file=sys.stderr)
            for error in resolved.errors:
                print(f"  {error}", file=sys.stderr)
            return 1
        profile = resolved.profile
        print(f"agent: {profile['agent_id']} — {profile.get('role')}")
        for key in ("active", "platforms", "capabilities", "prohibitions",
                    "write_scopes", "event_permissions", "verification_class",
                    "principal"):
            print(f"  {key}: {profile.get(key)}")
        if args.eval is not None:
            request = agents_mod.AgentRequest(
                action=args.eval,
                platform=args.platform,
                scope=args.scope,
                lane_owner=args.lane_owner,
                lane_frozen=args.frozen,
                event_type=args.event_type,
            )
            allowed, reasons = agents_mod.evaluate(profile, request)
            verdict = "ALLOW" if allowed else "DENY"
            print(f"  eval {args.eval}: {verdict}")
            for reason in reasons:
                print(f"    - {reason}")
            return 0 if allowed else 1
    return 0 if resolved.status == "REGISTERED" else 1


def _pool_path(args) -> Path | None:
    return Path(args.verifier_registry) if args.verifier_registry else None


def _resolve_pool(args, client) -> verifiers_mod.PoolResolution:
    return verifiers_mod.resolve_pool(
        None, path=_pool_path(args), repo=client.repo,
    )


def _verifier_rows(resolution: verifiers_mod.PoolResolution,
                   result: verifiers_mod.PoolResult,
                   repo: str | None) -> list[dict]:
    """Pool entries annotated with resolved status, sorted by verifier_id."""
    rows = []
    entries = result.pool.get("verifiers", []) if result.pool else []
    for entry in sorted(entries, key=lambda e: str(e.get("verifier_id", ""))):
        verifier_id = str(entry.get("verifier_id", ""))
        status = resolution.status_map.get(verifier_id) if resolution.status_map \
            else verifiers_mod.authentication_status(entry, repo)
        rows.append({
            "verifier_id": verifier_id,
            "principal": entry.get("principal"),
            "active": bool(entry.get("active")),
            "allowed_repositories": sorted(entry.get("allowed_repositories", [])),
            "capabilities": sorted(entry.get("capabilities", [])),
            "prohibitions": sorted(entry.get("prohibitions", [])),
            "status": status,
        })
    return rows


def cmd_verifiers(args) -> int:
    client = _client(args)
    result = verifiers_mod.load_pool(_pool_path(args))
    if not result.valid:
        payload = {"schema": verifiers_mod.POOL_SCHEMA_CONST, "valid": False,
                   "errors": result.errors, "verifiers": []}
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print("VERIFIER POOL INVALID — failing closed "
                  "(no formal IV can be satisfied):", file=sys.stderr)
            for error in result.errors:
                print(f"  {error}", file=sys.stderr)
        return 1
    resolution = _resolve_pool(args, client)
    rows = _verifier_rows(resolution, result, client.repo)
    if args.json:
        print(json.dumps({"schema": verifiers_mod.POOL_SCHEMA_CONST, "valid": True,
                          "errors": [], "repo": client.repo,
                          "verifiers": rows}, indent=2, sort_keys=True))
        return 0
    repo = client.repo or "?"
    print(f"ATLAS_VERIFIER_POOL_V1 — {len(rows)} declared verifiers (repo={repo})")
    for row in rows:
        principal = row["principal"] or "UNBOUND"
        active = "ACTIVE" if row["active"] else "inactive"
        print(f"  {row['verifier_id']:<10} {active:<8} principal={principal:<24} "
              f"status={row['status']}")
    return 0


def cmd_verifier(args) -> int:
    client = _client(args)
    result = verifiers_mod.load_pool(_pool_path(args))
    if not result.valid:
        print(f"{args.verifier_id}: VERIFIER_POOL_INVALID — failing closed",
              file=sys.stderr)
        for error in result.errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    resolution = _resolve_pool(args, client)
    rows = {row["verifier_id"]: row for row in
            _verifier_rows(resolution, result, client.repo)}
    row = rows.get(args.verifier_id)
    if row is None:
        if args.json:
            print(json.dumps({"verifier_id": args.verifier_id,
                              "status": verifiers_mod.VERIFIER_UNKNOWN,
                              "registered": False}, indent=2, sort_keys=True))
        else:
            print(f"{args.verifier_id}: UNREGISTERED — not in the verifier pool; "
                  "failing closed, no formal IV possible", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"registered": True, **row}, indent=2, sort_keys=True))
    else:
        print(f"verifier: {row['verifier_id']} — status={row['status']}")
        for key in ("principal", "active", "allowed_repositories", "capabilities",
                    "prohibitions"):
            print(f"  {key}: {row[key]}")
        if row["status"] != verifiers_mod.AUTHENTICATED:
            print("  formal IV: NOT SATISFIABLE — verifier is not AUTHENTICATED")
    return 0


def _live_pr_context(client: GhClient, pr: int) -> tuple[dict | None, str | None]:
    """Live PR record + failure reason; (None, reason) when unverifiable."""
    if not client.repo:
        return None, "GITHUB_UNAVAILABLE"
    match = next((p for p in client.open_prs() if p.get("number") == pr), None)
    if match is None:
        return None, "PR_NOT_IN_OPEN_FRONTIER"
    return match, None


def cmd_iv_eligibility(args) -> int:
    """Read-only: could a formal-IV receipt from this verifier satisfy the gate?"""
    client = _client(args)
    result = verifiers_mod.load_pool(_pool_path(args))
    resolution = _resolve_pool(args, client) if result.valid \
        else verifiers_mod.empty_resolution(pool_invalid=True, errors=result.errors)

    pr_record, failure = _live_pr_context(client, args.pr)
    head = tree = pr_author = None
    if pr_record is not None:
        head = pr_record.get("headRefOid")
        commit = client.commit(head) if head else None
        tree = commit.get("tree") if commit else None
        pr_author = (pr_record.get("author") or {}).get("login")

    verifier_status = None
    if resolution.status_map is not None:
        verifier_status = resolution.status_map.get(args.verifier,
                                                    verifiers_mod.VERIFIER_UNKNOWN)
    elif result.valid and result.pool is not None:
        entry = next((e for e in result.pool.get("verifiers", [])
                      if e.get("verifier_id") == args.verifier), None)
        verifier_status = verifiers_mod.authentication_status(entry, client.repo)

    receipt_rows = []
    issue = client.dag_issue()
    if issue:
        ingested = events_mod.ingest_comments(client.issue_comments(issue["number"]))
        for receipt in ingested.receipts:
            if receipt.get("pr") != args.pr \
                    or receipt.get("verifier_id") != args.verifier:
                continue
            source = receipt.get("_source") or {}
            ok, reasons = receipts_mod.formal_iv_status(
                receipt, head, tree, resolution.bindings, resolution.declared,
                resolution.present, source.get("author"),
                status_map=resolution.status_map,
                pool_invalid=resolution.pool_invalid,
                pr_author=pr_author,
            )
            receipt_rows.append({"receipt_id": receipt["receipt_id"],
                                 "eligible": ok, "reasons": reasons})

    reasons: list[str] = []
    if failure:
        reasons.append(failure)
    if resolution.pool_invalid:
        reasons.append("VERIFIER_POOL_INVALID")
    if verifier_status is not None and verifier_status != verifiers_mod.AUTHENTICATED:
        reasons.append(receipts_mod.status_rejection_reason(verifier_status))
    if not head:
        reasons.append("CANDIDATE_HEAD_UNKNOWN")
    if not tree:
        reasons.append("CANDIDATE_TREE_UNKNOWN")
    could_satisfy = not reasons

    payload = {
        "pr": args.pr,
        "verifier_id": args.verifier,
        "verifier_status": verifier_status or verifiers_mod.VERIFIER_UNKNOWN,
        "candidate_head": head,
        "candidate_tree": tree,
        "pr_author": pr_author,
        "pool": verifiers_mod.pool_summary(resolution),
        "receipts": receipt_rows,
        "could_satisfy_gate": could_satisfy,
        "reasons": sorted(set(reasons)),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"iv-eligibility pr/{args.pr} verifier={args.verifier} "
              f"status={payload['verifier_status']} "
              f"could_satisfy_gate={'YES' if could_satisfy else 'NO'}")
        print(f"  candidate head={head or 'UNKNOWN'} tree={tree or 'UNKNOWN'} "
              f"pr_author={pr_author or 'UNKNOWN'}")
        for reason in payload["reasons"]:
            print(f"  REASON: {reason}")
        for row in receipt_rows:
            print(f"  receipt {row['receipt_id']}: "
                  f"{'ELIGIBLE' if row['eligible'] else 'REJECTED'}")
            for reason in row["reasons"]:
                print(f"    - {reason}")
    return 0 if could_satisfy else 1


def cmd_next(args) -> int:
    """Read-only agent-aware routing (FEATURE_02 + FEATURE_03 stack truth)."""
    client = _client(args)
    snapshot = build_snapshot(client)
    registry = agents_mod.load_registry(args.registry)
    stacks = stack_mod.build_stacks(snapshot["nodes"], client,
                                    snapshot.get("main_branch") or "main")
    result = router_mod.route(args.agent, snapshot, registry, stacks)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(router_mod.route_summary(result))
        if result["routable"]:
            print(f"  blockers on lower-preference lanes: "
                  f"{len(result['blockers'])} (see --json)")
        for alt in result["routes"][:5]:
            if alt["lane"] != result.get("lane"):
                print(f"  alt: {alt['lane']} {alt['action_class']} "
                      f"({', '.join(alt['reasons']) or 'not routable'})")
    return 0 if result["routable"] else 1


def cmd_stack(args) -> int:
    client = _client(args)
    snapshot = build_snapshot(client)
    stacks = stack_mod.build_stacks(snapshot["nodes"], client,
                                    snapshot.get("main_branch") or "main")
    record = stacks.get(f"pr/{args.pr}")
    if record is None:
        print(f"PR #{args.pr} not in open-PR frontier", file=sys.stderr)
        return 2
    chain = stack_mod.chain_for(record["lane"], stacks)
    if args.json:
        print(json.dumps({"node": record, "chain": chain}, indent=2,
                         sort_keys=True))
        return 0
    print(f"stack for pr/{args.pr} — state={record['stack_state']} "
          f"depth={record['depth']} root={record['stack_root']}")
    for entry in chain:
        marker = "->" if entry["lane"] != record["lane"] else "*"
        print(f"  {marker} {entry['lane']:<9} {entry['stack_state']:<26} "
              f"head={str(entry['child_head'])[:10]} "
              f"parent={entry['parent_pr']} "
              f"ancestor={entry['parent_ancestor_of_child']}")
        for reason in entry["reasons"]:
            print(f"      - {reason}")
    if record["children"]:
        print(f"  children: {', '.join(record['children'])}")
    if record["restack_required"]:
        print("  RESTACK_REQUIRED (detection only — no auto-restack)")
    return 0


def cmd_stacks(args) -> int:
    client = _client(args)
    snapshot = build_snapshot(client)
    stacks = stack_mod.build_stacks(snapshot["nodes"], client,
                                    snapshot.get("main_branch") or "main")
    lanes = sorted(stacks, key=lambda l: (stacks[l]["stack_root"] or "~", l))
    if args.json:
        print(json.dumps({"stacks": [stacks[l] for l in lanes]}, indent=2,
                         sort_keys=True))
        return 0
    current = None
    for lane in lanes:
        record = stacks[lane]
        if record["stack_root"] != current:
            current = record["stack_root"]
            print(f"stack root: {current or '(unresolved)'}")
        print(f"  {lane:<9} d{record['depth']} {record['stack_state']:<26} "
              f"parent={record['parent_pr']} "
              f"ancestor={record['parent_ancestor_of_child']}")
    return 0


def _resolve_profile(args) -> agents_mod.ProfileResult:
    registry = agents_mod.load_registry(args.registry)
    return agents_mod.resolve_agent(registry, args.agent)


def _lane_owner(client, pr: int) -> str | None:
    issue = client.dag_issue()
    if not issue:
        return None
    ingested = events_mod.ingest_comments(client.issue_comments(issue["number"]))
    status, claimants = ownership(ingested.events, pr)
    return claimants[0] if status == "OWNED" else None


def _build_event_from_args(args, client, profile) -> dict:
    ctx = emitter_mod.resolve_context(client, args.pr, profile or {},
                                      expected_repo=args.expect_repo)
    return emitter_mod.build_event(
        ctx, event=args.event, state=args.state, note=args.note,
        dependencies=args.dependency or [], evidence=args.evidence or [],
        invalidates=args.invalidates or [], next_actions=args.next_action or [],
        expect_head=args.expect_head)


def cmd_event_build(args) -> int:
    """Read-only canonical event construction (FEATURE_04)."""
    resolved = _resolve_profile(args)
    if resolved.status != "REGISTERED":
        print(f"agent {args.agent}: {resolved.status}", file=sys.stderr)
        return 1
    client = _client(args)
    try:
        payload = _build_event_from_args(args, client, resolved.profile)
    except emitter_mod.EmitError as exc:
        print(f"event-build: FAIL {exc}", file=sys.stderr)
        return 1
    print(emitter_mod.fenced(payload), end="")
    return 0


def cmd_emit(args) -> int:
    """Emit a canonical event to the #719 bus (FEATURE_04)."""
    registry = agents_mod.load_registry(args.registry)
    resolved = agents_mod.resolve_agent(registry, args.agent)
    if resolved.status != "REGISTERED":
        print(f"agent {args.agent}: {resolved.status}", file=sys.stderr)
        return 1
    profile = resolved.profile or {}
    if not profile.get("active", False):
        print("emit: FAIL AGENT_INACTIVE", file=sys.stderr)
        return 1
    client = _client(args)
    owner = _lane_owner(client, args.pr)
    checks = emitter_mod.check_emit_permission(
        registry, args.agent, args.event, owner)
    if not checks.ok:
        for reason in checks.reasons:
            print(f"emit: DENY {reason}", file=sys.stderr)
        return 1
    try:
        payload = _build_event_from_args(args, client, profile)
        status = emitter_mod.emit_event(client, registry, payload,
                                        dry_run=args.dry_run)
    except emitter_mod.EmitError as exc:
        print(f"emit: FAIL {exc}", file=sys.stderr)
        return 1
    print(f"{status}: {payload['event_id']} pr={payload['pr']} "
          f"head={payload['head'][:12]} tree={payload['tree'][:12]} "
          f"parent={payload['parent_pr']}")
    return 0


def cmd_dispatch_status(args) -> int:
    """Read-only sibling-lane dispatch plan (FEATURE_06, zero mutation)."""
    client = _client(args)
    snapshot = build_snapshot(client, pool_path=_pool_path(args))
    node = _find_node(snapshot, args.pr)
    if node is None:
        print(f"PR #{args.pr} not in open-PR frontier", file=sys.stderr)
        return 2
    resolution = _resolve_pool(args, client)
    plan = dispatch_mod.plan_dispatch(node, client, None, None, resolution,
                                      evidence_store=_evidence_store(args))
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    print(f"dispatch-status pr/{plan['pr']} @ {str(plan['head'])[:12]} "
          f"frozen={plan['frozen']}")
    for lane in ("ci", "iv"):
        info = plan[lane]
        print(f"  {lane}: {info['lane_state']}")
        for reason in info["reasons"]:
            print(f"    - {reason}")
    evidence_view = plan.get("evidence") or {}
    print(f"  evidence: current_exact_head_complete="
          f"{evidence_view.get('current_exact_head_complete')}")
    for evidence_id in evidence_view.get("predecessor_only") or []:
        print(f"    predecessor_only: {evidence_id}")
    for evidence_id in evidence_view.get("reusable_by_proof") or []:
        print(f"    reusable_by_proof: {evidence_id}")
    return 0


def cmd_dispatch(args) -> int:
    """Plan + execute CI/IV lane dispatch (FEATURE_06). Denials are explicit;
    --dry-run performs zero GitHub mutation."""
    registry = agents_mod.load_registry(args.registry)
    resolved = agents_mod.resolve_agent(registry, args.agent)
    if resolved.status != "REGISTERED":
        print(f"agent {args.agent}: {resolved.status}", file=sys.stderr)
        return 1
    client = _client(args)
    if args.expect_repo is not None and client.repo != args.expect_repo:
        print(f"dispatch: FAIL WRONG_REPOSITORY_IDENTITY:{client.repo}"
              f"!={args.expect_repo}", file=sys.stderr)
        return 1
    snapshot = build_snapshot(client, pool_path=_pool_path(args))
    node = _find_node(snapshot, args.pr)
    if node is None:
        print(f"PR #{args.pr} not in open-PR frontier", file=sys.stderr)
        return 2
    resolution = _resolve_pool(args, client)
    plan = dispatch_mod.plan_dispatch(node, client, args.agent,
                                      resolved.profile, resolution,
                                      evidence_store=_evidence_store(args))
    result = dispatch_mod.execute_dispatch(
        plan, client, args.agent, resolved.profile, dry_run=args.dry_run)
    if args.json:
        print(json.dumps({"plan": plan, "result": result}, indent=2,
                         sort_keys=True))
    else:
        print(f"dispatch pr/{result['pr']} @ {str(result['head'])[:12]} "
              f"dry_run={result['dry_run']}")
        for lane in ("ci", "iv"):
            info = result[lane]
            print(f"  {lane}: {info['outcome']}")
            for reason in info["reasons"]:
                print(f"    - {reason}")
    denied = any(result[l]["outcome"] in (
        dispatch_mod.PERMISSION_DENIED, dispatch_mod.HEAD_MOVED,
        dispatch_mod.FAILED, dispatch_mod.BLOCKED) for l in ("ci", "iv"))
    return 1 if denied else 0


def cmd_handoff(args) -> int:
    """Read-only handoff packet for one PR (FEATURE_08, generation only)."""
    client = _client(args)
    try:
        packet = handoff_mod.build_handoff(
            args.pr, args.mode, client,
            evidence_store=_evidence_store(args),
            verifier_pool=_pool_path(args))
    except handoff_mod.HandoffStale as exc:
        print(f"handoff: FAIL {exc}", file=sys.stderr)
        return 2
    except handoff_mod.HandoffError as exc:
        print(f"handoff: FAIL {exc}", file=sys.stderr)
        return 2
    # Fail closed: a schema-invalid packet is never printed.
    errors = handoff_mod.validate_packet(packet)
    if errors:
        print("handoff: FAIL packet failed ATLAS_HANDOFF_V1 schema validation:",
              file=sys.stderr)
        for error in errors:
            print(f"  SCHEMA: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 0
    print(f"handoff {packet['handoff_id']} pr/{packet['pr']} mode={packet['mode']} "
          f"gate={packet['merge_guardian']['merge_gate']} "
          f"head={str(packet['head'])[:12]} fp={packet['truth_fingerprint'][:12]}")
    print(f"  owner: {packet['ownership']} "
          f"ci: {packet['ci']['status']} "
          f"iv: {packet['formal_iv']['state']} "
          f"stack: {packet['stack']['stack_state']} "
          f"frozen: {packet['frozen']}")
    for reason in packet["merge_guardian"]["reasons"]:
        print(f"  REASON: {reason}")
    for action in packet["next_actions"]:
        print(f"  NEXT: {action}")
    for unc in packet["uncertainty"]:
        print(f"  UNCERTAIN: {unc}")
    return 0


def cmd_seal_plan(args) -> int:
    """Read-only post-merge seal plan for one PR (FEATURE_09, planning only).

    Determines from live repository truth what was merged, what evidence
    remains valid, what must be rerun/reconciled, and when the lane can
    truthfully become SEALED. Never merges, seals, or restacks."""
    client = _client(args)
    try:
        plan = seal_plan_mod.build_seal_plan(
            args.pr, client,
            evidence_store=_evidence_store(args),
            repo_dir=Path(args.repo_dir))
    except Exception as exc:
        print(f"seal-plan: FAIL {exc}", file=sys.stderr)
        return 2
    # Fail closed: a schema-invalid plan is never printed.
    errors = seal_plan_mod.validate_plan(plan)
    if errors:
        print("seal-plan: FAIL plan failed ATLAS_POSTMERGE_PLAN_V1 "
              "schema validation:", file=sys.stderr)
        for error in errors:
            print(f"  SCHEMA: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    merged = plan["merged"]
    print(f"seal-plan {plan['plan_id']} pr/{plan['pr']} "
          f"state={plan['state']} seal_state={plan['seal_state']}")
    print(f"  merged: is_merged={merged['is_merged']} method={merged['method']} "
          f"commit={str(merged['merge_commit'])[:12] if merged['merge_commit'] else 'NONE'} "
          f"verified={merged['verified']}")
    print(f"  ancestry: candidate_in_main={plan['ancestry']['candidate_in_main']} "
          f"via={plan['ancestry']['via']}")
    main_head = plan["main"]["head_current"]
    print(f"  main: head_current="
          f"{str(main_head)[:12] if main_head else 'UNKNOWN'} "
          f"advanced_since_merge={plan['main']['advanced_since_merge']}")
    for reason in plan["blockers"]:
        print(f"  BLOCKER: {reason}")
    for action in plan["required_actions"]:
        print(f"  ACTION: {action}")
    for unc in plan["uncertainty"]:
        print(f"  UNCERTAIN: {unc}")
    return 0


def cmd_gate(args) -> int:
    snapshot = build_snapshot(_client(args))
    node = _find_node(snapshot, args.pr)
    if node is None:
        print(f"PR #{args.pr} not in open-PR frontier", file=sys.stderr)
        return 2
    gate = node["gate"]
    if args.json:
        print(json.dumps({"pr": args.pr, **gate}, indent=2, sort_keys=True))
    else:
        print(f"MERGE_GATE = {gate['merge_gate']}  (pr/{args.pr} @ {node['head'] or 'UNKNOWN'})")
        for reason in gate["reasons"]:
            print(f"  REASON: {reason}")
    return 0 if gate["merge_gate"] == "PASS" else 1


def cmd_evidence_ingest(args) -> int:
    try:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"evidence-ingest: cannot read {args.file}: {exc}", file=sys.stderr)
        return 1
    errors = evidence_mod.validate_record(payload)
    if errors:
        print("evidence-ingest: invalid ATLAS_EVIDENCE_V1 record:", file=sys.stderr)
        for error in errors:
            print(f"  SCHEMA: {error}", file=sys.stderr)
        return 1
    store = _evidence_store(args)
    added, records = store.ingest(payload)
    state = "stored" if added else "already-present"
    print(f"{state}: evidence_id={payload['evidence_id']} "
          f"total_records={len(records)}")
    return 0


def _live_head_tree(client: GhClient, pr: int) -> tuple[str | None, str | None, str | None]:
    """Live (head, tree) for an open PR; (None, None, reason) when unverifiable."""
    if not client.repo:
        return None, None, "GITHUB_UNAVAILABLE"
    match = next((p for p in client.open_prs() if p.get("number") == pr), None)
    if match is None:
        return None, None, "PR_NOT_IN_OPEN_FRONTIER"
    head = match.get("headRefOid")
    commit = client.commit(head) if head else None
    if not commit:
        return head, None, "CANDIDATE_TREE_UNKNOWN"
    return head, commit.get("tree"), None


def _default_main_head(client: GhClient) -> str | None:
    """Live default-branch head; None when unverifiable (fail closed)."""
    try:
        main = client.branch_head("main")
    except Exception:
        return None
    return main.get("sha") if main else None


def _live_evidence_context(client: GhClient, pr: int,
                           head: str | None, tree: str | None,
                           parent_head: str | None) -> dict:
    """Live truth for FEATURE_07 graph evaluation. Everything the record did
    not explicitly bind itself to stays None (no invented dependencies).
    `changed_files` stays None: live diff truth is only resolved on demand by
    `evidence-impact`, never guessed here."""
    return {
        "pr": pr,
        "current_head": head,
        "current_tree": tree,
        "current_parent_head": parent_head,
        "current_main_head": _default_main_head(client),
        "changed_files": None,
        "current_platform": None,
        "current_test_set": None,
        "current_toolchain": None,
        "current_verifier_principal": None,
        "current_verifier_session": None,
        "equivalence_proofs": [],
    }


def _stack_parent_head(snapshot: dict, pr: int) -> str | None:
    """Parent PR head from FEATURE_03 stack truth (None for root/missing)."""
    try:
        stacks = stack_mod.build_stacks(
            snapshot["nodes"], None, snapshot.get("main_branch") or "main")
    except Exception:
        return None
    record = stacks.get(f"pr/{pr}")
    if record is None:
        return None
    parent_pr = record.get("parent_pr")
    if parent_pr is None:
        return None
    node = _find_node(snapshot, parent_pr)
    return node.get("head") if node else None


def _safe_parent_head(client: GhClient, pr: int) -> str | None:
    """Parent PR head from FEATURE_03 stack truth; None when unresolvable.
    Snapshot construction needs a full client surface — degrade to None
    rather than crash on reduced/offline clients."""
    try:
        snapshot = build_snapshot(client)
    except Exception:
        return None
    return _stack_parent_head(snapshot, pr)


def cmd_evidence(args) -> int:
    """List stored artifacts for a PR, resolved against live truth via the
    FEATURE_07 dependency/invalidation graph (read-only). The D-009
    reuse_class classification is reported alongside the graph state; both
    agree by construction and neither weakens exact-head rules."""
    store = _evidence_store(args)
    records = store.for_pr(args.pr)
    client = _client(args)
    head, tree, unavailable = _live_head_tree(client, args.pr)
    parent_head = _safe_parent_head(client, args.pr)
    context = _live_evidence_context(client, args.pr, head, tree, parent_head)
    rows = []
    for record in records:
        if unavailable:
            reuse_class, reasons = evidence_mod.UNKNOWN, [unavailable]
            graph_row = {
                "evidence_id": record.get("evidence_id"),
                "evidence_class": record.get("evidence_class"),
                "state": evidence_graph_mod.UNKNOWN,
                "reasons": sorted([unavailable]),
                "dependencies": evidence_graph_mod.derive_dependencies(record),
                "reuse_proof": None,
                "uncertainty": [unavailable],
            }
        else:
            reuse_class, reasons = evidence_mod.classify(record, head, tree)
            graph_row = evidence_graph_mod.evaluate(record, context)
        rows.append({
            "evidence_id": record.get("evidence_id"),
            "producer": record.get("producer"),
            "scope": record.get("scope"),
            "result": record.get("result"),
            "head": record.get("head"),
            "tree": record.get("tree"),
            "reuse_class": reuse_class,
            "reasons": sorted(set(reasons)),
            "state": graph_row["state"],
            "evidence_class": graph_row["evidence_class"],
            "dependencies": graph_row["dependencies"],
            "reuse_proof": graph_row["reuse_proof"],
            "uncertainty": graph_row["uncertainty"],
        })
    if args.json:
        print(json.dumps({"pr": args.pr, "current_head": head,
                          "current_tree": tree, "parent_head": parent_head,
                          "records": rows}, indent=2, sort_keys=True))
        return 0
    print(f"pr/{args.pr} current_head={head or 'UNKNOWN'} "
          f"current_tree={tree or 'UNKNOWN'} "
          f"parent_head={str(parent_head)[:12] if parent_head else 'UNKNOWN'}")
    for row in rows:
        print(f"  {row['evidence_id']} "
              f"{row.get('evidence_class') or row.get('scope') or '-':<16} "
              f"{row['state']}")
        for dep in row["dependencies"]:
            print(f"    dep {dep['class']}: {dep['value']}")
        for reason in row["reasons"]:
            print(f"    - {reason}")
        proof = row.get("reuse_proof")
        if proof and proof.get("provenance"):
            prov = proof["provenance"]
            print(f"    reuse-proof by {prov['author']} at "
                  f"{prov['issued_at_utc']} via {prov['evidence_ref']}")
        for unc in row.get("uncertainty") or []:
            print(f"    ? {unc}")
    if not rows:
        print(f"  no stored evidence for PR #{args.pr}")
    return 0


def cmd_evidence_graph(args) -> int:
    """Full dependency/invalidation graph for one PR (FEATURE_07, read-only)."""
    store = _evidence_store(args)
    records = store.for_pr(args.pr)
    client = _client(args)
    head, tree, unavailable = _live_head_tree(client, args.pr)
    parent_head = _safe_parent_head(client, args.pr)
    context = _live_evidence_context(client, args.pr, head, tree, parent_head)
    graph = evidence_graph_mod.build_graph(records, context)
    payload = {
        "pr": args.pr,
        "current_head": head,
        "current_tree": tree,
        "parent_head": parent_head,
        "github_unavailable": unavailable,
        **graph,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(f"evidence-graph pr/{args.pr} "
          f"current_head={head or 'UNKNOWN'} nodes={len(graph['nodes'])}")
    for node in graph["nodes"]:
        print(f"  {node['evidence_id']} [{node['state']}]")
        for dep in node["dependencies"]:
            print(f"    dep {dep['class']}: {dep['value']}")
        for reason in node["reasons"]:
            print(f"    - {reason}")
    for edge in graph["edges"]:
        print(f"  edge {edge['from']} -> {edge['to']} ({edge['value']})")
    for unc in graph["uncertainty"]:
        print(f"  UNRESOLVED: {unc}")
    return 0


def cmd_evidence_impact(args) -> int:
    """Hypothetical A->B impact: per-artifact state after the transition.
    Changed files come from `git diff` (subprocess, fail-closed on error);
    nothing is mutated. Read-only."""
    store = _evidence_store(args)
    records = store.for_pr(args.pr)
    repo_dir = Path(args.repo_dir).resolve()
    changed = evidence_graph_mod.changed_files_between(
        repo_dir, args.from_sha, args.to_sha)
    impact = evidence_graph_mod.evidence_impact(
        records, args.from_sha, args.to_sha, changed)
    impact["pr"] = args.pr
    impact["repo_dir"] = str(repo_dir)
    if args.json:
        print(json.dumps(impact, indent=2, sort_keys=True))
        return 0
    print(f"evidence-impact pr/{args.pr} {args.from_sha[:12]}..{args.to_sha[:12]} "
          f"changed_files={'UNKNOWN (fail closed)' if changed is None else len(changed)}")
    for artifact in impact["artifacts"]:
        print(f"  {artifact['evidence_id']} [{artifact['state']}]")
        for reason in artifact["reasons"]:
            print(f"    - {reason}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas-dag",
        description="Read-only ATLAS DAG coordinator (D-006). No merge mutation.",
    )
    parser.add_argument("--repo", default=None, help="owner/repo (default: inferred via gh)")
    parser.add_argument("--runtime-dir", default=RUNTIME_DIR,
                        help="disposable runtime state directory (default: .atlas-runtime)")
    parser.add_argument("--registry", default=None,
                        help="agent registry JSON (default: registry/agents.json)")
    parser.add_argument("--verifier-registry", default=None,
                        help="verifier pool JSON (default: registry/verifiers.json)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot", help="rebuild DAG snapshot into runtime state")
    p_frontier = sub.add_parser(
        "frontier",
        help="compat FEATURE_10 view derived from FEATURE_12 multidimensional frontier")
    p_frontier.add_argument("--agent", default=None,
                            help="registered agent_id for prioritized frontier")
    p_frontier.add_argument("--weights", default=None,
                            help="ATLAS_FRONTIER_WEIGHTS_V1 JSON (default: registry/frontier_weights.json)")
    p_frontier.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_fmatrix = sub.add_parser(
        "frontier-matrix",
        help="multidimensional action frontier (FEATURE_12)")
    p_fmatrix.add_argument("--agent", default=None)
    p_fmatrix.add_argument("--weights", default=None)
    p_fmatrix.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_factions = sub.add_parser(
        "frontier-actions",
        help="agent-specific eligible/ineligible/blocked actions (FEATURE_12)")
    p_factions.add_argument("--agent", required=True)
    p_factions.add_argument("--weights", default=None)
    p_factions.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_explain_action = sub.add_parser(
        "explain-action",
        help="explain one action_id from the multidimensional frontier (FEATURE_12)")
    p_explain_action.add_argument("--action-id", required=True,
                                  help="e.g. pr/720:IMPLEMENT")
    p_explain_action.add_argument("--agent", default=None)
    p_explain_action.add_argument("--weights", default=None)
    p_explain_action.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_residuals = sub.add_parser(
        "residuals", help="list durable residuals (FEATURE_13)")
    p_residuals.add_argument("--agent", default=None)
    p_residuals.add_argument("--state", default=None,
                             help="filter by disposition or derived execution state")
    p_residuals.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_residual = sub.add_parser(
        "residual", help="inspect one residual by id (FEATURE_13)")
    p_residual.add_argument("residual_id")
    p_residual.add_argument("--agent", default=None)
    p_residual.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_res_reg = sub.add_parser(
        "residual-register",
        help="register structured residual via FEATURE_04 emit (FEATURE_13)")
    p_res_reg.add_argument("--agent", required=True)
    p_res_reg.add_argument("--pr", type=int, required=True)
    p_res_reg.add_argument("--description", required=True)
    p_res_reg.add_argument("--residual-type", required=True,
                           choices=sorted(residuals_mod.RESIDUAL_TYPES))
    p_res_reg.add_argument("--action-type", required=True,
                           choices=sorted(residuals_mod.ACTION_TYPES))
    p_res_reg.add_argument("--severity", default="P2")
    p_res_reg.add_argument("--residual-id", default=None)
    p_res_reg.add_argument("--prerequisite", action="append", default=[])
    p_res_reg.add_argument("--criterion", action="append", default=[])
    p_res_reg.add_argument("--dry-run", action="store_true")
    p_res_reg.add_argument("--expect-repo", default=None)
    p_res_reg.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_res_resolve = sub.add_parser(
        "residual-resolve",
        help="resolve/accept-risk/reopen residual via FEATURE_04 (FEATURE_13)")
    p_res_resolve.add_argument("residual_id")
    p_res_resolve.add_argument("--agent", required=True)
    p_res_resolve.add_argument("--disposition", required=True,
                               choices=["RESOLVED", "ACCEPTED_RISK", "REOPENED",
                                        "SUPERSEDED"])
    p_res_resolve.add_argument("--evidence", action="append", default=[])
    p_res_resolve.add_argument("--pr", type=int, default=None)
    p_res_resolve.add_argument("--note", default=None)
    p_res_resolve.add_argument("--dry-run", action="store_true")
    p_res_resolve.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_res_front = sub.add_parser(
        "residual-frontier",
        help="residual-backed Feature-12 actions for one agent (FEATURE_13)")
    p_res_front.add_argument("--agent", required=True)
    p_res_front.add_argument("--weights", default=None)
    p_res_front.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_score = sub.add_parser(
        "score", help="score one PR after authorization (FEATURE_10)")
    p_score.add_argument("--pr", type=int, required=True)
    p_score.add_argument("--agent", default=None)
    p_score.add_argument("--weights", default=None)
    p_score.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_explain = sub.add_parser(
        "explain-priority",
        help="explain score factor contributions for one PR (FEATURE_10)")
    p_explain.add_argument("--pr", type=int, required=True)
    p_explain.add_argument("--agent", default=None)
    p_explain.add_argument("--weights", default=None)
    p_explain.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_steal_status = sub.add_parser(
        "steal-status",
        help="read-only steal plan for one agent (FEATURE_11)")
    p_steal_status.add_argument("--agent", required=True)
    p_steal_status.add_argument("--weights", default=None)
    p_steal_status.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_steal = sub.add_parser(
        "steal",
        help="claim highest-value compatible unowned lane (FEATURE_11)")
    p_steal.add_argument("--agent", required=True)
    p_steal.add_argument("--weights", default=None)
    p_steal.add_argument("--dry-run", action="store_true",
                         help="zero GitHub mutation; report WOULD_CLAIM candidate")
    p_steal.add_argument("--expect-repo", default=None)
    p_steal.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    sub.add_parser("agents", help="registered agent profiles (FEATURE_01, fail closed)")
    p_next = sub.add_parser("next", help="agent-aware next safe action (FEATURE_02, read-only)")
    p_next.add_argument("--agent", required=True, help="registered agent_id")
    p_stack = sub.add_parser("stack", help="stack chain for one PR (FEATURE_03, read-only)")
    p_stack.add_argument("pr", type=int)
    sub.add_parser("stacks", help="all stack chains grouped by root (FEATURE_03)")
    for name, help_text in (("event-build", "canonical resolved event (FEATURE_04, read-only)"),
                            ("emit", "emit canonical event to #719 (FEATURE_04)")):
        p_ev = sub.add_parser(name, help=help_text)
        p_ev.add_argument("--agent", required=True, help="registered agent_id")
        p_ev.add_argument("--pr", type=int, required=True)
        p_ev.add_argument("--event", required=True, help="ATLAS_EVENT_V1 event type")
        p_ev.add_argument("--state", required=True)
        p_ev.add_argument("--note", default="")
        p_ev.add_argument("--expect-head", default=None,
                          help="assertion only: FAIL on mismatch, never authority")
        p_ev.add_argument("--expect-repo", default=None,
                          help="assert the resolved repository identity")
        p_ev.add_argument("--dependency", action="append")
        p_ev.add_argument("--evidence", action="append")
        p_ev.add_argument("--invalidates", action="append")
        p_ev.add_argument("--next-action", action="append")
        if name == "emit":
            p_ev.add_argument("--dry-run", action="store_true",
                              help="zero GitHub mutation")
    p_agent = sub.add_parser("agent", help="inspect/evaluate one agent profile (fail closed)")
    p_agent.add_argument("agent_id")
    p_agent.add_argument("--eval", default=None,
                         help="evaluate an action: read/write/post_event/post_receipt/"
                              "claim_lane/merge/satisfy_formal_iv/run_on_platform")
    p_agent.add_argument("--platform", default=None)
    p_agent.add_argument("--scope", default=None,
                         help="repo-relative path scope (write) or github surface")
    p_agent.add_argument("--lane-owner", default=None,
                         help="active lane owner from #719 truth, if any")
    p_agent.add_argument("--frozen", action="store_true",
                         help="lane is frozen per repository truth")
    p_agent.add_argument("--event-type", default=None)
    p_inspect = sub.add_parser("inspect", help="inspect one PR node")
    p_inspect.add_argument("pr", type=int)
    sub.add_parser("events", help="validated event + receipt stream from DAG Control issue")
    sub.add_parser("owners", help="current ownership map (ambiguity => UNKNOWN)")
    sub.add_parser("verifiers", help="verifier trust pool with resolved status (FEATURE_05)")
    p_verifier = sub.add_parser("verifier",
                                help="inspect one verifier pool entry (FEATURE_05, fail closed)")
    p_verifier.add_argument("verifier_id")
    p_iv = sub.add_parser("iv-eligibility",
                          help="read-only formal-IV satisfiability for pr+verifier (FEATURE_05)")
    p_iv.add_argument("--pr", type=int, required=True)
    p_iv.add_argument("--verifier", required=True, help="verifier_id from the pool")
    p_gate = sub.add_parser("gate", help="read-only merge guardian evaluation (D-008)")
    p_gate.add_argument("pr", type=int)
    p_disp_status = sub.add_parser(
        "dispatch-status", help="read-only CI/IV lane dispatch plan (FEATURE_06)")
    p_disp_status.add_argument("--pr", type=int, required=True)
    p_disp = sub.add_parser(
        "dispatch", help="plan + execute CI/IV lane dispatch (FEATURE_06)")
    p_disp.add_argument("--pr", type=int, required=True)
    p_disp.add_argument("--agent", required=True, help="registered agent_id")
    p_disp.add_argument("--dry-run", action="store_true",
                        help="zero GitHub mutation (report WOULD_* outcomes)")
    p_disp.add_argument("--expect-repo", default=None,
                        help="assert the resolved repository identity")
    p_evidence = sub.add_parser("evidence", help="stored evidence reuse classification (D-009)")
    p_evidence.add_argument("pr", type=int)
    p_ingest = sub.add_parser("evidence-ingest",
                              help="validate + store one ATLAS_EVIDENCE_V1 record (D-009)")
    p_ingest.add_argument("file")
    p_graph = sub.add_parser("evidence-graph",
                             help="dependency/invalidation graph for a PR (FEATURE_07, read-only)")
    p_graph.add_argument("pr", type=int)
    p_impact = sub.add_parser(
        "evidence-impact",
        help="hypothetical A->B impact on stored evidence (FEATURE_07, read-only)")
    p_impact.add_argument("--pr", type=int, required=True)
    p_impact.add_argument("--from", dest="from_sha", required=True)
    p_impact.add_argument("--to", dest="to_sha", required=True)
    p_impact.add_argument("--repo-dir", default=".",
                          help="git work tree for the diff (default: cwd)")
    p_handoff = sub.add_parser(
        "handoff", help="read-only handoff packet for one PR (FEATURE_08, generation only)")
    p_handoff.add_argument("--pr", type=int, required=True)
    p_handoff.add_argument("--mode", choices=list(handoff_mod.MODES), default="general",
                           help="audience emphasis; material truth is identical across modes")
    p_seal = sub.add_parser(
        "seal-plan",
        help="read-only post-merge seal plan for one PR (FEATURE_09, planning only)")
    p_seal.add_argument("--pr", type=int, required=True)
    p_seal.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    p_seal.add_argument("--repo-dir", default=".",
                        help="git work tree for local ancestry/diff truth (default: cwd)")
    return parser


COMMANDS = {
    "snapshot": cmd_snapshot,
    "frontier": cmd_frontier,
    "frontier-matrix": cmd_frontier_matrix,
    "frontier-actions": cmd_frontier_actions,
    "explain-action": cmd_explain_action,
    "residuals": cmd_residuals,
    "residual": cmd_residual,
    "residual-register": cmd_residual_register,
    "residual-resolve": cmd_residual_resolve,
    "residual-frontier": cmd_residual_frontier,
    "score": cmd_score,
    "explain-priority": cmd_explain_priority,
    "steal-status": cmd_steal_status,
    "steal": cmd_steal,
    "agents": cmd_agents,
    "agent": cmd_agent,
    "next": cmd_next,
    "stack": cmd_stack,
    "stacks": cmd_stacks,
    "event-build": cmd_event_build,
    "emit": cmd_emit,
    "inspect": cmd_inspect,
    "events": cmd_events,
    "owners": cmd_owners,
    "verifiers": cmd_verifiers,
    "verifier": cmd_verifier,
    "iv-eligibility": cmd_iv_eligibility,
    "dispatch-status": cmd_dispatch_status,
    "dispatch": cmd_dispatch,
    "gate": cmd_gate,
    "evidence": cmd_evidence,
    "evidence-ingest": cmd_evidence_ingest,
    "evidence-graph": cmd_evidence_graph,
    "evidence-impact": cmd_evidence_impact,
    "handoff": cmd_handoff,
    "seal-plan": cmd_seal_plan,
}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)
