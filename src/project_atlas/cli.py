"""Command-line interface for Project Atlas (A-007).

Exit codes:
- 0: success;
- 1: operational error (unsafe path, non-empty target, I/O failure);
- 2: usage error (argparse).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from project_atlas import __version__
from project_atlas.config import load_config
from project_atlas.discovery import discover, write_manifest
from project_atlas.domain.knowledge_query import QueryShape
from project_atlas.graph_acceptance import (
    GraphAcceptanceError,
    accept_graphify_artifacts,
    inspect_acceptance,
)
from project_atlas.indexes import build_indexes
from project_atlas.ingestion import ingest
from project_atlas.knowledge_query import (
    KnowledgeQueryError,
    answer_to_json,
    diagnostic_to_json,
    list_authoritative,
    query_diagnostic_from_error,
    query_knowledge,
    query_knowledge_fields,
)
from project_atlas.logging import configure_logging, get_logger
from project_atlas.migrations.claim_v2_migration import migrate_v2
from project_atlas.portfolio import build_portfolio
from project_atlas.scaffold import ScaffoldError, create_scaffold
from project_atlas.validation import validate

EXIT_OK = 0
EXIT_ERROR = 1

_log = get_logger("cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas",
        description="Project Atlas — source-backed, offline-first project knowledge compiler.",
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
        help="List authoritative-state records for the project (kind=authoritative).",
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
        if not result["ok"]:
            for error in result["errors"]:
                _log.error("validation: %s", error)
            return EXIT_ERROR
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
                if args.kind != "authoritative":
                    _log.error("query --list requires --kind authoritative")
                    return EXIT_ERROR
                diag_shape = QueryShape.LIST
                answers = list_authoritative(args.vault, args.project)
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

    parser.error(f"unknown command: {args.command}")  # pragma: no cover - argparse enforces


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
