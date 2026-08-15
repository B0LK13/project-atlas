"""AS-CODER-ALPHA-SOURCE-HEALTH-STALE-001 — inventory CLEAR must not hide disk drift.

Source-health reads vault artifacts only. After a disk edit without reconnect,
``health_state=CLEAR`` can look current. This helper rehashes active
connect-manifest sources. Missing source_root is UNKNOWN, never FRESH.

Independent of #380/#381. Does not rewrite ``connect.py`` or ``cli.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component
from project_atlas.source_identity import canonical_source_sha256

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-SOURCE-HEALTH-STALE-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-source-health-stale-001"
CONNECT_MANIFEST: Final[Path] = Path("generated") / "ops" / "connect-manifest.json"

DriftStatus = Literal["FRESH", "STALE", "UNKNOWN"]


class SourceHealthStaleError(ValueError):
    """Fail-closed source-health stale-inventory error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise SourceHealthStaleError(str(exc)) from exc


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def evaluate_source_inventory_drift(
    vault: Path, project_id: str | None
) -> dict[str, Any]:
    """Compare live active sources to connect-manifest for one project."""
    if not project_id:
        return {
            "status": "UNKNOWN",
            "reason": "source-health stale check requires an explicit project",
            "reason_code": "PROJECT_REQUIRED",
            "changed_paths": [],
            "package": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
        }
    scoped = _safe_project_id(project_id)
    vault_path = vault.expanduser().resolve()
    manifest = _read_json(vault_path / CONNECT_MANIFEST)
    if manifest is None:
        return {
            "status": "UNKNOWN",
            "reason": "connect-manifest absent or unreadable",
            "reason_code": "MANIFEST_ABSENT",
            "changed_paths": [],
            "package": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
        }
    sources = manifest.get("sources")
    rows: list[dict[str, str]] = []
    if isinstance(sources, list):
        for item in sources:
            if not isinstance(item, dict) or item.get("exclusion_reason"):
                continue
            owner = item.get("likely_project") or item.get("project_id")
            if isinstance(owner, str) and owner != scoped:
                continue
            path = item.get("path")
            digest = item.get("sha256")
            if isinstance(path, str) and path.strip():
                rows.append(
                    {
                        "path": path.replace("\\", "/"),
                        "sha256": digest if isinstance(digest, str) else "",
                    }
                )
    if not rows:
        return {
            "status": "UNKNOWN",
            "reason": "no project-scoped active sources",
            "reason_code": "NO_ACTIVE_SOURCES",
            "changed_paths": [],
            "package": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
        }
    raw_root = manifest.get("source_root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        receipt = _read_json(vault_path / "generated" / "ops" / "connect-receipt.json")
        raw_root = receipt.get("project_root") if receipt else None
    if (
        not isinstance(raw_root, str)
        or not raw_root.strip()
        or raw_root.startswith("\\\\")
        or ".." in Path(raw_root).parts
    ):
        return {
            "status": "UNKNOWN",
            "reason": "source_root missing or rejected; stored hashes are not live",
            "reason_code": "SOURCE_ROOT_UNVERIFIED",
            "changed_paths": [],
            "package": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
        }
    try:
        root = Path(raw_root).expanduser().resolve()
    except OSError:
        root = None
    if root is None or not root.is_dir():
        return {
            "status": "UNKNOWN",
            "reason": "source_root missing on disk; stored hashes are not live",
            "reason_code": "SOURCE_ROOT_UNVERIFIED",
            "changed_paths": [],
            "package": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
        }
    changed: list[str] = []
    for row in rows:
        rel = row["path"]
        if not rel or ".." in Path(rel).parts or rel.startswith("/"):
            changed.append(rel or "UNKNOWN")
            continue
        live_path = root / rel
        if not live_path.is_file():
            changed.append(rel)
            continue
        try:
            live = canonical_source_sha256(live_path)
        except OSError:
            changed.append(rel)
            continue
        if live != (row["sha256"] or ""):
            changed.append(rel)
    return {
        "status": "STALE" if changed else "FRESH",
        "reason": "live active sources drifted from connect-manifest"
        if changed
        else "live active sources match connect-manifest",
        "reason_code": "SOURCE_INVENTORY_STALE" if changed else "SOURCE_INVENTORY_FRESH",
        "changed_paths": changed,
        "package": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
    }
