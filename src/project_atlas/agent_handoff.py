"""AS-CODER-ALPHA-CONTEXT-001 + HANDOFF-001 — agent context export and handoff.

Builds paste-ready agent context and durable handoff packs from the Coder Alpha
project brief + evidence links. Does not invent estate facts; UNKNOWN remains.

Outputs (under vault):
- ``generated/ops/agent-context/<project>.md``
- ``generated/ops/agent-context/<project>.json``
- ``generated/ops/handoffs/<handoff_id>.json``
- ``generated/ops/handoffs/latest.json`` pointer
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from project_atlas.project_brief import ProjectBriefError, build_project_brief

PACKAGE_CONTEXT = "AS-CODER-ALPHA-CONTEXT-001"
PACKAGE_HANDOFF = "AS-CODER-ALPHA-HANDOFF-001"
GENERATOR_ID = "atlas-coder-alpha-context-handoff-001"
CONTEXT_DIR = Path("generated") / "ops" / "agent-context"
HANDOFF_DIR = Path("generated") / "ops" / "handoffs"


class AgentHandoffError(ValueError):
    """Fail-closed agent context/handoff error."""


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
    if not project_id or project_id in {".", ".."} or "/" in project_id or "\\" in project_id:
        raise AgentHandoffError(f"unsafe project id: {project_id!r}")
    return project_id


def _render_context_markdown(brief: dict[str, Any]) -> str:
    next_work = brief.get("suggested_next_work") or []
    evidence = brief.get("evidence_links") or []
    lines = [
        f"# Atlas Agent Context — {brief.get('project_id')}",
        "",
        "Derived from Atlas Truth Core via Coder Alpha brief. UI!=canonical.",
        "MODEL_OUTPUT!=AUTHORITY. UNKNOWN stays UNKNOWN.",
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
        "",
        "## Suggested next work",
    ]
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
            "",
        ]
    )
    return "\n".join(lines)


def export_agent_context(
    vault: Path,
    project_id: str,
    *,
    refresh_brief: bool = True,
) -> dict[str, Any]:
    """Export paste-ready agent context for ``project_id``."""
    vault = vault.expanduser().resolve()
    project_id = _safe_project_id(project_id)
    if not vault.is_dir():
        raise AgentHandoffError(f"vault is not a directory: {vault}")
    try:
        brief = build_project_brief(vault, project_id, refresh=refresh_brief)
    except ProjectBriefError as exc:
        raise AgentHandoffError(str(exc)) from exc

    markdown = _render_context_markdown(brief)
    payload = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.agent-context.v1",
        "package": PACKAGE_CONTEXT,
        "project_id": project_id,
        "brief": brief,
        "markdown": markdown,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "lens_is_authority": False,
            "invented_facts": False,
        },
    }
    md_path = vault / CONTEXT_DIR / f"{project_id}.md"
    json_path = vault / CONTEXT_DIR / f"{project_id}.json"
    _write_atomic(md_path, markdown.encode("utf-8"))
    _write_atomic(
        json_path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return {
        "schema_version": 1,
        "package": PACKAGE_CONTEXT,
        "status": "ok",
        "project_id": project_id,
        "markdown_path": md_path.relative_to(vault).as_posix(),
        "json_path": json_path.relative_to(vault).as_posix(),
        "purpose": brief.get("purpose"),
        "generated": {"by": GENERATOR_ID},
    }


def create_handoff(
    vault: Path,
    project_id: str,
    *,
    note: str | None = None,
    refresh_brief: bool = True,
) -> dict[str, Any]:
    """Create a durable handoff pack another agent can resume from."""
    context = export_agent_context(vault, project_id, refresh_brief=refresh_brief)
    vault = vault.expanduser().resolve()
    project_id = _safe_project_id(project_id)
    # Deterministic handoff id from content hash (no wall-clock).
    seed = json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")
    handoff_id = "handoff-" + hashlib.sha256(seed).hexdigest()[:16]
    pack = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.handoff.v1",
        "package": PACKAGE_HANDOFF,
        "handoff_id": handoff_id,
        "project_id": project_id,
        "context": context,
        "resume_instructions": [
            f"Read `{context['markdown_path']}` before coding",
            "Treat UNKNOWN as UNKNOWN; do not invent architecture/decisions",
            "Prefer vault Truth Core over chat memory",
            "After meaningful work, re-run atlas connect and atlas handoff create",
        ],
        "operator_note": note,
        "generated": {"by": GENERATOR_ID},
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "lens_is_authority": False,
        },
    }
    path = vault / HANDOFF_DIR / f"{handoff_id}.json"
    latest = vault / HANDOFF_DIR / "latest.json"
    body = (json.dumps(pack, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(path, body)
    _write_atomic(
        latest,
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "handoff_id": handoff_id,
                    "path": path.relative_to(vault).as_posix(),
                    "project_id": project_id,
                    "generated": {"by": GENERATOR_ID},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
    )
    return {
        "schema_version": 1,
        "package": PACKAGE_HANDOFF,
        "status": "ok",
        "handoff_id": handoff_id,
        "path": path.relative_to(vault).as_posix(),
        "latest_path": latest.relative_to(vault).as_posix(),
        "project_id": project_id,
        "context_markdown": context["markdown_path"],
        "generated": {"by": GENERATOR_ID},
    }


def resume_handoff(
    vault: Path,
    *,
    handoff_id: str | None = None,
) -> dict[str, Any]:
    """Load a handoff pack (latest if id omitted)."""
    vault = vault.expanduser().resolve()
    if handoff_id:
        if "/" in handoff_id or "\\" in handoff_id or handoff_id in {".", ".."}:
            raise AgentHandoffError(f"unsafe handoff id: {handoff_id!r}")
        path = vault / HANDOFF_DIR / f"{handoff_id}.json"
    else:
        latest = vault / HANDOFF_DIR / "latest.json"
        if not latest.is_file():
            raise AgentHandoffError("no handoff latest pointer; run atlas handoff create")
        try:
            pointer = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AgentHandoffError(f"unreadable handoff latest: {exc}") from exc
        rel = pointer.get("path") if isinstance(pointer, dict) else None
        if not isinstance(rel, str):
            raise AgentHandoffError("handoff latest pointer missing path")
        path = vault / rel
    if not path.is_file():
        raise AgentHandoffError(f"handoff pack missing: {path}")
    try:
        pack = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AgentHandoffError(f"unreadable handoff pack: {exc}") from exc
    if not isinstance(pack, dict):
        raise AgentHandoffError("handoff pack must be a JSON object")
    pack["status"] = "resumed"
    pack["resume_path"] = path.relative_to(vault).as_posix()
    return pack
