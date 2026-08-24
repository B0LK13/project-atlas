"""AS-CODER-ALPHA-UNKNOWN-API-001 — read-only unknown/conflict LIVE_API.

Projects ``atlas unknown`` / ``build_unknown_lens`` for agents and Web.
Never writes Layer B. UNKNOWN != HEALTHY. UNKNOWN != AUTHORITY.
No implicit portfolio-all.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_atlas.project_unknown import ProjectUnknownError, build_unknown_lens

PACKAGE_ID = "AS-CODER-ALPHA-UNKNOWN-API-001"
TRUTH_BOUNDARY = "UNKNOWN != HEALTHY / UNKNOWN != AUTHORITY / API != TRUTH CORE"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebUnknownError(ValueError):
    """Fail-closed unknown/conflict API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebUnknownError(
            "UNSUPPORTED_SCOPE",
            "unknown-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebUnknownError(
            "MALFORMED_INPUT",
            "unknown-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_project_unknown(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped unknown/conflict lens (read-only, derived)."""
    token = _safe_project_id(project_id)
    try:
        report = build_unknown_lens(vault, token)
    except ProjectUnknownError as exc:
        raise WebUnknownError(
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
    honesty["unknown_is_authority"] = False
    honesty["unknown_is_healthy"] = False
    honesty["unknown_is_fresh"] = False
    honesty["rollup_is_trust_score"] = False
    honesty["ui_is_canonical"] = False
    honesty["auto_execution"] = False
    payload["honesty"] = honesty
    return payload
