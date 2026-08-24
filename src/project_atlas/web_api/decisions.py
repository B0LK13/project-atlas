"""AS-CODER-ALPHA-DECISIONS-API-001 — read-only decisions LIVE_API.

Projects ``atlas decisions`` / ``build_decisions_lens`` for agents and Web.
Never writes Layer B. DECISIONS != AUTHORITY. Empty evidence stays UNKNOWN.
No implicit portfolio-all.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_atlas.project_decisions import ProjectDecisionsError, build_decisions_lens

PACKAGE_ID = "AS-CODER-ALPHA-DECISIONS-API-001"
TRUTH_BOUNDARY = "DECISIONS != AUTHORITY / LENS != LAYER B / API != TRUTH CORE"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebDecisionsError(ValueError):
    """Fail-closed decisions API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebDecisionsError(
            "UNSUPPORTED_SCOPE",
            "decisions-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebDecisionsError(
            "MALFORMED_INPUT",
            "decisions-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_project_decisions(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped decisions lens (read-only, derived)."""
    token = _safe_project_id(project_id)
    try:
        report = build_decisions_lens(vault, token)
    except ProjectDecisionsError as exc:
        raise WebDecisionsError(
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
    honesty["decisions_are_authority"] = False
    honesty["ui_is_canonical"] = False
    honesty["auto_execution"] = False
    payload["honesty"] = honesty
    return payload
