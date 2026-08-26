"""AS-CODER-ALPHA-CAPTURE-READ-001 -- vault-scoped session-capture REPORT READ.

Read-only consume of existing session-capture receipts under
``generated/ops/session-captures``. This module never calls
``capture_session`` or ``list_captures``, never writes capture state,
and never treats a session receipt as Truth Core.

Honesty:
- CAPTURE != AUTHORITY
- SESSION != TRUTH
- CONVERSATION != TRUTH
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-CAPTURE-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-capture-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.capture-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-CODER-ALPHA-CAPTURE-001",)
SOURCE_RELATIVE: Final[str] = "generated/ops/session-captures"
SOURCE_COMMAND: Final[str] = "atlas capture report"
TRUTH_BOUNDARY: Final[str] = (
    "CAPTURE != AUTHORITY / SESSION != TRUTH / CONVERSATION != TRUTH / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "CAPTURE != AUTHORITY",
    "SESSION != TRUTH",
    "CONVERSATION != TRUTH",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebCaptureReadError(ValueError):
    """Fail-closed session-capture REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "capture_is_authority": False,
        "session_is_truth": False,
        "conversation_is_truth": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "capture_state_written": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "owner_capability_granted": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "graph_is_authority": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebCaptureReadError(f"capture-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebCaptureReadError("capture-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebCaptureReadError("capture-read-path-escape")
    return resolved


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebCaptureReadError(f"capture-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebCaptureReadError(f"capture-read-artifact-not-object:{path.name}")
    honesty = payload.get("honesty")
    if isinstance(honesty, dict) and honesty.get("invented_facts") is True:
        raise WebCaptureReadError("capture-read-invented-facts")
    return payload


def _existing_captures(vault: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    malformed = 0
    directory = vault / Path(SOURCE_RELATIVE)
    if directory.exists():
        if not directory.is_dir():
            raise WebCaptureReadError("capture-read-artifact-not-dir")
        safe_dir = _inside(vault, directory)
        for path in sorted(safe_dir.glob("capture-*.json")):
            if not path.is_file():
                continue
            _inside(vault, path)
            try:
                payload = _load_json_object(path)
            except WebCaptureReadError as exc:
                if "invented-facts" in str(exc):
                    raise
                malformed += 1
                continue
            records.append({"path": path.relative_to(vault).as_posix(), "record": payload})
    return {
        "schema_version": 1,
        "artifact_count": len(records),
        "malformed_count": malformed,
        "artifacts": records,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    raw_count = view.get("artifact_count")
    raw_malformed = view.get("malformed_count")
    count = raw_count if isinstance(raw_count, int) else 0
    malformed = raw_malformed if isinstance(raw_malformed, int) else 0
    if count == 0 and malformed == 0:
        return (
            "EMPTY",
            "no existing session-capture receipts; EMPTY != HEALTHY; "
            "CAPTURE != AUTHORITY; SESSION != TRUTH",
            "EMPTY_CAPTURE_VIEW",
            False,
        )
    if count == 0 and malformed > 0:
        return (
            "UNKNOWN",
            "session-capture receipts exist but could not be read; UNKNOWN != HEALTHY",
            "UNKNOWN_CAPTURE_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing session-capture receipts projected; CAPTURE != AUTHORITY; "
        "SESSION != TRUTH",
        "CAPTURE_VIEW_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_relative": SOURCE_RELATIVE,
        "source_command": SOURCE_COMMAND,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "view": view,
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_capture_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing session captures. Never writes."""
    root = _resolve_vault(vault)
    return _envelope(view=_existing_captures(root))


def render_capture_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas capture report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          CAPTURE != AUTHORITY; SESSION != TRUTH; "
            "EMPTY != HEALTHY; UNKNOWN != HEALTHY; MCP != AUTHORITY; "
            "WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
