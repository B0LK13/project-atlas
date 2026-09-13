"""AT3-091 — Isolated Timeline.

Orders ledger events by document-declared valid-time.
Wall-clock / observed_at is not valid-time. Timeline != Truth Core.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    require_project,
    require_vault,
)
from project_atlas.atlas3.ledger import query_events

PACKAGE_ID: Final[str] = "AT3-091"
GENERATOR_ID: Final[str] = "atlas3-timeline-091"


def _truthy_wall_clock(value: object) -> bool:
    """Reject explicit wall-clock flags that are not the boolean False/absent.

    AT3-091-F1: ``is True`` let ``\"true\"`` / ``1`` smuggle wall-clock as
    document-declared valid-time.
    """
    if value is True:
        return True
    if isinstance(value, (int, float)) and value != 0:
        return True
    return isinstance(value, str) and value.strip().lower() in {"true", "1", "yes", "on"}


def _valid_key(event: dict[str, Any]) -> str:
    if _truthy_wall_clock(event.get("wall_clock_is_valid_time")):
        raise Atlas3Error(
            "WALL_CLOCK_AS_VALID_TIME",
            "timeline must not treat wall-clock as valid-time",
        )
    key = str(event.get("valid_time") or event.get("valid_from") or "").strip()
    observed = str(event.get("observed_at") or "").strip()
    if key and observed and key == observed:
        raise Atlas3Error(
            "WALL_CLOCK_AS_VALID_TIME",
            "timeline must not treat observed_at as declared valid-time",
        )
    return key


def compile_timeline(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compile a derived timeline from validated ledger rows."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    events = query_events(root, project_id=pid)
    rows: list[dict[str, Any]] = []
    unknown_temporal = 0
    for event in events:
        key = _valid_key(event)
        if not key:
            unknown_temporal += 1
        rows.append(
            {
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "summary": event.get("summary"),
                "valid_time": key or None,
                "temporal_status": "declared" if key else "UNKNOWN",
                "observed_at_is_valid_time": False,
                "wall_clock_is_valid_time": False,
            }
        )
    rows.sort(key=lambda item: (item["valid_time"] is None, item["valid_time"] or ""))
    status = "UNKNOWN" if not rows else "derived"
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "entries": rows,
        "counts": {"entries": len(rows), "unknown_temporal": unknown_temporal},
        "status": status,
        "reason": "NO_LEDGER_EVENTS" if not rows else "LEDGER_TIMELINE",
        "wall_clock_is_valid_time": False,
        "timeline_is_authority": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
