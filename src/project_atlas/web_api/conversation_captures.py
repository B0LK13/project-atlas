"""AS-CODER-ALPHA-CONVERSATION-CAPTURE-MCP-001 — read-only conversation inventory.

Lists quarantined conversation-capture receipts. Never submits, reviews, or
promotes. CAPTURE != TRUTH CORE.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.conversation_capture import (
    CAPTURE_DIR,
    ConversationCaptureError,
    list_conversation_captures,
)

PACKAGE_ID = "AS-CODER-ALPHA-CONVERSATION-CAPTURE-MCP-001"
CLI_PACKAGE = "AS-CODER-ALPHA-CONVERSATIONAL-CAPTURE-001"
TRUTH_BOUNDARY = (
    "CONVERSATION READ != AUTHORITY / CAPTURE != TRUTH CORE / "
    "MCP != WRITE / UI != CANONICAL / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)


class WebConversationCaptureError(ValueError):
    """Fail-closed conversation-capture read error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id.strip(), label="project id")
    except ValueError as exc:
        raise WebConversationCaptureError(str(exc)) from exc


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "capture_id": row.get("capture_id"),
        "project_id": row.get("project_id"),
        "source_provider": row.get("source_provider"),
        "summary": row.get("summary") or "UNKNOWN",
        "review_state": row.get("review_state") or "captured",
        "authority": False,
        "classification": row.get("classification"),
        "item_count": row.get("item_count") or 0,
        "path": row.get("path"),
        "status": "quarantined-evidence",
        "label": "Conversation capture — non-authoritative",
    }


def list_conversation_capture_inventory(
    vault: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Read-only vault-scoped conversation-capture inventory. Never writes."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise WebConversationCaptureError("vault is not a directory")
    scope: str | None = None
    if project_id is not None and str(project_id).strip():
        scope = _safe_project_id(str(project_id))
    try:
        capture_root = (vault / CAPTURE_DIR).resolve()
    except OSError as exc:
        raise WebConversationCaptureError("conversation-capture-root-unreadable") from exc
    if capture_root.exists() and not capture_root.is_relative_to(vault):
        raw_rows: list[dict[str, Any]] = []
    else:
        try:
            raw_rows = list_conversation_captures(vault, project_id=scope, limit=100)
        except ConversationCaptureError as exc:
            raise WebConversationCaptureError(str(exc)) from exc
    rows = [_public_row(row) for row in raw_rows if isinstance(row, dict)]
    rows.sort(key=lambda row: (str(row.get("project_id") or ""), str(row.get("capture_id") or "")))
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "cli_package": CLI_PACKAGE,
        "truth_boundary": TRUTH_BOUNDARY,
        "project_id": scope,
        "capture_count": len(rows),
        "captures": rows,
        "available": bool(rows),
        "generated": {"by": "atlas-coder-alpha-conversation-capture-mcp-001-read"},
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "ui_is_canonical": False,
            "unknown_is_valid": True,
            "fabricated_fields": False,
            "request_contains_project": scope is not None,
            "zero_arg_vault_scope": scope is None,
            "portfolio_implicit_all": False,
            "auto_execution": False,
            "submit_or_review": False,
            "truth_core_promotion": False,
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
        },
    }
