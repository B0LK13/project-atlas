"""AS-CODER-ALPHA-OBSIDIAN-READ-001 — read-only living-note inventory.

Lists existing ``generated/obsidian/projects/<id>/project-living.md`` notes.
Never materializes, never writes, never treats projection as authority.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component

PACKAGE_ID = "AS-CODER-ALPHA-OBSIDIAN-READ-001"
CLI_PACKAGE = "AS-CODER-ALPHA-OBSIDIAN-001"
TRUTH_BOUNDARY = (
    "OBSIDIAN READ != AUTHORITY / MCP != WRITE / "
    "PROJECTION != PLUGIN / UI != CANONICAL / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)
OBS_ROOT = Path("generated") / "obsidian" / "projects"
NOTE_NAME = "project-living.md"
_HUMAN_BEGIN = re.compile(r"<!--\s*BEGIN HUMAN:\s*([^\s>]+)\s*-->")


class WebObsidianError(ValueError):
    """Fail-closed Obsidian inventory read error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id.strip(), label="project id")
    except ValueError as exc:
        raise WebObsidianError(str(exc)) from exc


def _obsidian_root(vault: Path) -> Path | None:
    """Return the living-note root only when it stays inside the vault."""
    try:
        resolved = (vault / OBS_ROOT).resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(vault):
        return None
    return resolved


def _human_region_occupied(text: str) -> bool:
    """True when a HUMAN region contains non-whitespace. Does not return text."""
    for match in _HUMAN_BEGIN.finditer(text):
        name = match.group(1)
        end = re.search(
            rf"<!--\s*END HUMAN:\s*{re.escape(name)}\s*-->",
            text[match.end() :],
        )
        if end is None:
            continue
        inner = text[match.end() : match.end() + end.start()].strip()
        if inner:
            return True
    return False


def _safe_note(path: Path, root: Path) -> Path | None:
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if not resolved.is_file():
        return None
    if not resolved.is_relative_to(root):
        return None
    if resolved.name != NOTE_NAME:
        return None
    return resolved


def _summarize_note(vault: Path, project_id: str, path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    try:
        rel = path.relative_to(vault).as_posix()
    except ValueError:
        return None
    return {
        "project_id": project_id,
        "path": rel,
        "has_human_notes": _human_region_occupied(text),
        "has_generated_markers": (
            "<!-- atlas:generated:start -->" in text
            and "<!-- atlas:generated:end -->" in text
        ),
        "authority": False,
        "plugin_shipped": False,
    }


def list_obsidian_notes(
    vault: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Read-only vault-scoped living-note inventory. Never invents notes."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise WebObsidianError("vault is not a directory")
    scope: str | None = None
    if project_id is not None and str(project_id).strip():
        scope = _safe_project_id(str(project_id))
    root = _obsidian_root(vault)
    rows: list[dict[str, Any]] = []
    if root is not None and root.is_dir():
        for project_dir in sorted(root.iterdir(), key=lambda item: item.name):
            if not project_dir.is_dir() or project_dir.name.startswith("."):
                continue
            try:
                pid = _safe_project_id(project_dir.name)
            except WebObsidianError:
                continue
            if scope is not None and pid != scope:
                continue
            note = _safe_note(project_dir / NOTE_NAME, root)
            if note is None:
                continue
            summary = _summarize_note(vault, pid, note)
            if summary is not None:
                rows.append(summary)
    rows.sort(key=lambda row: str(row.get("project_id") or ""))
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "cli_package": CLI_PACKAGE,
        "truth_boundary": TRUTH_BOUNDARY,
        "project_id": scope,
        "note_count": len(rows),
        "notes": rows,
        "available": bool(rows),
        "generated": {"by": "atlas-coder-alpha-obsidian-read-001"},
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "ui_is_canonical": False,
            "unknown_is_valid": True,
            "fabricated_fields": False,
            "request_contains_project": scope is not None,
            "zero_arg_vault_scope": scope is None,
            "portfolio_implicit_all": False,
            "auto_execution": False,
            "materialize_or_write": False,
            "plugin_shipped": False,
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
        },
    }
