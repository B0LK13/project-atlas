"""AT3-048 — Unified LLM memory search over extracted items, not transcript dumps."""

from __future__ import annotations

from typing import Any

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    Atlas3Error,
    require_project,
    require_vault,
    write_json_atomic,
)
from project_atlas.atlas3.memory.privacy import scan_or_raise
from project_atlas.atlas3.memory.routing import assert_items_project_scope


def search_memory(
    items: list[dict[str, Any]],
    query: str,
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    scan_or_raise(query)
    if project_id is not None:
        assert_items_project_scope(items, project_id=project_id)
    else:
        scoped = {str(item.get("project_id") or "") for item in items if isinstance(item, dict)}
        scoped.discard("")
        if len(scoped) > 1:
            raise Atlas3Error(
                "PROJECT_MISMATCH",
                f"mixed-project memory search: {sorted(scoped)}",
            )
    needle = query.strip().lower()
    tokens = [part for part in needle.split() if part]
    hits: list[dict[str, Any]] = []
    for item in items:
        hay = " ".join(
            str(item.get(key) or "")
            for key in ("text", "item_type", "provider", "freshness")
        ).lower()
        if needle and (needle in hay or any(token in hay for token in tokens)):
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
