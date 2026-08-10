"""AS-2.0-INBOX-001 — Knowledge Inbox quarantine intake (≠ authority promote).

Bound to the Atlas 1.0 compatibility anchor. Never Layer B authority.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-INBOX-001"
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
TRUTH_BOUNDARY = "KNOWLEDGE INBOX ≠ AUTHORITY PROMOTE"
SCHEMA_KIND = "knowledge-inbox-receipt"


class KnowledgeInboxError(ValueError):
    """Fail-closed contract error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_knowledge_inbox_receipt(
    vault: Path,
    *,
    record_id: str,
    anchor: CompatibilityAnchor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a deterministic knowledge-inbox-receipt record."""
    _ = anchor or require_compatibility_anchor()
    rid = record_id.strip()
    if not _ID_RE.fullmatch(rid):
        raise KnowledgeInboxError("inbox-receipt-id-invalid")

    status = str(kwargs.get("status", "quarantined"))
    if status not in {"quarantined", "accepted-review", "rejected"}:
        raise KnowledgeInboxError("inbox-status-invalid")
    if bool(kwargs.get("promote_authority")):
        raise KnowledgeInboxError("inbox-authority-promote-forbidden")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": rid,
        "status": status,
        "promoted_to_authority": False,
        "item_count": int(kwargs.get("item_count", 0)),
        "authority": {
            "level": "derived",
            "note": "Inbox intake never promotes Layer B authority",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }

    try:
        validate_record(payload, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise KnowledgeInboxError(f"knowledge-inbox-receipt-schema-invalid:{exc}") from exc
    out = vault / "generated" / "ops" / "inbox" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
