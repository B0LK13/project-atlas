"""AS-CODER-ALPHA-OBSIDIAN-001 — living Obsidian project projection.

Writes derived Markdown under ``generated/obsidian/projects/<id>/`` that humans
can open in Obsidian. Atlas owns generated regions; HUMAN regions are preserved
byte-for-byte (AT-011). Not a plugin; not Layer B authority.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.project_brief import ProjectBriefError, build_project_brief

PACKAGE_ID = "AS-CODER-ALPHA-OBSIDIAN-001"
PACKAGE_ID_R1 = "AS-CODER-ALPHA-OBSIDIAN-R1-PROJECTION-001"
GENERATOR_ID = "atlas-coder-alpha-obsidian-r1-001"
OBS_ROOT = Path("generated") / "obsidian" / "projects"
_GENERATED_START = "<!-- atlas:generated:start -->"
_GENERATED_END = "<!-- atlas:generated:end -->"
_HUMAN_BEGIN = re.compile(r"<!--\s*BEGIN HUMAN:\s*([^\s>]+)\s*-->")
_HUMAN_END = re.compile(r"<!--\s*END HUMAN:\s*([^\s>]+)\s*-->")


class ObsidianProjectionError(ValueError):
    """Fail-closed Obsidian living-projection error."""


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id, label="project id")
    except ValueError as exc:
        raise ObsidianProjectionError(str(exc)) from exc


def _list_projects(vault: Path) -> list[str]:
    root = vault / "projects"
    if not root.is_dir():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def _validate_protected_markers(text: str, *, path: str) -> None:
    begins = _HUMAN_BEGIN.findall(text)
    ends = _HUMAN_END.findall(text)
    if len(begins) != len(ends) or sorted(begins) != sorted(ends):
        raise ObsidianProjectionError(f"malformed-protected-markers:{path}")
    start_count = text.count(_GENERATED_START)
    end_count = text.count(_GENERATED_END)
    if start_count != end_count or start_count > 1:
        raise ObsidianProjectionError(f"malformed-generated-markers:{path}")
    if start_count == 1 and text.index(_GENERATED_END) < text.index(_GENERATED_START):
        raise ObsidianProjectionError(f"malformed-generated-markers:{path}")


def _extract_human_regions(text: str) -> dict[str, str]:
    regions: dict[str, str] = {}
    for match in _HUMAN_BEGIN.finditer(text):
        name = match.group(1)
        end_match = re.search(
            rf"<!--\s*END HUMAN:\s*{re.escape(name)}\s*-->",
            text[match.end() :],
        )
        if end_match is None:
            raise ObsidianProjectionError(f"malformed-protected-markers:missing-end:{name}")
        regions[name] = text[match.start() : match.end() + end_match.end()]
    return regions


def _merge_protected_regions(*, existing: str | None, rendered: str, path: str) -> str:
    if existing is None:
        _validate_protected_markers(rendered, path=path)
        return rendered
    _validate_protected_markers(existing, path=path)
    _validate_protected_markers(rendered, path=path)
    prior_humans = _extract_human_regions(existing)
    if not prior_humans:
        return rendered
    merged = rendered
    for name, block in sorted(prior_humans.items()):
        pattern = re.compile(
            rf"<!--\s*BEGIN HUMAN:\s*{re.escape(name)}\s*-->.*?<!--\s*END HUMAN:\s*"
            rf"{re.escape(name)}\s*-->",
            re.DOTALL,
        )
        if not pattern.search(merged):
            merged = merged.rstrip() + "\n\n" + block + "\n"
        else:

            def _replacer(_match: re.Match[str], *, _block: str = block) -> str:
                return _block

            merged = pattern.sub(_replacer, merged, count=1)
    _validate_protected_markers(merged, path=path)
    return merged


def _yaml_scalar(value: str) -> str:
    if value == "" or any(ch in value for ch in (":", "#", "\n", '"', "'")):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _render_attention_section(attention: dict[str, Any] | None) -> list[str]:
    lines = ["", "## Attention (what requires action)"]
    if not attention:
        lines.append("UNKNOWN")
        return lines
    lines.append("ATTENTION LENS != AUTHORITY. Not an objective health score.")
    lines.append(f"rollup={attention.get('rollup') or 'UNKNOWN'}")
    raw_care = attention.get("care_about")
    care: list[Any] = raw_care if isinstance(raw_care, list) else []
    if not care:
        lines.append("- UNKNOWN")
        return lines
    for item in care[:8]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- [{item.get('level')}] {item.get('reason_code')}: "
            f"{item.get('why_seeing_this')} → {item.get('what_to_do')}"
        )
    return lines


def _render_source_health_section(health: dict[str, Any] | None) -> list[str]:
    lines = ["", "## Source health (failures / exclusions)"]
    if not health:
        lines.append("UNKNOWN")
        return lines
    lines.append("SOURCE HEALTH != AUTHORITY. No secret echo.")
    lines.append(f"health_state={health.get('health_state') or 'UNKNOWN'}")
    raw_rows = health.get("actionable")
    rows: list[Any] = raw_rows if isinstance(raw_rows, list) else []
    sample = [row for row in rows if isinstance(row, dict)][:6]
    if not sample:
        lines.append("- no failed/excluded sources in scoped report")
        return lines
    for row in sample:
        lines.append(
            f"- {row.get('source')} | {row.get('status')} | "
            f"{row.get('reason_code')} | {row.get('suggested_next_action')}"
        )
    return lines


def _render_roadmap_section(roadmap: dict[str, Any] | None) -> list[str]:
    lines = ["", "## Current project position (derived roadmap)"]
    if not roadmap:
        lines.append("UNKNOWN — no roadmap lens")
        return lines
    raw_here = roadmap.get("you_are_here")
    raw_nxt = roadmap.get("next_unlock")
    here: dict[str, Any] = raw_here if isinstance(raw_here, dict) else {}
    nxt: dict[str, Any] = raw_nxt if isinstance(raw_nxt, dict) else {}
    lines.append("ROADMAP!=CANONICAL_TRUTH. DERIVED_STATUS!=AUTHORITY.")
    lines.append(
        f"you_are_here={here.get('title') or 'UNKNOWN'} "
        f"[{here.get('status') or 'UNKNOWN'}/{here.get('lifecycle') or 'UNKNOWN'}]"
    )
    lines.append(
        f"next_unlock={nxt.get('title') or 'UNKNOWN'} "
        f"[{nxt.get('status') or 'UNKNOWN'}] "
        f"why={nxt.get('why') or nxt.get('unlock_condition') or 'UNKNOWN'}"
    )
    return lines


def _render_living_markdown(
    brief: dict[str, Any],
    *,
    attention: dict[str, Any] | None = None,
    source_health: dict[str, Any] | None = None,
    roadmap: dict[str, Any] | None = None,
) -> str:
    project_id = str(brief.get("project_id") or "UNKNOWN")
    next_work = brief.get("suggested_next_work") or []
    evidence = brief.get("evidence_links") or []
    lines = [
        "---",
        "type: AtlasLivingProject",
        f"title: {_yaml_scalar(f'Living knowledge — {project_id}')}",
        "schema_version: 1",
        f"package_id: {PACKAGE_ID}",
        f"project_id: {_yaml_scalar(project_id)}",
        "authority_level: derived",
        "plugin_shipped: false",
        "canonical_writes: false",
        "obsidian_ui_is_authority: false",
        "generated:",
        f"  by: {GENERATOR_ID}",
        "---",
        "",
        f"# Living knowledge — {project_id}",
        "",
        "Derived Obsidian projection from Atlas Truth Core via Coder Alpha brief.",
        "UI!=canonical. MODEL_OUTPUT!=AUTHORITY. UNKNOWN stays UNKNOWN.",
        "Not an Obsidian plugin; Atlas owns generated regions only.",
        "",
        _GENERATED_START,
        "",
        "## Project identity",
        str(brief.get("project_identity") or "UNKNOWN"),
        "",
        "## Purpose",
        str(brief.get("purpose") or "UNKNOWN"),
        "",
        "## Tech stack",
        str(brief.get("tech_stack") or "UNKNOWN"),
        "",
        "## Architecture summary",
        str(brief.get("architecture_summary") or "UNKNOWN"),
        "",
        "## Current state",
        str(brief.get("current_state") or "UNKNOWN"),
        "",
        "## Recent meaningful changes",
        str(brief.get("recent_meaningful_changes") or "UNKNOWN"),
        "",
        "## Important decisions",
        str(brief.get("important_decisions") or "UNKNOWN"),
        "",
        "## Known problems / unknown / conflicting",
        str(brief.get("unknown_or_conflicting") or "UNKNOWN"),
    ]
    lines.extend(_render_roadmap_section(roadmap))
    lines.extend(_render_attention_section(attention))
    lines.extend(_render_source_health_section(source_health))
    lines.extend(
        [
            "",
            "## Suggested next work",
        ]
    )
    if isinstance(next_work, list) and next_work:
        lines.extend(f"- {item}" for item in next_work)
    else:
        lines.append("- UNKNOWN")
    lines.extend(["", "## Evidence links"])
    if isinstance(evidence, list) and evidence:
        lines.extend(f"- `{item}`" for item in evidence[:40])
    else:
        lines.append("- UNKNOWN")
    lines.extend(
        [
            "",
            "## Honesty",
            "- authentic_pilot: false",
            "- atlas_opt_wake_gate: CLOSED",
            "- lens_is_authority: false",
            "- roadmap_is_canonical: false",
            "- attention_is_health_score: false",
            "- obsidian_ui_is_authority: false",
            "- plugin_shipped: false",
            "",
            _GENERATED_END,
            "",
            "<!-- BEGIN HUMAN: notes -->",
            "<!-- END HUMAN: notes -->",
            "",
        ]
    )
    return "\n".join(lines)


def project_note_path(vault: Path, project_id: str) -> Path:
    project_id = _safe_project_id(project_id)
    return vault / OBS_ROOT / project_id / "project-living.md"


def materialize_obsidian_projection(
    vault: Path,
    *,
    project_id: str | None = None,
    refresh_brief: bool = True,
) -> dict[str, Any]:
    """Materialize living Obsidian Markdown for one or all vault projects."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise ObsidianProjectionError(f"vault is not a directory: {vault}")
    projects = [_safe_project_id(project_id)] if project_id else _list_projects(vault)
    if not projects:
        raise ObsidianProjectionError("no projects found to project")

    written: list[str] = []
    for pid in projects:
        try:
            brief = build_project_brief(vault, pid, refresh=refresh_brief)
        except ProjectBriefError as exc:
            raise ObsidianProjectionError(str(exc)) from exc
        attention: dict[str, Any] | None = None
        source_health: dict[str, Any] | None = None
        roadmap: dict[str, Any] | None = None
        with contextlib.suppress(Exception):
            from project_atlas.attention_hygiene import classify_attention

            attention = classify_attention(vault, pid)
        with contextlib.suppress(Exception):
            from project_atlas.source_health import explain_source_health

            source_health = explain_source_health(vault, pid)
        with contextlib.suppress(Exception):
            from project_atlas.project_roadmap import build_roadmap_lens

            roadmap = build_roadmap_lens(vault, pid)
        rendered = _render_living_markdown(
            brief,
            attention=attention,
            source_health=source_health,
            roadmap=roadmap,
        )
        path = project_note_path(vault, pid)
        existing = path.read_text(encoding="utf-8") if path.is_file() else None
        merged = _merge_protected_regions(
            existing=existing,
            rendered=rendered,
            path=path.relative_to(vault).as_posix(),
        )
        _write_atomic(path, merged.encode("utf-8"))
        written.append(path.relative_to(vault).as_posix())

    receipt = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.obsidian-projection.v1",
        "package": PACKAGE_ID,
        "status": "ok",
        "notes_written": written,
        "plugin_shipped": False,
        "canonical_writes": False,
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "lens_is_authority": False,
            "obsidian_ui_is_authority": False,
            "canonical_knowledge_remains_atlas": True,
        },
        "r1_package": PACKAGE_ID_R1,
        "generated": {"by": GENERATOR_ID},
    }
    receipt_path = vault / "generated" / "ops" / "obsidian" / "living-projection-receipt.json"
    _write_atomic(
        receipt_path,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    receipt["receipt_path"] = receipt_path.relative_to(vault).as_posix()
    return receipt
