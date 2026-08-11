#!/usr/bin/env python3
"""Governed project documentation ingestion (AS-WP-004)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import atlas_config  # noqa: E402
from internal import ingestion_orchestrator, project_discovery  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--mda-command", default="mda")
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--best-effort", action="store_true", help="Quarantine failed documents and continue.")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        config, _, _ = atlas_config.load_config(args.config, start=args.project_root)
        project = project_discovery.discover_projects(args.project_root, project_root=args.project_root)[0]
        result = ingestion_orchestrator.ingest_project(
            project, vault_root=args.vault, config=config, incremental=args.incremental,
            dry_run=args.dry_run, strict=not args.best_effort, mda_command=args.mda_command,
        )
    except (OSError, ValueError, IndexError, ingestion_orchestrator.IngestionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    if args.json_output:
        print(json.dumps(result, ensure_ascii=False, default=str))
    else:
        print(f"{result['status']}: {result.get('project_id', project.project_id)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
