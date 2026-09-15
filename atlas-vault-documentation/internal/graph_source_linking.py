"""Link graph records to AS-WP-004 document revisions."""

from __future__ import annotations

from typing import Any


def link_sources(raw: dict[str, Any], inventory: dict[str, Any]) -> tuple[tuple[dict[str, str], ...], str]:
    by_id = {str(item["document_id"]): item for item in inventory.get("documents", [])}
    by_path = {str(item["relative_path"]): item for item in inventory.get("documents", [])}
    candidates = raw.get("source_documents", raw.get("sources", raw.get("source_document", [])))
    if isinstance(candidates, str):
        candidates = [candidates]
    if not isinstance(candidates, list):
        candidates = []
    links: list[dict[str, str]] = []
    for candidate in candidates:
        key = str(candidate)
        item = by_id.get(key) or by_path.get(key)
        if item is None:
            continue
        links.append({"document_id": str(item["document_id"]), "revision_sha256": str(item.get("sha256", ""))})
    if not links:
        return (), "inferred"
    primary = any((by_id[link["document_id"]].get("authority", {}).get("level") == "primary") for link in links)
    return tuple(sorted(links, key=lambda link: link["document_id"])), "verified" if primary else "supported"
