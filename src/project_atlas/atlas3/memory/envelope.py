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
    envelope["envelope_id"] = "a3ce-" + hashlib.sha256(
        json.dumps(
            {
                "provider": prov,
                "conversation_id": conversation_id.strip(),
                "message_id": message_id.strip(),
                "content_hash": hashed,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return envelope
