"""AT3-003 — Provider-neutral immutable engineering event envelope.

Does not mutate atlas_contracts.EventType or ops_events.EVENT_CATALOG.
Legacy ``kind`` / ``source_plane`` remain aliases of ``event_type`` / ``source``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    GENERATOR_ID,
    Atlas3Error,
    honesty_block,
    safe_project_id,
)

PACKAGE_ID: Final[str] = "AT3-003"
SCHEMA_NAME: Final[str] = "atlas3.engineering-event.v1"

EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "SOURCE_CHANGED",
        "COMMIT_CREATED",
        "PR_OPENED",
        "PR_REVIEWED",
        "PR_MERGED",
        "TEST_STARTED",
        "TEST_FAILED",
        "TEST_PASSED",
        "BUILD_STARTED",
        "BUILD_FINISHED",
        "DEPLOYMENT_STARTED",
        "DEPLOYMENT_FINISHED",
        "INCIDENT_OPENED",
        "INCIDENT_RESOLVED",
        "DECISION_RECORDED",
        "AGENT_STARTED",
        "AGENT_FINISHED",
        "AGENT_FAILED",
        "OWNER_APPROVED",
        "OWNER_REJECTED",
        "CONTEXT_INVALIDATED",
    }
)

KIND_TO_EVENT_TYPE: Final[dict[str, str]] = {
    "commit": "COMMIT_CREATED",
    "pr": "PR_OPENED",
    "test": "TEST_PASSED",
    "build": "BUILD_FINISHED",
    "deployment": "DEPLOYMENT_FINISHED",
    "incident": "INCIDENT_OPENED",
    "decision": "DECISION_RECORDED",
    "claim": "CONTEXT_INVALIDATED",
    "conversation": "SOURCE_CHANGED",
    "agent_action": "AGENT_STARTED",
    "file_change": "SOURCE_CHANGED",
    "task": "AGENT_FINISHED",
    "review": "PR_REVIEWED",
    "failure": "AGENT_FAILED",
    "owner_gate": "OWNER_APPROVED",
}

EVENT_TYPE_TO_KIND: Final[dict[str, str]] = {
    value: key for key, value in KIND_TO_EVENT_TYPE.items()
}

EVENT_KINDS: Final[frozenset[str]] = frozenset(KIND_TO_EVENT_TYPE)
SOURCE_PLANES: Final[frozenset[str]] = frozenset(
    {
        "agent_event",
        "ops_event",
        "conversation_capture",
        "engineering",
        "proof",
        "manual",
    }
)
AUTHORITY_CLASSES: Final[frozenset[str]] = frozenset(
    {"derived", "observed", "non-canonical"}
)


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _resolve_type(*, kind: str | None, event_type: str | None) -> tuple[str, str]:
    if event_type:
        resolved = event_type.strip().upper()
        if resolved not in EVENT_TYPES:
            raise Atlas3Error("UNKNOWN_EVENT_TYPE", f"unsupported event_type {event_type!r}")
        alias = EVENT_TYPE_TO_KIND.get(resolved, resolved.lower())
        if kind:
            event_kind = kind.strip().lower()
            if event_kind not in EVENT_KINDS:
                raise Atlas3Error("UNKNOWN_EVENT_KIND", f"unsupported event kind {kind!r}")
            expected = KIND_TO_EVENT_TYPE[event_kind]
            if expected != resolved:
                raise Atlas3Error(
                    "EVENT_TYPE_KIND_MISMATCH",
                    f"kind {event_kind!r} maps to {expected}, not {resolved}",
                )
            return resolved, event_kind
        return resolved, alias
    if not kind:
        raise Atlas3Error("UNKNOWN_EVENT_KIND", "kind or event_type is required")
    event_kind = kind.strip().lower()
    if event_kind not in EVENT_KINDS:
        raise Atlas3Error("UNKNOWN_EVENT_KIND", f"unsupported event kind {kind!r}")
    return KIND_TO_EVENT_TYPE[event_kind], event_kind


def normalize_engineering_event(
    *,
    project_id: str,
    kind: str | None = None,
    source_plane: str = "engineering",
    summary: str,
    subject_id: str = "",
    evidence_refs: list[str] | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    observed_at: str | None = None,
    recorded_at: str | None = None,
    payload: dict[str, Any] | None = None,
    event_type: str | None = None,
    source: str | None = None,
    source_id: str | None = None,
    actor: str | None = None,
    object_refs: list[str] | None = None,
    authority_class: str = "derived",
    valid_time: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic immutable engineering event."""
    pid = safe_project_id(project_id)
    resolved_type, event_kind = _resolve_type(kind=kind, event_type=event_type)
    plane = (source or source_plane).strip().lower()
    if plane not in SOURCE_PLANES:
        raise Atlas3Error("UNKNOWN_SOURCE_PLANE", f"unsupported source plane {plane!r}")
    if authority_class not in AUTHORITY_CLASSES:
        raise Atlas3Error("UNKNOWN_AUTHORITY_CLASS", authority_class)
    text = summary.strip()
    if not text:
        raise Atlas3Error("EMPTY_SUMMARY", "engineering event summary is required")
    refs = sorted({item.strip() for item in (evidence_refs or []) if item.strip()})
    objects = sorted({item.strip() for item in (object_refs or []) if item.strip()})
    src_id = (source_id or subject_id).strip()
    body = {
        "schema": SCHEMA_NAME,
        "schema_version": 1,
        "package": PACKAGE_ID,
        "project_id": pid,
        "event_type": resolved_type,
        "kind": event_kind,
        "source": plane,
        "source_plane": plane,
        "source_id": src_id,
        "subject_id": src_id,
        "actor": actor,
        "summary": text,
        "object_refs": objects,
        "evidence_refs": refs,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "valid_time": valid_time or valid_from,
        "observed_at": observed_at,
        "recorded_at": recorded_at,
        "authority_class": authority_class,
        "authority": authority_class,
        "payload": payload or {},
        "generated": {"by": GENERATOR_ID},
        "honesty": honesty_block(),
        "immutable": True,
        "truth_core": False,
    }
    digest = _canonical_hash(body)
    body["event_id"] = "a3ev-" + digest[7:23]
    body["content_hash"] = digest
    return body


