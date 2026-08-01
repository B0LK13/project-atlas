"""Deterministic, project-local Graphify identity resolution."""

from __future__ import annotations

import re
from typing import Any


def _safe(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-") or "unknown"


def resolve_node(raw: dict[str, Any], project_id: str, *, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    explicit = raw.get("atlas_entity_id") or raw.get("atlas_id")
    if explicit:
        value = str(explicit)
        if value.startswith(f"{project_id}:"):
            return {"atlas_entity_id": value, "status": "resolved", "method": "explicit-atlas-id", "confidence": "high", "alternatives": []}
        return {"atlas_entity_id": None, "status": "ambiguous", "method": "explicit-atlas-id", "confidence": "unknown", "alternatives": []}
    mappings = config.get("entity_mappings", {}) if isinstance(config.get("entity_mappings", {}), dict) else {}
    source_id = str(raw.get("id") or raw.get("node_id") or "")
    mapped = mappings.get(source_id)
    if mapped:
        return {"atlas_entity_id": str(mapped), "status": "resolved", "method": "configured-mapping", "confidence": "high", "alternatives": []}
    if not source_id:
        return {"atlas_entity_id": None, "status": "unresolved", "method": "missing-source-id", "confidence": "unknown", "alternatives": []}
    entity_type = _safe(str(raw.get("type") or raw.get("entity_type") or "unknown"))
    return {"atlas_entity_id": f"{project_id}:{entity_type}:{_safe(source_id)}", "status": "resolved", "method": "project-local-identifier", "confidence": "medium", "alternatives": []}
