"""Additive Atlas 3 CLI parsers and dispatch. Existing commands stay unchanged."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_atlas.atlas3.contracts import OPS_RELATIVE, Atlas3Error, read_json
from project_atlas.atlas3.ledger import append_event, ledger_status, list_events
from project_atlas.atlas3.memory.connector import provider_capabilities
from project_atlas.atlas3.memory.providers import memory_providers
from project_atlas.atlas3.memory.search import search_memory
from project_atlas.atlas3.proof import evaluate_proof
from project_atlas.atlas3.pulse import compile_pulse
from project_atlas.atlas3.start import compile_start

ATLAS3_COMMANDS = frozenset({"pulse", "start", "proof", "memory"})


def register_atlas3_parsers(subparsers: argparse._SubParsersAction[Any]) -> None:
    pulse = subparsers.add_parser(
        "pulse",
        help="Atlas 3 Pulse lens (derived; changed/matters/stale/conflicts/failed/decided/next).",
    )
    pulse.add_argument("--vault", type=Path, required=True, help="Vault directory.")
    pulse.add_argument("--project", required=True, help="Project id.")
    pulse.add_argument("--json", action="store_true")

    start = subparsers.add_parser(
        "start",
        help="Atlas 3 Start briefing (requires --budget; no RAG dump).",
    )
    start.add_argument("--vault", type=Path, required=True)
    start.add_argument("--project", required=True)
    start.add_argument("--budget", type=int, required=True, help="Token/context budget.")
    start.add_argument("--task", default=None, help="Optional current task text.")
    start.add_argument("--json", action="store_true")

    proof = subparsers.add_parser(
        "proof",
        help="Atlas 3 agent proof-of-work (model claim != proof).",
    )
    proof.add_argument("task_id")
    proof.add_argument("--vault", type=Path, required=True)
    proof.add_argument("--project", required=True)
    proof.add_argument("--evidence", default=None, help="Optional JSON object of stage evidence.")
    proof.add_argument("--model-claims-complete", action="store_true")
    proof.add_argument("--json", action="store_true")

    memory = subparsers.add_parser(
        "memory",
        help="Atlas 3 LLM memory (search/status/providers; not live full-history sync).",
    )
    mem_sub = memory.add_subparsers(dest="memory_command", required=True)
    mem_sub.add_parser("providers", help="Honest provider capability matrix.")
    status = mem_sub.add_parser("status", help="Connector + ledger status.")
    status.add_argument("--vault", type=Path, required=True)
    status.add_argument("--project", required=True)
    search = mem_sub.add_parser("search", help="Search extracted memory items.")
    search.add_argument("query")
    search.add_argument("--vault", type=Path, required=True)
    search.add_argument("--project", required=True)
    sync = mem_sub.add_parser(
        "sync",
        help="Report sync capability honesty (does not invent live provider APIs).",
    )
    sync.add_argument("--json", action="store_true")
    for name in ("conflicts", "stale"):
        parser = mem_sub.add_parser(
            name, help=f"Memory {name} (requires prior reconcile artifact)."
        )
        parser.add_argument("--vault", type=Path, required=True)
        parser.add_argument("--project", required=True)

    ledger = subparsers.add_parser(
        "ledger",
        help="Atlas 3 universal event ledger (derived; does not write ops_events).",
    )
    led_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    append = led_sub.add_parser("append")
    append.add_argument("--vault", type=Path, required=True)
    append.add_argument("--project", required=True)
    append.add_argument("--kind", required=True)
    append.add_argument("--summary", required=True)
    append.add_argument("--plane", default="engineering")
    listed = led_sub.add_parser("list")
    listed.add_argument("--vault", type=Path, required=True)
    listed.add_argument("--project", required=True)


def _dump(payload: dict[str, Any], *, as_json: bool) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def dispatch_atlas3(args: argparse.Namespace) -> int | None:
    command = getattr(args, "command", None)
    if command not in ATLAS3_COMMANDS and command != "ledger":
        return None
    try:
        if command == "pulse":
            return _dump(compile_pulse(args.vault, args.project), as_json=True)
        if command == "start":
            return _dump(
                compile_start(
                    args.vault,
                    args.project,
                    token_budget=int(args.budget),
                    current_task=getattr(args, "task", None),
                ),
                as_json=True,
            )
        if command == "proof":
            evidence = None
            if getattr(args, "evidence", None):
                evidence = json.loads(args.evidence)
            return _dump(
                evaluate_proof(
                    args.vault,
                    args.task_id,
                    project_id=args.project,
                    evidence=evidence,
                    model_claims_complete=bool(getattr(args, "model_claims_complete", False)),
                ),
                as_json=True,
            )
        if command == "memory":
            sub = getattr(args, "memory_command", "")
            if sub == "providers":
                return _dump(memory_providers(), as_json=True)
            if sub == "sync":
                caps = provider_capabilities()
                caps["synchronized"] = False
                caps["note"] = (
                    "atlas memory sync reports capability honesty only; "
                    "live full-history sync is not implemented."
                )
                return _dump(caps, as_json=True)
            if sub == "status":
                vault = Path(args.vault)
                recon = read_json(
                    vault / OPS_RELATIVE / "memory" / args.project / "reconcile.json"
                )
                return _dump(
                    {
                        "providers": provider_capabilities(),
                        "ledger": ledger_status(args.vault, args.project),
                        "reconcile_present": recon is not None,
                        "live_full_history_sync": False,
                    },
                    as_json=True,
                )
            if sub in {"search", "conflicts", "stale"}:
                recon = read_json(
                    Path(args.vault) / OPS_RELATIVE / "memory" / args.project / "reconcile.json"
                )
                items = ((recon or {}).get("reconciliation") or {}).get("items") or []
                if sub == "search":
                    return _dump(search_memory(items, args.query), as_json=True)
                if sub == "conflicts":
                    return _dump(
                        ((recon or {}).get("reconciliation") or {}).get("conflicts")
                        or {"conflicted_history": False, "reason": "NO_RECONCILE"},
                        as_json=True,
                    )
                stale = ((recon or {}).get("reconciliation") or {}).get("stale_memories") or []
                return _dump({"stale_count": len(stale), "items": stale}, as_json=True)
        if command == "ledger":
            sub = getattr(args, "ledger_command", "")
            if sub == "append":
                return _dump(
                    append_event(
                        args.vault,
                        args.project,
                        kind=args.kind,
                        source_plane=args.plane,
                        summary=args.summary,
                    ),
                    as_json=True,
                )
            if sub == "list":
                return _dump(
                    {"events": list_events(args.vault, args.project)},
                    as_json=True,
                )
    except Atlas3Error as exc:
        print(json.dumps({"ok": False, "error": exc.code, "detail": str(exc)}, sort_keys=True))
        return 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": "ATLAS3_ERROR", "detail": str(exc)},
                sort_keys=True,
            )
        )
        return 1
    return None
