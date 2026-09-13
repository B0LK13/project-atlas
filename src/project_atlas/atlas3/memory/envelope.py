"""Canonical conversation envelope (D-192 §6)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Final

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.connector import IMPORT_MODES

SCHEMA_NAME: Final[str] = "atlas3.conversation-envelope.v1"
PROVIDER_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
ROLES: Final[frozenset[str]] = frozenset({"user", "assistant", "system", "tool", "owner"})
PRIVACY_CLASSES: Final[frozenset[str]] = frozenset(
    {"include", "exclude", "redact", "quarantine"}
)
MAX_CONTENT_CHARS: Final[int] = 8_000


def content_hash(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def envelope_id_for(
    *,
    provider: str,
    conversation_id: str,
    message_id: str,
    content_hash: str,
) -> str:
    """Deterministic envelope identity bound to provider/ids/hash."""
    return "a3ce-" + hashlib.sha256(
        json.dumps(
            {
                "provider": provider,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "content_hash": content_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]


def verify_envelope(row: dict[str, Any]) -> None:
    """Fail-closed consume-time envelope integrity. AT3-046-F1.

    Stolen envelope_id + altered schema/hash/body must not apply.
    """
    if not isinstance(row, dict):
        raise Atlas3Error("ENVELOPE_INVALID", "envelope must be an object")
    if row.get("schema") != SCHEMA_NAME:
        raise Atlas3Error(
            "ENVELOPE_SCHEMA_INVALID",
            "conversation envelope schema mismatch",
        )
    digest = str(row.get("content_hash") or "")
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise Atlas3Error("ENVELOPE_HASH_MISMATCH", "content_hash is required")
    ref = str(row.get("content_reference") or "")
    # Short references are the full hashed body (build_envelope truncates at 240).
    if 0 < len(ref) < 240 and content_hash(ref) != digest:
        raise Atlas3Error(
            "ENVELOPE_HASH_MISMATCH",
            "content_hash does not match content_reference",
        )
    expected_id = envelope_id_for(
        provider=str(row.get("provider") or ""),
        conversation_id=str(row.get("conversation_id") or ""),
        message_id=str(row.get("message_id") or ""),
        content_hash=digest,
    )
    if str(row.get("envelope_id") or "") != expected_id:
        raise Atlas3Error(
            "ENVELOPE_IDENTITY_MISMATCH",
            "envelope_id is not bound to provider/ids/content_hash",
        )


def build_envelope(
    *,
    provider: str,
    conversation_id: str,
    message_id: str,
    role: str,
    text: str,
    import_mode: str,
    project_id: str | None = None,
    parent_message_id: str | None = None,
    thread_id: str | None = None,
    source_timestamp: str | None = None,
    retrieved_at: str | None = None,
    model_name: str | None = None,
    source_url_or_external_id: str | None = None,
    privacy_class: str = "include",
    retention_class: str = "minimized",
    provider_metadata: dict[str, Any] | None = None,
    attachment_refs: list[str] | None = None,
) -> dict[str, Any]:
    prov = provider.strip().lower()
    if PROVIDER_RE.fullmatch(prov) is None:
        raise Atlas3Error("MALFORMED_PROVIDER", f"invalid provider {provider!r}")
    mode = import_mode.strip().upper()
    if mode not in IMPORT_MODES:
        raise Atlas3Error("UNKNOWN_IMPORT_MODE", f"unsupported import_mode {import_mode!r}")
    mapped_role = role.strip().lower()
    if mapped_role not in ROLES:
        raise Atlas3Error("UNKNOWN_ROLE", f"unsupported role {role!r}")
    if privacy_class not in PRIVACY_CLASSES:
        raise Atlas3Error("UNKNOWN_PRIVACY_CLASS", privacy_class)
    body = text.strip()
    if len(body) > MAX_CONTENT_CHARS:
        raise Atlas3Error("OVERSIZED_MESSAGE", f"message exceeds {MAX_CONTENT_CHARS} characters")
    hashed = content_hash(body)
    envelope = {
        "schema": SCHEMA_NAME,
        "schema_version": 1,
        "provider": prov,
        "provider_account_scope": None,
        "conversation_id": conversation_id.strip(),
        "message_id": message_id.strip(),
        "parent_message_id": parent_message_id,
        "thread_id": thread_id,
        "project_id": project_id,
        "source_timestamp": source_timestamp,
        "retrieved_at": retrieved_at,
        "role": mapped_role,
        "content_hash": hashed,
        "content_reference": body[:240],
        "attachment_refs": attachment_refs or [],
        "model_name": model_name,
        "tool_refs": [],
        "source_url_or_external_id": source_url_or_external_id,
        "import_mode": mode,
        "sync_cursor": None,
        "provider_metadata": provider_metadata or {},
        "privacy_class": privacy_class,
        "retention_class": retention_class,
        "raw_transcript_persisted": False,
    }
    envelope["envelope_id"] = envelope_id_for(
        provider=prov,
        conversation_id=conversation_id.strip(),
        message_id=message_id.strip(),
        content_hash=hashed,
    )
    return envelope