def _body_for_hash(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"event_id", "content_hash"}}


def verify_engineering_event(record: dict[str, Any], *, expected_project_id: str) -> None:
    """Fail-closed read-path validation for ledger rows."""
    if not isinstance(record, dict):
        raise Atlas3Error("LEDGER_CORRUPT", "ledger line is not an object")
    if record.get("schema") != SCHEMA_NAME:
        raise Atlas3Error("LEDGER_SCHEMA_INVALID", "engineering event schema mismatch")
    schema_version = record.get("schema_version")
    if schema_version not in {1, "1"}:
        raise Atlas3Error("LEDGER_SCHEMA_INVALID", "unsupported schema_version")
    pid = str(record.get("project_id") or "")
    if pid != expected_project_id:
        raise Atlas3Error("PROJECT_MISMATCH", "ledger row project_id does not match scope")
    event_id = str(record.get("event_id") or "")
    if not event_id:
        raise Atlas3Error("LEDGER_SCHEMA_INVALID", "event_id is required")
    event_type = str(record.get("event_type") or "")
    if event_type not in EVENT_TYPES:
        raise Atlas3Error("LEDGER_SCHEMA_INVALID", f"unsupported event_type {event_type!r}")
    digest = str(record.get("content_hash") or "")
    if not digest.startswith("sha256:"):
        raise Atlas3Error("LEDGER_SCHEMA_INVALID", "content_hash is required")
    expected_digest = _canonical_hash(_body_for_hash(record))
    if digest != expected_digest:
        raise Atlas3Error("CONTENT_HASH_MISMATCH", "engineering event content_hash mismatch")


def ingest_existing_agent_event(raw: dict[str, Any], *, project_id: str) -> dict[str, Any]:
    """Wrap a landed AgentEvent-shaped dict. Does not mutate the source."""
    if not isinstance(raw, dict):
        raise Atlas3Error("MALFORMED_AGENT_EVENT", "agent event must be an object")
    event_type = str(raw.get("event_type") or raw.get("type") or "agent_action")
    kind_map = {
        "session-start": "agent_action",
        "implementation": "agent_action",
        "decision": "decision",
        "validation": "review",
        "blocker": "failure",
        "failure": "failure",
        "recovery": "agent_action",
        "completion": "task",
        "receipt": "review",
    }
    kind = kind_map.get(event_type, "agent_action")
    summary = str(raw.get("summary") or raw.get("title") or event_type)
    return normalize_engineering_event(
        project_id=project_id,
        kind=kind,
        source_plane="agent_event",
        summary=summary,
        subject_id=str(raw.get("event_id") or ""),
        evidence_refs=[str(raw.get("event_id") or "")] if raw.get("event_id") else [],
        payload={"source_event_type": event_type, "wrapped": True},
        actor=str(raw.get("agent_id") or "") or None,
    )
