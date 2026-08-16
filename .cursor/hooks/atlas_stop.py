#!/usr/bin/env python3
"""AS-ORCH-001C thin Cursor stop adapter.

Cursor is transport only. This script contains no workflow policy, role
selection, privilege decisions, or prose parsing. It reads stop-event JSON
from stdin and prints exactly one JSON object to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def repository_root() -> Path:
    """Repo root from this file path. Hook cwd is not assumed to be the root."""
    return Path(__file__).resolve().parents[2]


def main() -> int:
    raw = sys.stdin.buffer.read()
    try:
        payload: object = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        print(f"atlas_stop: invalid stdin JSON: {exc}", file=sys.stderr)
        sys.stdout.write("{}\n")
        return 0
    root = repository_root()
    try:
        try:
            from project_atlas.orchestration.cursor_bridge import handle_stop_event
        except ImportError:
            src = root / "src"
            if src.is_dir() and str(src) not in sys.path:
                sys.path.insert(0, str(src))
            from project_atlas.orchestration.cursor_bridge import handle_stop_event
        response = handle_stop_event(payload, root=root)
    except Exception as exc:  # noqa: BLE001 — hook must fail closed to {}
        print(f"atlas_stop: bridge error: {type(exc).__name__}", file=sys.stderr)
        sys.stdout.write("{}\n")
        return 0
    sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
