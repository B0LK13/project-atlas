"""AS-CODER-ALPHA-EVENT-TOMBSTONES-READ-001 — vault-scoped deletion lens.

Projects the existing AS-INT-010 tombstone index so humans and agents can
see removed agent-event units. A deletion must remain visible. This module
never writes, never records tombstones, and never grants owner capability.

Honesty:
- DELETED is never VANISHED
- EMPTY is never HEALTHY
- UNKNOWN is never CLEAN
- this lens is not Truth Core authority
- UI / MCP / API projections are not canonical
- a demo fixture must not masquerade as authentic estate inventory
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.event_tombstones import (
    INDEX_RELATIVE,
    INDEX_SCHEMA,
    TombstoneError,
    list_tombstones,
    load_index,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-EVENT-TOMBSTONES-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-event-tombstones-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.event-tombstones-read.v1"
SOURCE_PACKAGE: Final[str] = "AS-INT-010"
TRUTH_BOUNDARY: Final[str] = (
    "DELETED != VANISHED / EMPTY != HEALTHY / UNKNOWN != CLEAN / LENS != AUTHORITY"
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "DELETED_VISIBLE"]


class EventTombstonesReadError(ValueError):
    """Fail-closed event-tombstone read error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "deleted_is_vanished": False,
        "empty_is_healthy": False,
        "unknown_is_clean": False,
        "unknown_is_healthy": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "write_applied": False,
        "tombstone_recorded": False,
        "demo_is_authentic": False,
        "receipt_is_live_certification": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise EventTombstonesReadError(
            f"event-tombstones-vault-unreadable:{exc}"
        ) from exc
    if not root.is_dir():
        raise EventTombstonesReadError("event-tombstones-vault-missing")
    return root


def _safe_project_id(project_id: str) -> str:
    token = project_id.strip()
    if not token or "/" in token or "\\" in token or token in {".", ".."}:
        raise EventTombstonesReadError(
            f"event-tombstones-project-unsafe:{project_id!r}"
        )
    return token


def _public_row(raw: dict[str, Any]) -> dict[str, Any]:
    deleted_paths = [
        item for item in (raw.get("deleted_paths") or []) if isinstance(item, str)
    ]
    return {
        "unit_key": raw.get("unit_key"),
        "project_id": raw.get("project_id"),
        "event_id": raw.get("event_id"),
        "reason": raw.get("reason"),
        "state": raw.get("state") or "deleted",
        "deleted_paths": deleted_paths,
        "authority": False,
        "label": "Removed event unit — operational tombstone, not project authority",
    }


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    scoped: bool,
    project_id: str | None,
    rows: list[dict[str, Any]],
    index_present: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_package": SOURCE_PACKAGE,
        "source_schema": INDEX_SCHEMA,
        "truth_boundary": TRUTH_BOUNDARY,
        "scoped": scoped,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "index_present": index_present,
        "index_path": INDEX_RELATIVE.as_posix(),
        "deleted_count": len(rows),
        "tombstones": rows,
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }
    if project_id is not None:
        payload["project_id"] = project_id
    return payload


def build_event_tombstones_read(
    vault: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Read-only tombstone projection. Never writes."""
    root = _resolve_vault(vault)
    scoped = (project_id or "").strip() or None
    if scoped is not None:
        scoped = _safe_project_id(scoped)

    index_path = root / INDEX_RELATIVE
    if not index_path.is_file():
        return _envelope(
            status="UNKNOWN",
            reason=(
                "event-tombstone index is absent; absence is not a clean "
                "or healthy inventory"
            ),
            reason_code="INDEX_ABSENT",
            available=False,
            scoped=scoped is not None,
            project_id=scoped,
            rows=[],
            index_present=False,
        )

    try:
        load_index(root)
        raw_rows = list_tombstones(root)
    except TombstoneError as exc:
        raise EventTombstonesReadError(
            f"event-tombstones-index-malformed:{exc}"
        ) from exc

    rows = [_public_row(item) for item in raw_rows if isinstance(item, dict)]
    if scoped is not None:
        rows = [item for item in rows if item.get("project_id") == scoped]

    if rows:
        return _envelope(
            status="DELETED_VISIBLE",
            reason="removed event units remain visible as operational tombstones",
            reason_code="TOMBSTONES_PRESENT",
            available=True,
            scoped=scoped is not None,
            project_id=scoped,
            rows=rows,
            index_present=True,
        )
    return _envelope(
        status="EMPTY",
        reason=(
            "tombstone index is present and empty for this scope; "
            "EMPTY is not healthy and does not invent deletions"
        ),
        reason_code="INDEX_EMPTY",
        available=True,
        scoped=scoped is not None,
        project_id=scoped,
        rows=[],
        index_present=True,
    )


def render_event_tombstones_read_text(report: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    lines = [
        f"atlas event-tombstones [{report.get('status', 'UNKNOWN')}]",
        f"  available:    {report.get('available')}",
        f"  reason:       {report.get('reason_code')}",
        f"  scoped:       {report.get('scoped')}",
        f"  index:        {report.get('index_present')}",
        f"  deleted:      {report.get('deleted_count')}",
    ]
    project_id = report.get("project_id")
    if isinstance(project_id, str) and project_id:
        lines.append(f"  project:      {project_id}")
    rows = report.get("tombstones")
    if isinstance(rows, list):
        for item in rows[:8]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"  tombstone:    {item.get('unit_key')} ({item.get('reason')})"
            )
    lines.append(
        "  honesty:      DELETED != VANISHED; EMPTY != HEALTHY; LENS != AUTHORITY"
    )
    return "\n".join(lines) + "\n"
