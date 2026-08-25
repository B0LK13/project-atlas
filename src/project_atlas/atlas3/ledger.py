"""AT3-014 — Universal event ledger.

Append-only derived JSONL under generated/ops/atlas3/ledger/.
Does not write generated/ops/events/ (ops_events dual-writer forbidden).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    Atlas3Error,
    require_project,
    require_vault,
    write_json_atomic,
)
from project_atlas.atlas3.events import normalize_engineering_event

PACKAGE_ID: Final[str] = "AT3-014"
LEDGER_RELATIVE: Final[Path] = OPS_RELATIVE / "ledger"


def _ledger_path(vault: Path, project_id: str) -> Path:
    return vault / LEDGER_RELATIVE / f"{project_id}.jsonl"


def append_event(
    vault: Path,
    project_id: str,
    event: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Append a normalized event. Replay of the same event_id is idempotent."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    record = event or normalize_engineering_event(project_id=pid, **kwargs)
    if record.get("project_id") != pid:
        raise Atlas3Error("PROJECT_MISMATCH", "event project_id does not match ledger project")
    path = _ledger_path(root, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = list_events(root, pid)
    for prior in existing:
        if prior.get("event_id") == record.get("event_id"):
            return {
                "status": "ok",
                "package": PACKAGE_ID,
                "idempotency": "replay",
                "event_id": record["event_id"],
                "path": str(LEDGER_RELATIVE / f"{pid}.jsonl"),
            }
    line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
    return {
        "status": "ok",
        "package": PACKAGE_ID,
        "idempotency": "appended",
        "event_id": record["event_id"],
        "path": str(LEDGER_RELATIVE / f"{pid}.jsonl"),
        "kind": record.get("kind"),
    }


def list_events(
    vault: Path,
    project_id: str,
    *,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _ledger_path(root, pid)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise Atlas3Error("LEDGER_CORRUPT", f"malformed ledger line: {exc}") from exc
        if isinstance(item, dict) and (kind is None or item.get("kind") == kind):
            rows.append(item)
    return rows


def ledger_status(vault: Path, project_id: str) -> dict[str, Any]:
    rows = list_events(vault, project_id)
    kinds: dict[str, int] = {}
    for row in rows:
        key = str(row.get("kind") or "unknown")
        kinds[key] = kinds.get(key, 0) + 1
    payload = {
        "package": PACKAGE_ID,
        "project_id": project_id,
        "event_count": len(rows),
        "kinds": dict(sorted(kinds.items())),
        "store": str(LEDGER_RELATIVE / f"{project_id}.jsonl"),
        "dual_writes_ops_events": False,
    }
    write_json_atomic(
        require_vault(vault) / OPS_RELATIVE / "ledger" / f"{project_id}.status.json",
        payload,
    )
    return payload
