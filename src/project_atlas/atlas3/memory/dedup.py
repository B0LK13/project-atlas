"""AT3-041 — Cross-LLM exact and near-duplicate detection."""

from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+")


def _normalize_text(text: str) -> str:
    return " ".join(_TOKEN.findall(text.lower()))


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def deduplicate_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in items:
        key = _normalize_text(str(item.get("text") or ""))
        if not key:
            key = str(item.get("source_content_hash") or id(item))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)

    collapsed: list[dict[str, Any]] = []
    duplicates = 0
    for key in order:
        members = groups[key]
        primary = dict(members[0])
        sources = []
        for member in members:
            sources.append(
                {
                    "provider": member.get("provider"),
                    "conversation_id": member.get("conversation_id"),
                    "message_id": member.get("message_id"),
                    "source_content_hash": member.get("source_content_hash"),
                }
            )
        if len(members) > 1:
            duplicates += len(members) - 1
        primary["evidence_sources"] = sources
        primary["duplicate_count"] = len(members)
        collapsed.append(primary)

    near = 0
    seen: list[set[str]] = []
    for item in collapsed:
        tokens = _tokens(str(item.get("text") or ""))
        for prior in seen:
            if tokens and prior and len(tokens & prior) / len(tokens | prior) >= 0.8:
                near += 1
                break
        seen.append(tokens)

    return {
        "package": "AT3-041",
        "items": collapsed,
        "input_count": len(items),
        "collapsed_count": len(collapsed),
        "duplicates_collapsed": duplicates,
        "near_duplicates": near,
        "original_provenance_erased": False,
    }
