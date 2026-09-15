"""Registered agent adapter metadata."""

from __future__ import annotations

CAPABILITIES = {"filesystem_read": True, "filesystem_write": True, "shell": True, "network": False, "source_control": True, "atlas_cli": True}
ADAPTERS = {
    "generic": {"adapter_id": "generic-cli-v1", "agent_type": "cli-agent", "receipt_required": True, "capabilities": CAPABILITIES},
    "cli": {"adapter_id": "generic-cli-v1", "agent_type": "cli-agent", "receipt_required": True, "capabilities": CAPABILITIES},
    "ide": {"adapter_id": "ide-agent-v1", "agent_type": "ide-agent", "receipt_required": True, "capabilities": CAPABILITIES},
    "background": {"adapter_id": "background-agent-v1", "agent_type": "background-agent", "receipt_required": True, "capabilities": CAPABILITIES},
    "remote": {"adapter_id": "remote-agent-v1", "agent_type": "remote-agent", "receipt_required": True, "capabilities": {**CAPABILITIES, "network": False}},
}


def get(agent_type: str) -> dict[str, object]:
    return dict(ADAPTERS.get(agent_type, ADAPTERS["generic"]))
