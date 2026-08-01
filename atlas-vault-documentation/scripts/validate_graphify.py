#!/usr/bin/env python3
"""Strictly validate derived Graphify state and projections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from internal import graph_validation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    report = graph_validation.validate(args.vault, args.project_id)
    print(json.dumps(report.as_dict()) if args.json_output else ("ok" if report.ok else "failed"))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
