"""Session bootstrap and environment injection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from agent_control import agent_identity, preflight, session


def start(*, project_root: Path, vault_root: Path | None, agent_type: str, agent_value: str | None, task_id: str, skill_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    report = preflight.run(project_root=project_root, vault_root=vault_root, agent_type=agent_type, agent_value=agent_value, skill_root=skill_root)
    sid = agent_identity.session_id(str(report["agent"]["agent_id"]), str(report["project_id"]))
    state: dict[str, Any] = {"schema_version": 1, "bootstrap_version": 1, "session": {"session_id": sid, "task_id": task_id, "project_id": report["project_id"], "started_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat().replace("+00:00", "Z")}, "agent": report["agent"], "skill": report["skill"], "vault": report["vault"], "events": {"session-start": [], "implementation": [], "decision": [], "validation": [], "blocked": [], "completion": []}, "pipeline": {"captured": 0, "normalized": 0, "verified": 0, "routed": 0, "pending_spool": 0}, "preflight": report, "status": "active"}
    session.save(Path(str(report["vault"]["root"])), state)
    environment = {"ATLAS_VAULT_ROOT": str(report["vault"]["root"]), "ATLAS_VAULT_ID": str(report["vault"]["vault_id"]), "ATLAS_PROJECT_ID": str(report["project_id"]), "ATLAS_PROJECT_SLUG": str(report["project_id"]), "ATLAS_AGENT_ID": str(report["agent"]["agent_id"]), "ATLAS_ADAPTER_ID": str(report["agent"].get("adapter_id", "unknown")), "ATLAS_SESSION_ID": sid, "ATLAS_SKILL_PATH": str(report["skill"]["path"]), "ATLAS_SKILL_ID": str(report["skill"]["id"]), "ATLAS_SKILL_VERSION": str(report["skill"]["version"]), "ATLAS_SKILL_SHA256": str(report["skill"]["sha256"]), "ATLAS_WORK_PACKAGE": task_id, "ATLAS_STRICT": "1"}
    from agent_control import event_client
    event_client.document(vault_root=Path(str(report["vault"]["root"])), session_id=sid, event_type="session-start", summary="Managed Atlas agent session started", work_package=task_id, spool=bool(report["spool"].get("mode")))
    return session.load(Path(str(report["vault"]["root"])), sid), environment


def injected_context(state: dict[str, Any]) -> str:
    return "\n".join(["Atlas governed-work session is active.", f"Operational skill: {state['skill']['path']}", f"Skill version: {state['skill']['version']}", f"Skill SHA-256: {state['skill']['sha256']}", f"Project: {state['session']['project_id']}", f"Vault: {state['vault']['vault_id']}", "Acknowledge the skill and run capability-check before modifying files.", "Use atlas-agent document for material events.", "Do not write protected Atlas state directly.", "Report completion only after strict postflight and a valid receipt."])
