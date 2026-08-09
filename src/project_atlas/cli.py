"""Command-line interface for Project Atlas (A-007).

Exit codes:
- 0: success (``atlas validate``: also WARNING/INFO-only findings — AS-H-010);
- 1: operational error (unsafe path, non-empty target, I/O failure), or
  ``atlas validate`` ERROR findings / legacy validation errors (AS-H-010);
- 2: usage error (argparse).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from project_atlas import __version__
from project_atlas.backup import (
    BackupError,
    create_snapshot,
    restore_bundle,
    verify_bundle,
)
from project_atlas.config import load_config
from project_atlas.discovery import discover, write_manifest
from project_atlas.domain.knowledge_query import KnowledgeQueryErrorCode, QueryShape
from project_atlas.event_retention import (
    RetentionError,
    apply_event_retention,
)
from project_atlas.graph_acceptance import (
    GraphAcceptanceError,
    accept_graphify_artifacts,
    inspect_acceptance,
)
from project_atlas.graph_relationships import (
    GraphRelationshipError,
    inspect_relationship_store,
    store_from_acceptance,
    write_relationship_outputs,
)
from project_atlas.graph_resolution import (
    GraphResolutionError,
    inspect_resolution,
    resolve_from_acceptance,
    write_resolution_outputs,
)
from project_atlas.indexes import build_indexes
from project_atlas.ingestion import ingest
from project_atlas.knowledge_query import (
    KnowledgeQueryError,
    answer_to_json,
    diagnostic_to_json,
    list_authoritative,
    list_temporal,
    query_diagnostic_from_error,
    query_knowledge,
    query_knowledge_fields,
)
from project_atlas.logging import configure_logging, get_logger
from project_atlas.migrations.claim_v2_migration import migrate_v2
from project_atlas.ops_events import (
    OpsEventError,
    apply_retention,
    read_events,
    record_health_transition,
)
from project_atlas.ops_health import (
    OpsHealthError,
    emit_health_snapshot,
    snapshot_to_json,
)
from project_atlas.ops_report import (
    OpsReportError,
    emit_ops_report,
    report_to_json,
)
from project_atlas.portfolio import build_portfolio
from project_atlas.receipt_revocation import (
    RevocationError,
    inventory_with_revocations,
    list_revocations,
    receipt_trust_disposition,
    revoke_receipt,
)
from project_atlas.scaffold import ScaffoldError, create_scaffold
from project_atlas.validation import validate, validation_exit_code
from project_atlas.xproj_duplicates import (
    XprojDuplicateError,
    detect_project_duplicates,
    inspect_duplicate_detection,
    write_duplicate_outputs,
)
from project_atlas.xproj_edges import (
    XprojEdgeError,
    apply_edge_registrations,
    inspect_edge_registry,
    load_edge_registry_state,
    write_edge_outputs,
)
from project_atlas.xproj_registry import (
    XprojRegistryError,
    apply_registrations,
    inspect_registry,
    load_registry_state,
    write_registry_outputs,
)

EXIT_OK = 0
EXIT_ERROR = 1

_log = get_logger("cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Project Atlas - source-backed, offline-first project knowledge compiler.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to a TOML configuration file (default: probe atlas.toml / pyproject.toml).",
    )
    parser.add_argument("--log-level", default=None, help="DEBUG, INFO, WARNING, ERROR, CRITICAL.")
    parser.add_argument("--log-format", choices=["console", "json"], default=None)

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version", help="Print the Project Atlas version.")

    init_parser = subparsers.add_parser("init", help="Create a vault scaffold (FR-001).")
    init_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Vault output directory. Must not exist as a file or non-empty directory.",
    )

    discover_parser = subparsers.add_parser(
        "discover", help="Discover source documents into a manifest (FR-002)."
    )
    discover_parser.add_argument("--source", type=Path, required=True)
    discover_parser.add_argument("--output", type=Path, required=True)

    ingest_parser = subparsers.add_parser(
        "ingest", help="Ingest a source manifest into an OKF Vault (FR-005-FR-008)."
    )
    ingest_parser.add_argument("--manifest", type=Path, required=True)
    ingest_parser.add_argument("--vault", type=Path, required=True)

    indexes_parser = subparsers.add_parser(
        "build-indexes", help="Build deterministic lexical indexes under generated/ (FR-010)."
    )
    indexes_parser.add_argument("--vault", type=Path, required=True)

    portfolio_parser = subparsers.add_parser(
        "build-portfolio",
        help="Build derived portfolio intelligence reports under generated/portfolio/ (AS-MVP-001)",
    )
    portfolio_parser.add_argument("--vault", type=Path, required=True)

    migrate_parser = subparsers.add_parser(
        "migrate-v2",
        help="Migrate claims to Identity v2 and generate an alias map (AS-CORE-003)",
    )
    migrate_parser.add_argument("--vault", type=Path, required=True)
    migrate_parser.add_argument("--project", type=str, required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate Vault structure, provenance links and safety (FR-012)."
    )
    validate_parser.add_argument("--vault", type=Path, required=True)

    accept_graph_parser = subparsers.add_parser(
        "accept-graph",
        help=(
            "Accept inventory-backed Graphify artifacts as derived-only "
            "(AS-GRAPH-001; no authority/claims/relationship store writes)."
        ),
    )
    accept_graph_parser.add_argument("--source", type=Path, required=True)
    accept_graph_parser.add_argument("--manifest", type=Path, required=True)
    accept_graph_parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail closed on first rejection (default: true).",
    )

    resolve_graph_parser = subparsers.add_parser(
        "resolve-graph",
        help=(
            "Resolve accepted Graphify nodes to project-local Atlas entity ids "
            "(AS-GRAPH-002; derived-only; no authority/claims/relationship writes)."
        ),
    )
    resolve_graph_parser.add_argument("--source", type=Path, required=True)
    resolve_graph_parser.add_argument("--manifest", type=Path, required=True)
    resolve_graph_parser.add_argument(
        "--mapping",
        type=Path,
        default=None,
        help="Optional project-local mapping table JSON (deterministic; no remote fetch).",
    )
    resolve_graph_parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help=(
            "Optional vault root for derived emits under generated/graph/resolved/ "
            "and generated/graph/quarantine-candidates/ only."
        ),
    )
    resolve_graph_parser.add_argument(
        "--write",
        action="store_true",
        help="Write optional derived resolution outputs (requires --vault).",
    )
    resolve_graph_parser.add_argument(
        "--project-uuid",
        type=str,
        default=None,
        help=(
            "Optional local project UUID binding for durable project_uuid hits "
            "(ADV-G2-007; unbound/foreign UUID fails closed)."
        ),
    )
    resolve_graph_parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail closed on first rejection (default: true).",
    )

    store_graph_parser = subparsers.add_parser(
        "store-graph",
        help=(
            "Normalize accepted Graphify edges into derived relationship records "
            "(AS-GRAPH-003; derived-only; no authority/claims/CP relationships writes)."
        ),
    )
    store_graph_parser.add_argument("--source", type=Path, required=True)
    store_graph_parser.add_argument("--manifest", type=Path, required=True)
    store_graph_parser.add_argument(
        "--mapping",
        type=Path,
        default=None,
        help="Optional project-local mapping table JSON (deterministic; no remote fetch).",
    )
    store_graph_parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help=(
            "Optional vault root for derived emits under generated/graph/relationships/ "
            "and generated/graph/relationship-quarantine/ only."
        ),
    )
    store_graph_parser.add_argument(
        "--write",
        action="store_true",
        help="Write optional derived relationship outputs (requires --vault).",
    )
    store_graph_parser.add_argument(
        "--project-uuid",
        type=str,
        default=None,
        help=(
            "Optional local project UUID binding for durable project_uuid hits "
            "(passed through AS-GRAPH-002 resolve)."
        ),
    )
    store_graph_parser.add_argument(
        "--max-edges",
        type=int,
        default=None,
        help="Optional edge capacity gate (fail closed when exceeded; ADV-G3-030).",
    )
    store_graph_parser.add_argument(
        "--strict",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fail closed on first rejection (default: true).",
    )

    query_parser = subparsers.add_parser(
        "query",
        help=(
            "Read-only knowledge query over temporal and authoritative state "
            "(AS-CORE-007 point / AS-CORE-008 multi-field)."
        ),
    )
    query_parser.add_argument("--vault", type=Path, required=True)
    query_parser.add_argument("--project", type=str, required=True)
    query_parser.add_argument("--subject", type=str, default=None)
    query_parser.add_argument(
        "--field",
        action="append",
        default=None,
        dest="field_args",
        help=(
            "Field name. Repeat for AS-CORE-008 multi-field composition; "
            "a single --field keeps the AS-CORE-007 point path."
        ),
    )
    query_parser.add_argument(
        "--fields",
        type=str,
        default=None,
        dest="fields_csv",
        help=(
            "Comma-separated field list for AS-CORE-008 multi-field query "
            "(mutually exclusive with --field)."
        ),
    )
    query_parser.add_argument(
        "--kind",
        choices=["authoritative", "temporal", "explain"],
        default="authoritative",
        help="Query kind (distinct from AS-RET-001 retrieval kinds).",
    )
    query_parser.add_argument(
        "--list",
        action="store_true",
        help=(
            "List kind-scoped records for the project "
            "(--kind authoritative|temporal; AS-QUERY-001)."
        ),
    )
    query_parser.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format (json).",
    )

    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be created without writing anything.",
    )

    # AS-OBS-001 / AS-OBS-002 / AS-OBS-003 - operational observability (ops plane only).
    ops_parser = subparsers.add_parser(
        "ops",
        help=(
            "Operational observability commands "
            "(AS-OBS-001 health / AS-OBS-002 events / AS-OBS-003 report; "
            "health != authority)."
        ),
    )
    ops_sub = ops_parser.add_subparsers(dest="ops_command", required=True)
    health_parser = ops_sub.add_parser(
        "health",
        help=(
            "Emit a regenerable operational health snapshot under "
            "generated/ops/ (AS-OBS-001; consume-only collectors)."
        ),
    )
    health_parser.add_argument("--vault", type=Path, required=True)
    health_parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Optional stable project UUID filter (name-only forbidden by contract).",
    )
    health_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the snapshot JSON to stdout (always schema-bound).",
    )
    health_parser.add_argument(
        "--no-write",
        action="store_true",
        help="Collect/normalize only; do not persist generated/ops/health-snapshot.json.",
    )
    # AS-OBS-002 — append-only OPS-EVT-* stream (thin additive CLI).
    events_parser = ops_sub.add_parser(
        "events",
        help=(
            "Read or update the append-only operational event stream under "
            "generated/ops/events/ (AS-OBS-002; events != authority)."
        ),
    )
    events_parser.add_argument("--vault", type=Path, required=True)
    events_parser.add_argument(
        "--json",
        action="store_true",
        help="Print events JSON array to stdout.",
    )
    events_parser.add_argument(
        "--record-health-transitions",
        action="store_true",
        help=(
            "Diff OBS-001 health snapshot vs stored prior and append "
            "OPS-EVT-HEALTH-TRANSITION only when health changes "
            "(no fabricated bootstrap events)."
        ),
    )
    events_parser.add_argument(
        "--retain",
        action="store_true",
        help="Apply count-based retention to the event stream.",
    )
    events_parser.add_argument(
        "--max-events",
        type=int,
        default=10_000,
        help="Retention cap (newest N events; default 10000).",
    )
    # AS-OBS-003 — regenerable ops-report projection (tip-safe; consume-only).
    report_parser = ops_sub.add_parser(
        "report",
        help=(
            "Emit regenerable ops-report JSON/Markdown under "
            "generated/ops/ops-report.* (AS-OBS-003; ops report != authority)."
        ),
    )
    report_parser.add_argument("--vault", type=Path, required=True)
    report_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the ops-report JSON to stdout.",
    )
    report_parser.add_argument(
        "--no-write",
        action="store_true",
        help="Project only; do not persist generated/ops/ops-report.*",
    )
    report_parser.add_argument(
        "--no-events",
        action="store_true",
        help="Skip optional OBS-002 events panel (snapshot-only report).",
    )
    report_parser.add_argument(
        "--archive",
        action="store_true",
        help="Also copy into generated/ops/archive/ops-report-NNNN.* (last-N).",
    )
    report_parser.add_argument(
        "--max-archive",
        type=int,
        default=50,
        help="Archive retention cap (default 50).",
    )

    # AS-XPROJ-001 - global entity registry (derived; explicit registration only).
    xproj_parser = subparsers.add_parser(
        "register-global-entity",
        help=(
            "Apply explicit global-entity / join registrations "
            "(AS-XPROJ-001; derived-only; no name-merge; no authority writes)."
        ),
    )
    xproj_parser.add_argument(
        "--registrations",
        type=Path,
        required=True,
        help="JSON file: {\"registrations\": [ {kind: entity|join, ...}, ... ] }.",
    )
    xproj_parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help=(
            "Optional vault root for derived emits under state/global-entities/ "
            "(joins/ and quarantine-candidates/ only)."
        ),
    )
    xproj_parser.add_argument(
        "--write",
        action="store_true",
        help="Write optional derived registry outputs (requires --vault).",
    )

    # AS-XPROJ-002 - cross-project edges (derived; explicit globals only).
    xproj_edge_parser = subparsers.add_parser(
        "register-global-edge",
        help=(
            "Apply explicit cross-project edge registrations "
            "(AS-XPROJ-002; derived-only; no name-merge; no authority writes)."
        ),
    )
    xproj_edge_parser.add_argument(
        "--edges",
        type=Path,
        required=True,
        help='JSON file: {"edges": [ {kind: edge, ...}, ... ] }.',
    )
    xproj_edge_parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help=(
            "Vault root with XPROJ-001 globals/joins; optional emits under "
            "state/global-entities/edges/ and edge-quarantine/."
        ),
    )
    xproj_edge_parser.add_argument(
        "--write",
        action="store_true",
        help="Write optional derived edge outputs (requires --vault).",
    )

    # AS-XPROJ-003 - duplicate / successor review candidates (derived; no autocollapse).
    xproj_dup_parser = subparsers.add_parser(
        "detect-project-duplicates",
        help=(
            "Detect duplicate / successor / monorepo-overlap review candidates "
            "(AS-XPROJ-003; derived-only; never UUID rewrite / name-merge)."
        ),
    )
    xproj_dup_parser.add_argument(
        "--projects",
        type=Path,
        required=True,
        help='JSON file: {"projects": [ {project_id, ...}, ... ] }.',
    )
    xproj_dup_parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help=(
            "Optional vault root for derived emits under "
            "generated/xproj/duplicate-candidates/ only."
        ),
    )
    xproj_dup_parser.add_argument(
        "--write",
        action="store_true",
        help="Write optional derived duplicate-candidate outputs (requires --vault).",
    )
    xproj_dup_parser.add_argument(
        "--approved-monorepo-root",
        action="append",
        default=[],
        dest="approved_monorepo_roots",
        help="Approved monorepo root for path-prefix overlap (repeatable).",
    )

    # AS-BACKUP-001: verified snapshot / fixture restore (ops durability != authority).
    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help=(
            "Create or verify an Atlas recovery bundle (AS-BACKUP-001; "
            "operational durability != project authority)."
        ),
    )
    snapshot_parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help="Vault root to snapshot (required unless --verify).",
    )
    snapshot_parser.add_argument(
        "--cp",
        type=Path,
        default=None,
        help="Optional control-plane root for D4 receipts.",
    )
    snapshot_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="External bundle output directory (required unless --verify).",
    )
    snapshot_parser.add_argument(
        "--bundle",
        type=Path,
        default=None,
        help="Existing bundle directory (required with --verify).",
    )
    snapshot_parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify MANIFEST digests for an existing bundle; do not create.",
    )
    snapshot_parser.add_argument(
        "--include-d5",
        action="store_true",
        help="Include optional warm D5 derived cache (not used for cold certification).",
    )

    restore_parser = subparsers.add_parser(
        "restore",
        help=(
            "Restore a verified Atlas recovery bundle onto an empty disposable "
            "target (AS-BACKUP-001; fixture certify only)."
        ),
    )
    restore_parser.add_argument("--bundle", type=Path, required=True)
    restore_parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Empty disposable restore target (AT-013 path safety).",
    )
    restore_parser.add_argument(
        "--tier",
        choices=["T0", "T1", "T2", "T3", "T4"],
        default="T3",
        help="Restore tier (default T3 governance-complete cold path omits D5).",
    )
    restore_parser.add_argument(
        "--expect-vault-logical-id",
        type=str,
        default=None,
        help="Refuse restore when bundle vault_logical_id disagrees (RS-06).",
    )

    # AS-INT-009 — raw package / receipt retention (operational; not authority).
    retention_parser = subparsers.add_parser(
        "retention",
        help=(
            "Apply deterministic raw-package and receipt retention caps "
            "(AS-INT-009; count/size only; never Layer B / never INT-010 tombstones)."
        ),
    )
    retention_sub = retention_parser.add_subparsers(
        dest="retention_command", required=True
    )
    retention_apply = retention_sub.add_parser(
        "apply",
        help="Apply retention to sources/agent-events and receipts/agent-events.",
    )
    retention_apply.add_argument("--vault", type=Path, required=True)
    retention_apply.add_argument(
        "--max-packages",
        type=int,
        default=None,
        help="Count cap (lexicographic keep-newest); overrides vault policy when set.",
    )
    retention_apply.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        help="Total byte cap across retained units; overrides vault policy when set.",
    )
    retention_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute victims and write report without deleting.",
    )
    retention_apply.add_argument(
        "--json",
        action="store_true",
        help="Print the retention report JSON to stdout.",
    )

    # AS-INT-011 — receipt revocation / invalidation (operational; not authority).
    revocation_parser = subparsers.add_parser(
        "revocation",
        help=(
            "Record or inspect agent-event receipt revocation / invalidation "
            "(AS-INT-011; never deletes receipt files; never Layer B)."
        ),
    )
    revocation_sub = revocation_parser.add_subparsers(
        dest="revocation_command", required=True
    )
    revocation_revoke = revocation_sub.add_parser(
        "revoke",
        help="Mark a receipt revoked or invalidated (does not delete the file).",
    )
    revocation_revoke.add_argument("--vault", type=Path, required=True)
    revocation_revoke.add_argument("--project", type=str, required=True)
    revocation_revoke.add_argument("--event", type=str, required=True)
    revocation_revoke.add_argument(
        "--reason",
        type=str,
        choices=("operator", "skill_policy", "integrity"),
        default="operator",
        help="Revocation reason (default: operator).",
    )
    revocation_revoke.add_argument(
        "--status",
        type=str,
        choices=("revoked", "invalidated"),
        default=None,
        help="Override default status for the reason.",
    )
    revocation_revoke.add_argument(
        "--detail",
        type=str,
        default=None,
        help="Optional deterministic detail string (no wall-clock).",
    )
    revocation_revoke.add_argument(
        "--json",
        action="store_true",
        help="Print the revocation index JSON to stdout.",
    )
    revocation_list = revocation_sub.add_parser(
        "list",
        help="List receipt revocations from generated/ops/receipt-revocations.json.",
    )
    revocation_list.add_argument("--vault", type=Path, required=True)
    revocation_list.add_argument(
        "--json",
        action="store_true",
        help="Print revocations JSON to stdout.",
    )
    revocation_status = revocation_sub.add_parser(
        "status",
        help="Show active/revoked/invalidated disposition for one receipt.",
    )
    revocation_status.add_argument("--vault", type=Path, required=True)
    revocation_status.add_argument("--project", type=str, required=True)
    revocation_status.add_argument("--event", type=str, required=True)
    revocation_status.add_argument(
        "--json",
        action="store_true",
        help="Print disposition JSON to stdout.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except (OSError, ValueError) as exc:
        configure_logging()
        _log.error("configuration error: %s", exc)
        return EXIT_ERROR

    level = args.log_level or config.logging.level
    log_format = args.log_format or config.logging.format
    configure_logging(level=level, log_format=log_format)

    if args.command == "version":
        print(f"project-atlas {__version__}")
        return EXIT_OK

    if args.command == "init":
        try:
            plan = create_scaffold(args.output, dry_run=args.dry_run)
        except (ScaffoldError, OSError) as exc:
            _log.error("init failed: %s", exc)
            return EXIT_ERROR
        action = "would create" if args.dry_run else "created"
        print(f"{action} vault scaffold at {plan.root}")
        print(f"  directories: {len(plan.directories)}")
        print(f"  files:       {len(plan.files)}")
        if args.dry_run:
            for relative, _ in plan.files:
                print(f"  - {relative}")
        return EXIT_OK

    if args.command == "discover":
        try:
            manifest = discover(
                args.source,
                excludes=config.discovery.exclude_globs,
                max_file_size=config.discovery.max_file_size_bytes,
            )
            write_manifest(manifest, args.output)
        except (OSError, ValueError) as exc:
            _log.error("discover failed: %s", exc)
            return EXIT_ERROR
        print(f"discovered {len(manifest['sources'])} sources")
        print(f"agent event packages: {len(manifest.get('agent_events', []))}")
        print(f"manifest: {args.output}")
        return EXIT_OK

    if args.command == "ingest":
        try:
            result = ingest(args.manifest, args.vault)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            _log.error("ingest failed: %s", exc)
            return EXIT_ERROR
        print(f"ingested {result['documents_ingested']} documents")
        print(f"projects: {result['projects']}")
        print(f"agent events: {result.get('events_ingested', 0)}")
        print(f"quarantined events: {result.get('events_quarantined', 0)}")
        return EXIT_OK

    if args.command == "build-indexes":
        try:
            result = build_indexes(args.vault)
        except (OSError, ValueError) as exc:
            _log.error("build-indexes failed: %s", exc)
            return EXIT_ERROR
        print(f"indexed {result['projects']} projects and {result['sources']} sources")
        return EXIT_OK

    if args.command == "build-portfolio":
        try:
            result = build_portfolio(args.vault)
        except (OSError, ValueError) as exc:
            _log.error("build-portfolio failed: %s", exc)
            return EXIT_ERROR
        print(f"portfolio built for {result['projects']} projects")
        print(f"outputs: {', '.join(result['outputs'])}")
        return EXIT_OK

    if args.command == "migrate-v2":
        try:
            result = migrate_v2(args.vault, args.project)
        except (OSError, RuntimeError, ValueError) as exc:
            _log.error("migration failed: %s", exc)
            return EXIT_ERROR
        print(f"status: {result['status']}")
        if "migrated_claims" in result:
            print(f"migrated claims: {result['migrated_claims']}")
        if "receipt" in result:
            print(f"receipt: {result['receipt']}")
        return EXIT_OK

    if args.command == "validate":
        try:
            result = validate(args.vault)
        except (OSError, ValueError) as exc:
            _log.error("validate failed: %s", exc)
            return EXIT_ERROR
        # AS-H-010: severity→exit (ERROR→1; WARNING/INFO alone→0; preserve usage→2).
        exit_code = validation_exit_code(result)
        if exit_code != EXIT_OK:
            logged: set[str] = set()
            for error in result["errors"]:
                _log.error("validation: %s", error)
                logged.add(error)
            for finding in result.get("findings") or []:
                if not isinstance(finding, dict):
                    continue
                if finding.get("severity") != "error":
                    continue
                message = finding.get("message")
                if isinstance(message, str) and message and message not in logged:
                    _log.error("validation: %s", message)
            return EXIT_ERROR
        for finding in result.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            severity = finding.get("severity")
            message = finding.get("message")
            if not isinstance(message, str) or not message:
                continue
            if severity == "warning":
                _log.warning("validation: %s", message)
            elif severity == "info":
                _log.info("validation: %s", message)
        print(f"validated {result['markdown_files']} Markdown files")
        return EXIT_OK

    if args.command == "accept-graph":
        try:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise GraphAcceptanceError("manifest-not-object")
            receipt = accept_graphify_artifacts(
                project_root=args.source,
                manifest=manifest,
                config=config,
                strict=args.strict,
            )
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _log.error("accept-graph failed: %s", exc)
            return EXIT_ERROR
        summary = inspect_acceptance(receipt)
        print(json.dumps(summary, indent=2, sort_keys=True))
        print(f"accepted: {receipt.accepted_count}")
        print(f"rejected: {receipt.rejected_count}")
        print(f"nodes: {receipt.node_count}")
        print(f"edges: {receipt.edge_count}")
        print(f"semantic: {receipt.semantic_status}")
        print("authority: derived")
        return EXIT_OK

    if args.command == "resolve-graph":
        try:
            if args.write and args.vault is None:
                raise GraphResolutionError("resolve-graph --write requires --vault")
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise GraphResolutionError("manifest-not-object")
            mapping: dict[str, object] | None = None
            if args.mapping is not None:
                loaded = json.loads(args.mapping.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise GraphResolutionError("mapping-table-malformed")
                mapping = loaded
            _receipt, resolution = resolve_from_acceptance(
                project_root=args.source,
                manifest=manifest,
                mapping_table=mapping,
                config=config,
                local_project_uuid=args.project_uuid,
                strict=args.strict,
            )
            written: list[str] = []
            if args.write:
                assert args.vault is not None
                written = write_resolution_outputs(resolution, vault=args.vault)
            summary = inspect_resolution(resolution)
            print(json.dumps(summary, indent=2, sort_keys=True))
            print(f"resolved: {resolution.resolved_count}")
            print(f"quarantined: {resolution.quarantined_count}")
            print("authority: derived")
            if written:
                print(f"written: {len(written)}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _log.error("resolve-graph failed: %s", exc)
            return EXIT_ERROR
        return EXIT_OK

    if args.command == "store-graph":
        try:
            if args.write and args.vault is None:
                raise GraphRelationshipError("store-graph --write requires --vault")
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise GraphRelationshipError("manifest-not-object")
            store_mapping: dict[str, object] | None = None
            if args.mapping is not None:
                loaded = json.loads(args.mapping.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise GraphRelationshipError("mapping-table-malformed")
                store_mapping = loaded
            max_edges = args.max_edges
            _receipt, _resolution, store = store_from_acceptance(
                project_root=args.source,
                manifest=manifest,
                mapping_table=store_mapping,
                config=config,
                local_project_uuid=args.project_uuid,
                strict=args.strict,
                **({"max_edges": max_edges} if max_edges is not None else {}),
            )
            store_written: list[str] = []
            if args.write:
                assert args.vault is not None
                store_written = write_relationship_outputs(store, vault=args.vault)
            summary = inspect_relationship_store(store)
            print(json.dumps(summary, indent=2, sort_keys=True))
            print(f"retained: {store.retained_count}")
            print(f"quarantined: {store.quarantined_count}")
            print("authority: derived")
            if store_written:
                print(f"written: {len(store_written)}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _log.error("store-graph failed: %s", exc)
            return EXIT_ERROR
        return EXIT_OK

    if args.command == "query":
        field_args: list[str] | None = args.field_args
        fields_csv: str | None = args.fields_csv
        diag_shape = QueryShape.UNKNOWN
        diag_field: str | None = None
        diag_fields: list[str] | None = None
        try:
            if args.list:
                if field_args or fields_csv:
                    _log.error("query --list cannot be combined with --field/--fields")
                    return EXIT_ERROR
                diag_shape = QueryShape.LIST
                if args.kind == "authoritative":
                    answers = list_authoritative(args.vault, args.project)
                elif args.kind == "temporal":
                    answers = list_temporal(args.vault, args.project)
                else:
                    # AS-QUERY-001: unsupported list kind → fail-closed diagnostic
                    raise KnowledgeQueryError(
                        KnowledgeQueryErrorCode.UNSUPPORTED_KIND,
                        f"query --list does not support --kind {args.kind!r}",
                    )
                print(answer_to_json(answers), end="")
                return EXIT_OK
            if field_args and fields_csv:
                _log.error("query --field and --fields are mutually exclusive")
                return EXIT_ERROR
            if not args.subject:
                _log.error(
                    "query requires --subject and --field/--fields unless --list is set"
                )
                return EXIT_ERROR
            if fields_csv is not None:
                multifield = [part.strip() for part in fields_csv.split(",")]
                diag_shape = QueryShape.MULTIFIELD
                diag_fields = multifield
                csv_answer = query_knowledge_fields(
                    args.vault,
                    args.project,
                    args.subject,
                    multifield,
                    kind=args.kind,
                )
                print(answer_to_json(csv_answer), end="")
                return EXIT_OK
            if not field_args:
                _log.error(
                    "query requires --subject and --field/--fields unless --list is set"
                )
                return EXIT_ERROR
            if len(field_args) == 1:
                # Preserve AS-CORE-007 point-query CLI contract.
                diag_shape = QueryShape.POINT
                diag_field = field_args[0]
                point_answer = query_knowledge(
                    args.vault,
                    args.project,
                    args.subject,
                    field_args[0],
                    kind=args.kind,
                )
                print(answer_to_json(point_answer), end="")
                return EXIT_OK
            diag_shape = QueryShape.MULTIFIELD
            diag_fields = list(field_args)
            multi_answer = query_knowledge_fields(
                args.vault,
                args.project,
                args.subject,
                field_args,
                kind=args.kind,
            )
            print(answer_to_json(multi_answer), end="")
            return EXIT_OK
        except KnowledgeQueryError as exc:
            # AS-QUERY-DIAG-001-FR-009: structured stdout on integrity/request failures.
            _log.error("query failed [%s]: %s", exc.code.value, exc.message)
            diagnostic = query_diagnostic_from_error(
                exc,
                project_id=args.project,
                subject=args.subject,
                field=diag_field,
                fields=diag_fields,
                kind=args.kind,
                query_shape=diag_shape,
            )
            print(diagnostic_to_json(diagnostic), end="")
            return EXIT_ERROR
        except (OSError, ValueError, TypeError) as exc:
            _log.error("query failed: %s", exc)
            return EXIT_ERROR

    if args.command == "ops":
        if args.ops_command == "health":
            try:
                snapshot = emit_health_snapshot(
                    args.vault,
                    project_filter=args.project,
                    persist=not args.no_write,
                )
            except (OpsHealthError, OSError, ValueError, TypeError) as exc:
                _log.error("ops health failed: %s", exc)
                return EXIT_ERROR
            if args.json or args.no_write:
                print(snapshot_to_json(snapshot), end="")
            else:
                print(f"estate rollup: {snapshot['rollup']['estate']}")
                print(f"signals: {len(snapshot['signals'])}")
                print(
                    f"snapshot: {args.vault / 'generated' / 'ops' / 'health-snapshot.json'}"
                )
            return EXIT_OK
        if args.ops_command == "events":
            try:
                if args.record_health_transitions:
                    record_health_transition(args.vault)
                if args.retain:
                    apply_retention(args.vault, max_events=args.max_events)
                events = read_events(args.vault)
            except (OpsEventError, OSError, ValueError, TypeError) as exc:
                _log.error("ops events failed: %s", exc)
                return EXIT_ERROR
            if args.json:
                print(
                    json.dumps(events, indent=2, sort_keys=True, ensure_ascii=False)
                    + "\n",
                    end="",
                )
            else:
                print(f"events: {len(events)}")
                print(
                    f"stream: {args.vault / 'generated' / 'ops' / 'events' / 'stream.jsonl'}"
                )
            return EXIT_OK
        if args.ops_command == "report":
            try:
                report = emit_ops_report(
                    args.vault,
                    include_events=not args.no_events,
                    persist=not args.no_write,
                    archive=args.archive and not args.no_write,
                    max_archive=args.max_archive,
                )
            except (OpsReportError, OSError, ValueError, TypeError) as exc:
                _log.error("ops report failed: %s", exc)
                return EXIT_ERROR
            if args.json or args.no_write:
                print(report_to_json(report), end="")
            else:
                print(f"estate rollup: {report['rollup']['estate']}")
                print(f"snapshot_status: {report['snapshot_status']}")
                print(f"signals: {len(report['signals'])}")
                print(
                    f"report: {args.vault / 'generated' / 'ops' / 'ops-report.json'}"
                )
            return EXIT_OK
        parser.error(f"unknown ops command: {args.ops_command}")  # pragma: no cover

    if args.command == "register-global-entity":
        try:
            if args.write and args.vault is None:
                raise XprojRegistryError("register-global-entity --write requires --vault")
            payload = json.loads(args.registrations.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise XprojRegistryError("registrations-not-object")
            raw = payload.get("registrations")
            if not isinstance(raw, list):
                raise XprojRegistryError("registrations-not-array")
            requests: list[dict[str, object]] = []
            for index, item in enumerate(raw):
                if not isinstance(item, dict):
                    raise XprojRegistryError(f"registration-not-object:{index}")
                requests.append(item)
            prior_entities = None
            prior_joins = None
            if args.vault is not None:
                prior_entities, prior_joins = load_registry_state(args.vault)
            xproj_result = apply_registrations(
                requests,
                prior_entities=prior_entities,
                prior_joins=prior_joins,
            )
            xproj_written: list[str] = []
            if args.write:
                assert args.vault is not None
                xproj_written = write_registry_outputs(xproj_result, vault=args.vault)
            summary = inspect_registry(xproj_result)
            print(json.dumps(summary, indent=2, sort_keys=True))
            print(f"registered: {xproj_result.registered_count}")
            print(f"joined: {xproj_result.joined_count}")
            print(f"quarantined: {xproj_result.quarantined_count}")
            print("authority: derived")
            if xproj_written:
                print(f"written: {len(xproj_written)}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _log.error("register-global-entity failed: %s", exc)
            return EXIT_ERROR
        return EXIT_OK

    if args.command == "register-global-edge":
        try:
            if args.write and args.vault is None:
                raise XprojEdgeError("register-global-edge --write requires --vault")
            if args.vault is None:
                raise XprojEdgeError("register-global-edge requires --vault")
            payload = json.loads(args.edges.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise XprojEdgeError("edges-not-object")
            raw = payload.get("edges")
            if not isinstance(raw, list):
                raise XprojEdgeError("edges-not-array")
            edge_requests: list[dict[str, object]] = []
            for index, item in enumerate(raw):
                if not isinstance(item, dict):
                    raise XprojEdgeError(f"edge-not-object:{index}")
                edge_requests.append(item)
            entities, joins = load_registry_state(args.vault)
            prior_edges = load_edge_registry_state(args.vault)
            edge_result = apply_edge_registrations(
                edge_requests,
                entities=entities,
                joins=joins,
                prior_edges=prior_edges,
            )
            edge_written: list[str] = []
            if args.write:
                edge_written = write_edge_outputs(edge_result, vault=args.vault)
            edge_summary = inspect_edge_registry(edge_result)
            print(json.dumps(edge_summary, indent=2, sort_keys=True))
            print(f"registered: {edge_result.registered_count}")
            print(f"quarantined: {edge_result.quarantined_count}")
            print("authority: derived")
            if edge_written:
                print(f"written: {len(edge_written)}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _log.error("register-global-edge failed: %s", exc)
            return EXIT_ERROR
        return EXIT_OK

    if args.command == "detect-project-duplicates":
        try:
            if args.write and args.vault is None:
                raise XprojDuplicateError(
                    "detect-project-duplicates --write requires --vault"
                )
            payload = json.loads(args.projects.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise XprojDuplicateError("projects-not-object")
            raw = payload.get("projects")
            if not isinstance(raw, list):
                raise XprojDuplicateError("projects-not-array")
            projects: list[dict[str, object]] = []
            for index, item in enumerate(raw):
                if not isinstance(item, dict):
                    raise XprojDuplicateError(f"project-not-object:{index}")
                projects.append(item)
            dup_result = detect_project_duplicates(
                projects,
                approved_monorepo_roots=args.approved_monorepo_roots or None,
            )
            dup_written: list[str] = []
            if args.write:
                assert args.vault is not None
                dup_written = write_duplicate_outputs(dup_result, vault=args.vault)
            summary = inspect_duplicate_detection(dup_result)
            print(json.dumps(summary, indent=2, sort_keys=True))
            print(f"review_candidates: {dup_result.review_count}")
            print(f"rejects: {dup_result.reject_count}")
            print("authority: derived")
            print("autocollapse: false")
            if dup_written:
                print(f"written: {len(dup_written)}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            _log.error("detect-project-duplicates failed: %s", exc)
            return EXIT_ERROR
        return EXIT_OK

    if args.command == "retention":
        if args.retention_command == "apply":
            try:
                report = apply_event_retention(
                    args.vault,
                    max_packages=args.max_packages,
                    max_bytes=args.max_bytes,
                    dry_run=args.dry_run,
                )
            except (RetentionError, OSError, ValueError, TypeError) as exc:
                _log.error("retention apply failed: %s", exc)
                return EXIT_ERROR
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True) + "\n", end="")
            else:
                print(f"status: {report['status']}")
                print(f"units_removed: {report['counts']['units_removed']}")
                print(
                    f"report: {args.vault / 'generated' / 'ops' / 'retention-report.json'}"
                )
            return EXIT_OK
        parser.error(  # pragma: no cover
            f"unknown retention command: {args.retention_command}"
        )

    if args.command == "revocation":
        if args.revocation_command == "revoke":
            try:
                revocation_index = revoke_receipt(
                    args.vault,
                    project_id=args.project,
                    event_id=args.event,
                    reason=args.reason,
                    status=args.status,
                    detail=args.detail,
                )
            except (RevocationError, OSError, ValueError, TypeError) as exc:
                _log.error("revocation revoke failed: %s", exc)
                return EXIT_ERROR
            if args.json:
                print(
                    json.dumps(revocation_index, indent=2, sort_keys=True) + "\n",
                    end="",
                )
            else:
                entry = revocation_index["revocations"][-1]
                for row in revocation_index["revocations"]:
                    if row["unit_key"] == f"{args.project}/{args.event}":
                        entry = row
                        break
                print(f"status: {entry['status']}")
                print(f"reason: {entry['reason']}")
                print(f"unit_key: {entry['unit_key']}")
                print(
                    "index: "
                    f"{args.vault / 'generated' / 'ops' / 'receipt-revocations.json'}"
                )
            return EXIT_OK
        if args.revocation_command == "list":
            try:
                rows = list_revocations(args.vault)
                if args.json:
                    payload = {
                        "schema": "atlas.receipt_revocation.index.v1",
                        "revocations": rows,
                        "inventory": inventory_with_revocations(args.vault),
                    }
                    print(json.dumps(payload, indent=2, sort_keys=True) + "\n", end="")
                else:
                    print(f"revocations: {len(rows)}")
                    for row in rows:
                        print(
                            f"  {row['unit_key']} {row['status']} ({row['reason']})"
                        )
            except (RevocationError, OSError, ValueError, TypeError) as exc:
                _log.error("revocation list failed: %s", exc)
                return EXIT_ERROR
            return EXIT_OK
        if args.revocation_command == "status":
            try:
                disposition = receipt_trust_disposition(
                    args.vault, project_id=args.project, event_id=args.event
                )
                payload = {
                    "unit_key": f"{args.project}/{args.event}",
                    "disposition": disposition,
                }
                if args.json:
                    print(json.dumps(payload, indent=2, sort_keys=True) + "\n", end="")
                else:
                    print(f"unit_key: {payload['unit_key']}")
                    print(f"disposition: {disposition}")
            except (RevocationError, OSError, ValueError, TypeError) as exc:
                _log.error("revocation status failed: %s", exc)
                return EXIT_ERROR
            return EXIT_OK
        parser.error(  # pragma: no cover
            f"unknown revocation command: {args.revocation_command}"
        )

    if args.command == "snapshot":
        try:
            if args.verify:
                if args.bundle is None:
                    raise BackupError("snapshot --verify requires --bundle")
                result = verify_bundle(args.bundle)
                print(f"verified: {result['snapshot_id']}")
                print(f"vault_logical_id: {result['vault_logical_id']}")
                print(f"members: {result['member_count']}")
                return EXIT_OK
            if args.vault is None or args.output is None:
                raise BackupError("snapshot create requires --vault and --output")
            result = create_snapshot(
                args.vault,
                args.output,
                cp=args.cp,
                include_d5=args.include_d5,
            )
        except (BackupError, OSError, ValueError, TypeError) as exc:
            _log.error("snapshot failed: %s", exc)
            return EXIT_ERROR
        print(f"bundle: {result['bundle']}")
        print(f"snapshot_id: {result['snapshot_id']}")
        print(f"vault_logical_id: {result['vault_logical_id']}")
        print(f"members: {result['member_count']}")
        print(f"domains: {','.join(result['domains_included'])}")
        return EXIT_OK

    if args.command == "restore":
        try:
            result = restore_bundle(
                args.bundle,
                args.output,
                tier=args.tier,
                expected_vault_logical_id=args.expect_vault_logical_id,
            )
        except (BackupError, OSError, ValueError, TypeError) as exc:
            _log.error("restore failed: %s", exc)
            return EXIT_ERROR
        print(f"restored: {result['target']}")
        print(f"snapshot_id: {result['snapshot_id']}")
        print(f"vault_logical_id: {result['vault_logical_id']}")
        print(f"members: {result['member_count']}")
        print(f"tier: {result['tier']}")
        return EXIT_OK
    parser.error(f"unknown command: {args.command}")  # pragma: no cover - argparse enforces


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
