"""Machine-readable managed-agent session state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def path(root: Path, session_id: str) -> Path:
    return root / ".atlas" / "sessions" / f"{session_id}.json"


def save(root: Path, state: dict[str, Any]) -> Path:
    target = path(root, str(state["session"]["session_id"]))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load(root: Path, session_id: str) -> dict[str, Any]:
    target = path(root, session_id)
    if not target.is_file():
        raise ValueError(f"session not found: {session_id}")
    return cast(dict[str, Any], json.loads(target.read_text(encoding="utf-8")))
