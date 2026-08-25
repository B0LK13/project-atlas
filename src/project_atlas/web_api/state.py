"""AS-CODER-ALPHA-STATE-API-001 — read-only Current State LIVE_API.

Projects ``atlas state`` / ``build_state_lens`` for agents and Web.
Never writes Layer B or ``generated/answers``. STATE != AUTHORITY.
Distinct from intelligence ``/v1/project-state``. Explicit ``?project=`` only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_atlas.project_state import ProjectStateError, build_state_lens

PACKAGE_ID = "AS-CODER-ALPHA-STATE-API-001"
TRUTH_BOUNDARY = (
    "STATE != AUTHORITY / ROLLUP != TRUST SCORE / UNKNOWN != HEALTHY / "
    "API != TRUTH CORE / != /v1/project-state"
)
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebStateError(ValueError):
    """Fail-closed current-state API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebStateError(
            "UNSUPPORTED_SCOPE",
            "state-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebStateError(
            "MALFORMED_INPUT",
            "state-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_project_current_state(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped current-state lens (read-only, derived)."""
    token = _safe_project_id(project_id)
    try:
        report = build_state_lens(vault, token)
    except ProjectStateError as exc:
        raise WebStateError(
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
    honesty["state_is_authority"] = False
    honesty["rollup_is_trust_score"] = False
    honesty["unknown_is_healthy"] = False
    honesty["ui_is_canonical"] = False
    honesty["auto_execution"] = False
    honesty["authentic_pilot"] = False
    payload["honesty"] = honesty
    return payload
