"""AS-CODER-ALPHA-OPS-EVENTS-READ-001 — vault-scoped ops-event stream read.

Reads existing ``generated/ops/events/stream.jsonl`` so humans and agents
can see recorded OPS-EVT-* facts without emitting, retaining, or inventing
events.

Honesty:
- missing stream stays UNKNOWN (never HEALTHY / FRESH)
- empty stream is EMPTY, not HEALTHY
- recorded events are operational facts, not project authority
- this lens never writes, retains, or records health transitions
- UI / MCP / API projections are not canonical
- ops events are not owner capability or AUTHENTIC_PILOT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.ops_events import (
    MANIFEST_RELATIVE,
    STREAM_RELATIVE,
    OpsEventError,
    load_stream_manifest,
    read_events,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-OPS-EVENTS-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-ops-events-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.ops-events-read.v1"
TRUTH_BOUNDARY: Final[str] = (
    "OPS EVENT STREAM != AUTHORITY / EMPTY != HEALTHY / ABSENT != FABRICATED"
)
DEFAULT_LIMIT: Final[int] = 100
MAX_LIMIT: Final[int] = 500

StatusRollup = Literal["UNKNOWN", "EMPTY", "RECORDED"]


class OpsEventsReadError(ValueError):
    """Fail-closed ops-events-read error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "ops_events_are_authority": False,
        "empty_is_healthy": False,
        "absent_is_fabricated": False,
        "unknown_is_healthy": False,
        "unknown_is_fresh": False,
        "presence_is_validate": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "fabricated_events": False,
        "health_transition_recorded": False,
        "retention_applied": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def build_ops_events_read(vault: Path, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Read-only ops-event projection. Never writes. Never invents events."""
    if limit < 1 or limit > MAX_LIMIT:
        raise OpsEventsReadError("ops-events-limit-out-of-range")
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise OpsEventsReadError(f"ops-events-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise OpsEventsReadError("ops-events-vault-missing")

    stream_present = (root / STREAM_RELATIVE).is_file()
    manifest_present = (root / MANIFEST_RELATIVE).is_file()
    try:
        events = read_events(root)
        manifest = load_stream_manifest(root)
    except OpsEventError as exc:
        raise OpsEventsReadError(str(exc)) from exc

    event_count = len(events)
    truncated = event_count > limit
    returned = events[-limit:] if truncated else list(events)

    if not stream_present:
        rollup: StatusRollup = "UNKNOWN"
        reason_code = "STREAM_ABSENT"
        reason = (
            "No ops event stream on disk; absence is not HEALTHY and is not "
            "a fabricated event list."
        )
        available = False
    elif event_count == 0:
        rollup = "EMPTY"
        reason_code = "STREAM_EMPTY"
        reason = (
            "Ops event stream exists but contains no events; EMPTY != HEALTHY."
        )
        available = True
    else:
        rollup = "RECORDED"
        reason_code = "STREAM_RECORDED"
        reason = (
            "Ops events are recorded operational facts; they are not project "
            "authority, freshness, or AUTHENTIC_PILOT."
        )
        available = True

    next_sequence = manifest.get("next_sequence")
    last_event_uid = manifest.get("last_event_uid")
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": rollup,
        "reason": reason,
        "reason_code": reason_code,
        "stream_present": stream_present,
        "manifest_present": manifest_present,
        "stream_path": STREAM_RELATIVE.as_posix(),
        "event_count": event_count,
        "returned_count": len(returned),
        "truncated": truncated,
        "next_sequence": next_sequence if isinstance(next_sequence, int) else None,
        "last_event_uid": last_event_uid if isinstance(last_event_uid, str) else None,
        "events": list(returned),
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }


def render_ops_events_read_text(report: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    rows = report.get("events") or []
    ids = [
        str(row.get("event_id"))
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("event_id"), str)
    ]
    present_text = ", ".join(ids) if ids else "(none)"
    lines = [
        f"atlas ops-events [{report.get('status', 'UNKNOWN')}]",
        f"  available: {report.get('available')}",
        f"  reason:    {report.get('reason_code')}",
        f"  events:    {report.get('event_count')} (returned {report.get('returned_count')})",
        f"  stream:    {report.get('stream_present')}",
        f"  present:   {present_text}",
        "  honesty:   OPS EVENT STREAM != AUTHORITY; EMPTY != HEALTHY; ABSENT != FABRICATED",
    ]
    return "\n".join(lines) + "\n"
