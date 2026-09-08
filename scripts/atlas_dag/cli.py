"""atlas-dag command-line interface (D-006). Read-only coordinator; no merge mutation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import agents as agents_mod
from . import emitter as emitter_mod
from . import events as events_mod
from . import evidence as evidence_mod
from . import router as router_mod
from . import stack as stack_mod
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
    snapshot = build_snapshot(_client(args))
    if args.json:
        print(json.dumps(snapshot["nodes"], indent=2, sort_keys=True))
        return 0
    print(f"{'LANE':<10} {'STATE':<18} {'WAITING_ON':<28} HEAD")
    for node in snapshot["nodes"]:
        print(f"{node['lane']:<10} {node['state']:<18} "
              f"{','.join(node['waiting_on']) or '-':<28} {node['head'] or 'UNKNOWN'}")
    print(f"SAFE_RUNNABLE_COUNT={snapshot['safe_runnable_count']}")
    return 0


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
        print(f"evidence-ingest: invalid ATLAS_EVIDENCE_V1 record:", file=sys.stderr)
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


def cmd_evidence(args) -> int:
    store = _evidence_store(args)
    records = store.for_pr(args.pr)
    if not records:
        if args.json:
            head, tree, _unavailable = _live_head_tree(_client(args), args.pr)
            print(json.dumps({"pr": args.pr, "current_head": head, "current_tree": tree,
                              "records": []}, indent=2, sort_keys=True))
        else:
            print(f"no stored evidence for PR #{args.pr}")
        return 0
    head, tree, unavailable = _live_head_tree(_client(args), args.pr)
    rows = []
    for record in records:
        if unavailable:
            reuse_class, reasons = evidence_mod.UNKNOWN, [unavailable]
        else:
            reuse_class, reasons = evidence_mod.classify(record, head, tree)
        rows.append({
            "evidence_id": record["evidence_id"],
            "producer": record["producer"],
            "scope": record["scope"],
            "result": record["result"],
            "head": record["head"],
            "tree": record["tree"],
            "reuse_class": reuse_class,
            "reasons": reasons,
        })
    if args.json:
        print(json.dumps({"pr": args.pr, "current_head": head, "current_tree": tree,
                          "records": rows}, indent=2, sort_keys=True))
        return 0
    print(f"pr/{args.pr} current_head={head or 'UNKNOWN'} current_tree={tree or 'UNKNOWN'}")
    for row in rows:
        print(f"  {row['evidence_id']} {row['scope']:<14} {row['result']:<4} "
              f"{row['reuse_class']}")
        for reason in row["reasons"]:
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
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("snapshot", help="rebuild DAG snapshot into runtime state")
    sub.add_parser("frontier", help="list nodes with frontier states")
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
    p_gate = sub.add_parser("gate", help="read-only merge guardian evaluation (D-008)")
    p_gate.add_argument("pr", type=int)
    p_evidence = sub.add_parser("evidence", help="stored evidence reuse classification (D-009)")
    p_evidence.add_argument("pr", type=int)
    p_ingest = sub.add_parser("evidence-ingest",
                              help="validate + store one ATLAS_EVIDENCE_V1 record (D-009)")
    p_ingest.add_argument("file")
    return parser


COMMANDS = {
    "snapshot": cmd_snapshot,
    "frontier": cmd_frontier,
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
    "gate": cmd_gate,
    "evidence": cmd_evidence,
    "evidence-ingest": cmd_evidence_ingest,
}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return COMMANDS[args.command](args)
