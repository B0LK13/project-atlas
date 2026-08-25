"""AS-CODER-ALPHA-INDEX-STATUS-001 — vault-scoped lexical index readiness.

Reads existing ``generated/indexes/*.json`` artifacts so humans and agents
can see whether retrieval indexes are present without running
``atlas build-indexes`` or inventing a query.

Honesty:
- missing / unreadable indexes stay UNKNOWN (never HEALTHY / FRESH)
- presence is not validate-pass, freshness, or query answers
- obsolete ``indexes/`` is never treated as the generated contract
- index status is not owner capability or AUTHENTIC_PILOT
- UI / MCP / API projections are not canonical
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

from project_atlas.indexes import GENERATED_INDEX_ROOT, LEGACY_INDEX_ROOT

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-INDEX-STATUS-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-index-status-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.index-status.v1"
TRUTH_BOUNDARY: Final[str] = (
    "INDEX_STATUS != AUTHORITY / PRESENCE != VALIDATE / UNKNOWN != HEALTHY"
)

Presence = Literal["absent", "ok", "unreadable"]
StatusRollup = Literal["UNKNOWN", "PARTIAL", "RECORDED"]
IndexRole = Literal["required", "companion", "optional"]

REQUIRED_INDEXES: Final[tuple[str, ...]] = (
    "sources.json",
    "claims.json",
    "concepts.json",
    "conflicts.json",
    "authority.json",
    "provenance.json",
)
COMPANION_INDEXES: Final[tuple[str, ...]] = ("reviews.json",)
OPTIONAL_INDEXES: Final[tuple[str, ...]] = ("impact-graph.json",)


class IndexStatusError(ValueError):
    """Fail-closed index-status error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "lens_is_authority": False,
        "index_status_is_authority": False,
        "presence_is_validate": False,
        "presence_is_fresh": False,
        "presence_is_query_answer": False,
        "unknown_is_healthy": False,
        "unknown_is_fresh": False,
        "legacy_indexes_are_authoritative": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "ui_is_canonical": False,
        "mcp_is_authority": False,
        "fabricated_indexes": False,
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


def _id_count(payload: dict[str, Any] | None) -> int | None:
    if payload is None:
        return None
    ids = payload.get("ids")
    if isinstance(ids, list):
        return len([item for item in ids if isinstance(item, str) and item.strip()])
    lineage = payload.get("by_source_lineage_id")
    if isinstance(lineage, dict):
        return len(lineage)
    return None


def _project_index(
    *,
    name: str,
    role: IndexRole,
    presence: Presence,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "name": name,
        "relative_path": f"{GENERATED_INDEX_ROOT}/{name}",
        "role": role,
        "presence": presence,
        "id_count": _id_count(payload) if presence == "ok" else None,
    }


def _inspect(
    root: Path, name: str, role: IndexRole
) -> dict[str, Any]:
    presence, payload = _read_json_object(root / GENERATED_INDEX_ROOT / name)
    return _project_index(
        name=name, role=role, presence=presence, payload=payload
    )


def build_index_status(vault: Path) -> dict[str, Any]:
    """Read-only index-status projection. Never writes. Never invents HEALTHY."""
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise IndexStatusError(f"index-status-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise IndexStatusError("index-status-vault-missing")

    required = [_inspect(root, name, "required") for name in REQUIRED_INDEXES]
    companions = [_inspect(root, name, "companion") for name in COMPANION_INDEXES]
    optional = [_inspect(root, name, "optional") for name in OPTIONAL_INDEXES]

    required_ok = [row for row in required if row["presence"] == "ok"]
    required_bad = [row for row in required if row["presence"] != "ok"]
    unreadable = [
        row
        for row in (*required, *companions, *optional)
        if row["presence"] == "unreadable"
    ]
    legacy_present = (root / LEGACY_INDEX_ROOT).exists()

    if not required_ok and required_bad:
        rollup: StatusRollup = "UNKNOWN"
        if all(row["presence"] == "unreadable" for row in required):
            reason_code = "REQUIRED_INDEXES_UNREADABLE"
            reason = (
                "Required lexical indexes exist but are unreadable; "
                "status stays UNKNOWN."
            )
        else:
            reason_code = "REQUIRED_INDEXES_ABSENT"
            reason = (
                "No required lexical indexes on disk; run atlas build-indexes "
                "before treating retrieval as available."
            )
    elif required_bad:
        rollup = "PARTIAL"
        if any(row["presence"] == "unreadable" for row in required_bad):
            reason_code = "REQUIRED_INDEX_UNREADABLE"
            reason = (
                "Some required lexical indexes are unreadable; presence is not "
                "a validate pass."
            )
        else:
            reason_code = "REQUIRED_INDEXES_INCOMPLETE"
            reason = (
                "Some required lexical indexes are missing; status is PARTIAL, "
                "not HEALTHY."
            )
    else:
        rollup = "RECORDED"
        reason_code = "REQUIRED_INDEXES_PRESENT"
        reason = (
            "Required lexical indexes are present; this is not freshness, "
            "validate-pass, or query authority."
        )

    if legacy_present:
        reason_code = "LEGACY_INDEXES_PRESENT"
        reason = (
            "Obsolete indexes/ directory is present; it is not the generated "
            "lexical contract and is not authoritative."
        )

    if unreadable and rollup == "RECORDED" and not legacy_present:
        # Companion/optional damage must not look like a clean retrieval surface.
        reason_code = "COMPANION_INDEX_UNREADABLE"
        reason = (
            "Required indexes are present but a companion/optional index is "
            "unreadable; skip treating the surface as complete."
        )

    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "available": bool(required_ok),
        "status": rollup,
        "reason": reason,
        "reason_code": reason_code,
        "required_present": len(required_ok),
        "required_total": len(REQUIRED_INDEXES),
        "legacy_indexes_present": legacy_present,
        "indexes": [*required, *companions, *optional],
        "honesty": _honesty(),
        "generated": {"by": GENERATOR_ID},
    }


def render_index_status_text(report: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields."""
    rows = report.get("indexes") or []
    present = [
        str(row.get("name"))
        for row in rows
        if isinstance(row, dict) and row.get("presence") == "ok"
    ]
    present_text = ", ".join(present) if present else "(none)"
    lines = [
        f"atlas index-status [{report.get('status', 'UNKNOWN')}]",
        f"  available: {report.get('available')}",
        f"  reason:    {report.get('reason_code')}",
        f"  required:  {report.get('required_present')}/{report.get('required_total')}",
        f"  legacy:    {report.get('legacy_indexes_present')}",
        f"  present:   {present_text}",
        "  honesty:   INDEX_STATUS != AUTHORITY; PRESENCE != VALIDATE; UNKNOWN != HEALTHY",
    ]
    return "\n".join(lines) + "\n"
