"""Read-only project inventory for the web shell (AS-WEB-001).

Lists project identifiers from the vault ``projects/`` tree and optional
``.atlas/vault.json`` identity metadata. Never creates, renames, or deletes
project directories and never mutates Layer B notes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class ProjectSummary(TypedDict):
    """Non-authoritative project listing row for UI display."""

    project_id: str
    has_project_note: bool
    path: str


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def vault_identity(vault: Path) -> dict[str, Any] | None:
    """Best-effort vault identity (read-only). Missing → None."""
    return _read_json(vault / ".atlas" / "vault.json")


def list_projects(vault: Path) -> list[ProjectSummary]:
    """Return sorted project summaries from ``projects/*/`` only.

    Absent ``projects/`` yields an empty list (honest emptiness — not an
    invented catalog). Does not scan claims or compile concepts.
    """
    root = vault / "projects"
    if not root.is_dir():
        return []
    rows: list[ProjectSummary] = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        # Skip hidden / system dirs.
        if entry.name.startswith("."):
            continue
        note = entry / "project.md"
        rows.append(
            {
                "project_id": entry.name,
                "has_project_note": note.is_file(),
                "path": f"projects/{entry.name}",
            }
        )
    return rows
