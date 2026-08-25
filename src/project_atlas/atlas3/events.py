"""AT3-003 — Engineering event model.

Normalizes agent/ops/conversation/engineering signals into one envelope.
Does not mutate atlas_contracts.EventType or ops_events.EVENT_CATALOG.
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

EVENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "commit",
        "pr",
        "test",
        "build",
        "deployment",
        "incident",
        "decision",
        "claim",
        "conversation",
        "agent_action",
        "file_change",
        "task",
        "review",
        "failure",
        "owner_gate",
    }
)

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


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def normalize_engineering_event(
    *,
    project_id: str,
    kind: str,
    source_plane: str,
    summary: str,
    subject_id: str = "",
    evidence_refs: list[str] | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    observed_at: str | None = None,
    recorded_at: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic engineering event. Temporal fields are optional observations."""
    pid = safe_project_id(project_id)
    event_kind = kind.strip().lower()
    if event_kind not in EVENT_KINDS:
        raise Atlas3Error("UNKNOWN_EVENT_KIND", f"unsupported event kind {kind!r}")
    plane = source_plane.strip().lower()
    if plane not in SOURCE_PLANES:
        raise Atlas3Error("UNKNOWN_SOURCE_PLANE", f"unsupported source plane {source_plane!r}")
    text = summary.strip()
    if not text:
        raise Atlas3Error("EMPTY_SUMMARY", "engineering event summary is required")
    refs = sorted({item.strip() for item in (evidence_refs or []) if item.strip()})
    body = {
        "schema": SCHEMA_NAME,
        "schema_version": 1,
        "package": PACKAGE_ID,
        "project_id": pid,
        "kind": event_kind,
        "source_plane": plane,
        "subject_id": subject_id.strip(),
        "summary": text,
        "evidence_refs": refs,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "observed_at": observed_at,
        "recorded_at": recorded_at,
        "payload": payload or {},
        "authority": "derived",
        "generated": {"by": GENERATOR_ID},
        "honesty": honesty_block(),
    }
    body["event_id"] = "a3ev-" + _canonical_hash(body)[7:23]
    body["content_hash"] = _canonical_hash(body)
    return body


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
    )
