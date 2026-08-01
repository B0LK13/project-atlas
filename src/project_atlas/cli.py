"""Command-line interface for Project Atlas (A-007).

Exit codes:
- 0: success;
- 1: operational error (unsafe path, non-empty target, I/O failure);
- 2: usage error (argparse).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from project_atlas import __version__
from project_atlas.config import load_config
from project_atlas.discovery import discover, write_manifest
from project_atlas.indexes import build_indexes
from project_atlas.ingestion import ingest
from project_atlas.logging import configure_logging, get_logger
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
        "build-indexes", help="Build deterministic Vault indexes (FR-010)."
    )
    indexes_parser.add_argument("--vault", type=Path, required=True)

    validate_parser = subparsers.add_parser(
        "validate", help="Validate Vault structure, provenance links and safety (FR-012)."
    )
    validate_parser.add_argument("--vault", type=Path, required=True)
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
        except OSError as exc:
            _log.error("build-indexes failed: %s", exc)
            return EXIT_ERROR
        print(f"indexed {result['projects']} projects and {result['sources']} sources")
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

    parser.error(f"unknown command: {args.command}")  # pragma: no cover - argparse enforces


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
