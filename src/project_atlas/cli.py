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
from project_atlas.logging import configure_logging, get_logger
from project_atlas.scaffold import ScaffoldError, create_scaffold

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

    parser.error(f"unknown command: {args.command}")  # pragma: no cover - argparse enforces


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
