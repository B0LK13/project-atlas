"""Read-only provider matrix for `atlas memory providers`."""

from __future__ import annotations

from typing import Any

from project_atlas.atlas3.memory.chatgpt import chatgpt_capability
from project_atlas.atlas3.memory.claude import claude_capability
from project_atlas.atlas3.memory.connector import provider_capabilities
from project_atlas.atlas3.memory.gemini import gemini_capability


def memory_providers() -> dict[str, Any]:
    caps = provider_capabilities()
    return {
        **caps,
        "chatgpt_detail": chatgpt_capability(),
        "chatgpt_current": {
            "conversation_sync": "NOT_IMPLEMENTED",
            "export_import": "IMPLEMENTED",
            "live_full_history_sync": False,
            "replaces_chatgpt_bridge": False,
            "state": "EXPORT_ONLY",
        },
        "claude_detail": claude_capability(),
        "claude_current": {
            "conversation_sync": "NOT_IMPLEMENTED",
            "export_import": "IMPLEMENTED",
            "bootstrap_adapter": "CLAUDE.md",
            "bootstrap_is_ingestion": False,
            "state": "EXPORT_ONLY",
        },
        "gemini_detail": gemini_capability(),
        "gemini_current": {
            "conversation_sync": "NOT_IMPLEMENTED",
            "export_import": "IMPLEMENTED",
            "bootstrap_adapter": "GEMINI.md",
            "bootstrap_is_ingestion": False,
            "state": "EXPORT_ONLY",
        },
    }
