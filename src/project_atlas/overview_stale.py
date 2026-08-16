"""AS-CODER-ALPHA-OVERVIEW-STALE-001 — derived overview must not hide drift.

The overview lens reads vault Layer A imported evidence + Layer B project
notes only. After a disk edit, delete, or rename without reconnect,
``status=derived`` (or an unchanged README blurb) can look current.

This helper rehashes project-scoped active connect-manifest sources.
Missing ``source_root`` or inventory is UNKNOWN, never FRESH.

Independent of #380/#381/#383/#385/#386/#387/#388. Does not rewrite
``connect.py`` or ``cli.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component
from project_atlas.source_identity import canonical_source_sha256

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-OVERVIEW-STALE-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-overview-stale-001"
CONNECT_MANIFEST: Final[Path] = Path("generated") / "ops" / "connect-manifest.json"
CONNECT_RECEIPT: Final[Path] = Path("generated") / "ops" / "connect-receipt.json"

DriftStatus = Literal["FRESH", "STALE", "UNKNOWN"]


class OverviewStaleError(ValueError):
    """Fail-closed overview stale-inventory error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise OverviewStaleError(str(exc)) from exc


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _unknown(reason: str, reason_code: str) -> dict[str, Any]:
    return {
        "status": "UNKNOWN",
        "reason": reason,
        "reason_code": reason_code,
        "changed_paths": [],
        "package": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "unknown_is_fresh": False,
            "stale_is_current": False,
            "lens_is_authority": False,
        },
    }


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


def evaluate_overview_inventory_drift(
    vault: Path, project_id: str | None
) -> dict[str, Any]:
    """Compare live active sources to connect-manifest for one project."""
    if not project_id:
        return _unknown(
            "overview stale check requires an explicit project",
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
            owner = item.get("likely_project") or item.get("project_id")
            if isinstance(owner, str) and owner != scoped:
                continue
            path = item.get("path")
            digest = item.get("sha256")
            if (
                isinstance(path, str)
                and path.strip()
                and isinstance(digest, str)
                and digest.strip()
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
        "honesty": {
            "unknown_is_fresh": False,
            "stale_is_current": False,
            "lens_is_authority": False,
        },
    }
