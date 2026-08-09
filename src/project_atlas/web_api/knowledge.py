"""Read-only knowledge / answer inventory for the web shell (AS-WEB-ACCEPT).

Lists schema-shaped answer JSON under ``generated/answers/`` when present.
Missing directory → empty list (unknown inventory, never invented claims).
Never compiles knowledge and never writes Layer B.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

ANSWERS_RELATIVE = Path("generated") / "answers"


class KnowledgeAnswerSummary(TypedDict):
    """Non-authoritative answer listing row for UI display."""

    answer_id: str
    path: str
    subject: str | None
    field: str | None
    has_value: bool


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def list_knowledge_answers(vault: Path) -> list[KnowledgeAnswerSummary]:
    """Return sorted answer summaries from ``generated/answers/*.json`` only."""
    root = vault / ANSWERS_RELATIVE
    if not root.is_dir():
        return []
    rows: list[KnowledgeAnswerSummary] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_file() or entry.suffix.lower() != ".json":
            continue
        if entry.name.startswith("."):
            continue
        payload = _read_json(entry)
        if payload is None:
            continue
        answer_id = str(payload.get("answer_id") or entry.stem)
        rows.append(
            {
                "answer_id": answer_id,
                "path": f"generated/answers/{entry.name}",
                "subject": str(payload["subject"]) if payload.get("subject") else None,
                "field": str(payload["field"]) if payload.get("field") else None,
                "has_value": payload.get("value") is not None,
            }
        )
    return rows
