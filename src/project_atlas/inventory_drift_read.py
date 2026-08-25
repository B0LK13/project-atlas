"""AS-CODER-ALPHA-INVENTORY-DRIFT-READ-001 — vault-scoped freshness lens.

Projects live connect-inventory drift so humans and agents can inspect
whether active sources still match ``generated/ops/connect-manifest.json``.

This module never writes, never runs connect, and never grants owner
capability. Evaluation uses the existing inventory-drift library.

Honesty:
- UNKNOWN is never FRESH or HEALTHY
- STALE is never CURRENT
- this lens is not Truth Core authority
- UI / MCP / API projections are not canonical
- a demo fixture must not masquerade as authentic estate freshness
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.inventory_drift import (
    CONNECT_MANIFEST,
    UNKNOWN_PROJECT,
    InventoryDriftError,
    evaluate_connect_inventory_drift,
)
from project_atlas.inventory_drift import (
    PACKAGE_ID as DRIFT_PACKAGE_ID,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-INVENTORY-DRIFT-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-inventory-drift-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.inventory-drift-read.v1"
TRUTH_BOUNDARY: Final[str] = (
    "STALE != CURRENT / UNKNOWN != FRESH / LENS != AUTHORITY"
)

StatusRollup = Literal["UNKNOWN", "FRESH", "STALE"]


class InventoryDriftReadError(ValueError):
    """Fail-closed inventory-drift read error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "stale_is_current": False,
        "unknown_is_fresh": False,
        "unknown_is_healthy": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "write_applied": False,
        "connect_applied": False,
        "demo_is_authentic": False,
        "receipt_is_live_certification": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise InventoryDriftReadError(f"inventory-drift-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise InventoryDriftReadError("inventory-drift-vault-missing")
    return root


def _read_manifest(vault: Path) -> dict[str, Any] | None:
    path = vault / CONNECT_MANIFEST
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _owner_token(item: dict[str, Any]) -> str | None:
    raw = item.get("likely_project") or item.get("project_id")
    if not isinstance(raw, str):
        return None
    owner = raw.strip()
    if not owner or owner == UNKNOWN_PROJECT:
        return None
    return owner


def project_ids_from_manifest(vault: Path) -> list[str]:
    """Deterministic real-project owners from the connect inventory."""
    manifest = _read_manifest(vault)
    if manifest is None:
        return []
    sources = manifest.get("sources")
    found: set[str] = set()
    if isinstance(sources, list):
        for item in sources:
            if not isinstance(item, dict) or item.get("exclusion_reason"):
                continue
            owner = _owner_token(item)
            if owner is not None:
                found.add(owner)
    return sorted(found)


def _wrap_project(vault: Path, project_id: str) -> dict[str, Any]:
    try:
        drift = evaluate_connect_inventory_drift(vault, project_id)
    except InventoryDriftError as exc:
        raise InventoryDriftReadError(str(exc)) from exc
    status_raw = drift.get("status")
    status = status_raw if status_raw in {"FRESH", "STALE", "UNKNOWN"} else "UNKNOWN"
    changed = [
        item for item in (drift.get("changed_paths") or []) if isinstance(item, str)
    ]
    honesty = _honesty()
    source_honesty = drift.get("honesty")
    if isinstance(source_honesty, dict):
        for key, value in source_honesty.items():
            if key in honesty and isinstance(value, (bool, str)):
                honesty[key] = value
    honesty.update(_honesty())
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_package": DRIFT_PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "scoped": True,
        "project_id": project_id,
        "available": status in {"FRESH", "STALE"},
        "status": status,
        "reason": drift.get("reason"),
        "reason_code": drift.get("reason_code"),
        "changed_paths": changed,
        "manifest_path": CONNECT_MANIFEST.as_posix(),
        "honesty": honesty,
        "generated": {"by": GENERATOR_ID},
    }


def _rollup(rows: list[dict[str, Any]]) -> tuple[StatusRollup, str, str]:
    statuses = [str(row.get("status") or "UNKNOWN") for row in rows]
    if any(status == "STALE" for status in statuses):
        return (
            "STALE",
            "SOURCE_INVENTORY_STALE",
            "at least one scoped project drifted from connect-manifest",
        )
    if statuses and all(status == "FRESH" for status in statuses):
        return (
            "FRESH",
            "SOURCE_INVENTORY_FRESH",
            "scoped live sources match connect-manifest",
        )
    if not rows:
        return (
            "UNKNOWN",
            "NO_SCOPED_PROJECTS",
            "no real project owners in connect-manifest; absence is not FRESH",
        )
    return (
        "UNKNOWN",
        "MIXED_OR_UNKNOWN",
        "inventory drift is UNKNOWN for at least one scoped project; UNKNOWN is not FRESH",
    )


def build_inventory_drift_read(
    vault: Path,
    project_id: str | None = None,
    *,
    extra_project_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Read-only inventory-drift projection. Never writes."""
    root = _resolve_vault(vault)
    scoped = (project_id or "").strip() or None
    if scoped == UNKNOWN_PROJECT:
        return {
            "schema_version": 1,
            "schema": SCHEMA_ID,
            "package_id": PACKAGE_ID,
            "source_package": DRIFT_PACKAGE_ID,
            "truth_boundary": TRUTH_BOUNDARY,
            "scoped": True,
            "project_id": UNKNOWN_PROJECT,
            "available": False,
            "status": "UNKNOWN",
            "reason": "unknown-project is never an authoritative inventory owner",
            "reason_code": "SENTINEL_PROJECT",
            "changed_paths": [],
            "manifest_path": CONNECT_MANIFEST.as_posix(),
            "honesty": _honesty(),
            "generated": {"by": GENERATOR_ID},
        }
    if scoped:
        return _wrap_project(root, scoped)

    ids: set[str] = set(project_ids_from_manifest(root))
    for raw in extra_project_ids or []:
        token = raw.strip() if isinstance(raw, str) else ""
        if token and token != UNKNOWN_PROJECT:
            ids.add(token)
    rows = [_wrap_project(root, pid) for pid in sorted(ids)]
    status, reason_code, reason = _rollup(rows)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_package": DRIFT_PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "scoped": False,
        "available": any(bool(row.get("available")) for row in rows),
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "project_count": len(rows),
        "projects": rows,
        "manifest_path": CONNECT_MANIFEST.as_posix(),
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }


def render_inventory_drift_read_text(report: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    lines = [
        f"atlas inventory-drift [{report.get('status', 'UNKNOWN')}]",
        f"  available:    {report.get('available')}",
        f"  reason:       {report.get('reason_code')}",
        f"  scoped:       {report.get('scoped')}",
    ]
    project_id = report.get("project_id")
    if isinstance(project_id, str) and project_id:
        lines.append(f"  project:      {project_id}")
    changed = report.get("changed_paths")
    if isinstance(changed, list) and changed:
        preview = ", ".join(str(item) for item in changed[:8])
        lines.append(f"  changed:      {preview}")
    count = report.get("project_count")
    if isinstance(count, int):
        lines.append(f"  projects:     {count}")
    lines.append(
        "  honesty:      STALE != CURRENT; UNKNOWN != FRESH; LENS != AUTHORITY"
    )
    return "\n".join(lines) + "\n"
