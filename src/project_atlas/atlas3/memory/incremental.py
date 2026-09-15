"""AT3-046 — Incremental conversation sync honesty.

Local export-cursor incremental apply is implemented.
Live provider incremental sync remains EXTERNAL_BLOCKED.
Does not import or replace chatgpt_bridge. Does not write Truth Core.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    MERGE_AUTHORIZATION,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
)
from project_atlas.atlas3.memory.routing import assert_turns_project_scope

PACKAGE_ID: Final[str] = "AT3-046"
GENERATOR_ID: Final[str] = "atlas3-incremental-046"
LIVE_PROVIDER_INCREMENTAL_SYNC: Final[str] = "EXTERNAL_BLOCKED"
_LIVE_SYNC_VALUES: Final[frozenset[str]] = frozenset({"IMPLEMENTED", "LIVE", "SYNCED"})
_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    {
        "credentials",
        "api_key",
        "authorization",
        "access_token",
        "bearer",
        "password",
    }
)


def incremental_capability() -> dict[str, Any]:
    """Honest incremental-sync capability. Live provider sync stays blocked."""
    return {
        "package": PACKAGE_ID,
        "local_export_cursor": "IMPLEMENTED",
        "live_provider_incremental_sync": LIVE_PROVIDER_INCREMENTAL_SYNC,
        "live_full_history_sync": False,
        "chatgpt_history_api": False,
        "native_history_api": False,
        "conversation_sync": "NOT_IMPLEMENTED",
        "writes_truth_core": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "new_cli_command": True,
        "certified_for_merge": False,
        "merge_authorization": MERGE_AUTHORIZATION,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def _reject_live_or_secret(row: dict[str, Any], *, label: str) -> None:
    if row.get("live_full_history_sync") is True or row.get("live_incremental_sync") is True:
        raise Atlas3Error(
            "INCREMENTAL_LIVE_CLAIMED",
            f"{label} must not claim live incremental or full-history sync",
        )
    if row.get("history_api") is True or row.get("native_history_api") is True:
        raise Atlas3Error(
            "INCREMENTAL_LIVE_CLAIMED",
            f"{label} native history API is EXTERNAL_BLOCKED",
        )
    sync = str(row.get("conversation_sync") or "")
    if sync in _LIVE_SYNC_VALUES:
        raise Atlas3Error(
            "INCREMENTAL_LIVE_CLAIMED",
            f"{label} live conversation sync is EXTERNAL_BLOCKED",
        )
    mode = str(row.get("import_mode") or "").strip().upper()
    if mode == "API":
        raise Atlas3Error(
            "INCREMENTAL_LIVE_CLAIMED",
            f"{label} import_mode=API is not local export-cursor incremental",
        )
    for key in _SECRET_KEYS:
        if row.get(key):
            raise Atlas3Error(
                "INCREMENTAL_CREDENTIAL_REFUSED",
                f"{label} must not carry {key}",
            )
    meta = row.get("provider_metadata")
    if isinstance(meta, dict):
        for key in _SECRET_KEYS:
            if meta.get(key):
                raise Atlas3Error(
                    "INCREMENTAL_CREDENTIAL_REFUSED",
                    f"{label} provider_metadata must not carry {key}",
                )
        _reject_live_or_secret(
            {k: meta[k] for k in meta if k not in _SECRET_KEYS},
            label=f"{label}.provider_metadata",
        )


def _require_envelope_list(raw: object, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise Atlas3Error("INCREMENTAL_INVALID", f"{label} must be a list")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Atlas3Error(
                "INCREMENTAL_INVALID",
                f"{label}[{index}] must be an object",
            )
        _reject_live_or_secret(item, label=f"{label}[{index}]")
        rows.append(item)
    return rows


def envelope_cursor(row: dict[str, Any]) -> str:
    """Stable cursor token from a local envelope. Not a wall-clock watermark."""
    eid = row.get("envelope_id")
    if isinstance(eid, str) and eid.startswith("a3ce-"):
        return eid
    digest = row.get("content_hash")
    if isinstance(digest, str) and digest.startswith("sha256:"):
        return digest
    raise Atlas3Error("INCREMENTAL_INVALID", "envelope missing cursor identity")


def _expected_cursor(accepted: list[dict[str, Any]]) -> str:
    if not accepted:
        return ""
    return envelope_cursor(accepted[-1])


def apply_local_incremental(
    accepted: object,
    incoming: object,
    *,
    cursor: str | None,
    conversation_id: str,
    project_id: str,
) -> dict[str, Any]:
    """Apply a local export-cursor delta. Never talks to a live provider API."""
    accepted_rows = _require_envelope_list(accepted, label="accepted")
    incoming_rows = _require_envelope_list(incoming, label="incoming")
    pid = assert_turns_project_scope(accepted_rows + incoming_rows, project_id=project_id)
    cid = conversation_id.strip()
    if not cid:
        raise Atlas3Error("INCREMENTAL_INVALID", "conversation_id is required")
    for label, rows in (("accepted", accepted_rows), ("incoming", incoming_rows)):
        for index, row in enumerate(rows):
            explicit = row.get("conversation_id")
            if explicit is not None and str(explicit) != cid:
                raise Atlas3Error(
                    "INCREMENTAL_CONVERSATION_MISMATCH",
                    f"{label}[{index}] conversation_id {explicit!r} != {cid!r}",
                )
    expected = _expected_cursor(accepted_rows)
    provided = "" if cursor is None else str(cursor)
    if accepted_rows and provided == "":
        raise Atlas3Error(
            "INCREMENTAL_CURSOR_REQUIRED",
            "non-empty accepted batch requires the last accepted cursor",
        )
    if provided != expected:
        raise Atlas3Error(
            "INCREMENTAL_CURSOR_MISMATCH",
            "cursor does not match last accepted local envelope",
        )
    seen = {envelope_cursor(row) for row in accepted_rows}
    applied: list[dict[str, Any]] = []
    skipped = 0
    for row in incoming_rows:
        token = envelope_cursor(row)
        if token in seen:
            skipped += 1
            continue
        bound = dict(row)
        bound["project_id"] = pid
        bound["conversation_id"] = cid
        bound["sync_cursor"] = token
        bound["import_mode"] = str(bound.get("import_mode") or "EXPORT")
        applied.append(bound)
        seen.add(token)
    next_cursor = envelope_cursor(applied[-1]) if applied else expected
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "status": "derived",
        "reason": "LOCAL_EXPORT_CURSOR_INCREMENTAL",
        "project_id": pid,
        "conversation_id": cid,
        "accepted_count": len(accepted_rows),
        "incoming_count": len(incoming_rows),
        "applied_count": len(applied),
        "skipped_already_accepted": skipped,
        "applied": applied,
        "cursor": provided,
        "next_cursor": next_cursor,
        "live_provider_incremental_sync": LIVE_PROVIDER_INCREMENTAL_SYNC,
        "live_full_history_sync": False,
        "live_sync_used": False,
        "chatgpt_history_api": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "certified_for_merge": False,
        "merge_authorization": MERGE_AUTHORIZATION,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def load_envelope_list(source: Path) -> list[dict[str, Any]]:
    """Read a JSON envelope list. Mixed valid+corrupt fails closed."""
    if not source.is_file():
        raise Atlas3Error("INCREMENTAL_NOT_FOUND", f"envelope list not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error("INCREMENTAL_INVALID", "envelope list is not readable JSON") from exc
    return _require_envelope_list(payload, label=str(source))
