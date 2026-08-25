"""AT3-048 — Unified LLM memory search over extracted items, not transcript dumps."""

from __future__ import annotations

from typing import Any

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    require_project,
    require_vault,
    write_json_atomic,
)
from project_atlas.atlas3.memory.privacy import scan_or_raise


def search_memory(
    items: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    scan_or_raise(query)
    needle = query.strip().lower()
    hits: list[dict[str, Any]] = []
    for item in items:
        hay = " ".join(
            str(item.get(key) or "")
            for key in ("text", "item_type", "provider", "freshness")
        ).lower()
        if needle and needle in hay:
            hits.append(
                {
                    "item_type": item.get("item_type"),
                    "text": item.get("text"),
                    "provider": item.get("provider"),
                    "freshness": item.get("freshness"),
                    "source_content_hash": item.get("source_content_hash"),
                    "conversation_id": item.get("conversation_id"),
                    "authority": item.get("authority", "NON_CANONICAL"),
                    "evidence_sources": item.get("evidence_sources"),
                }
            )
    return {
        "package": "AT3-048",
        "query": query,
        "hit_count": len(hits),
        "hits": hits,
        "transcript_dump": False,
        "provenance_preserved": True,
    }


def persist_search(vault: Any, project_id: str, result: dict[str, Any]) -> dict[str, Any]:
    root = require_vault(vault)
    pid = require_project(root, project_id)
    write_json_atomic(root / OPS_RELATIVE / "memory" / pid / "search.json", result)
    return result
