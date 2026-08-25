"""AS-CODER-ALPHA-MISSION-READ-001 -- vault-scoped mission REPORT READ.

Read-only wrap of the existing ``GET /v1/mission`` derived view
(AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001). This module never writes
mission state, never invents PILOT rows, and never treats the mission
view as Truth Core or authority.

Honesty:
- MISSION != AUTHORITY
- VIEW != TRUTH CORE
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-MISSION-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-mission-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.mission-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = (
    "AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001",
)
SOURCE_ROUTE: Final[str] = "/v1/mission"
TRUTH_BOUNDARY: Final[str] = (
    "MISSION != AUTHORITY / VIEW != TRUTH CORE / EMPTY != HEALTHY / "
    "UNKNOWN != HEALTHY / MCP != AUTHORITY / WRITE_APPLIED = false / "
    "D149_TOUCHED = NO / src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "MISSION != AUTHORITY",
    "VIEW != TRUTH CORE",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebMissionReadError(ValueError):
    """Fail-closed mission REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "mission_is_authority": False,
        "view_is_truth_core": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "mission_state_written": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "owner_capability_granted": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "graph_is_authority": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebMissionReadError(f"mission-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebMissionReadError("mission-read-vault-missing")
    return root


def _existing_mission_view(vault: Path) -> dict[str, Any]:
    """Call the existing GET /v1/mission builder. Never writes."""
    # Lazy import: web_mission_workspace imports AppService at module load.
    from project_atlas.app_service import AppServiceError
    from project_atlas.web_mission_workspace import build_mission_view

    try:
        view = build_mission_view(vault)
    except AppServiceError as exc:
        raise WebMissionReadError(f"mission-read-view-unreadable:{exc}") from exc
    except OSError as exc:
        raise WebMissionReadError(f"mission-read-view-unreadable:{exc}") from exc
    if not isinstance(view, dict):
        raise WebMissionReadError("mission-read-view-invalid")
    return view


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    project_count_raw = view.get("project_count")
    project_count = project_count_raw if isinstance(project_count_raw, int) else 0
    empty_projects = view.get("empty_projects") is True or project_count == 0
    read_plane = view.get("read_plane")
    rollup = view.get("rollup")
    if empty_projects:
        return (
            "EMPTY",
            "existing GET /v1/mission view has no projects; EMPTY != HEALTHY; "
            "MISSION != AUTHORITY; VIEW != TRUTH CORE",
            "EMPTY_MISSION_VIEW",
            False,
        )
    if read_plane == "unread" or rollup == "unknown":
        return (
            "UNKNOWN",
            "existing GET /v1/mission view is unread or unknown; "
            "UNKNOWN != HEALTHY; MISSION != AUTHORITY; VIEW != TRUTH CORE",
            "UNKNOWN_MISSION_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing GET /v1/mission derived view is projected; "
        "MISSION != AUTHORITY; VIEW != TRUTH CORE",
        "MISSION_VIEW_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_route": SOURCE_ROUTE,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "view": view,
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_mission_view(vault: Path) -> dict[str, Any]:
    """Read-only wrap of GET /v1/mission. Never writes mission state."""
    root = _resolve_vault(vault)
    view = _existing_mission_view(root)
    return _envelope(view=view)


def render_mission_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas mission report [{view.get('status', 'UNKNOWN')}]",
        f"  available:      {view.get('available')}",
        f"  reason:         {view.get('reason_code')}",
        f"  source_route:   {view.get('source_route', SOURCE_ROUTE)}",
        f"  project_count:  {inner.get('project_count', 0)}",
        f"  read_plane:     {inner.get('read_plane', 'UNKNOWN')}",
        f"  rollup:         {inner.get('rollup', 'unknown')}",
        (
            "  honesty:        MISSION != AUTHORITY; VIEW != TRUTH CORE; "
            "EMPTY != HEALTHY; UNKNOWN != HEALTHY; MCP != AUTHORITY; "
            "WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
