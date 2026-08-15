"""AS-CODER-ALPHA-INBOX-API-001 — read-only Knowledge Inbox LIVE_API.

Projects ``list_inbox_items`` for agents and Web. Never writes Layer B.
INBOX != AUTHORITY. CAPTURE != VERIFIED FACT. No implicit portfolio-all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_atlas.knowledge_inbox import (
    ALLOWED_STATUS,
    KnowledgeInboxError,
    list_inbox_items,
)

PACKAGE_ID = "AS-CODER-ALPHA-INBOX-API-001"
TRUTH_BOUNDARY = "INBOX != AUTHORITY / CAPTURE != VERIFIED FACT / API != TRUTH CORE"
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class WebInboxError(ValueError):
    """Fail-closed inbox API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _map_inbox_error(exc: KnowledgeInboxError) -> WebInboxError:
    code = exc.code or "MALFORMED_INPUT"
    honesty = (
        code
        if code in {"UNSUPPORTED_SCOPE", "MALFORMED_INPUT", "PATH_UNSAFE", "VAULT_NOT_FOUND"}
        else "MALFORMED_INPUT"
    )
    return WebInboxError(code, str(exc), honesty=honesty)


def _safe_limit(limit: int) -> int:
    if limit < 1 or limit > MAX_LIMIT:
        raise WebInboxError(
            "MALFORMED_INPUT",
            "inbox-limit-out-of-range",
            honesty="MALFORMED_INPUT",
        )
    return limit


def _safe_status(status: str | None) -> str | None:
    if status is None:
        return None
    token = status.strip()
    if not token:
        return None
    if token not in ALLOWED_STATUS:
        raise WebInboxError(
            "MALFORMED_INPUT",
            "inbox-status-invalid",
            honesty="MALFORMED_INPUT",
        )
    return token


def read_inbox(
    vault: Path,
    project_id: str,
    *,
    status: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return project-scoped inbox observations (read-only, derived)."""
    status_filter = _safe_status(status)
    bounded = _safe_limit(limit)
    try:
        report = list_inbox_items(
            vault,
            project_id=project_id,
            status=status_filter,
            limit=bounded,
        )
    except KnowledgeInboxError as exc:
        raise _map_inbox_error(exc) from exc
    payload = dict(report)
    payload["api_package"] = PACKAGE_ID
    payload["authority"] = "derived"
    payload["truth_boundary"] = TRUTH_BOUNDARY
    payload["honesty"] = {
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "inbox_is_authority": False,
        "capture_is_verified_fact": False,
        "promoted_to_authority": False,
        "unknown_is_valid": True,
    }
    payload["promoted_to_authority"] = False
    return payload
