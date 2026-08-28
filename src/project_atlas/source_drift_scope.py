"""AS-CODER-ALPHA-SOURCE-DRIFT-SCOPE-001 — project-scoped inventory filter.

Shared helper so stale-inventory checks do not import unowned,
``unknown-project``, or sibling-owned connect-manifest rows into an
explicit project scope (CLOUD-031-C CC-P1-002 / D-044).

This package does not mutate overview or architecture lenses (those
surfaces are held by #389 / #404). Consumers adopt the filter.

Also rejects live paths that escape ``source_root`` via symlink
(CC-P2-002). Paths only — no secret echo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-SOURCE-DRIFT-SCOPE-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-source-drift-scope-001"
UNKNOWN_PROJECT: Final[str] = "unknown-project"


def manifest_row_owner(item: dict[str, Any]) -> str | None:
    """Return explicit owner token, or None when ownership is missing."""
    raw = item.get("likely_project") or item.get("project_id")
    if not isinstance(raw, str):
        return None
    owner = raw.strip()
    return owner or None


def manifest_row_matches_scoped_project(
    item: dict[str, Any],
    project_id: str,
) -> bool:
    """Return True only for an exact owner match of an explicit project.

    When ``project_id`` is set, missing owner, ``unknown-project``, empty
    owner, and sibling owners are excluded. Unowned rows must not STALE
    an unrelated scoped project.
    """
    scoped = (project_id or "").strip()
    if not scoped:
        return False
    owner = manifest_row_owner(item)
    if owner is None or owner == UNKNOWN_PROJECT:
        return False
    return owner == scoped


def live_path_contained(root: Path, rel: str) -> Path | None:
    """Resolve ``root / rel`` only when it stays inside ``root``.

    Rejects empty, absolute, ``..`` segments, and symlink escape.
    Does not read file bytes — callers hash only after this guard.
    """
    token = (rel or "").replace("\\", "/").strip()
    if not token or token.startswith("/") or ".." in Path(token).parts:
        return None
    try:
        resolved_root = root.expanduser().resolve()
        live = (resolved_root / token).resolve()
    except OSError:
        return None
    if not live.is_relative_to(resolved_root):
        return None
    return live
