"""atlas-studio CLI — A0 snapshot + A1 Mission Control + A2 governed claim.

STUDIO_UI != AUTHORITY
MISSION_CONTROL = PROJECTION_OF_ATLAS_TRUTH
ATTENTION != AUTHORIZATION
STALE != CURRENT
UNKNOWN != HEALTHY
REQUESTED != CLAIMED
PREVIEW != EXECUTION
CONTROL_PLANE_REVALIDATES_AT_EXECUTION

A0/A1 commands remain read-only. A2 claim-* commands produce intents /
previews / evaluations; only claim-execute may mutate via atlas_dag emitter
after revalidation — never BUTTON→OWNER_CLAIMED. Dispatch/steal-auto = NOT.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from atlas_studio import (
    ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME,
    ATTENTION_NE_AUTHORIZATION,
    GRANTS_NO_MUTATION,
    MODEL_PROVIDER_NE_ATLAS_ARCHITECTURE,
    NESTED_HONESTY_FAIL_CLOSED,
    NO_CLI_TEXT_PARSING_AS_PROTOCOL,
    NO_WHOLESALE_CORE_REWRITE,
    O1_IN_PROCESS_ATLAS_DAG_RO_RUNTIME,
    O6_SEAL_EVIDENCE_MAY_BE_UNKNOWN,
    REUSE_BEFORE_REIMPLEMENT,
    STALE_NE_CURRENT,
    STUDIO_CRASH_NE_AGENT_TASK_TERMINATION,
    STUDIO_UI_NE_AUTHORITY,
    UI_STATE_IS_PROJECTION,
    UNKNOWN_NE_HEALTHY,
    __version__,
)
from atlas_studio.mission_control import (
    DEFAULT_MAX_AGE_SECONDS,
    SCHEMA_CONST as MC_SCHEMA_CONST,
    build_mission_control,
    format_mission_control_tui,
    honesty_block as mc_honesty_block,
    validate_mission_control,
)
from atlas_studio.snapshot import (
    SCHEMA_CONST,
    build_studio_snapshot,
    honesty_block,
    validate_studio_snapshot,
)


def cmd_snapshot(args: argparse.Namespace) -> int:
    packet = build_studio_snapshot(
        agent_id=args.agent,
        live=True,
        repo=args.repo,
        verifier_pool_path=args.verifier_registry,
        weights_path=args.weights,
    )
    errors = validate_studio_snapshot(packet)
    if errors:
        print("atlas-studio snapshot: FAIL schema:", file=sys.stderr)
        for err in errors[:20]:
            print(f"  SCHEMA: {err}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 0
    print(
        f"studio-snapshot schema={packet['schema']} "
        f"status={packet['slice_status']} "
        f"agent={packet.get('agent')} agent_status={packet.get('agent_status')} "
        f"fp={packet['snapshot_fingerprint'][:12]}…"
    )
    for name, panel in sorted((packet.get("panels") or {}).items()):
        print(f"  {name:<22} {panel.get('status')}")
    print("HONESTY: STUDIO_UI!=AUTHORITY / UI_STATE=PROJECTION / GRANTS_NO_MUTATION")
    if packet.get("slice_status") == "UNKNOWN":
        return 1
    return 0


def _run_mission_control_once(args: argparse.Namespace) -> tuple[dict, int]:
    packet = build_mission_control(
        agent_id=args.agent,
        live=True,
        repo=args.repo,
        verifier_pool_path=getattr(args, "verifier_registry", None),
        weights_path=getattr(args, "weights", None),
        max_age_seconds=int(args.max_age_seconds),
    )
    errors = validate_mission_control(packet)
    if errors:
        print("atlas-studio mission-control: FAIL schema:", file=sys.stderr)
        for err in errors[:20]:
            print(f"  SCHEMA: {err}", file=sys.stderr)
        return packet, 1
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(format_mission_control_tui(packet))
    # Honest non-zero when OFFLINE/UNKNOWN mission (still valid schema).
    if packet.get("mission_status") in ("UNKNOWN", "OFFLINE"):
        return packet, 1
    if packet.get("freshness", {}).get("state") == "OFFLINE":
        return packet, 1
    return packet, 0


def cmd_mission_control(args: argparse.Namespace) -> int:
    """Rebuild each tick; never treat prior frame as LIVE without rebuild."""
    watch = getattr(args, "watch", None)
    if watch is None or int(watch) <= 0:
        _packet, code = _run_mission_control_once(args)
        return code

    interval = max(1, int(watch))
    # Simple TUI refresh loop — full rebuild every tick (no sticky LIVE cache).
    try:
        while True:
            if not args.json:
                # Clear-ish separator between frames; avoid ANSI dependency.
                print("\n" + "=" * 72)
                print(f"(watch={interval}s — rebuilding Mission Control)")
            _packet, code = _run_mission_control_once(args)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nmission-control watch stopped", file=sys.stderr)
        return 0


def _load_intent_file(path: str) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("intent file must contain a JSON object")
    return data


def _live_claim_context(
    agent_id: str,
    *,
    repo: str | None,
    clock=None,
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    """Build MC + frontier matrix + registry for claim commands (fail closed)."""
    from atlas_dag import agents as agents_mod
    from atlas_dag import frontier_matrix as fm_mod
    from atlas_dag import model as model_mod
    from atlas_dag import stack as stack_mod
    from atlas_dag.gh import GhClient
    from atlas_studio.mission_control import build_mission_control

    mc = build_mission_control(
        agent_id=agent_id,
        live=True,
        repo=repo,
        clock=clock,
    )
    client = GhClient(repo=repo) if repo else GhClient()
    snap = model_mod.build_snapshot(client)
    stacks = stack_mod.build_stacks(
        snap["nodes"], client, snap.get("main_branch") or "main"
    )
    registry = agents_mod.load_registry()
    matrix = fm_mod.build_frontier_matrix(
        snap,
        agent_id,
        registry,
        stacks=stacks,
        clock=clock,
    )
    return mc, matrix, registry


def cmd_claim_candidates(args: argparse.Namespace) -> int:
    from atlas_studio import action_intent as gc

    if args.agent:
        try:
            mc, matrix, _registry = _live_claim_context(args.agent, repo=args.repo)
        except Exception as exc:  # noqa: BLE001
            print(f"atlas-studio claim-candidates: FAIL {exc}", file=sys.stderr)
            return 1
        packet = gc.list_claim_candidates(
            agent_id=args.agent,
            frontier_matrix=matrix,
            mission_control=mc,
        )
    else:
        packet = gc.list_claim_candidates(agent_id=None, frontier_matrix={"actions": []})
        packet["notes"] = list(packet.get("notes") or []) + ["AGENT_REQUIRED_FOR_LIVE"]

    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(
            f"claim-candidates agent={packet.get('agent')} "
            f"n={len(packet.get('candidates') or [])}"
        )
        for c in packet.get("candidates") or []:
            print(
                f"  {c.get('lane')} action_id={c.get('action_id')} "
                f"head={(c.get('head') or '')[:12]}"
            )
        print("HONESTY: REQUESTED!=CLAIMED / RANKING!=AUTHORIZATION / PREVIEW!=EXECUTION")
    return 0


def cmd_claim_preview(args: argparse.Namespace) -> int:
    from atlas_studio import action_intent as gc

    try:
        mc, matrix, _registry = _live_claim_context(args.agent, repo=args.repo)
        preview = gc.preview_ownership_claim(
            agent_id=args.agent,
            lane=args.lane,
            frontier_matrix=matrix,
            mission_control=mc,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"atlas-studio claim-preview: FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(preview, indent=2, sort_keys=True))
    else:
        print(
            f"claim-preview status={preview.get('preview_status')} "
            f"lane={preview.get('target_lane')} "
            f"runnable={preview.get('runnable_state')} "
            f"eligible={preview.get('agent_eligible')}"
        )
        for line in preview.get("why") or []:
            print(f"  why: {line}")
        for line in preview.get("impact") or []:
            print(f"  impact: {line}")
        print("HONESTY: PREVIEW!=EXECUTION / REQUESTED!=CLAIMED")
    return 0 if preview.get("preview_status") != "UNKNOWN" else 1


def cmd_claim_intent(args: argparse.Namespace) -> int:
    from atlas_studio import action_intent as gc

    try:
        mc, matrix, _registry = _live_claim_context(args.agent, repo=args.repo)
        preview = gc.preview_ownership_claim(
            agent_id=args.agent,
            lane=args.lane,
            frontier_matrix=matrix,
            mission_control=mc,
        )
        intent = gc.build_ownership_claim_intent(
            agent_id=args.agent,
            lane=args.lane,
            source_mc_fingerprint=str(mc.get("snapshot_fingerprint")),
            source_frontier_fingerprint=matrix.get("frontier_fingerprint"),
            candidate_action_id=preview.get("candidate_action_id"),
            target_head=preview.get("target_head"),
            max_age_seconds=int(args.max_age_seconds),
            notes="atlas-studio claim-intent (stdout only; not authorization)",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"atlas-studio claim-intent: FAIL {exc}", file=sys.stderr)
        return 1
    # Intent JSON to stdout only — never auto-execute.
    print(json.dumps(intent, indent=2, sort_keys=True))
    return 0


def cmd_claim_evaluate(args: argparse.Namespace) -> int:
    from atlas_studio import action_intent as gc

    try:
        intent = _load_intent_file(args.intent_file)
        agent_id = str(intent.get("actor_agent_id") or "")
        mc, matrix, registry = _live_claim_context(agent_id, repo=args.repo)
        decision = gc.evaluate_ownership_claim_intent(
            intent,
            frontier_matrix=matrix,
            mission_control=mc,
            registry=registry,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"atlas-studio claim-evaluate: FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(decision, indent=2, sort_keys=True))
    else:
        print(
            f"claim-evaluate decision={decision.get('decision')} "
            f"mutated={decision.get('mutated')} "
            f"intent={decision.get('intent_id')}"
        )
        for r in decision.get("reasons") or []:
            print(f"  reason: {r}")
        print("HONESTY: EVALUATE!=EXECUTE / CONTROL_PLANE_REVALIDATES")
    return 0 if decision.get("decision") == gc.EXECUTE_ALLOWED else 1


def cmd_claim_execute(args: argparse.Namespace) -> int:
    from atlas_dag.gh import GhClient
    from atlas_studio import action_intent as gc

    try:
        # argparse required=True still accepts "" / whitespace; normalize.
        pinned_repo = (args.repo or "").strip()
        if not pinned_repo:
            print(
                "atlas-studio claim-execute: FAIL "
                "EXPECTED_REPO_REQUIRED_AT_EXECUTE "
                "(--repo must be a non-empty owner/name)",
                file=sys.stderr,
            )
            return 2
        intent = _load_intent_file(args.intent_file)
        agent_id = str(intent.get("actor_agent_id") or "")
        mc, matrix, registry = _live_claim_context(agent_id, repo=pinned_repo)
        client = GhClient(repo=pinned_repo)
        decision = gc.execute_ownership_claim(
            intent,
            client=client,
            registry=registry,
            frontier_matrix=matrix,
            mission_control=mc,
            dry_run=bool(args.dry_run),
            expected_repo=pinned_repo,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"atlas-studio claim-execute: FAIL {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(decision, indent=2, sort_keys=True))
    else:
        print(
            f"claim-execute decision={decision.get('decision')} "
            f"mutated={decision.get('mutated')} dry_run={decision.get('dry_run')} "
            f"emit={decision.get('emit_status')}"
        )
        for r in decision.get("reasons") or []:
            print(f"  reason: {r}")
        print(
            "HONESTY: CONTROL_PLANE_REVALIDATES_AT_EXECUTION / "
            "STUDIO_NEVER_SELF_AUTHORIZES / DRY_RUN!=EXECUTED"
        )
        print(
            "NEXT: save this decision JSON, then "
            "`atlas-studio action-evidence --decision-file <path>` "
            "(AUTO_RETRY=FORBIDDEN); after interrupt use "
            "`atlas-studio intent-continuity --intent-file … --decision-file …`"
        )
    outcome = decision.get("decision")
    if args.dry_run:
        ok = outcome == gc.EXECUTE_ALLOWED and decision.get("dry_run") is True
    else:
        ok = outcome == gc.EXECUTED and decision.get("mutated") is True
    return 0 if ok else 1


def cmd_mission_journey(args: argparse.Namespace) -> int:
    """AS-STUDIO-A2-002 RO mission journey — never mutates."""
    from atlas_studio.mission_journey import (
        build_mission_journey,
        format_mission_journey_tui,
        validate_mission_journey,
    )

    try:
        docs_root = args.docs_root
        if docs_root is None and not args.no_docs:
            # Default: repository docs/ when running inside a checkout.
            candidate = Path(__file__).resolve().parents[2] / "docs"
            docs_root = str(candidate) if candidate.is_dir() else None
        packet = build_mission_journey(
            agent_id=args.agent,
            repo=args.repo,
            live=bool(args.live),
            docs_root=docs_root,
            preview_lane=args.preview_lane,
            verifier_pool_path=args.verifier_registry,
            weights_path=args.weights,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"atlas-studio mission-journey: FAIL {exc}", file=sys.stderr)
        return 1
    errors = validate_mission_journey(packet)
    if errors:
        for err in errors:
            print(f"  SCHEMA: {err}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(format_mission_journey_tui(packet))
    return 0


def cmd_action_evidence(args: argparse.Namespace) -> int:
    """AS-STUDIO-A2-004 RO action evidence + recovery — never re-executes."""
    from atlas_studio.action_evidence import (
        build_action_evidence,
        format_action_evidence_tui,
        validate_action_evidence,
    )

    packet = build_action_evidence(
        decision_file=args.decision_file,
        spool_dir=args.spool_dir,
        write_spool=bool(args.write_spool),
    )
    errors = validate_action_evidence(packet)
    if errors:
        for err in errors:
            print(f"  SCHEMA: {err}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(format_action_evidence_tui(packet))
    # Exit 0 for inspect success; outcome_class is in the packet (not a mutation gate).
    return 0


def cmd_intent_continuity(args: argparse.Namespace) -> int:
    """AS-STUDIO-A2-005 RO intent continuity — never executes."""
    from atlas_studio.intent_continuity import (
        build_intent_continuity,
        format_intent_continuity_tui,
        validate_intent_continuity,
    )

    packet = build_intent_continuity(
        intent_file=args.intent_file,
        decision_file=args.decision_file,
        evidence_file=args.evidence_file,
    )
    errors = validate_intent_continuity(packet)
    if errors:
        for err in errors:
            print(f"  SCHEMA: {err}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(packet, indent=2, sort_keys=True))
    else:
        print(format_intent_continuity_tui(packet))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    report: dict[str, Any] = {
        "schema": "ATLAS_STUDIO_DOCTOR_V0",
        "version": __version__,
        "ok": True,
        "checks": [],
    }

    def add(name: str, ok: bool, detail: str) -> None:
        report["checks"].append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            report["ok"] = False

    try:
        from atlas_dag import control_view as cv  # noqa: F401
        from atlas_dag import frontier_matrix as fm  # noqa: F401
        from atlas_dag import telemetry as tel  # noqa: F401

        add("import_atlas_dag", True, "control_view+telemetry+frontier_matrix ok")
    except Exception as exc:  # noqa: BLE001
        add("import_atlas_dag", False, f"{type(exc).__name__}:{exc}")

    honesty = honesty_block()
    required = (
        "studio_ui_ne_authority",
        "ui_state_is_projection",
        "grants_no_mutation",
        "no_cli_text_parsing_as_protocol",
    )
    honesty_ok = all(honesty.get(k) is True for k in required)
    add("honesty_flags", honesty_ok, json.dumps(honesty, sort_keys=True))

    mc_honesty = mc_honesty_block()
    mc_required = (
        "attention_ne_authorization",
        "stale_ne_current",
        "unknown_ne_healthy",
        "nested_honesty_fail_closed",
        "grants_no_mutation",
    )
    mc_honesty_ok = all(mc_honesty.get(k) is True for k in mc_required)
    add("mc_honesty_flags", mc_honesty_ok, json.dumps(mc_honesty, sort_keys=True))

    consts_ok = all(
        (
            STUDIO_UI_NE_AUTHORITY,
            ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME,
            UI_STATE_IS_PROJECTION,
            NO_CLI_TEXT_PARSING_AS_PROTOCOL,
            NO_WHOLESALE_CORE_REWRITE,
            REUSE_BEFORE_REIMPLEMENT,
            MODEL_PROVIDER_NE_ATLAS_ARCHITECTURE,
            STUDIO_CRASH_NE_AGENT_TASK_TERMINATION,
            GRANTS_NO_MUTATION,
            ATTENTION_NE_AUTHORIZATION,
            STALE_NE_CURRENT,
            UNKNOWN_NE_HEALTHY,
            NESTED_HONESTY_FAIL_CLOSED,
            O1_IN_PROCESS_ATLAS_DAG_RO_RUNTIME,
            O6_SEAL_EVIDENCE_MAY_BE_UNKNOWN,
        )
    )
    add("design_law_consts", consts_ok, "module honesty consts")

    try:
        from atlas_dag import control_view as cv_mod
        from atlas_dag import telemetry as tel_mod

        fixed = "2026-09-09T00:00:00Z"
        packet = build_studio_snapshot(
            repository="doctor/local",
            control_view=cv_mod.build_global_control_view(
                repository="doctor/local",
                clock=lambda: fixed,
                seal_scan="skipped_for_latency",
            ),
            telemetry_packet=tel_mod.build_coordination_telemetry(
                repository="doctor/local",
                clock=lambda: fixed,
                seal_projection="deferred_or_skipped",
            ),
            clock=lambda: fixed,
        )
        errors = validate_studio_snapshot(packet)
        add(
            "schema_validate",
            not errors and packet["schema"] == SCHEMA_CONST,
            "ok" if not errors else "; ".join(errors[:5]),
        )
    except Exception as exc:  # noqa: BLE001
        add("schema_validate", False, f"{type(exc).__name__}:{exc}")

    # Brief MC schema check (A1)
    try:
        from atlas_dag import control_view as cv_mod
        from atlas_dag import telemetry as tel_mod

        fixed = "2026-09-09T00:00:00Z"
        mc = build_mission_control(
            repository="doctor/local",
            control_view=cv_mod.build_global_control_view(
                repository="doctor/local",
                clock=lambda: fixed,
                seal_scan="skipped_for_latency",
            ),
            telemetry_packet=tel_mod.build_coordination_telemetry(
                repository="doctor/local",
                clock=lambda: fixed,
                seal_projection="deferred_or_skipped",
            ),
            clock=lambda: fixed,
            max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
        )
        mc_errors = validate_mission_control(mc)
        add(
            "mc_schema_validate",
            not mc_errors and mc["schema"] == MC_SCHEMA_CONST,
            "ok" if not mc_errors else "; ".join(mc_errors[:5]),
        )
    except Exception as exc:  # noqa: BLE001
        add("mc_schema_validate", False, f"{type(exc).__name__}:{exc}")

    # A2: governed claim modules + schemas; no general mutation surface.
    try:
        from atlas_studio import action_intent as gc

        ok_schemas, detail = gc.schemas_loadable()
        add("a2_action_intent_import", True, "action_intent importable")
        add("a2_schemas_load", ok_schemas, detail)
        add(
            "a2_dispatch_steal_auto_not_started",
            gc.DISPATCH_STEAL_AUTO_NOT_STARTED is True,
            "DISPATCH/STEAL_AUTO=NOT_STARTED",
        )
        from atlas_studio import governance as gov

        by_type = {row["action_type"]: row for row in gov.supported_actions()}
        claim_impl = by_type.get("OWNERSHIP_CLAIM", {}).get("status") == "IMPLEMENTED"
        futures = (
            "CI_DISPATCH",
            "IV_REQUEST",
            "HANDOFF_DELIVER",
            "STEAL_EXECUTE",
            "MERGE",
            "WORKTREE_OPEN",
        )
        futures_ok = all(
            by_type.get(name, {}).get("status") == "NOT_STARTED" for name in futures
        )
        add(
            "a2_governance_substrate",
            claim_impl and futures_ok,
            (
                "OWNERSHIP_CLAIM=IMPLEMENTED; futures=NOT_STARTED"
                if claim_impl and futures_ok
                else f"registry={sorted(by_type)}"
            ),
        )
        # Confirm mission_control does not import governed claim (A1 boundary).
        import atlas_studio.mission_control as mc_mod

        mc_src = Path(mc_mod.__file__).read_text(encoding="utf-8")
        add(
            "a1_mc_no_action_intent_import",
            "action_intent" not in mc_src and "governance" not in mc_src,
            "mission_control does not import action_intent/governance",
        )
        # No general dispatch/merge mutation helpers on package root.
        import atlas_studio as studio_pkg

        root_names = {n.lower() for n in dir(studio_pkg) if not n.startswith("_")}
        general_mutation = {"dispatch", "merge", "force_merge", "steal_write"}
        leaked = sorted(general_mutation & root_names)
        add(
            "no_general_mutation_surface_on_package",
            not leaked,
            "ok" if not leaked else f"leaked:{leaked}",
        )
    except Exception as exc:  # noqa: BLE001
        add("a2_action_intent_import", False, f"{type(exc).__name__}:{exc}")

    # A2-002: mission journey RO composition.
    try:
        from atlas_studio import mission_journey as mj

        j_honesty = mj.honesty_block()
        add(
            "a2_002_journey_honesty",
            j_honesty.get("journey_ne_mutation") is True
            and j_honesty.get("knowledge_ne_permission") is True
            and j_honesty.get("preview_ne_execution") is True,
            json.dumps(j_honesty, sort_keys=True),
        )
        fixture_mc = {
            "schema": MC_SCHEMA_CONST,
            "generated_at_utc": "2026-09-09T12:00:00Z",
            "repository": "B0LK13/project-atlas",
            "agent": None,
            "agent_status": "NONE",
            "slice_status": "UNKNOWN",
            "mission_status": "UNKNOWN",
            "snapshot_fingerprint": "a" * 64,
            "freshness": {"state": "UNKNOWN"},
            "honesty": {},
            "views": {},
            "attention": {"items": []},
            "studio_snapshot": {"schema": SCHEMA_CONST, "slice_status": "UNKNOWN"},
            "provenance": {},
        }
        # Minimal injected journey — may not pass full MC schema; journey tolerates warn.
        journey = mj.build_mission_journey(
            mission_control=fixture_mc,
            claim_listing={"schema": "ATLAS_STUDIO_CLAIM_CANDIDATES_V1", "candidates": []},
            knowledge_items=[],
            clock=lambda: "2026-09-09T12:00:00Z",
        )
        j_errs = mj.validate_mission_journey(journey)
        add(
            "a2_002_mission_journey_schema",
            not j_errs and journey.get("schema") == mj.SCHEMA_CONST,
            "ok" if not j_errs else "; ".join(j_errs[:5]),
        )
        add(
            "a2_002_journey_no_execute_surface",
            "Never mutates; never executes claims" in Path(mj.__file__).read_text(encoding="utf-8"),
            "journey build docstring forbids execute",
        )
    except Exception as exc:  # noqa: BLE001
        add("a2_002_mission_journey", False, f"{type(exc).__name__}:{exc}")

    # A2-004: action evidence + recovery (monitor != re-execute).
    try:
        from atlas_studio import action_evidence as ae

        honesty = ae.honesty_block()
        add(
            "a2_004_evidence_honesty",
            honesty.get("auto_retry_forbidden") is True
            and honesty.get("uncertain_mutation_ne_nothing_changed") is True
            and honesty.get("capture_ne_authority") is True,
            json.dumps(honesty, sort_keys=True),
        )
        failed = {
            "schema": "ATLAS_STUDIO_ACTION_DECISION_V1",
            "decision": "EXECUTION_FAILED",
            "action_type": "OWNERSHIP_CLAIM",
            "intent_id": "intent-test",
            "mutated": False,
            "reasons": ["executor raised"],
            "evidence": {"mutation_state": "UNKNOWN"},
            "honesty": {},
            "evaluated_at_utc": "2026-09-09T12:00:00Z",
        }
        packet = ae.build_action_evidence(
            decision=failed, clock=lambda: "2026-09-09T12:00:00Z"
        )
        errs = ae.validate_action_evidence(packet)
        add(
            "a2_004_action_evidence_schema",
            not errs
            and packet.get("outcome_class") == ae.FAILED_UNCERTAIN
            and packet["recovery"]["auto_retry"] is False,
            "ok" if not errs else "; ".join(errs[:5]),
        )
        add(
            "a2_004_no_auto_retry",
            packet["recovery"]["auto_retry"] is False,
            "recovery.auto_retry must stay false",
        )
    except Exception as exc:  # noqa: BLE001
        add("a2_004_action_evidence", False, f"{type(exc).__name__}:{exc}")

    # A2-005: intent continuity / interrupted session inspect.
    try:
        from atlas_studio import intent_continuity as ic

        honesty = ic.honesty_block()
        add(
            "a2_005_continuity_honesty",
            honesty.get("inspect_ne_execute") is True
            and honesty.get("stale_intent_ne_permission") is True
            and honesty.get("auto_retry_forbidden") is True,
            json.dumps(honesty, sort_keys=True),
        )
        intent = {
            "schema": "ATLAS_STUDIO_ACTION_INTENT_V1",
            "intent_id": "intent-test",
            "action_type": "OWNERSHIP_CLAIM",
            "requested_at_utc": "2026-09-09T10:00:00Z",
            "max_age_seconds": 60,
        }
        packet = ic.build_intent_continuity(
            intent=intent, clock=lambda: "2026-09-09T12:00:00Z"
        )
        errs = ic.validate_intent_continuity(packet)
        add(
            "a2_005_intent_continuity_schema",
            not errs
            and packet.get("continuity_state") == ic.STALE_INTENT
            and packet["recovery"]["auto_retry"] is False,
            "ok" if not errs else "; ".join(errs[:5]),
        )
    except Exception as exc:  # noqa: BLE001
        add("a2_005_intent_continuity", False, f"{type(exc).__name__}:{exc}")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"atlas-studio doctor version={__version__} ok={report['ok']}")
        for check in report["checks"]:
            mark = "PASS" if check["ok"] else "FAIL"
            print(f"  {mark} {check['name']}: {check['detail'][:120]}")
        print(
            "HONESTY: STUDIO_UI!=AUTHORITY / ATTENTION!=AUTHORIZATION / "
            "STALE!=CURRENT / UNKNOWN!=HEALTHY / REQUESTED!=CLAIMED"
        )
    return 0 if report["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas-studio",
        description=(
            "Atlas Studio A0/A1 RO projection + A2 governed OWNERSHIP_CLAIM "
            "(STUDIO_UI!=AUTHORITY; preview!=execution)."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Build ATLAS_STUDIO_SNAPSHOT_V1 (RO)")
    snap.add_argument("--agent", default=None, help="Agent id (optional)")
    snap.add_argument("--repo", default=None, help="owner/name override for gh")
    snap.add_argument("--verifier-registry", default=None)
    snap.add_argument("--weights", default=None)
    snap.add_argument("--json", action="store_true")
    snap.set_defaults(func=cmd_snapshot)

    mc = sub.add_parser(
        "mission-control",
        aliases=["mc"],
        help="Build ATLAS_STUDIO_MISSION_CONTROL_V1 (RO Mission Control)",
    )
    mc.add_argument("--agent", default=None, help="Agent id (optional)")
    mc.add_argument("--repo", default=None, help="owner/name override for gh")
    mc.add_argument("--verifier-registry", default=None)
    mc.add_argument("--weights", default=None)
    mc.add_argument(
        "--max-age-seconds",
        type=int,
        default=DEFAULT_MAX_AGE_SECONDS,
        help=f"Freshness TTL (default {DEFAULT_MAX_AGE_SECONDS})",
    )
    mc.add_argument(
        "--watch",
        type=int,
        default=0,
        metavar="SECONDS",
        help="Optional TUI refresh interval; rebuilds each tick (never sticky LIVE)",
    )
    mc.add_argument("--json", action="store_true")
    mc.set_defaults(func=cmd_mission_control)

    # --- A2 governed OWNERSHIP_CLAIM (preview/intent/evaluate/execute separated) ---
    cc = sub.add_parser(
        "claim-candidates",
        help="List F12 OWNERSHIP_CLAIM candidates (RO projection)",
    )
    cc.add_argument("--agent", default=None, help="Agent id")
    cc.add_argument("--repo", default=None)
    cc.add_argument("--json", action="store_true")
    cc.set_defaults(func=cmd_claim_candidates)

    cp = sub.add_parser(
        "claim-preview",
        help="Preview ownership claim why/impact (RO; never mutates)",
    )
    cp.add_argument("--agent", required=True)
    cp.add_argument("--lane", required=True, help="Lane id, e.g. pr/123")
    cp.add_argument("--repo", default=None)
    cp.add_argument("--json", action="store_true")
    cp.set_defaults(func=cmd_claim_preview)

    ci = sub.add_parser(
        "claim-intent",
        help="Build ATLAS_STUDIO_ACTION_INTENT_V1 JSON on stdout (no execute)",
    )
    ci.add_argument("--agent", required=True)
    ci.add_argument("--lane", required=True)
    ci.add_argument("--repo", default=None)
    ci.add_argument(
        "--max-age-seconds",
        type=int,
        default=DEFAULT_MAX_AGE_SECONDS,
    )
    ci.add_argument("--json", action="store_true", help="Ignored; intent is always JSON")
    ci.set_defaults(func=cmd_claim_intent)

    ce = sub.add_parser(
        "claim-evaluate",
        help="Revalidate intent against live truth (no mutate)",
    )
    ce.add_argument("--intent-file", required=True)
    ce.add_argument("--repo", default=None)
    ce.add_argument("--json", action="store_true")
    ce.set_defaults(func=cmd_claim_evaluate)

    cx = sub.add_parser(
        "claim-execute",
        help="Revalidate then emit OWNER_CLAIMED via atlas_dag emitter if allowed",
    )
    cx.add_argument("--intent-file", required=True)
    cx.add_argument(
        "--repo",
        required=True,
        help="owner/name — required: execution is pinned to an explicit repo identity",
    )
    cx.add_argument("--json", action="store_true")
    cx.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate and allow path without emit_event",
    )
    cx.set_defaults(func=cmd_claim_execute)

    journey = sub.add_parser(
        "mission-journey",
        aliases=["journey"],
        help="AS-STUDIO-A2-002 RO mission journey (MC+knowledge+dev+claim next steps)",
    )
    journey.add_argument("--agent", default=None, help="Agent id (optional)")
    journey.add_argument("--repo", default=None, help="owner/name override for gh")
    journey.add_argument(
        "--live",
        action="store_true",
        help="Build live Mission Control (RO); default uses builders when injected N/A",
    )
    journey.add_argument(
        "--docs-root",
        default=None,
        help="Docs root for knowledge projection (default: repo docs/)",
    )
    journey.add_argument(
        "--no-docs",
        action="store_true",
        help="Skip default docs/ scan; knowledge state UNAVAILABLE unless injected",
    )
    journey.add_argument(
        "--preview-lane",
        default=None,
        help="Optional lane (e.g. pr/123) to attach claim preview (never executes)",
    )
    journey.add_argument("--verifier-registry", default=None)
    journey.add_argument("--weights", default=None)
    journey.add_argument("--json", action="store_true")
    journey.set_defaults(func=cmd_mission_journey)

    evidence = sub.add_parser(
        "action-evidence",
        aliases=["evidence"],
        help=(
            "AS-STUDIO-A2-004 inspect decision evidence + recovery "
            "(never re-executes; optional non-canonical spool)"
        ),
    )
    evidence.add_argument(
        "--decision-file",
        default=None,
        help="Path to ATLAS_STUDIO_ACTION_DECISION_V1 JSON",
    )
    evidence.add_argument(
        "--write-spool",
        action="store_true",
        help="Write non-canonical knowledge spool (CAPTURE!=AUTHORITY)",
    )
    evidence.add_argument(
        "--spool-dir",
        default=None,
        help="Directory for optional knowledge spool write",
    )
    evidence.add_argument("--json", action="store_true")
    evidence.set_defaults(func=cmd_action_evidence)

    continuity = sub.add_parser(
        "intent-continuity",
        aliases=["continuity"],
        help=(
            "AS-STUDIO-A2-005 inspect intent continuity after interrupt/stale/duplicate "
            "(never executes)"
        ),
    )
    continuity.add_argument("--intent-file", default=None, help="Intent JSON path")
    continuity.add_argument(
        "--decision-file",
        default=None,
        help="Optional prior ATLAS_STUDIO_ACTION_DECISION_V1",
    )
    continuity.add_argument(
        "--evidence-file",
        default=None,
        help="Optional prior ATLAS_STUDIO_ACTION_EVIDENCE_V1",
    )
    continuity.add_argument("--json", action="store_true")
    continuity.set_defaults(func=cmd_intent_continuity)

    doc = sub.add_parser("doctor", help="Import/honesty/schema diagnostics")
    doc.add_argument("--json", action="store_true")
    doc.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
