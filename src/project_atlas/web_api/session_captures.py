"""AS-CODER-ALPHA-SESSION-CAPTURE-READ-001 — read-only session inventory.

Lists ops session-capture receipts. Never records, writes, or promotes.
SESSION CAPTURE != TRUTH CORE.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.session_capture import (
    CAPTURE_DIR,
    SessionCaptureError,
    list_captures,
)

PACKAGE_ID = "AS-CODER-ALPHA-SESSION-CAPTURE-READ-001"
CLI_PACKAGE = "AS-CODER-ALPHA-CAPTURE-001"
TRUTH_BOUNDARY = (
    "SESSION READ != AUTHORITY / OPS_RECEIPT != TRUTH CORE / "
    "MCP != WRITE / UI != CANONICAL / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)


class WebSessionCaptureError(ValueError):
    """Fail-closed session-capture read error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id.strip(), label="project id")
    except ValueError as exc:
        raise WebSessionCaptureError(str(exc)) from exc


def _public_row(row: dict[str, Any]) -> dict[str, Any] | None:
    rel = str(row.get("path") or "")
    if not rel or rel.startswith("/") or "\\" in rel or ".." in rel.split("/"):
        return None
    return {
        "capture_id": row.get("capture_id"),
        "project_id": row.get("project_id"),
        "kind": row.get("kind") or "note",
        "source": row.get("source") or "UNKNOWN",
        "summary": row.get("summary") or "UNKNOWN",
        "path": rel,
        "authority": False,
        "status": "ops-receipt",
        "label": "Session capture — non-authoritative",
    }


def list_session_capture_inventory(
    vault: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Read-only vault-scoped session-capture inventory. Never writes."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise WebSessionCaptureError("vault is not a directory")
    scope: str | None = None
    if project_id is not None and str(project_id).strip():
        scope = _safe_project_id(str(project_id))
    try:
        capture_root = (vault / CAPTURE_DIR).resolve()
    except OSError as exc:
        raise WebSessionCaptureError("session-capture-root-unreadable") from exc
    if capture_root.exists() and not capture_root.is_relative_to(vault):
        raw_rows: list[dict[str, Any]] = []
    else:
        try:
            raw_rows = list_captures(vault, project_id=scope, limit=100)
        except SessionCaptureError as exc:
            raise WebSessionCaptureError(str(exc)) from exc
    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        public = _public_row(row)
        if public is not None:
            rows.append(public)
    rows.sort(
        key=lambda row: (
            str(row.get("project_id") or ""),
            str(row.get("capture_id") or ""),
        )
    )
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "cli_package": CLI_PACKAGE,
        "truth_boundary": TRUTH_BOUNDARY,
        "project_id": scope,
        "capture_count": len(rows),
        "captures": rows,
        "available": bool(rows),
        "generated": {"by": "atlas-coder-alpha-session-capture-read-001"},
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "ui_is_canonical": False,
            "unknown_is_valid": True,
            "unknown_equals_healthy": False,
            "fabricated_fields": False,
            "request_contains_project": scope is not None,
            "zero_arg_vault_scope": scope is None,
            "portfolio_implicit_all": False,
            "auto_execution": False,
            "record_or_write": False,
            "truth_core_promotion": False,
            "conversation_surface": False,
            "owner_gate_grant": False,
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
        },
    }
