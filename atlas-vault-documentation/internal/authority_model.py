"""Transparent source-authority assignment for AS-WP-004."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any


def assign_authority(relative_path: str, *, config: dict[str, Any]) -> dict[str, Any]:
    path = relative_path.replace("\\", "/")
    authority = config.get("authority", {})
    if not isinstance(authority, dict):
        authority = {}
    for pattern in authority.get("primary", []) if isinstance(authority.get("primary", []), list) else []:
        if fnmatch(path, str(pattern)):
            return {"level": "primary", "reason": "configured-primary-path"}
    for pattern in authority.get("derived", []) if isinstance(authority.get("derived", []), list) else []:
        if fnmatch(path, str(pattern)):
            return {"level": "derived", "reason": "configured-derived-path"}
    lowered = path.lower()
    if "graphify-out/" in lowered or lowered.startswith("generated/"):
        return {"level": "derived", "reason": "generated-artifact-path"}
    if path.lower().endswith(("readme.md", "changelog.md", "worklog.md")):
        return {"level": "maintained", "reason": "maintained-project-document"}
    return {"level": "maintained", "reason": "default-maintained-documentation"}
