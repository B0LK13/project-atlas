"""Additive Atlas 3 CLI parsers and dispatch. Existing commands stay unchanged."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project_atlas.atlas3.adv_bind import bind_adversarial_result
from project_atlas.atlas3.capabilities import list_capabilities
from project_atlas.atlas3.causal import compile_causal_graph
from project_atlas.atlas3.compat import prove_compatibility
from project_atlas.atlas3.contracts import OPS_RELATIVE, Atlas3Error, read_json
from project_atlas.atlas3.decided import compile_decided_by
from project_atlas.atlas3.decision_explorer import compile_decision_explorer
from project_atlas.atlas3.engineering_nodes import compile_engineering_nodes
from project_atlas.atlas3.estate_nodes import compile_estate_nodes
from project_atlas.atlas3.file_graph import compile_file_graph
from project_atlas.atlas3.home import compile_home
from project_atlas.atlas3.impact import compile_impact_explorer
from project_atlas.atlas3.inventory import compile_inventory
from project_atlas.atlas3.iv_bind import bind_independent_verification
from project_atlas.atlas3.ledger import append_event, ledger_status, list_events, query_events
from project_atlas.atlas3.memory.claude import import_claude_export
from project_atlas.atlas3.memory.connector import provider_capabilities
from project_atlas.atlas3.memory.gemini import import_gemini_export
from project_atlas.atlas3.memory.honesty import wrap_intent_state_honesty
from project_atlas.atlas3.memory.intent import extract_intent_report
from project_atlas.atlas3.memory.lineage import build_session_lineage
from project_atlas.atlas3.memory.providers import memory_providers
from project_atlas.atlas3.memory.routing import assert_items_project_scope
from project_atlas.atlas3.memory.search import search_memory
from project_atlas.atlas3.proof import evaluate_proof
from project_atlas.atlas3.provider_register import (
    assert_cli_design,
    compile_provider_register,
)
from project_atlas.atlas3.pulse import compile_pulse
from project_atlas.atlas3.rel_expand import expand_relationships
from project_atlas.atlas3.start import compile_start
from project_atlas.atlas3.surface import compile_surface_contract, evaluate_surface_claim
from project_atlas.atlas3.timeline import compile_timeline
from project_atlas.atlas3.transport import prove_transport_is_not_authority
from project_atlas.atlas3.truth_graph import compile_truth_graph
from project_atlas.atlas3.twin_health import compile_twin_health

ATLAS3_COMMANDS = frozenset(
    {
        "pulse",
        "start",
        "proof",
        "memory",
        "capabilities",
        "compatibility",
        "inventory",
        "file-graph",
        "estate-nodes",
        "causal-graph",
        "decided-by",
        "rel-expand",
        "iv-bind",
        "adv-bind",
        "surface-contract",
        "transport-authority",
        "provider-register",
        "impact-explorer",
        "twin-health",
        "home",
        "timeline",
        "decision-explorer",
        "truth-graph",
    }
)


def register_atlas3_parsers(subparsers: argparse._SubParsersAction[Any]) -> None:
    pulse = subparsers.add_parser(
        "pulse",
        help=(
            "Atlas 3 Pulse lens (derived; changed/matters/stale/conflicts/"
            "failed/decided/attention/next)."
        ),
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
    start.add_argument(
        "--freshness",
        default="UNKNOWN",
        choices=["CURRENT", "ALLOW_STALE_HISTORICAL", "UNKNOWN"],
        help="Freshness requirement. CURRENT refuses stale-as-current-truth.",
    )
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
    claude = mem_sub.add_parser(
        "claude",
        help="Import a Claude JSON export fixture (not a live history API).",
    )
    claude.add_argument("--export", type=Path, required=True, help="Claude JSON export path.")
    claude.add_argument("--conversation-id", required=True, help="Conversation id to bind.")
    claude.add_argument("--project", default=None, help="Optional project id tag.")
    gemini = mem_sub.add_parser(
        "gemini",
        help="Import a Gemini JSON export fixture (not a live history API).",
    )
    gemini.add_argument("--export", type=Path, required=True, help="Gemini JSON export path.")
    gemini.add_argument("--conversation-id", required=True, help="Conversation id to bind.")
    gemini.add_argument("--project", default=None, help="Optional project id tag.")
    for name in ("conflicts", "stale", "intent", "lineage"):
        parser = mem_sub.add_parser(
            name, help=f"Memory {name} (requires prior reconcile artifact)."
        )
        parser.add_argument("--vault", type=Path, required=True)
        parser.add_argument("--project", required=True)
    honesty = mem_sub.add_parser(
        "honesty",
        help="Intent vs current-state honesty wrapper (does not collapse layers).",
        description="Intent vs current-state honesty wrapper (does not collapse layers).",
    )
    honesty.add_argument("--vault", type=Path, required=True)
    honesty.add_argument("--project", required=True)

    ledger = subparsers.add_parser(
        "ledger",
        help="Atlas 3 universal event ledger (derived; does not write ops_events).",
    )
    led_sub = ledger.add_subparsers(dest="ledger_command", required=True)
    append = led_sub.add_parser("append")
    append.add_argument("--vault", type=Path, required=True)
    append.add_argument("--project", required=True)
    append.add_argument("--kind", default=None)
    append.add_argument("--event-type", default=None)
    append.add_argument("--summary", required=True)
    append.add_argument("--plane", default="engineering")
    listed = led_sub.add_parser("list")
    listed.add_argument("--vault", type=Path, required=True)
    listed.add_argument("--project", required=True)
    listed.add_argument("--kind", default=None)
    listed.add_argument("--event-type", default=None)
    queried = led_sub.add_parser("query")
    queried.add_argument("--vault", type=Path, required=True)
    queried.add_argument("--project", required=True)
    queried.add_argument("--event-type", default=None)
    queried.add_argument("--kind", default=None)
    queried.add_argument("--observed-from", default=None)
    queried.add_argument("--observed-to", default=None)
    nodes = led_sub.add_parser(
        "nodes",
        help="Project PR/commit/test/build nodes from the ledger (not git history).",
        description="Project PR/commit/test/build nodes from the ledger (not git history).",
    )
    nodes.add_argument("--vault", type=Path, required=True)
    nodes.add_argument("--project", required=True)

    caps = subparsers.add_parser(
        "capabilities",
        help="Atlas 3 semantic capability registry (surfaces are projections).",
    )
    caps.add_argument("--json", action="store_true")

    compatibility = subparsers.add_parser(
        "compatibility",
        help="Atlas 3 2.x-to-3.x compatibility prover (additive; no truth write).",
    )
    compatibility.add_argument("--vault", type=Path, required=True)
    compatibility.add_argument("--json", action="store_true")

    inventory = subparsers.add_parser(
        "inventory",
        help="Atlas 3 repository/component inventory (derived; not Truth Core).",
        description="Atlas 3 repository/component inventory (derived; not Truth Core).",
    )
    inventory.add_argument("--vault", type=Path, required=True)
    inventory.add_argument("--project", required=True)
    inventory.add_argument("--json", action="store_true")

    file_graph = subparsers.add_parser(
        "file-graph",
        help="Atlas 3 file/symbol graph (declared; does not walk host trees).",
        description="Atlas 3 file/symbol graph (declared; does not walk host trees).",
    )
    file_graph.add_argument("--vault", type=Path, required=True)
    file_graph.add_argument("--project", required=True)
    file_graph.add_argument("--json", action="store_true")

    estate_nodes = subparsers.add_parser(
        "estate-nodes",
        help="Atlas 3 service/environment nodes (declared fixture; not authentic estate).",
        description="Atlas 3 service/environment nodes (declared fixture; not authentic estate).",
    )
    estate_nodes.add_argument("--vault", type=Path, required=True)
    estate_nodes.add_argument("--project", required=True)
    estate_nodes.add_argument("--json", action="store_true")

    causal_graph = subparsers.add_parser(
        "causal-graph",
        help="Atlas 3 causal graph (declared CAUSED_BY; graph is not authority).",
        description="Atlas 3 causal graph (declared CAUSED_BY; graph is not authority).",
    )
    causal_graph.add_argument("--vault", type=Path, required=True)
    causal_graph.add_argument("--project", required=True)
    causal_graph.add_argument("--json", action="store_true")

    decided_by = subparsers.add_parser(
        "decided-by",
        help="Atlas 3 DECIDED_BY provenance (owner_origin required).",
        description="Atlas 3 DECIDED_BY provenance (owner_origin required).",
    )
    decided_by.add_argument("--vault", type=Path, required=True)
    decided_by.add_argument("--project", required=True)
    decided_by.add_argument("--json", action="store_true")

    rel_expand = subparsers.add_parser(
        "rel-expand",
        help="Atlas 3 derived relationship expansion (graph is not authority).",
        description="Atlas 3 derived relationship expansion (graph is not authority).",
    )
    rel_expand.add_argument("--vault", type=Path, required=True)
    rel_expand.add_argument("--project", required=True)
    rel_expand.add_argument("--json", action="store_true")

    iv_bind = subparsers.add_parser(
        "iv-bind",
        help="Atlas 3 IV binding (exact HEAD/TREE; does not grant merge).",
        description="Atlas 3 IV binding (exact HEAD/TREE; does not grant merge).",
    )
    iv_bind.add_argument("--package", required=True)
    iv_bind.add_argument("--candidate-head", required=True)
    iv_bind.add_argument("--candidate-tree", required=True)
    iv_bind.add_argument("--observed-head", required=True)
    iv_bind.add_argument("--observed-tree", required=True)
    iv_bind.add_argument("--iv-result", required=True, choices=["PASS", "FAIL"])
    iv_bind.add_argument("--verifier", required=True)

    adv_bind = subparsers.add_parser(
        "adv-bind",
        help="Atlas 3 ADV binding (exact HEAD/TREE; does not grant merge).",
        description="Atlas 3 ADV binding (exact HEAD/TREE; does not grant merge).",
    )
    adv_bind.add_argument("--package", required=True)
    adv_bind.add_argument("--candidate-head", required=True)
    adv_bind.add_argument("--candidate-tree", required=True)
    adv_bind.add_argument("--observed-head", required=True)
    adv_bind.add_argument("--observed-tree", required=True)
    adv_bind.add_argument("--adv-result", required=True, choices=["PASS", "FAIL"])
    adv_bind.add_argument("--adv-id", required=True)

    surface_contract = subparsers.add_parser(
        "surface-contract",
        help="Atlas 3 surface contract (CLI/API/Web/TUI/MCP/A2A; not authority).",
        description="Atlas 3 surface contract (CLI/API/Web/TUI/MCP/A2A; not authority).",
    )
    surface_contract.add_argument("--surface", default=None, help="Optional surface id.")
    surface_contract.add_argument(
        "--claim",
        default="projection",
        help="Surface claim (projection/derived/read/transport).",
    )
    surface_contract.add_argument(
        "--transport-status",
        default=None,
        help="Optional transport status. Success is not authority.",
    )

    transport_authority = subparsers.add_parser(
        "transport-authority",
        help="Atlas 3 transport prover (HTTP/CLI/MCP/A2A success is not authority).",
        description="Atlas 3 transport prover (HTTP/CLI/MCP/A2A success is not authority).",
    )
    transport_authority.add_argument("--surface", required=True)
    transport_authority.add_argument("--transport-status", required=True)
    transport_authority.add_argument(
        "--authority-claim",
        default=None,
        help="Forbidden. Transport cannot grant authority claims.",
    )

    provider_register = subparsers.add_parser(
        "provider-register",
        help="Atlas 3 provider-register CLI design (no CLI proliferation).",
        description="Atlas 3 provider-register CLI design (no CLI proliferation).",
    )
    provider_register.add_argument(
        "--propose",
        default=None,
        help="Optional comma-separated proposed commands to check against the allowlist.",
    )

    impact_explorer = subparsers.add_parser(
        "impact-explorer",
        help="Atlas 3 impact explorer data (declared; graph is not authority).",
        description="Atlas 3 impact explorer data (declared; graph is not authority).",
    )
    impact_explorer.add_argument("--vault", type=Path, required=True)
    impact_explorer.add_argument("--project", required=True)

    twin_health = subparsers.add_parser(
        "twin-health",
        help="Atlas 3 twin health (derived; health is not authority).",
        description="Atlas 3 twin health (derived; health is not authority).",
    )
    twin_health.add_argument("--vault", type=Path, required=True)
    twin_health.add_argument("--project", required=True)

    home = subparsers.add_parser(
        "home",
        help="Atlas 3 Home composer (Pulse+Start+twin health; not Truth Core).",
        description="Atlas 3 Home composer (Pulse+Start+twin health; not Truth Core).",
    )
    home.add_argument("--vault", type=Path, required=True)
    home.add_argument("--project", required=True)
    home.add_argument("--budget", type=int, required=True, help="Token/context budget.")
    home.add_argument("--task", default=None, help="Optional current task text.")
    home.add_argument(
        "--freshness",
        default="UNKNOWN",
        choices=["CURRENT", "ALLOW_STALE_HISTORICAL", "UNKNOWN"],
        help="Freshness requirement. CURRENT refuses stale-as-current-truth.",
    )

    timeline = subparsers.add_parser(
        "timeline",
        help="Atlas 3 Timeline (declared valid-time; wall-clock is not valid-time).",
        description="Atlas 3 Timeline (declared valid-time; wall-clock is not valid-time).",
    )
    timeline.add_argument("--vault", type=Path, required=True)
    timeline.add_argument("--project", required=True)

    decision_explorer = subparsers.add_parser(
        "decision-explorer",
        help=(
            "Atlas 3 Decision Explorer (declared; model paraphrase is not an owner decision)."
        ),
        description=(
            "Atlas 3 Decision Explorer (declared; model paraphrase is not an owner decision)."
        ),
    )
    decision_explorer.add_argument("--vault", type=Path, required=True)
    decision_explorer.add_argument("--project", required=True)

    truth_graph = subparsers.add_parser(
        "truth-graph",
        help="Atlas 3 Truth Graph UX (declared; graph is not authority).",
        description="Atlas 3 Truth Graph UX (declared; graph is not authority).",
    )
    truth_graph.add_argument("--vault", type=Path, required=True)
    truth_graph.add_argument("--project", required=True)


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
                    freshness_requirement=str(getattr(args, "freshness", "UNKNOWN")),
                ),
                as_json=True,
            )
        if command == "capabilities":
            return _dump(list_capabilities(), as_json=True)
        if command == "compatibility":
            return _dump(prove_compatibility(args.vault), as_json=True)
        if command == "inventory":
            return _dump(compile_inventory(args.vault, args.project), as_json=True)
        if command == "file-graph":
            return _dump(compile_file_graph(args.vault, args.project), as_json=True)
        if command == "estate-nodes":
            return _dump(compile_estate_nodes(args.vault, args.project), as_json=True)
        if command == "causal-graph":
            return _dump(compile_causal_graph(args.vault, args.project), as_json=True)
        if command == "decided-by":
            return _dump(compile_decided_by(args.vault, args.project), as_json=True)
        if command == "rel-expand":
            return _dump(expand_relationships(args.vault, args.project), as_json=True)
        if command == "iv-bind":
            return _dump(
                bind_independent_verification(
                    candidate_head=str(args.candidate_head),
                    candidate_tree=str(args.candidate_tree),
                    observed_head=str(args.observed_head),
                    observed_tree=str(args.observed_tree),
                    iv_result=str(args.iv_result),
                    verifier_id=str(args.verifier),
                    package_id=str(args.package),
                ),
                as_json=True,
            )
        if command == "truth-graph":
            return _dump(compile_truth_graph(args.vault, args.project), as_json=True)
        if command == "decision-explorer":
            return _dump(compile_decision_explorer(args.vault, args.project), as_json=True)
        if command == "timeline":
            return _dump(compile_timeline(args.vault, args.project), as_json=True)
        if command == "home":
            return _dump(
                compile_home(
                    args.vault,
                    args.project,
                    token_budget=int(args.budget),
                    current_task=getattr(args, "task", None),
                    freshness_requirement=str(getattr(args, "freshness", "UNKNOWN")),
                ),
                as_json=True,
            )
        if command == "twin-health":
            return _dump(compile_twin_health(args.vault, args.project), as_json=True)
        if command == "impact-explorer":
            return _dump(compile_impact_explorer(args.vault, args.project), as_json=True)
        if command == "provider-register":
            proposed = getattr(args, "propose", None)
            if proposed:
                return _dump(
                    assert_cli_design(str(proposed).split(",")),
                    as_json=True,
                )
            return _dump(compile_provider_register(), as_json=True)
        if command == "transport-authority":
            return _dump(
                prove_transport_is_not_authority(
                    surface=str(args.surface),
                    transport_status=str(args.transport_status),
                    authority_claim=getattr(args, "authority_claim", None),
                ),
                as_json=True,
            )
        if command == "surface-contract":
            if getattr(args, "surface", None):
                return _dump(
                    evaluate_surface_claim(
                        surface=str(args.surface),
                        claim=str(getattr(args, "claim", "projection")),
                        transport_status=getattr(args, "transport_status", None),
                    ),
                    as_json=True,
                )
            return _dump(compile_surface_contract(), as_json=True)
        if command == "adv-bind":
            return _dump(
                bind_adversarial_result(
                    candidate_head=str(args.candidate_head),
                    candidate_tree=str(args.candidate_tree),
                    observed_head=str(args.observed_head),
                    observed_tree=str(args.observed_tree),
                    adv_result=str(args.adv_result),
                    adv_id=str(args.adv_id),
                    package_id=str(args.package),
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
            if sub == "claude":
                envelopes = import_claude_export(
                    Path(args.export),
                    conversation_id=str(args.conversation_id),
                    project_id=getattr(args, "project", None),
                )
                return _dump(
                    {
                        "package": "AT3-037",
                        "provider": "claude",
                        "import_mode": "EXPORT",
                        "conversation_id": str(args.conversation_id),
                        "project_id": getattr(args, "project", None),
                        "envelope_count": len(envelopes),
                        "envelopes": envelopes,
                        "conversation_sync": "NOT_IMPLEMENTED",
                        "live_full_history_sync": False,
                        "promoted_to_truth_core": 0,
                    },
                    as_json=True,
                )
            if sub == "gemini":
                envelopes = import_gemini_export(
                    Path(args.export),
                    conversation_id=str(args.conversation_id),
                    project_id=getattr(args, "project", None),
                )
                return _dump(
                    {
                        "package": "AT3-038",
                        "provider": "gemini",
                        "import_mode": "EXPORT",
                        "conversation_id": str(args.conversation_id),
                        "project_id": getattr(args, "project", None),
                        "envelope_count": len(envelopes),
                        "envelopes": envelopes,
                        "conversation_sync": "NOT_IMPLEMENTED",
                        "live_full_history_sync": False,
                        "promoted_to_truth_core": 0,
                    },
                    as_json=True,
                )
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
            if sub in {"search", "conflicts", "stale", "intent", "lineage", "honesty"}:
                recon = read_json(
                    Path(args.vault) / OPS_RELATIVE / "memory" / args.project / "reconcile.json"
                )
                items = ((recon or {}).get("reconciliation") or {}).get("items") or []
                assert_items_project_scope(items, project_id=args.project)
                if sub == "lineage":
                    return _dump(
                        build_session_lineage(items, requested_project_id=args.project),
                        as_json=True,
                    )
                if sub == "honesty":
                    return _dump(
                        wrap_intent_state_honesty(items, requested_project_id=args.project),
                        as_json=True,
                    )
                if sub == "intent":
                    return _dump(
                        extract_intent_report(items, requested_project_id=args.project),
                        as_json=True,
                    )
                if sub == "search":
                    return _dump(
                        search_memory(items, args.query, project_id=args.project),
                        as_json=True,
                    )
                if sub == "conflicts":
                    return _dump(
                        ((recon or {}).get("reconciliation") or {}).get("conflicts")
                        or {"conflicted_history": False, "reason": "NO_RECONCILE"},
                        as_json=True,
                    )
                stale = ((recon or {}).get("reconciliation") or {}).get("stale_memories") or []
                assert_items_project_scope(stale, project_id=args.project)
                return _dump({"stale_count": len(stale), "items": stale}, as_json=True)
        if command == "ledger":
            sub = getattr(args, "ledger_command", "")
            if sub == "append":
                return _dump(
                    append_event(
                        args.vault,
                        args.project,
                        kind=getattr(args, "kind", None),
                        event_type=getattr(args, "event_type", None),
                        source_plane=args.plane,
                        summary=args.summary,
                    ),
                    as_json=True,
                )
            if sub == "list":
                return _dump(
                    {
                        "events": list_events(
                            args.vault,
                            args.project,
                            kind=getattr(args, "kind", None),
                            event_type=getattr(args, "event_type", None),
                        )
                    },
                    as_json=True,
                )
            if sub == "query":
                return _dump(
                    {
                        "events": query_events(
                            args.vault,
                            project_id=args.project,
                            event_type=getattr(args, "event_type", None),
                            kind=getattr(args, "kind", None),
                            observed_from=getattr(args, "observed_from", None),
                            observed_to=getattr(args, "observed_to", None),
                        )
                    },
                    as_json=True,
                )
            if sub == "nodes":
                return _dump(compile_engineering_nodes(args.vault, args.project), as_json=True)
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
