"""AS-PROJECT-ROADMAP-001 — read-only roadmap projection for LIVE_API / Web.

Derives in memory. Never writes Layer B. ROADMAP != CANONICAL_TRUTH.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.project_roadmap import ProjectRoadmapError, build_roadmap_lens

PACKAGE_ID = "AS-PROJECT-ROADMAP-001"


class WebRoadmapError(ValueError):
    """Fail-closed web roadmap read error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise WebRoadmapError(str(exc)) from exc


def read_project_roadmap(vault: Path, project_id: str) -> dict[str, Any]:
    """Read-only derive. Does not materialize files."""
    project_id = _safe_project_id(project_id)
    try:
        lens = build_roadmap_lens(vault, project_id)
    except ProjectRoadmapError as exc:
        raise WebRoadmapError(str(exc)) from exc
    out = dict(lens)
    out["available"] = lens.get("status") == "derived" or bool(lens.get("items"))
    out["honesty"] = {
        **dict(lens.get("honesty") or {}),
        "ui_is_canonical": False,
        "roadmap_is_canonical": False,
    }
    return out
