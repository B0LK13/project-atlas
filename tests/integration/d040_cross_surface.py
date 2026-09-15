"""D-040 cross-surface brief field helpers (test-only)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FIELD_SET = (
    "purpose",
    "current_state",
    "architecture_summary",
    "recent_meaningful_changes",
    "important_decisions",
    "unknown_or_conflicting",
)

_OBSIDIAN_HEADINGS: dict[str, str] = {
    "purpose": "Purpose",
    "architecture_summary": "Architecture summary",
    "current_state": "Current state",
    "recent_meaningful_changes": "Recent meaningful changes",
    "important_decisions": "Important decisions",
    "unknown_or_conflicting": "Known problems / unknown / conflicting",
}

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def load_disk_brief(vault: Path, project_id: str) -> dict[str, Any]:
    path = vault / "generated" / "ops" / f"project-brief-{project_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def brief_field_values(payload: dict[str, Any]) -> dict[str, str]:
    return {field: str(payload.get(field) or "") for field in FIELD_SET}


def parse_obsidian_brief_fields(markdown: str) -> dict[str, str]:
    """Parse living Obsidian projection sections inside generated regions."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(markdown))
    for index, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        sections[title] = body

    out: dict[str, str] = {}
    for field, heading in _OBSIDIAN_HEADINGS.items():
        out[field] = sections.get(heading, "")
    return out


def assert_fields_match_authority(
    *,
    authority: dict[str, str],
    surface: str,
    observed: dict[str, str],
) -> None:
    for field in FIELD_SET:
        assert observed[field] == authority[field], (
            f"{surface}.{field} mismatch: {observed[field]!r} != {authority[field]!r}"
        )
