"""atlas-studio CLI — A0 Linux read-only slice (AS-STUDIO-A0-001).

STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
STUDIO_CRASH != AGENT_TASK_TERMINATION

Commands: snapshot | doctor. No mutation surfaces.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from atlas_studio import (
    ATLAS_DAEMON_IS_AUTHORITATIVE_RUNTIME,
    GRANTS_NO_MUTATION,
    MODEL_PROVIDER_NE_ATLAS_ARCHITECTURE,
    NO_CLI_TEXT_PARSING_AS_PROTOCOL,
    NO_WHOLESALE_CORE_REWRITE,
    REUSE_BEFORE_REIMPLEMENT,
    STUDIO_CRASH_NE_AGENT_TASK_TERMINATION,
    STUDIO_UI_NE_AUTHORITY,
    UI_STATE_IS_PROJECTION,
    __version__,
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
    # Honest non-zero when fully UNKNOWN (e.g. gh unavailable) — still valid schema.
    if packet.get("slice_status") == "UNKNOWN":
        return 1
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

    # Import atlas_dag surfaces
    try:
        from atlas_dag import control_view as cv  # noqa: F401
        from atlas_dag import telemetry as tel  # noqa: F401

        add("import_atlas_dag", True, "control_view+telemetry import ok")
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

    # Module-level design-law consts
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
        )
    )
    add("design_law_consts", consts_ok, "module honesty consts")

    # Minimal injected snapshot validates
    try:
        packet = build_studio_snapshot(
            repository="doctor/local",
            control_view={
                "schema": "ATLAS_GLOBAL_CONTROL_VIEW_V1",
                "view_fingerprint": "a" * 64,
                "agent_status": "NONE",
                "repository": "doctor/local",
                "panels": {},
            },
            telemetry_packet={
                "schema": "ATLAS_COORDINATION_TELEMETRY_V1",
                "telemetry_fingerprint": "b" * 64,
                "agent_status": "NONE",
                "categories": {},
            },
            clock=lambda: "2026-09-09T00:00:00Z",
        )
        errors = validate_studio_snapshot(packet)
        add(
            "schema_validate",
            not errors and packet["schema"] == SCHEMA_CONST,
            "ok" if not errors else "; ".join(errors[:5]),
        )
    except Exception as exc:  # noqa: BLE001
        add("schema_validate", False, f"{type(exc).__name__}:{exc}")

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"atlas-studio doctor version={__version__} ok={report['ok']}")
        for check in report["checks"]:
            mark = "PASS" if check["ok"] else "FAIL"
            print(f"  {mark} {check['name']}: {check['detail'][:120]}")
        print("HONESTY: STUDIO_UI!=AUTHORITY / ATLAS_DAEMON=AUTHORITATIVE_RUNTIME")
    return 0 if report["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas-studio",
        description=(
            "Atlas Studio A0 read-only projection "
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

    doc = sub.add_parser("doctor", help="Import/honesty/schema diagnostics")
    doc.add_argument("--json", action="store_true")
    doc.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
