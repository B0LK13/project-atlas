"""AS-CODER-ALPHA-CHANGED-API-001 — read-only What Changed LIVE_API.

Projects ``atlas changed`` / ``build_changed_lens`` for agents and Web.
Never writes Layer B or rotates connect inventories. CHANGED != KDIFF.
Missing inventory stays UNKNOWN history, never invented UNCHANGED.
No implicit portfolio-all.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_atlas.project_changed import (
    INVENTORY_RELATIVE,
    PREV_INVENTORY_RELATIVE,
    ProjectChangedError,
    build_changed_lens,
    diff_inventories,
)

PACKAGE_ID = "AS-CODER-ALPHA-CHANGED-API-001"
TRUTH_BOUNDARY = (
    "CHANGED != KDIFF / CHANGED != AUTHORITY / UNKNOWN HISTORY != UNCHANGED"
)
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebChangedError(ValueError):
    """Fail-closed what-changed API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebChangedError(
            "UNSUPPORTED_SCOPE",
            "changed-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebChangedError(
            "MALFORMED_INPUT",
            "changed-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _empty_inventory() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.connect-inventory.v1",
        "package": "AS-CODER-ALPHA-CHANGED-001",
        "sources": [],
        "by_path": {},
        "generated": {"by": "atlas-coder-alpha-changed-api-001"},
    }


def read_project_changed(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped what-changed lens (read-only, derived)."""
    token = _safe_project_id(project_id)
    current = _read_json(vault / INVENTORY_RELATIVE)
    previous = _read_json(vault / PREV_INVENTORY_RELATIVE)
    if current is None:
        # Missing inventory is UNKNOWN history, not invented UNCHANGED.
        current = _empty_inventory()
        previous = None
    try:
        delta = diff_inventories(previous, current)
        report = build_changed_lens(
            vault,
            token,
            previous=previous,
            current=current,
            delta=delta,
        )
    except ProjectChangedError as exc:
        raise WebChangedError(
            "MALFORMED_INPUT",
            str(exc),
            honesty="MALFORMED_INPUT",
        ) from exc
    payload = dict(report)
    payload["api_package"] = PACKAGE_ID
    payload["authority"] = "derived"
    payload["truth_boundary"] = TRUTH_BOUNDARY
    honesty = dict(payload.get("honesty") or {})
    honesty["lens_is_authority"] = False
    honesty["changed_is_authority"] = False
    honesty["changed_is_kdiff"] = False
    honesty["unknown_is_healthy"] = False
    honesty["unknown_is_fresh"] = False
    honesty["ui_is_canonical"] = False
    honesty["auto_execution"] = False
    payload["honesty"] = honesty
    return payload
