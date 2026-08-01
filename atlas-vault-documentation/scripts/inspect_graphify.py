#!/usr/bin/env python3
"""Inspect one Graphify artifact without mutating the vault."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from internal import graphify_parser  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        nodes, edges = graphify_parser.parse_artifact({"path": str(args.artifact)})
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4
    result = {"ok": True, "project_id": args.project_id, "artifact": str(args.artifact), "nodes": len(nodes), "edges": len(edges)}
    print(json.dumps(result) if args.json_output else f"{len(nodes)} nodes, {len(edges)} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
