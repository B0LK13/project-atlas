"""Explicit acknowledgement of the resolved operational skill."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_control import session


def acknowledge(root: Path, session_id: str, skill_id: str, version: str, sha256: str) -> dict[str, Any]:
    state = session.load(root, session_id)
    if state.get("events", {}).get("implementation") or state.get("events", {}).get("completion"):
        raise ValueError("skill acknowledgement must precede governed work")
    expected = state.get("skill", {})
    if (skill_id, version, sha256) != (expected.get("id"), expected.get("version"), expected.get("sha256")):
        raise ValueError("skill acknowledgement does not match bootstrap skill")
    existing = state.get("skill_acknowledgement")
    if existing:
        if any(existing.get(key) != value for key, value in (("skill_id", skill_id), ("version", version), ("sha256", sha256), ("session_id", session_id))):
            raise ValueError("conflicting skill acknowledgement")
        return {"ok": True, "session_id": session_id, "acknowledgement": existing, "idempotent": True}
    ack = {"skill_id": skill_id, "version": version, "sha256": sha256, "acknowledged_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "session_id": session_id, "agent_id": state["agent"]["agent_id"], "adapter_id": state["agent"].get("adapter_id", "unknown"), "bootstrap_version": state.get("bootstrap_version", 1)}
    state["skill_acknowledgement"] = ack
    session.save(root, state)
    return {"ok": True, "session_id": session_id, "acknowledgement": ack}
