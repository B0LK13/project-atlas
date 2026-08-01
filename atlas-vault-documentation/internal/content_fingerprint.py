"""Streaming content fingerprints for AS-WP-004 inventories."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_hash(records: list[dict[str, object]]) -> str:
    """Hash stable semantic inventory fields, excluding runtime timestamps."""
    import json

    semantic = []
    for record in sorted(records, key=lambda item: str(item["document_id"])):
        semantic.append({
            key: record.get(key)
            for key in (
                "document_id", "relative_path", "extension", "media_type",
                "size_bytes", "sha256", "classification", "authority",
                "processing", "security",
            )
        })
    payload = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
