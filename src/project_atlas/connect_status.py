"""AS-CODER-ALPHA-CONNECT-STATUS-001 — vault-scoped connect freshness read.

Projects existing ``connect-receipt`` and ``incremental-connect-receipt``
artifacts so humans and agents can see whether Atlas last bound this vault
without re-running compile. The lens is operational only.

Honesty:
- missing / unreadable receipts stay UNKNOWN (never FRESH)
- incremental skip is not Truth Core authority
- connect status is not owner capability or AUTHENTIC_PILOT
- UI / MCP / API projections are not canonical
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.connect import RECEIPT_RELATIVE
from project_atlas.incremental_connect import INCREMENTAL_RECEIPT_RELATIVE

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-CONNECT-STATUS-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-connect-status-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.connect-status.v1"
TRUTH_BOUNDARY: Final[str] = (
    "CONNECT_STATUS != AUTHORITY / SKIP != TRUTH CORE / UNKNOWN != FRESH"
)

Presence = Literal["absent", "ok", "unreadable"]
StatusRollup = Literal["UNKNOWN", "RECORDED"]


class ConnectStatusError(ValueError):
    """Fail-closed connect-status error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "connect_status_is_authority": False,
        "skip_is_truth_core": False,
        "unknown_is_fresh": False,
        "unknown_is_healthy": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "fabricated_receipt": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _read_json_object(path: Path) -> tuple[Presence, dict[str, Any] | None]:
    if not path.is_file():
        return "absent", None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "unreadable", None
    if isinstance(raw, dict):
        return "ok", raw
    return "unreadable", None


def _safe_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _safe_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _project_connect_receipt(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "status": None,
            "vault_id": None,
            "project_root": None,
            "bound_project_id": None,
            "projects": [],
            "documents_ingested": None,
            "incremental_disposition": None,
        }
    incremental = payload.get("incremental")
    disposition = None
    if isinstance(incremental, dict):
        disposition = _safe_str(incremental.get("disposition"))
    return {
        "status": _safe_str(payload.get("status")),
        "vault_id": _safe_str(payload.get("vault_id")),
        "project_root": _safe_str(payload.get("project_root")),
        "bound_project_id": _safe_str(payload.get("bound_project_id")),
        "projects": _safe_str_list(payload.get("projects")),
        "documents_ingested": _safe_int(payload.get("documents_ingested")),
        "incremental_disposition": disposition,
    }


def _project_incremental_receipt(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "disposition": None,
            "status": None,
            "operational_only": True,
        }
    return {
        "disposition": _safe_str(payload.get("disposition")),
        "status": _safe_str(payload.get("status")),
        "operational_only": True,
    }


def build_connect_status(vault: Path) -> dict[str, Any]:
    """Read-only connect-status projection. Never writes. Never invents FRESH."""
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise ConnectStatusError(f"connect-status-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise ConnectStatusError("connect-status-vault-missing")

    connect_presence, connect_payload = _read_json_object(root / RECEIPT_RELATIVE)
    incremental_presence, incremental_payload = _read_json_object(
        root / INCREMENTAL_RECEIPT_RELATIVE
    )

    if connect_presence == "ok":
        rollup: StatusRollup = "RECORDED"
        reason_code = "CONNECT_RECEIPT_PRESENT"
        reason = "A connect receipt is present; this is not a freshness or authority claim."
    elif connect_presence == "unreadable":
        rollup = "UNKNOWN"
        reason_code = "CONNECT_RECEIPT_UNREADABLE"
        reason = "Connect receipt exists but is unreadable; status stays UNKNOWN."
    else:
        rollup = "UNKNOWN"
        reason_code = "CONNECT_RECEIPT_ABSENT"
        reason = "No connect receipt on disk; run atlas connect before treating the vault as bound."

    if incremental_presence == "unreadable" and rollup == "RECORDED":
        # Incremental artifact damage must not look like a clean skip.
        reason_code = "INCREMENTAL_RECEIPT_UNREADABLE"
        reason = (
            "Connect receipt is present but the incremental receipt is unreadable; "
            "skip honesty stays UNKNOWN."
        )

    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": connect_presence == "ok",
        "status": rollup,
        "reason": reason,
        "reason_code": reason_code,
        "connect_receipt": {
            "presence": connect_presence,
            "relative_path": RECEIPT_RELATIVE.as_posix(),
            **_project_connect_receipt(connect_payload),
        },
        "incremental_receipt": {
            "presence": incremental_presence,
            "relative_path": INCREMENTAL_RECEIPT_RELATIVE.as_posix(),
            **_project_incremental_receipt(incremental_payload),
        },
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }


def render_connect_status_text(report: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    connect = report.get("connect_receipt") or {}
    incremental = report.get("incremental_receipt") or {}
    projects = connect.get("projects") or []
    project_text = ", ".join(projects) if isinstance(projects, list) and projects else "(none)"
    lines = [
        f"atlas connect-status [{report.get('status', 'UNKNOWN')}]",
        f"  available: {report.get('available')}",
        f"  reason:    {report.get('reason_code')}",
        f"  vault_id:  {connect.get('vault_id') or 'UNKNOWN'}",
        f"  project:   {connect.get('project_root') or 'UNKNOWN'}",
        f"  bound:     {connect.get('bound_project_id') or 'UNKNOWN'}",
        f"  projects:  {project_text}",
        f"  ingested:  {connect.get('documents_ingested')}",
        f"  incremental: {incremental.get('disposition') or incremental.get('presence')}",
        "  honesty:   CONNECT_STATUS != AUTHORITY; SKIP != TRUTH CORE; UNKNOWN != FRESH",
    ]
    return "\n".join(lines) + "\n"
