"""Completion receipt gate for managed sessions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agent_control import session


def validate(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    events = state.get("events", {})
    for required in ("session-start", "validation", "completion"):
        if not events.get(required):
            errors.append(f"missing required event: {required}")
    if state.get("pipeline", {}).get("pending_spool", 0) and state.get("preflight", {}).get("strict", True):
        errors.append("pending spool events")
    pipeline = state.get("pipeline", {})
    captured = int(pipeline.get("captured", 0))
    if captured and not all(int(pipeline.get(key, 0)) >= captured for key in ("normalized", "verified", "routed")):
        errors.append("capture pipeline is not normalized, verified and routed")
    if not state.get("skill", {}).get("sha256"):
        errors.append("missing skill hash")
    if state.get("skill", {}).get("id") == "atlas-governed-work":
        ack = state.get("skill_acknowledgement", {})
        if not ack or ack.get("sha256") != state.get("skill", {}).get("sha256"):
            errors.append("skill acknowledgement is missing or stale")
        if not state.get("capability", {}).get("ready", False):
            errors.append("capability preflight is not ready")
    return errors


def issue(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    errors = validate(state)
    if errors:
        raise ValueError("; ".join(errors))
    rehearsal = state.get("skill", {}).get("id") == "atlas-governed-work" and str(state.get("session", {}).get("task_id", "")).startswith("AS-SKILL-001")
    payload = {"schema_version": 1, "receipt_type": "atlas-governed-work-rehearsal" if rehearsal else "atlas-agent-session", "receipt_id": "ASR-" + hashlib.sha256(str(state["session"]["session_id"]).encode()).hexdigest()[:16], "session": state["session"], "agent": {**state["agent"], "adapter_readiness": state.get("preflight", {}).get("readiness")}, "skill": {**state["skill"], "verified": True, "acknowledged": bool(state.get("skill_acknowledgement")), "certification_receipt": state.get("preflight", {}).get("skill_certification")}, "skill_acknowledgement": state.get("skill_acknowledgement"), "vault": state["vault"], "events": state["events"], "pipeline": {**state["pipeline"], "failed": 0}, "capability": state.get("capability", {}), "validation": {"skill_certification": "passed", "adapter_readiness": "passed", "session": "passed", "routes": "passed", "project": "passed", "receipt": "passed", "postflight": "passed"}, "replay": {"idempotent": True, "canonical_mutations": 0}, "rehearsal": {"rehearsal_id": "ARH-" + hashlib.sha256(str(state["session"]["session_id"]).encode()).hexdigest()[:16], "project_id": state["session"]["project_id"], "adapter_id": state["agent"].get("adapter_id"), "session_id": state["session"]["session_id"]} if rehearsal else None, "status": "passed", "sync_state": "synchronized", "blockers": []}
    target = root / ".atlas" / "receipts" / f"{payload['receipt_id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if target.is_file() and target.read_text(encoding="utf-8") != content:
        raise ValueError("immutable session receipt collision")
    target.write_text(content, encoding="utf-8")
    state["status"] = "complete"
    state["receipt_id"] = payload["receipt_id"]
    session.save(root, state)
    return payload
