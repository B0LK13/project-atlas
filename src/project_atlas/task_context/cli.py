"""CLI handlers for ``atlas task-context`` (ATLAS-TASK-CONTEXT-AND-CONTINUITY-001)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_atlas.task_context.assemble import (
    assemble_packet,
    check_freshness,
    compare_packets,
    load_packet,
    write_packet,
)
from project_atlas.task_context.models import TaskContextError
from project_atlas.task_context.views import render_human_summary, render_view

EXIT_OK, EXIT_ERROR, EXIT_USAGE = 0, 1, 2


def _print(payload: dict[str, Any] | str, *, as_json: bool) -> None:
    if isinstance(payload, str):
        print(payload)
        return
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True) + "\n", end="")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True) + "\n", end="")


def register_parser(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "task-context",
        help=(
            "Compose/inspect task-bound context packets "
            "(AS-TASK-CONTEXT-AND-CONTINUITY-001; != authority/dispatch)."
        ),
    )
    sub = parser.add_subparsers(dest="task_context_command", required=True)

    compose = sub.add_parser("compose", help="Assemble a task context packet.")
    compose.add_argument("--contract", type=Path, required=True)
    compose.add_argument("--workspace", type=Path, required=True)
    compose.add_argument("--evidence", type=Path, default=None)
    compose.add_argument("--budget-chars", type=int, default=48_000)
    compose.add_argument("--output", type=Path, required=True)
    compose.add_argument("--json", action="store_true")

    inspect_p = sub.add_parser("inspect", help="Show provenance and selection reasons.")
    inspect_p.add_argument("--packet", type=Path, required=True)
    inspect_p.add_argument("--json", action="store_true")

    budget = sub.add_parser("budget", help="Show budget allocation report.")
    budget.add_argument("--packet", type=Path, required=True)
    budget.add_argument("--json", action="store_true")

    fresh = sub.add_parser("freshness", help="Recheck packet against workspace/contract.")
    fresh.add_argument("--packet", type=Path, required=True)
    fresh.add_argument("--workspace", type=Path, required=True)
    fresh.add_argument("--contract", type=Path, default=None)
    fresh.add_argument("--json", action="store_true")

    diff = sub.add_parser("diff", help="Compare two packet versions.")
    diff.add_argument("--left", type=Path, required=True)
    diff.add_argument("--right", type=Path, required=True)
    diff.add_argument("--json", action="store_true")

    export = sub.add_parser("export", help="Export executor or reviewer view.")
    export.add_argument("--packet", type=Path, required=True)
    export.add_argument(
        "--view",
        choices=("executor", "reviewer", "continuation"),
        required=True,
    )
    export.add_argument(
        "--workspace-inspectable",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    export.add_argument("--json", action="store_true")

    cont = sub.add_parser("continuation", help="Generate continuation view from evidence.")
    cont.add_argument("--packet", type=Path, required=True)
    cont.add_argument(
        "--workspace-inspectable",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    cont.add_argument("--json", action="store_true")


def run(args: argparse.Namespace) -> int:
    try:
        return _run(args)
    except TaskContextError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "code": exc.code}, sort_keys=True))
        return EXIT_ERROR
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return EXIT_ERROR


def _run(args: argparse.Namespace) -> int:
    cmd = args.task_context_command
    as_json = bool(getattr(args, "json", False))

    if cmd == "compose":
        packet = assemble_packet(
            contract=args.contract,
            workspace_root=args.workspace,
            evidence_path=args.evidence,
            budget_chars=args.budget_chars,
        )
        write_packet(packet, args.output)
        if as_json:
            _print(packet.model_dump(mode="json"), as_json=True)
        else:
            print(render_human_summary(packet))
            print(f"wrote: {args.output}")
        return EXIT_OK

    if cmd == "inspect":
        packet = load_packet(args.packet)
        payload = {
            "packet_id": packet.packet_id,
            "content_digest": packet.content_digest,
            "contract": packet.contract.model_dump(mode="json"),
            "selection_limits": list(packet.selection_limits),
            "fragments": [
                {
                    "fragment_id": f.fragment_id,
                    "trust_layer": f.trust_layer.value,
                    "tier": f.tier.value,
                    "included": f.included,
                    "exclusion_reason": f.exclusion_reason,
                    "source_path": f.source_path,
                    "source_identity": (
                        f.source_identity.model_dump(mode="json") if f.source_identity else None
                    ),
                    "reasons": [r.model_dump(mode="json") for r in f.selection_reasons],
                    "chars": f.char_size,
                }
                for f in packet.fragments
            ],
            "uncertainties": [u.model_dump(mode="json") for u in packet.uncertainties],
            "honesty": packet.honesty,
        }
        _print(payload, as_json=True)
        return EXIT_OK

    if cmd == "budget":
        packet = load_packet(args.packet)
        payload = (
            packet.budget_report.model_dump(mode="json")
            if packet.budget_report
            else {"error": "no budget_report"}
        )
        _print(payload, as_json=True)
        return EXIT_OK

    if cmd == "freshness":
        report = check_freshness(
            args.packet,
            workspace_root=args.workspace,
            contract_path=args.contract,
        )
        _print(report, as_json=True)
        return EXIT_OK

    if cmd == "diff":
        report = compare_packets(args.left, args.right)
        _print(report, as_json=True)
        return EXIT_OK

    if cmd == "export":
        packet = load_packet(args.packet)
        view = render_view(
            packet,
            args.view,
            workspace_inspectable=bool(args.workspace_inspectable),
        )
        _print(view, as_json=True)
        return EXIT_OK

    if cmd == "continuation":
        packet = load_packet(args.packet)
        view = render_view(
            packet,
            "continuation",
            workspace_inspectable=bool(args.workspace_inspectable),
        )
        _print(view, as_json=True)
        return EXIT_OK

    return EXIT_USAGE
