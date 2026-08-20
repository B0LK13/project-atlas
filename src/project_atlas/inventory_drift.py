"""AS-CODER-ALPHA-INVENTORY-DRIFT-001 — shared connect-inventory freshness.

Compares live active sources to ``generated/ops/connect-manifest.json``.
Missing root or inventory is UNKNOWN, never FRESH. Stored hashes alone
are not live evidence.

This module is source-drift only. It does not rank Next, score attention,
compose briefs, extract architecture slots, or classify state.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component
from atlas_contracts.paths import resolve_under_root
from project_atlas.source_identity import canonical_source_sha256

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-INVENTORY-DRIFT-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-inventory-drift-001"
CONNECT_MANIFEST: Final[Path] = Path("generated") / "ops" / "connect-manifest.json"
CONNECT_RECEIPT: Final[Path] = Path("generated") / "ops" / "connect-receipt.json"
UNKNOWN_PROJECT: Final[str] = "unknown-project"

DriftStatus = Literal["FRESH", "STALE", "UNKNOWN"]


class InventoryDriftError(ValueError):
    """Fail-closed inventory-drift error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise InventoryDriftError(str(exc)) from exc


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _honesty() -> dict[str, bool]:
    return {
        "unknown_is_fresh": False,
        "unknown_is_healthy": False,
        "stale_is_current": False,
        "lens_is_authority": False,
    }


def _unknown(reason: str, reason_code: str) -> dict[str, Any]:
    return {
        "status": "UNKNOWN",
        "reason": reason,
        "reason_code": reason_code,
        "changed_paths": [],
        "package": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "honesty": _honesty(),
    }


def _row_owner(item: dict[str, Any]) -> str | None:
    """Return an explicit owner token, or None when ownership is missing."""
    raw = item.get("likely_project") or item.get("project_id")
    if not isinstance(raw, str):
        return None
    owner = raw.strip()
    return owner or None


def _row_matches_scoped_project(item: dict[str, Any], scoped: str) -> bool:
    """Exact real-project owner only. Sentinel/missing/sibling stay out of scope.

    ``unknown-project`` is never an authoritative owner, including when the
    requested ``project_id`` is itself the sentinel (D-OWNER-DRIFT-039).
    """
    if scoped == UNKNOWN_PROJECT:
        return False
    owner = _row_owner(item)
    if owner is None or owner == UNKNOWN_PROJECT:
        return False
    return owner == scoped


def _source_root(manifest: dict[str, Any], vault: Path) -> Path | None:
    raw_root = manifest.get("source_root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        receipt = _read_json(vault / CONNECT_RECEIPT)
        raw_root = receipt.get("project_root") if receipt else None
    if (
        not isinstance(raw_root, str)
        or not raw_root.strip()
        or raw_root.startswith("\\\\")
        or ".." in Path(raw_root).parts
    ):
        return None
    try:
        root = Path(raw_root).expanduser().resolve()
    except OSError:
        return None
    if not root.is_dir():
        return None
    return root


def evaluate_connect_inventory_drift(
    vault: Path,
    project_id: str | None,
    *,
    path_filter: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Compare live active sources to the connect-manifest for one project.

    Unscoped manifest rows (no ``likely_project`` / ``project_id``) are
    omitted when a project is required (D-044/D-050). Path traversal is
    rejected, not followed. Secret content is never returned.
    """
    if not project_id:
        return _unknown(
            "inventory drift check requires an explicit project",
            "PROJECT_REQUIRED",
        )
    scoped = _safe_project_id(project_id)
    vault_path = vault.expanduser().resolve()
    manifest = _read_json(vault_path / CONNECT_MANIFEST)
    if manifest is None:
        return _unknown(
            "connect-manifest absent or unreadable",
            "MANIFEST_ABSENT",
        )
    sources = manifest.get("sources")
    rows: list[dict[str, str]] = []
    if isinstance(sources, list):
        for item in sources:
            if not isinstance(item, dict) or item.get("exclusion_reason"):
                continue
            if not _row_matches_scoped_project(item, scoped):
                continue
            path = item.get("path")
            digest = item.get("sha256")
            if (
                isinstance(path, str)
                and path.strip()
                and isinstance(digest, str)
                and digest.strip()
                and (path_filter is None or path_filter(path))
            ):
                rows.append(
                    {
                        "path": path.replace("\\", "/"),
                        "sha256": digest,
                    }
                )
    if not rows:
        return _unknown(
            "no project-scoped hashed active sources",
            "NO_ACTIVE_SOURCES",
        )
    root = _source_root(manifest, vault_path)
    if root is None:
        return _unknown(
            "source_root missing or rejected; stored hashes are not live",
            "SOURCE_ROOT_UNVERIFIED",
        )
    changed: list[str] = []
    for row in rows:
        rel = row["path"]
        try:
            live_path = resolve_under_root(root, rel, label="source path")
        except ValueError:
            changed.append(rel or "UNKNOWN")
            continue
        if not live_path.is_file():
            changed.append(rel)
            continue
        try:
            live = canonical_source_sha256(live_path)
        except OSError:
            changed.append(rel)
            continue
        if live != row["sha256"]:
            changed.append(rel)
    stale = bool(changed)
    return {
        "status": "STALE" if stale else "FRESH",
        "reason": (
            "live active sources drifted from connect-manifest"
            if stale
            else "live active sources match connect-manifest"
        ),
        "reason_code": "SOURCE_INVENTORY_STALE" if stale else "SOURCE_INVENTORY_FRESH",
        "changed_paths": changed,
        "package": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "honesty": _honesty(),
    }


def attach_source_drift(
    lens: dict[str, Any],
    vault: Path,
    project_id: str,
    *,
    path_filter: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Attach drift metadata. Does not invent lens-specific meaning."""
    inspected = [
        item for item in (lens.get("inspected_artifacts") or []) if isinstance(item, str)
    ]
    inspected.append("generated/ops/connect-manifest.json")
    drift = evaluate_connect_inventory_drift(
        vault, project_id, path_filter=path_filter
    )
    drift_status = str(drift.get("status") or "UNKNOWN")
    changed_paths = [
        item for item in (drift.get("changed_paths") or []) if isinstance(item, str)
    ]
    notes = [item for item in (lens.get("notes") or []) if isinstance(item, str)]
    summary = lens.get("summary")
    value = lens.get("value")
    if drift_status == "STALE":
        notes.append("STALE SOURCE INVENTORY != CURRENT LENS; reconnect first")
        if isinstance(summary, str) and summary:
            annotated = f"{summary}; source_inventory_stale={len(changed_paths)}"
            # Keep distinct published values (e.g. next suggested-work line).
            if value == summary:
                value = annotated
            summary = annotated
    honesty = dict(lens.get("honesty") or {}) if isinstance(lens.get("honesty"), dict) else {}
    honesty.update(
        {
            "lens_is_authority": False,
            "unknown_is_healthy": False,
            "unknown_is_fresh": False,
            "stale_is_current": False,
            "source_inventory_stale": drift_status == "STALE",
        }
    )
    lens["summary"] = summary
    lens["value"] = value
    lens["inspected_artifacts"] = inspected
    lens["notes"] = notes
    lens["source_drift"] = {
        "status": drift_status,
        "reason": drift.get("reason"),
        "reason_code": drift.get("reason_code"),
        "changed_paths": changed_paths[:20],
        "package": PACKAGE_ID,
        "honesty": drift.get("honesty") or _honesty(),
    }
    lens["honesty"] = honesty
    return lens
