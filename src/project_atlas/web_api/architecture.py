"""AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001 — read-only architecture LIVE_API.

Projects ``build_architecture_lens`` for agents and Web. Never writes Layer B.
ARCHITECTURE LENS != AUTHORITY. No implicit portfolio-all. No secret echo.
Does not materialize ``generated/answers/``. Does not invent stack.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_atlas.project_architecture import (
    ProjectArchitectureError,
    build_architecture_lens,
)

PACKAGE_ID = "AS-CODER-ALPHA-ARCHITECTURE-SURFACE-001"
TRUTH_BOUNDARY = (
    "ARCHITECTURE LENS != AUTHORITY / UI != CANONICAL / "
    "UNKNOWN != STACK / API != TRUTH CORE / NO SECRET ECHO"
)
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebArchitectureError(ValueError):
    """Fail-closed architecture API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebArchitectureError(
            "UNSUPPORTED_SCOPE",
            "architecture-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebArchitectureError(
            "MALFORMED_INPUT",
            "architecture-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_architecture(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped architecture lens (read-only, derived, no writes)."""
    token = _safe_project_id(project_id)
    try:
        lens = build_architecture_lens(vault, token)
    except ProjectArchitectureError as exc:
        raise WebArchitectureError(
            "MALFORMED_INPUT",
            str(exc),
            honesty="MALFORMED_INPUT",
        ) from exc
    payload = dict(lens)
    payload["api_package"] = PACKAGE_ID
    payload["truth_boundary"] = TRUTH_BOUNDARY
    honesty = dict(payload.get("honesty") or {})
    honesty["lens_is_authority"] = False
    honesty["ui_is_canonical"] = False
    payload["honesty"] = honesty
    return payload
