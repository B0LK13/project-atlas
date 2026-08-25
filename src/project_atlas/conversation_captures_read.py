"""AS-CODER-ALPHA-CONVERSATION-CAPTURES-READ-001 — vault-scoped capture lens.

Projects existing CAPTURE-002 quarantined conversation evidence so humans
and agents can inspect the inventory. This module never writes, never
promotes review_state to Truth Core, and never grants owner capability.

Honesty:
- CAPTURE is never Truth Core
- REVIEWED is never PROMOTED
- EMPTY is never HEALTHY
- UNKNOWN is never CLEAN
- QUARANTINE is never owner authority
- this lens is not Truth Core authority
- UI / MCP / API projections are not canonical
- a demo fixture must not masquerade as authentic estate inventory
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.conversation_capture import (
    CAPTURE_DIR,
    ConversationCaptureError,
    list_conversation_captures,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-CONVERSATION-CAPTURES-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-conversation-captures-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.conversation-captures-read.v1"
SOURCE_PACKAGE: Final[str] = "AS-CODER-ALPHA-CONVERSATIONAL-CAPTURE-001"
TRUTH_BOUNDARY: Final[str] = (
    "CAPTURE != TRUTH CORE / REVIEWED != PROMOTED / EMPTY != HEALTHY / "
    "UNKNOWN != CLEAN / QUARANTINE != AUTHORITY / LENS != AUTHORITY"
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class ConversationCapturesReadError(ValueError):
    """Fail-closed conversation-capture read error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "capture_is_truth_core": False,
        "reviewed_is_promoted": False,
        "quarantine_is_authority": False,
        "empty_is_healthy": False,
        "unknown_is_clean": False,
        "unknown_is_healthy": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "owner_capability_granted": False,
        "authentic_pilot": False,
        "write_applied": False,
        "conversation_is_owner_grant": False,
        "demo_is_authentic": False,
        "receipt_is_live_certification": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise ConversationCapturesReadError(
            f"conversation-captures-vault-unreadable:{exc}"
        ) from exc
    if not root.is_dir():
        raise ConversationCapturesReadError("conversation-captures-vault-missing")
    return root


def _safe_project_id(project_id: str) -> str:
    token = project_id.strip()
    if not token or "/" in token or "\\" in token or token in {".", ".."}:
        raise ConversationCapturesReadError(
            f"conversation-captures-project-unsafe:{project_id!r}"
        )
    return token


def _public_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "capture_id": raw.get("capture_id"),
        "project_id": raw.get("project_id"),
        "source_provider": raw.get("source_provider"),
        "summary": raw.get("summary"),
        "review_state": raw.get("review_state"),
        "classification": raw.get("classification"),
        "item_count": raw.get("item_count"),
        "path": raw.get("path"),
        "projection_path": raw.get("projection_path"),
        "status": raw.get("status") or "quarantined-evidence",
        "authority": False,
        "promoted_to_authority": False,
        "label": "Conversation capture — quarantined evidence, not Truth Core",
    }


def _envelope(
    *,
    status: StatusRollup,
    reason: str,
    reason_code: str,
    available: bool,
    scoped: bool,
    project_id: str | None,
    rows: list[dict[str, Any]],
    directory_present: bool,
    unreadable_count: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_package": SOURCE_PACKAGE,
        "truth_boundary": TRUTH_BOUNDARY,
        "scoped": scoped,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "directory_present": directory_present,
        "directory_path": CAPTURE_DIR.as_posix(),
        "capture_count": len(rows),
        "unreadable_count": unreadable_count,
        "captures": rows,
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }
    if project_id is not None:
        payload["project_id"] = project_id
    return payload


def _unreadable_capture_count(root: Path) -> int:
    capture_root = root / CAPTURE_DIR
    if not capture_root.is_dir():
        return 0
    bad = 0
    for path in sorted(capture_root.glob("ccap-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            bad += 1
            continue
        if not isinstance(payload, dict):
            bad += 1
    return bad


def build_conversation_captures_read(
    vault: Path,
    project_id: str | None = None,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    """Read-only conversation-capture projection. Never writes."""
    root = _resolve_vault(vault)
    scoped = (project_id or "").strip() or None
    if scoped is not None:
        scoped = _safe_project_id(scoped)
    if limit < 1:
        raise ConversationCapturesReadError("conversation-captures-limit-invalid")

    capture_root = root / CAPTURE_DIR
    if not capture_root.is_dir():
        return _envelope(
            status="UNKNOWN",
            reason=(
                "conversation-capture directory is absent; absence is not a "
                "clean or healthy inventory"
            ),
            reason_code="DIRECTORY_ABSENT",
            available=False,
            scoped=scoped is not None,
            project_id=scoped,
            rows=[],
            directory_present=False,
            unreadable_count=0,
        )

    unreadable = _unreadable_capture_count(root)
    try:
        raw_rows = list_conversation_captures(root, project_id=scoped, limit=limit)
    except ConversationCaptureError as exc:
        raise ConversationCapturesReadError(
            f"conversation-captures-list-failed:{exc.code}"
        ) from exc

    rows = [_public_row(item) for item in raw_rows if isinstance(item, dict)]
    if rows:
        return _envelope(
            status="PRESENT",
            reason=(
                "quarantined conversation captures remain visible as "
                "non-authoritative evidence"
            ),
            reason_code="CAPTURES_PRESENT",
            available=True,
            scoped=scoped is not None,
            project_id=scoped,
            rows=rows,
            directory_present=True,
            unreadable_count=unreadable,
        )
    if unreadable:
        return _envelope(
            status="UNKNOWN",
            reason=(
                "conversation-capture files exist but could not be read; "
                "unreadable evidence is not an empty or healthy inventory"
            ),
            reason_code="CAPTURES_UNREADABLE",
            available=False,
            scoped=scoped is not None,
            project_id=scoped,
            rows=[],
            directory_present=True,
            unreadable_count=unreadable,
        )
    return _envelope(
        status="EMPTY",
        reason=(
            "conversation-capture directory is present and empty for this "
            "scope; EMPTY is not healthy and does not invent captures"
        ),
        reason_code="DIRECTORY_EMPTY",
        available=True,
        scoped=scoped is not None,
        project_id=scoped,
        rows=[],
        directory_present=True,
        unreadable_count=0,
    )


def render_conversation_captures_read_text(report: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    lines = [
        f"atlas conversation-captures [{report.get('status', 'UNKNOWN')}]",
        f"  available:    {report.get('available')}",
        f"  reason:       {report.get('reason_code')}",
        f"  scoped:       {report.get('scoped')}",
        f"  directory:    {report.get('directory_present')}",
        f"  captures:     {report.get('capture_count')}",
    ]
    project_id = report.get("project_id")
    if isinstance(project_id, str) and project_id:
        lines.append(f"  project:      {project_id}")
    rows = report.get("captures")
    if isinstance(rows, list):
        for item in rows[:8]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"  capture:      {item.get('capture_id')} "
                f"[{item.get('review_state')}] {item.get('summary')}"
            )
    lines.append(
        "  honesty:      CAPTURE != TRUTH CORE; REVIEWED != PROMOTED; "
        "EMPTY != HEALTHY; LENS != AUTHORITY"
    )
    return "\n".join(lines) + "\n"
