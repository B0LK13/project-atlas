"""Machine-readable incremental Graphify state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def load(path: Path, project_id: str) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "project_id": project_id, "artifacts": {}, "nodes": {}, "relationships": {}, "quarantine": {}, "last_successful_transaction": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("unsupported graph ingestion state schema")
    return cast(dict[str, Any], data)


def save(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
