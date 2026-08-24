"""AS-CODER-ALPHA-ATTENTION-API-001 — read-only attention hygiene LIVE_API.

Projects ``atlas attention`` / ``classify_attention`` for agents and Web.
Never writes Layer B. ATTENTION != AUTHORITY. Not ``/v1/project-attention``
(intelligence risk ranker). No implicit portfolio-all.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_atlas.attention_hygiene import AttentionHygieneError, classify_attention

PACKAGE_ID = "AS-CODER-ALPHA-ATTENTION-API-001"
TRUTH_BOUNDARY = (
    "ATTENTION != AUTHORITY / HYGIENE != INTELLIGENCE RANK / API != TRUTH CORE"
)
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class WebAttentionError(ValueError):
    """Fail-closed attention-hygiene API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not token:
        raise WebAttentionError(
            "UNSUPPORTED_SCOPE",
            "attention-requires-project",
            honesty="UNSUPPORTED_SCOPE",
        )
    if len(token) > 64 or not _ID_RE.fullmatch(token):
        raise WebAttentionError(
            "MALFORMED_INPUT",
            "attention-project-id-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_project_attention_hygiene(vault: Path, project_id: str) -> dict[str, Any]:
    """Return project-scoped attention hygiene (read-only, derived)."""
    token = _safe_project_id(project_id)
    try:
        report = classify_attention(vault, token)
    except AttentionHygieneError as exc:
        raise WebAttentionError(
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
    honesty["attention_is_authority"] = False
    honesty["attention_is_command"] = False
    honesty["hygiene_is_intelligence_rank"] = False
    honesty["ui_is_canonical"] = False
    honesty["auto_execution"] = False
    payload["honesty"] = honesty
    return payload
