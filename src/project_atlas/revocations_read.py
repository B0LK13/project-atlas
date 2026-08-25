"""AS-CODER-ALPHA-REVOCATIONS-READ-001 — vault-scoped receipt-revocation list.

Reads existing ``generated/ops/receipt-revocations.json`` so humans and
agents can inspect recorded revocation / invalidation rows without writing,
revoking, or inventing authority.

Honesty:
- missing index stays UNKNOWN (never HEALTHY / FRESH)
- empty index is EMPTY, not HEALTHY
- recorded rows are operational facts, not project authority
- this lens never writes, revokes, or grants owner capability
- UI / MCP / API projections are not canonical
- receipt revocation is not AUTHENTIC_PILOT or owner authorization
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.receipt_revocation import (
    INDEX_RELATIVE,
    RevocationError,
    list_revocations,
)

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-REVOCATIONS-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-revocations-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.revocations-read.v1"
TRUTH_BOUNDARY: Final[str] = (
    "RECEIPT REVOCATION != AUTHORITY / EMPTY != HEALTHY / ABSENT != FABRICATED"
)
DEFAULT_LIMIT: Final[int] = 100
MAX_LIMIT: Final[int] = 500

StatusRollup = Literal["UNKNOWN", "EMPTY", "RECORDED"]


class RevocationsReadError(ValueError):
    """Fail-closed revocations-read error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "revocations_are_authority": False,
        "empty_is_healthy": False,
        "absent_is_fabricated": False,
        "unknown_is_healthy": False,
        "unknown_is_fresh": False,
        "presence_is_validate": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "fabricated_revocations": False,
        "revoke_applied": False,
        "write_applied": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def build_revocations_read(
    vault: Path, *, limit: int = DEFAULT_LIMIT
) -> dict[str, Any]:
    """Read-only revocation-index projection. Never writes. Never invents rows."""
    if limit < 1 or limit > MAX_LIMIT:
        raise RevocationsReadError("revocations-limit-out-of-range")
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise RevocationsReadError(f"revocations-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise RevocationsReadError("revocations-vault-missing")

    index_present = (root / INDEX_RELATIVE).is_file()
    if not index_present:
        rows: list[dict[str, Any]] = []
        rollup: StatusRollup = "UNKNOWN"
        reason_code = "INDEX_ABSENT"
        reason = (
            "No receipt-revocation index on disk; absence is not HEALTHY and "
            "is not a fabricated revocation list."
        )
        available = False
    else:
        try:
            rows = list_revocations(root)
        except RevocationError as exc:
            raise RevocationsReadError(str(exc)) from exc
        if not rows:
            rollup = "EMPTY"
            reason_code = "INDEX_EMPTY"
            reason = (
                "Receipt-revocation index exists but contains no rows; "
                "EMPTY != HEALTHY."
            )
            available = True
        else:
            rollup = "RECORDED"
            reason_code = "INDEX_RECORDED"
            reason = (
                "Receipt revocations are recorded operational facts; they are "
                "not project authority, owner capability, or AUTHENTIC_PILOT."
            )
            available = True

    truncated = len(rows) > limit
    returned = list(rows[:limit]) if truncated else list(rows)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": rollup,
        "reason": reason,
        "reason_code": reason_code,
        "index_present": index_present,
        "index_path": INDEX_RELATIVE.as_posix(),
        "revocation_count": len(rows),
        "returned_count": len(returned),
        "truncated": truncated,
        "revocations": returned,
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }


def render_revocations_read_text(report: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    rows = report.get("revocations") or []
    keys = [
        str(row.get("unit_key"))
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("unit_key"), str)
    ]
    present_text = ", ".join(keys) if keys else "(none)"
    lines = [
        f"atlas revocations [{report.get('status', 'UNKNOWN')}]",
        f"  available: {report.get('available')}",
        f"  reason:    {report.get('reason_code')}",
        f"  rows:      {report.get('revocation_count')} "
        f"(returned {report.get('returned_count')})",
        f"  index:     {report.get('index_present')}",
        f"  present:   {present_text}",
        "  honesty:   RECEIPT REVOCATION != AUTHORITY; "
        "EMPTY != HEALTHY; ABSENT != FABRICATED",
    ]
    return "\n".join(lines) + "\n"
