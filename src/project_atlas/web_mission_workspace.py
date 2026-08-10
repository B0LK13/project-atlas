"""AS-2.1 mission/workspace live read compositions.

Composes operator lenses from AppService + OBS presence only.
Never invents PILOT estate rows. UI ≠ canonical · Graph ≠ authority.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_atlas.app_service import open_app_service
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-WEB-MISSION-WORKSPACE-LIVE-001"
TRUTH_BOUNDARY = (
    "MISSION/WORKSPACE LIVE COMPOSE != PILOT INVENT / UI!=CANONICAL / "
    "GRAPH!=AUTHORITY"
)


def build_mission_view(vault: Path) -> dict[str, Any]:
    """Compose a mission-control read view from live vault projections."""
    require_compatibility_anchor()
    svc = open_app_service(vault)
    health = svc.health()
    vault_health = health.get("vault_health") or {}
    projects = svc.projects()
    ops = vault / "generated" / "ops"
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "lens": "mission",
        "read_plane": "ops_snapshot" if vault_health.get("available") else "unread",
        "data_source": "live_api",
        "demo_isolated": False,
        "mission_board_available": True,
        "rollup": vault_health.get("rollup", "unknown"),
        "project_count": len(projects),
        "obs_present": (ops / "obs").exists(),
        "scheduler_present": (ops / "scheduler").exists(),
        "pilot_estate_rows": [],
        "authentic_pilot": False,
        "ui_canonical": False,
        "graph_authority": False,
        "unknown_equals_healthy": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "note": "Live composition from vault projections; no PILOT invent",
        "generated": {"by": "project-atlas"},
    }


def build_workspace_view(vault: Path) -> dict[str, Any]:
    """Compose a workspace read view from live vault projections."""
    require_compatibility_anchor()
    svc = open_app_service(vault)
    health = svc.health()
    vault_health = health.get("vault_health") or {}
    projects = svc.projects()
    knowledge = svc.knowledge()
    ops = vault / "generated" / "ops"
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "lens": "workspace",
        "read_plane": "ops_snapshot" if vault_health.get("available") else "unread",
        "data_source": "live_api",
        "demo_isolated": False,
        "workspace_board_available": True,
        "rollup": vault_health.get("rollup", "unknown"),
        "project_count": len(projects),
        "knowledge_count": len(knowledge),
        "collab_present": (ops / "collab").exists(),
        "web_actions_present": (ops / "web-actions").exists(),
        "pilot_estate_rows": [],
        "authentic_pilot": False,
        "ui_canonical": False,
        "graph_authority": False,
        "unknown_equals_healthy": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "note": "Live composition from vault projections; no PILOT invent",
        "generated": {"by": "project-atlas"},
    }
