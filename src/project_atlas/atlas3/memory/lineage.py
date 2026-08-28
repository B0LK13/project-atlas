"""AT3-045 — Provider identity + session lineage.

Binds conversation_id + provider + content hashes. Same conversation
cannot change provider. Same message_id cannot change payload hash.
Cross-project rows fail closed. Isolated Atlas 3 memory plane only.

Honesty:
- METADATA != AUTHORITY
- LINEAGE != TRUTH CORE
- PROVIDER SPOOFING FAILS CLOSED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from typing import Any, Final

from project_atlas.atlas3.contracts import Atlas3Error

PACKAGE_ID: Final[str] = "AT3-045"
GENERATOR_ID: Final[str] = "atlas3-lineage-045"
TRUTH_BOUNDARY: Final[str] = (
    "METADATA != AUTHORITY / LINEAGE != TRUTH CORE / "
    "PROVIDER SPOOFING FAILS CLOSED / MERGE_AUTHORIZATION = NOT_GRANTED"
)


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_session_lineage(
    envelopes: list[dict[str, Any]],
    *,
    requested_project_id: str,
) -> dict[str, Any]:
    """Derive session lineage. Never writes."""
    pid = requested_project_id.strip()
    if not pid:
        raise Atlas3Error("PROJECT_REQUIRED", "requested_project_id is required")

    sessions: dict[str, dict[str, Any]] = {}
    message_hashes: dict[str, str] = {}
    rows: list[dict[str, Any]] = []

    for raw in envelopes:
        if not isinstance(raw, dict):
            raise Atlas3Error("LINEAGE_ENVELOPE_INVALID", "envelope is not an object")
        item_project = str(raw.get("project_id") or "").strip()
        if item_project != pid:
            raise Atlas3Error(
                "CROSS_PROJECT",
                f"REQUESTED_PROJECT_ID={pid} ITEM_PROJECT_ID={item_project or 'missing'}",
            )
        conversation_id = str(raw.get("conversation_id") or "").strip()
        provider = str(raw.get("provider") or "").strip().lower()
        message_id = str(raw.get("message_id") or "").strip()
        content_hash = str(raw.get("content_hash") or raw.get("source_content_hash") or "").strip()
        if not conversation_id or not provider or not message_id or not content_hash:
            raise Atlas3Error(
                "LINEAGE_IDENTITY_INCOMPLETE",
                "conversation_id, provider, message_id, and content_hash are required",
            )

        prior = sessions.get(conversation_id)
        if prior is not None and prior["provider"] != provider:
            raise Atlas3Error(
                "PROVIDER_SPOOF",
                f"conversation {conversation_id} provider {prior['provider']} != {provider}",
            )
        if prior is None:
            sessions[conversation_id] = {
                "conversation_id": conversation_id,
                "provider": provider,
                "project_id": pid,
                "message_count": 0,
            }
        sessions[conversation_id]["message_count"] = (
            int(sessions[conversation_id]["message_count"]) + 1
        )

        prior_hash = message_hashes.get(message_id)
        if prior_hash is not None and prior_hash != content_hash:
            raise Atlas3Error(
                "LINEAGE_HASH_MISMATCH",
                f"message_id {message_id} content_hash changed",
            )
        message_hashes[message_id] = content_hash
        rows.append(
            {
                "conversation_id": conversation_id,
                "provider": provider,
                "message_id": message_id,
                "content_hash": content_hash,
                "project_id": pid,
            }
        )

    session_rows = [sessions[key] for key in sorted(sessions)]
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "truth_boundary": TRUTH_BOUNDARY,
        "session_count": len(session_rows),
        "message_count": len(rows),
        "sessions": session_rows,
        "messages": sorted(rows, key=lambda row: _canonical(row)),
        "honesty": {
            "metadata_is_authority": False,
            "lineage_is_truth_core": False,
            "provider_spoof_accepted": False,
            "write_applied": False,
            "MERGE_AUTHORIZATION": "NOT_GRANTED",
        },
    }
