#!/usr/bin/env python3
"""Strictly validate AS-WP-004 ingestion artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from internal import ingestion_validation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        report = ingestion_validation.validate(args.vault, args.project_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    payload = report.as_dict()
    print(json.dumps(payload, ensure_ascii=False) if args.json_output else f"Validated {report.documents_checked} document(s): {'ok' if report.ok else 'failed'}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
