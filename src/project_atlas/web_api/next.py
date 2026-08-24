"""AS-CODER-ALPHA-NEXT-API-001 — read-only What Next LIVE_API.

Projects ``atlas next`` / ``build_next_lens`` for agents and Web.
Never writes Layer B. NEXT != AUTHORITY. NEXT != COMMAND.
No implicit portfolio-all. Does not resurrect AS-2.0-NEXT-001.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_atlas.project_next import ProjectNextError, build_next_lens

PACKAGE_ID = "AS-CODER-ALPHA-NEXT-API-001"
TRUTH_BOUNDARY = (
    "NEXT LENS != AUTHORITY / NEXT ACTION != COMMAND / API != TRUTH CORE"
)
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebNextError(ValueError):
    """Fail-closed What Next API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebNextError(
            "UNSUPPORTED_SCOPE",
            "next-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebNextError(
            "MALFORMED_INPUT",
            "next-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_project_next(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped What Next (read-only, derived)."""
    token = _safe_project_id(project_id)
    try:
        report = build_next_lens(vault, token)
    except ProjectNextError as exc:
        raise WebNextError(
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
    honesty["next_is_authority"] = False
    honesty["next_is_command"] = False
    honesty["ui_is_canonical"] = False
    honesty["auto_execution"] = False
    honesty["unknown_is_valid"] = True
    payload["honesty"] = honesty
    return payload
