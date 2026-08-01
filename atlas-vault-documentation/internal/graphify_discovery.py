"""Acceptance of inventory-backed Graphify artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from internal import content_fingerprint


def discover_artifacts(inventory: dict[str, Any], project_root: Path, *, config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    config = config or {}
    graphify = config.get("graphify", {}) if isinstance(config.get("graphify", {}), dict) else {}
    if graphify.get("enabled", True) is False or graphify.get("semantic_ingestion", True) is False:
        return []
    root = project_root.resolve()
    result: list[dict[str, Any]] = []
    for item in inventory.get("documents", []):
        if item.get("classification", {}).get("type") != "graphify-output":
            continue
        relative = str(item.get("relative_path", ""))
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"graphify artifact escapes project root: {relative}") from exc
        if not path.is_file():
            raise ValueError(f"graphify artifact missing: {relative}")
        actual = content_fingerprint.sha256_file(path)
        if actual != item.get("sha256"):
            raise ValueError(f"graphify artifact hash mismatch: {relative}")
        if item.get("authority", {}).get("level") != "derived":
            raise ValueError(f"graphify artifact authority is not derived: {relative}")
        result.append({"artifact_id": f"{inventory['project_id']}:{relative}", "relative_path": relative, "path": str(path), "sha256": actual, "size_bytes": path.stat().st_size})
    return sorted(result, key=lambda value: str(value["relative_path"]).casefold())
