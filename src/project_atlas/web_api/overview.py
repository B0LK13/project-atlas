"""AS-CODER-ALPHA-OVERVIEW-API-001 — read-only Project Overview LIVE_API.

Projects ``atlas overview`` / ``build_overview_lens`` for agents and Web.
Never writes Layer B or ``generated/answers``. OVERVIEW != AUTHORITY.
No implicit portfolio-all. Explicit ``?project=`` only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_atlas.overview import OverviewError, build_overview_lens

PACKAGE_ID = "AS-CODER-ALPHA-OVERVIEW-API-001"
TRUTH_BOUNDARY = (
    "OVERVIEW != AUTHORITY / UNKNOWN != HEALTHY / API != TRUTH CORE"
)
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebOverviewError(ValueError):
    """Fail-closed overview API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebOverviewError(
            "UNSUPPORTED_SCOPE",
            "overview-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebOverviewError(
            "MALFORMED_INPUT",
            "overview-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_project_overview(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped overview lens (read-only, derived)."""
    token = _safe_project_id(project_id)
    try:
        report = build_overview_lens(vault, token)
    except OverviewError as exc:
        raise WebOverviewError(
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
    honesty["overview_is_authority"] = False
    honesty["unknown_is_healthy"] = False
    honesty["ui_is_canonical"] = False
    honesty["auto_execution"] = False
    honesty["authentic_pilot"] = False
    payload["honesty"] = honesty
    return payload
