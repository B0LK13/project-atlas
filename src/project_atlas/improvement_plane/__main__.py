"""Executable entry point: ``python -m project_atlas.improvement_plane``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from project_atlas.improvement_plane.report import (
    PACKAGE_ID,
    compile_improvement_report,
    render_markdown_summary,
    write_report_files,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m project_atlas.improvement_plane",
        description=(
            f"{PACKAGE_ID}: read-only delivery-evidence improvement report. "
            "Recommendations cite sources and grant no authority."
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="Repository root containing docs/evidence (default: .)",
    )
    parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help="Optional Atlas vault root for read-only ops receipt inventory",
    )
    parser.add_argument(
        "--reference-utc",
        default=None,
        help=(
            "Optional ISO-8601 UTC reference for waiting-age calculation. "
            "When omitted, waiting age stays unknown."
        ),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path for machine-readable report JSON",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="Optional path for operator Markdown summary",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON report to stdout (default prints Markdown summary)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = compile_improvement_report(
        args.repo,
        vault_path=args.vault,
        reference_utc=args.reference_utc,
    )
    write_report_files(
        report,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_markdown_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
