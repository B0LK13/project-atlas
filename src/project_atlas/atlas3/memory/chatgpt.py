"""AT3-036 — ChatGPT export adapter.

Wraps landed parse_chat_export. Does not import or replace chatgpt_bridge.
Live full-history sync is not implemented.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.memory.normalize import normalize_turns
from project_atlas.openai_importer_fixtures import parse_chat_export, parse_chat_export_file

PACKAGE_ID: Final[str] = "AT3-036"
LIVE_FULL_HISTORY_SYNC: Final[bool] = False


def import_chatgpt_export(
    source: Path | str,
    *,
    conversation_id: str,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Parse a ChatGPT-style export into canonical envelopes."""
    if isinstance(source, Path):
        if not source.is_file():
            raise Atlas3Error("EXPORT_NOT_FOUND", f"export file not found: {source}")
        turns = parse_chat_export_file(source)
    else:
        turns = parse_chat_export(source)
    payload = [turn.as_dict() if hasattr(turn, "as_dict") else dict(turn) for turn in turns]
    return normalize_turns(
        payload,
        provider="chatgpt",
        conversation_id=conversation_id,
        import_mode="EXPORT",
        project_id=project_id,
    )


def chatgpt_capability() -> dict[str, Any]:
    return {
        "package": PACKAGE_ID,
        "export_import": "IMPLEMENTED",
        "atlas_readonly_from_chatgpt": "IMPLEMENTED_AS_DEMO_MCP",
        "live_full_history_sync": LIVE_FULL_HISTORY_SYNC,
        "replaces_chatgpt_bridge": False,
        "uses_parse_chat_export": True,
    }
