"""Read-only vault health / read-status views (AS-WEB-001).

Consumes OBS health snapshot at ``generated/ops/health-snapshot.json`` when
present. Missing or unreadable snapshot → ``unknown`` — never ``healthy``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, TypedDict

from project_atlas.web_api.projects import ProjectSummary, list_projects, vault_identity

OBS_HEALTH_SNAPSHOT_RELATIVE = Path("generated") / "ops" / "health-snapshot.json"

HealthState = Literal["healthy", "degraded", "unhealthy", "unknown"]
ReadPlane = Literal["unread", "ops_snapshot", "stub"]


class VaultHealthView(TypedDict):
    """UI-facing health view — operational plane only; not project authority."""

    available: bool
    rollup: HealthState
    truth_plane: str
    authority_plane: str
    note: str
    source: str
    disclaimer: str


class ReadStatus(TypedDict):
    """Combined read status payload for the web shell."""

    vault_present: bool
    vault_id: str | None
    read_plane: ReadPlane
    health: VaultHealthView
    projects: list[ProjectSummary]
    ui_canonical: bool
    graph_authority: bool
    unknown_equals_healthy: bool


_DISCLAIMER = (
    "OPERATIONAL HEALTH ≠ PROJECT AUTHORITY; UI ≠ canonical; "
    "Graph ≠ authority; Unknown ≠ healthy"
)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _unknown_health(*, source: str) -> VaultHealthView:
    return {
        "available": False,
        "rollup": "unknown",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "OPERATIONAL HEALTH ≠ PROJECT AUTHORITY",
        "source": source,
        "disclaimer": _DISCLAIMER,
    }


def read_vault_health(vault: Path) -> VaultHealthView:
    """Consume OBS snapshot if present; otherwise return unknown (not healthy)."""
    path = vault / OBS_HEALTH_SNAPSHOT_RELATIVE
    raw = _read_json(path)
    if raw is None:
        return _unknown_health(source="missing-or-unreadable-ops-snapshot")

    rollup_raw = raw.get("rollup")
    estate: HealthState = "unknown"
    if isinstance(rollup_raw, dict):
        value = rollup_raw.get("estate")
        # Malformed rollup must not be treated as healthy.
        allowed: tuple[HealthState, ...] = ("healthy", "degraded", "unhealthy", "unknown")
        estate = value if value in allowed else "unknown"

    truth = raw.get("truth_plane")
    authority = raw.get("authority_plane")
    note = raw.get("note")
    return {
        "available": True,
        "rollup": estate,
        "truth_plane": truth if isinstance(truth, str) else "operational",
        "authority_plane": authority if isinstance(authority, str) else "none",
        "note": (
            note
            if isinstance(note, str)
            else "OPERATIONAL HEALTH ≠ PROJECT AUTHORITY"
        ),
        "source": str(OBS_HEALTH_SNAPSHOT_RELATIVE).replace("\\", "/"),
        "disclaimer": _DISCLAIMER,
    }


def read_status(vault: Path) -> ReadStatus:
    """Compose a single read-status document for the web shell.

    Never writes. Flags make ADR-008 invariants explicit for consumers.
    """
    present = vault.is_dir()
    identity = vault_identity(vault) if present else None
    vault_id: str | None = None
    if isinstance(identity, dict):
        for key in ("vault_uuid", "vault_id"):
            value = identity.get(key)
            if isinstance(value, str) and value.strip():
                vault_id = value.strip()
                break

    health = (
        read_vault_health(vault)
        if present
        else _unknown_health(source="vault-absent")
    )
    projects = list_projects(vault) if present else []
    read_plane: ReadPlane = "ops_snapshot" if health["available"] else "unread"

    return {
        "vault_present": present,
        "vault_id": vault_id,
        "read_plane": read_plane,
        "health": health,
        "projects": projects,
        "ui_canonical": False,
        "graph_authority": False,
        "unknown_equals_healthy": False,
    }
