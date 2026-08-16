"""AS-CODER-ALPHA-SOURCE-HEALTH-API-001 — read-only source-health LIVE_API.

Projects ``atlas source-health`` for agents and Web. Never writes Layer B.
SOURCE HEALTH != AUTHORITY. No implicit portfolio-all. No secret echo.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_atlas.source_health import SourceHealthError, explain_source_health

PACKAGE_ID = "AS-CODER-ALPHA-SOURCE-HEALTH-API-001"
TRUTH_BOUNDARY = "SOURCE HEALTH != AUTHORITY / NO SECRET ECHO / API != TRUTH CORE"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebSourceHealthError(ValueError):
    """Fail-closed source-health API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebSourceHealthError(
            "UNSUPPORTED_SCOPE",
            "source-health-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebSourceHealthError(
            "MALFORMED_INPUT",
            "source-health-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_source_health(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped source-health (read-only, derived)."""
    token = _safe_project_id(project_id)
    try:
        report = explain_source_health(vault, token)
    except SourceHealthError as exc:
        raise WebSourceHealthError(
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
    honesty["ui_is_canonical"] = False
    payload["honesty"] = honesty
    return payload
