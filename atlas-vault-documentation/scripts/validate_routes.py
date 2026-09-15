#!/usr/bin/env python3
"""Validate Atlas routing artifacts (AS-WP-003).

Exit codes: 0 ok, 1 validation errors, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import atlas_config  # noqa: E402
from internal import project_identity, router_validation  # noqa: E402

EXIT_OK = 0
EXIT_ERRORS = 1
EXIT_USAGE = 2


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--vault", type=Path)
    result.add_argument("--project-id")
    result.add_argument("--config", type=Path)
    result.add_argument("--strict", action="store_true")
    result.add_argument("--json", action="store_true", dest="json_output")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config, _, _ = atlas_config.load_config(args.config)
    except atlas_config.ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_USAGE
    vault_value = atlas_config.resolve(args.vault, "ATLAS_VAULT", config, "atlas", "vault")
    if not vault_value:
        print("ERROR: provide --vault, ATLAS_VAULT, or atlas.vault", file=sys.stderr)
        return EXIT_USAGE
    vault_root = Path(vault_value).expanduser().resolve()

    if args.project_id:
        if not project_identity.SAFE_PROJECT_ID.fullmatch(args.project_id):
            print(f"ERROR: unsafe project id: {args.project_id!r}", file=sys.stderr)
            return EXIT_USAGE
        projects = [args.project_id]
    else:
        projects = router_validation.discover_projects(vault_root)

    combined = router_validation.RouteValidationReport(projects_checked=0)
    for project_id in projects:
        report = router_validation.validate_project(vault_root, project_id)
        combined.projects_checked += report.projects_checked
        combined.events_checked += report.events_checked
        combined.receipts_checked += report.receipts_checked
        combined.logs_checked += report.logs_checked
        combined.work_packages_checked += report.work_packages_checked
        combined.regions_checked += report.regions_checked
        combined.errors.extend(report.errors)
        combined.warnings.extend(report.warnings)

    if args.strict and combined.warnings:
        combined.errors.extend(f"strict: {w}" for w in combined.warnings)

    payload = combined.as_dict()
    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            f"Checked {combined.projects_checked} project(s), "
            f"{combined.events_checked} event(s), "
            f"{combined.receipts_checked} receipt(s)"
        )
        for error in combined.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        for warning in combined.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
    return EXIT_OK if combined.ok else EXIT_ERRORS


if __name__ == "__main__":
    raise SystemExit(main())
