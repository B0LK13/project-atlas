#!/usr/bin/env python3
"""Discover bounded Atlas projects (AS-WP-004)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from internal import project_discovery  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--nested-repository-policy", choices=("parent-project", "separate-project"), default="parent-project")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        records = project_discovery.discover_projects(
            args.workspace_root, project_root=args.project_root, max_depth=args.max_depth,
            nested_repository_policy=args.nested_repository_policy,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    payload: dict[str, Any] = {"ok": True, "projects": [record.as_dict() for record in records]}
    print(json.dumps(payload, ensure_ascii=False) if args.json_output else "\n".join(f"{r.project_id}: {r.root}" for r in records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
