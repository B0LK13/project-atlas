"""AS-CODER-ALPHA-INBOX-API-001 — read-only Knowledge Inbox LIVE_API.

Projects ``atlas inbox list`` / ``list_inbox_items`` for agents and Web.
Never writes Layer B. INBOX != AUTHORITY. LISTING != MUTATION != COMMAND.
No implicit portfolio-all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_atlas.knowledge_inbox import KnowledgeInboxError, list_inbox_items

PACKAGE_ID = "AS-CODER-ALPHA-INBOX-API-001"
TRUTH_BOUNDARY = (
    "INBOX != AUTHORITY / LISTING != MUTATION != COMMAND / API != TRUTH CORE"
)


class WebInboxError(ValueError):
    """Fail-closed inbox-list API error."""

    def __init__(self, code: str, message: str, *, honesty: str) -> None:
        self.code = code
        self.honesty = honesty
        super().__init__(message)


def _honesty_for(code: str) -> str:
    if code == "UNSUPPORTED_SCOPE":
        return "UNSUPPORTED_SCOPE"
    return "MALFORMED_INPUT"


def read_project_inbox(
    vault: Path,
    project_id: str,
    *,
    status: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Return project-scoped inbox list (read-only, derived)."""
    try:
        report = list_inbox_items(
            vault,
            project_id=project_id,
            status=status,
            limit=limit,
        )
    except KnowledgeInboxError as exc:
        raise WebInboxError(
            exc.code,
            str(exc),
            honesty=_honesty_for(exc.code),
        ) from exc
    payload = dict(report)
    payload["api_package"] = PACKAGE_ID
    payload["authority"] = "derived"
    payload["truth_boundary"] = TRUTH_BOUNDARY
    honesty = dict(payload.get("honesty") or {})
    honesty["lens_is_authority"] = False
    honesty["inbox_is_authority"] = False
    honesty["inbox_is_command"] = False
    honesty["listing_is_mutation"] = False
    honesty["ui_is_canonical"] = False
    honesty["auto_execution"] = False
    payload["honesty"] = honesty
    return payload
