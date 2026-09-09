"""atlas-studio CLI — A0 snapshot + A1 Mission Control.

STUDIO_UI != AUTHORITY
MISSION_CONTROL = PROJECTION_OF_ATLAS_TRUTH
ATTENTION != AUTHORIZATION
STALE != CURRENT
UNKNOWN != HEALTHY
NO_MUTATION_API_IN_A1

Commands: snapshot | mission-control (mc) | doctor. No mutation surfaces.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
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

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"atlas-studio doctor version={__version__} ok={report['ok']}")
        for check in report["checks"]:
            mark = "PASS" if check["ok"] else "FAIL"
            print(f"  {mark} {check['name']}: {check['detail'][:120]}")
        print(
            "HONESTY: STUDIO_UI!=AUTHORITY / ATTENTION!=AUTHORIZATION / "
            "STALE!=CURRENT / UNKNOWN!=HEALTHY"
        )
    return 0 if report["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas-studio",
        description=(
            "Atlas Studio A0/A1 read-only projection "
            "(STUDIO_UI!=AUTHORITY; no mutation)."
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

    doc = sub.add_parser("doctor", help="Import/honesty/schema diagnostics")
    doc.add_argument("--json", action="store_true")
    doc.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
