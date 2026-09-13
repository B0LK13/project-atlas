"""AT3-048 — Unified LLM memory search over extracted items, not transcript dumps."""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    Atlas3Error,
    require_project,
    require_vault,
    write_json_atomic,
)
from project_atlas.atlas3.memory.privacy import scan_or_raise
from project_atlas.atlas3.memory.routing import assert_items_project_scope

PACKAGE_ID: Final[str] = "AT3-048"
SEARCH_AUTHORITY: Final[str] = "NON_CANONICAL"
_FORBIDDEN_AUTHORITY: Final[frozenset[str]] = frozenset(
    {
        "TRUTH_CORE",
        "CANONICAL",
        "OWNER",
        "MERGE",
        "AUTHORITY",
        "GOVERNOR",
        "SECURITY",
        "HUMAN",
        "RELEASE",
        "SIGNOFF",
    }
)


def _normalize_authority_token(value: object) -> str:
    return str(value).strip().upper().replace("-", "_").replace(" ", "_")


def _search_hit_authority(item: dict[str, Any], *, label: str) -> str:
    """Memory search is non-canonical. Forged Truth Core / owner labels fail closed."""
    raw = item.get("authority", SEARCH_AUTHORITY)
    if raw is None or raw == "":
        return SEARCH_AUTHORITY
    token = _normalize_authority_token(raw)
    if token == SEARCH_AUTHORITY:
        return SEARCH_AUTHORITY
    if token in _FORBIDDEN_AUTHORITY or "TRUTH_CORE" in token:
        raise Atlas3Error(
            "AUTHORITY_CLAIM_FORBIDDEN",
            f"{label} must not claim {raw!r}",
        )
    raise Atlas3Error(
        "AUTHORITY_CLAIM_FORBIDDEN",
        f"{label} authority {raw!r} is not allowed on the memory search path",
    )


def search_capability() -> dict[str, Any]:
    return {
        "package": PACKAGE_ID,
        "transcript_dump": False,
        "provenance_preserved": True,
        "auto_promote_to_truth_core": False,
        "cross_project_search": False,
    }


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
    if not isinstance(items, list):
        raise Atlas3Error("SEARCH_INVALID", "items must be a list")
    needle = query.strip().lower()
    tokens = [part for part in needle.split() if part]
    hits: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise Atlas3Error("SEARCH_INVALID", "item is not an object")
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
                    "authority": _search_hit_authority(item, label="search hit"),
                    "evidence_sources": item.get("evidence_sources"),
                }
            )
    return {
        "package": PACKAGE_ID,
        "query": query,
        "hit_count": len(hits),
        "hits": hits,
        "transcript_dump": False,
        "provenance_preserved": True,
    }


def persist_search(vault: Any, project_id: str, result: dict[str, Any]) -> dict[str, Any]:
    root = require_vault(vault)
    pid = require_project(root, project_id)
    if not isinstance(result, dict):
        raise Atlas3Error("SEARCH_INVALID", "persist result must be an object")
    hits = result.get("hits")
    if hits is not None:
        if not isinstance(hits, list):
            raise Atlas3Error("SEARCH_INVALID", "persist hits must be a list")
        for index, hit in enumerate(hits):
            if not isinstance(hit, dict):
                raise Atlas3Error("SEARCH_INVALID", f"persist hit {index} is not an object")
            _search_hit_authority(hit, label=f"persist hit[{index}]")
    write_json_atomic(root / OPS_RELATIVE / "memory" / pid / "search.json", result)
    return result
