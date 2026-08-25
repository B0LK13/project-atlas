"""AT3-039 — Provider-neutral conversation normalization."""

from __future__ import annotations

from typing import Any

from project_atlas.atlas3.memory.envelope import build_envelope
from project_atlas.atlas3.memory.privacy import apply_privacy

ROLE_ALIASES = {
    "human": "user",
    "user": "user",
    "assistant": "assistant",
    "ai": "assistant",
    "model": "assistant",
    "system": "system",
    "tool": "tool",
    "owner": "owner",
}


def normalize_turns(
    turns: list[dict[str, Any]],
    *,
    provider: str,
    conversation_id: str,
    import_mode: str,
    project_id: str | None = None,
    privacy_class: str = "include",
) -> list[dict[str, Any]]:
    envelopes: list[dict[str, Any]] = []
    parent: str | None = None
    for index, turn in enumerate(turns):
        raw_role = str(turn.get("role") or "assistant").strip().lower()
        role = ROLE_ALIASES.get(raw_role, raw_role)
        raw_text = str(turn.get("text") or turn.get("content") or "")
        text = apply_privacy(raw_text, privacy_class=privacy_class)
        message_id = str(turn.get("message_id") or f"msg-{index + 1}")
        envelopes.append(
            build_envelope(
                provider=provider,
                conversation_id=conversation_id,
                message_id=message_id,
                role=role,
                text=text,
                import_mode=import_mode,
                project_id=project_id,
                parent_message_id=parent,
                model_name=str(turn.get("model_name") or "") or None,
                source_timestamp=str(turn.get("source_timestamp") or "") or None,
                privacy_class=privacy_class,
                provider_metadata={"source_index": index},
            )
        )
        parent = message_id
    return envelopes
