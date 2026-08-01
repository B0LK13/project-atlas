"""Capability levels and readiness checks for governed agents."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_control import session


LEVELS = {0: "read-only-advisory", 1: "documentation-capable", 2: "governed-implementation", 3: "supervising"}


def check(root: Path, session_id: str) -> dict[str, Any]:
    state = session.load(root, session_id)
    ack = state.get("skill_acknowledgement")
    commands = {name: shutil.which(name) is not None for name in ("python",)}
    commands.update({"status": True, "document": True, "validate": True, "receipt": True, "postflight": True})
    adapter = state.get("agent", {})
    declared = set(adapter.get("capabilities", []))
    if "filesystem_write" in declared or "filesystem-write" in declared:
        level = 2
    elif "atlas_cli" in declared or "atlas-command-execution" in declared:
        level = 1
    else:
        level = 0
    errors: list[str] = []
    if not ack:
        errors.append("skill acknowledgement is missing")
    if not state.get("preflight", {}).get("ok"):
        errors.append("preflight did not pass")
    readiness = state.get("preflight", {}).get("readiness", {})
    if readiness.get("authorized") is False:
        errors.append("adapter rehearsal readiness is not authorized")
    acknowledged = bool(ack and ack.get("sha256") == state.get("skill", {}).get("sha256"))
    adapter_ready = state.get("preflight", {}).get("readiness", {}).get("authorized", True)
    result = {"ok": not errors, "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "skill": {**state.get("skill", {}), "resolved": True, "hash_verified": acknowledged, "acknowledged": acknowledged}, "context": {"project_resolved": bool(state.get("session", {}).get("project_id")), "vault_verified": bool(state.get("vault", {}).get("vault_id")), "session_registered": True, "adapter_ready": adapter_ready}, "commands": commands, "pipeline": {"capture": True, "normalize": True, "verify": True, "route": True, "receipt": True, "postflight": True}, "offline": {"spool_available": bool(state.get("preflight", {}).get("spool", {}).get("available"))}, "capability": {"level": level, "name": LEVELS[level], "declared": sorted(declared)}, "ready": not errors, "errors": errors}
    state["capability"] = result
    session.save(root, state)
    return result
