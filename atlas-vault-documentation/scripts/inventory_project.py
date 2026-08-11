#!/usr/bin/env python3
"""Build a deterministic AS-WP-004 document inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import atlas_config  # noqa: E402
from internal import document_inventory, project_discovery  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        config, _, _ = atlas_config.load_config(args.config, start=args.project_root)
        project_id = args.project_id or project_discovery.discover_projects(args.project_root, project_root=args.project_root)[0].project_id
        inventory = document_inventory.inventory_project(args.project_root, project_id=project_id, config=config)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document_inventory.serialize_inventory(inventory), encoding="utf-8")
    except (OSError, ValueError, IndexError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    payload = {"ok": True, "project_id": inventory["project_id"], "documents": len(inventory["documents"]), "inventory_sha256": inventory["inventory_sha256"], "output": str(args.output)}
    print(json.dumps(payload, ensure_ascii=False) if args.json_output else f"Inventoried {payload['documents']} document(s): {payload['inventory_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
