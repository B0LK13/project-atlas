"""AS-CODER-ALPHA-ARCHITECTURE-STALE-001 — derived architecture must not hide drift.

The architecture lens reads imported architecture-bearing documents, not
live disk. After a disk edit, delete, or rename without reconnect,
``status=derived`` can look current.

This helper rehashes project-scoped architecture-bearing connect-manifest
sources. Missing ``source_root`` or inventory is UNKNOWN, never FRESH.

Independent of #389 overview_stale. Does not rewrite ``connect.py`` or
``cli.py``. Does not edit ``WORKLOG.md`` or ``docs/backlog.md``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, Literal

from atlas_contracts.identity import safe_relative_component
from project_atlas.source_identity import canonical_source_sha256

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-ARCHITECTURE-STALE-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-architecture-stale-001"
CONNECT_MANIFEST: Final[Path] = Path("generated") / "ops" / "connect-manifest.json"
CONNECT_RECEIPT: Final[Path] = Path("generated") / "ops" / "connect-receipt.json"

DriftStatus = Literal["FRESH", "STALE", "UNKNOWN"]


class ArchitectureStaleError(ValueError):
    """Fail-closed architecture stale-inventory error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise ArchitectureStaleError(str(exc)) from exc


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


def is_architecture_bearing_path(path: str) -> bool:
    """Match architecture-authority candidates. README is never architecture."""
    posix = path.replace("\\", "/").removeprefix("./")
    lower = posix.lower()
    if lower.startswith(("docs/demo/", "fixtures/", "deps/")):
        return False
    if "/atlas-2.2/" in lower or "/atlas-2.1/" in lower:
        return False
    if Path(posix).name.lower() in {"readme.md", "readme.txt", "readme"}:
        return False
    if lower in {
        "docs/plan.md",
        "agents.md",
        "claude.md",
        "architecture.md",
        "docs/prp.md",
        "docs/atlas-2.0/architecture.md",
    }:
        return True
    if lower.endswith("/architecture.md") and lower.startswith("docs/"):
        return True
    return bool(lower.endswith("/plan.md"))


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


def evaluate_architecture_inventory_drift(
    vault: Path,
    project_id: str | None,
    *,
    path_filter: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """Compare live architecture-bearing sources to connect-manifest."""
    accept = path_filter or is_architecture_bearing_path
    if not project_id:
        return _unknown(
            "architecture stale check requires an explicit project",
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
                and accept(path)
            ):
                rows.append(
                    {
                        "path": path.replace("\\", "/"),
                        "sha256": digest,
                    }
                )
    if not rows:
        return _unknown(
            "no project-scoped hashed architecture-bearing sources",
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
            "live architecture sources drifted from connect-manifest"
            if stale
            else "live architecture sources match connect-manifest"
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
