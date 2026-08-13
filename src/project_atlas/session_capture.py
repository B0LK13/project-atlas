"""AS-CODER-ALPHA-CAPTURE-001/002 — meaningful + conversational session capture.

Explicit ``atlas capture record`` writes durable session-memory receipts under
``generated/ops/session-captures/``. Handoff create can semi-auto capture.
``atlas capture conversation`` (CAPTURE-002 / D-042) records conversational
plane turns (Ask2 / agent dialogue) as ops receipts — never Layer B authority,
never sole certifier. UNKNOWN stays UNKNOWN.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.secrets import redact_text, scan_text

PACKAGE_ID = "AS-CODER-ALPHA-CAPTURE-001"
PACKAGE_CONVERSATIONAL = "AS-CODER-ALPHA-CAPTURE-002"
GENERATOR_ID = "atlas-coder-alpha-capture-001"
GENERATOR_CONVERSATIONAL = "atlas-coder-alpha-capture-002"
CAPTURE_DIR = Path("generated") / "ops" / "session-captures"
ALLOWED_KINDS = frozenset(
    {"milestone", "decision", "blocker", "note", "handoff", "conversation"}
)
ALLOWED_SOURCES = frozenset(
    {
        "explicit",
        "handoff-auto",
        "semi-auto",
        "conversational",
        "ask2",
        "context-export",
    }
)
ALLOWED_TURN_ROLES = frozenset({"user", "assistant", "system", "tool"})
_MAX_TURNS = 12
_MAX_TURN_CHARS = 800


class SessionCaptureError(ValueError):
    """Fail-closed session capture error."""


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
        raise SessionCaptureError(str(exc)) from exc


def _normalize_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    for raw in values:
        text = str(raw).strip()
        if text and text not in out:
            out.append(text)
    return out


def _normalize_turns(turns: list[dict[str, str]] | None) -> list[dict[str, str]]:
    if not turns:
        return []
    out: list[dict[str, str]] = []
    for raw in turns[:_MAX_TURNS]:
        role = str(raw.get("role") or "").strip().lower()
        text = str(raw.get("text") or "").strip()
        if role not in ALLOWED_TURN_ROLES or not text:
            continue
        if scan_text(text):
            text = redact_text(text)
        if len(text) > _MAX_TURN_CHARS:
            text = text[: _MAX_TURN_CHARS - 3].rstrip() + "..."
        out.append({"role": role, "text": text})
    return out


def capture_session(
    vault: Path,
    project_id: str,
    *,
    summary: str,
    kind: str = "milestone",
    decisions: list[str] | None = None,
    changes: list[str] | None = None,
    next_work: list[str] | None = None,
    unknowns: list[str] | None = None,
    source: str = "explicit",
    turns: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Record a meaningful session capture receipt (ops, not authority)."""
    vault = vault.expanduser().resolve()
    project_id = _safe_project_id(project_id)
    if not vault.is_dir():
        raise SessionCaptureError(f"vault is not a directory: {vault}")
    summary_text = (summary or "").strip()
    if not summary_text:
        raise SessionCaptureError("summary is required for meaningful capture")
    if scan_text(summary_text):
        summary_text = redact_text(summary_text)
    kind_norm = (kind or "milestone").strip().lower()
    if kind_norm not in ALLOWED_KINDS:
        raise SessionCaptureError(
            f"unsupported capture kind {kind_norm!r}; "
            f"allowed: {', '.join(sorted(ALLOWED_KINDS))}"
        )
    source_norm = (source or "explicit").strip().lower()
    if source_norm not in ALLOWED_SOURCES:
        raise SessionCaptureError(f"unsupported capture source: {source_norm!r}")

    package = PACKAGE_CONVERSATIONAL if kind_norm == "conversation" else PACKAGE_ID
    generator = GENERATOR_CONVERSATIONAL if kind_norm == "conversation" else GENERATOR_ID
    plane = "conversational" if kind_norm == "conversation" else "session"
    normalized_turns = _normalize_turns(turns) if kind_norm == "conversation" else []
    body: dict[str, Any] = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.session-capture.v1",
        "package": package,
        "project_id": project_id,
        "kind": kind_norm,
        "source": source_norm,
        "plane": plane,
        "summary": summary_text,
        "decisions": _normalize_list(decisions),
        "changes": _normalize_list(changes),
        "next_work": _normalize_list(next_work),
        "unknowns": _normalize_list(unknowns),
        "authority": {
            "level": "ops-receipt",
            "note": (
                "Conversational capture is ops memory only; never Layer B authority "
                "and never sole certifier."
                if plane == "conversational"
                else "Session capture is not Layer B authority; requires connect/ingest to promote."
            ),
        },
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "lens_is_authority": False,
            "invented_facts": False,
            "conversational_sole_certifier": False,
            "plane": plane,
        },
        "generated": {"by": generator},
    }
    if kind_norm == "conversation":
        body["turns"] = normalized_turns
        body["turn_count"] = len(normalized_turns)
        body["truth_boundary"] = (
            "CONVERSATIONAL CAPTURE ≠ AUTHORITY / ≠ SOLE CERTIFIER / ≠ LAYER B"
        )
    seed = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    capture_id = "capture-" + hashlib.sha256(seed).hexdigest()[:16]
    body["capture_id"] = capture_id

    path = vault / CAPTURE_DIR / f"{capture_id}.json"
    latest = vault / CAPTURE_DIR / "latest.json"
    encoded = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(path, encoded)
    _write_atomic(
        latest,
        (
            json.dumps(
                {
                    "schema_version": 1,
                    "capture_id": capture_id,
                    "project_id": project_id,
                    "path": path.relative_to(vault).as_posix(),
                    "generated": {"by": generator},
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8"),
    )
    return {
        "schema_version": 1,
        "package": package,
        "status": "ok",
        "capture_id": capture_id,
        "project_id": project_id,
        "path": path.relative_to(vault).as_posix(),
        "latest_path": latest.relative_to(vault).as_posix(),
        "kind": kind_norm,
        "source": source_norm,
        "plane": plane,
        "summary": summary_text,
        "turn_count": len(normalized_turns) if kind_norm == "conversation" else 0,
        "generated": {"by": generator},
    }


def capture_conversation(
    vault: Path,
    project_id: str,
    *,
    summary: str,
    turns: list[dict[str, str]] | None = None,
    decisions: list[str] | None = None,
    changes: list[str] | None = None,
    next_work: list[str] | None = None,
    unknowns: list[str] | None = None,
    source: str = "conversational",
) -> dict[str, Any]:
    """Record a conversational-plane session capture (D-042 / CAPTURE-002).

    Dialogue is ops memory only. It must never become Layer B authority or the
    sole certifier of project truth.
    """
    source_norm = (source or "conversational").strip().lower()
    if source_norm not in {"conversational", "ask2", "context-export", "semi-auto", "explicit"}:
        raise SessionCaptureError(f"unsupported conversational source: {source_norm!r}")
    return capture_session(
        vault,
        project_id,
        summary=summary,
        kind="conversation",
        decisions=decisions,
        changes=changes,
        next_work=next_work,
        unknowns=unknowns
        or ["Conversational capture is not project authority"],
        source=source_norm,
        turns=turns,
    )


def capture_context_export(
    vault: Path,
    project_id: str,
    *,
    note: str | None = None,
) -> dict[str, Any]:
    """Semi-auto conversational capture when agent context is exported (D-042)."""
    summary = (note or "").strip() or (
        f"Agent context exported for project {project_id} (conversational session boundary)"
    )
    return capture_conversation(
        vault,
        project_id,
        summary=summary,
        turns=[{"role": "system", "text": "atlas context export"}],
        source="context-export",
        unknowns=["Context export marks a session boundary; not a governing decision"],
    )


def list_captures(
    vault: Path,
    *,
    project_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List session captures in deterministic reverse ``capture_id`` order.

    Ordering is lexicographic on content-hash ids (no wall-clock recency).
    """
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise SessionCaptureError(f"vault is not a directory: {vault}")
    if limit < 1:
        raise SessionCaptureError("limit must be >= 1")
    if project_id is not None:
        project_id = _safe_project_id(project_id)
    root = vault / CAPTURE_DIR
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("capture-*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if project_id is not None and payload.get("project_id") != project_id:
            continue
        items.append(
            {
                "capture_id": payload.get("capture_id"),
                "project_id": payload.get("project_id"),
                "kind": payload.get("kind"),
                "source": payload.get("source"),
                "plane": payload.get("plane") or "session",
                "summary": payload.get("summary"),
                "path": path.relative_to(vault).as_posix(),
                "decisions": payload.get("decisions") or [],
                "changes": payload.get("changes") or [],
                "next_work": payload.get("next_work") or [],
                "unknowns": payload.get("unknowns") or [],
                "turn_count": payload.get("turn_count") or 0,
            }
        )
        if len(items) >= limit:
            break
    return items


def render_captures_markdown(captures: list[dict[str, Any]]) -> list[str]:
    """Render capture bullets for agent context (no invented content)."""
    if not captures:
        return ["- UNKNOWN (no session captures yet; run atlas capture record)"]
    lines: list[str] = []
    for item in captures:
        summary = item.get("summary") or "UNKNOWN"
        kind = item.get("kind") or "note"
        cid = item.get("capture_id") or "UNKNOWN"
        plane = item.get("plane") or "session"
        label = f"{kind}/conversational" if plane == "conversational" else str(kind)
        lines.append(f"- [{label}] {summary} (`{cid}`)")
        if plane == "conversational":
            lines.append(
                "  - truth: conversational ops memory ≠ authority / ≠ sole certifier"
            )
        for decision in item.get("decisions") or []:
            lines.append(f"  - decision: {decision}")
        for change in item.get("changes") or []:
            lines.append(f"  - change: {change}")
        for nxt in item.get("next_work") or []:
            lines.append(f"  - next: {nxt}")
        for unknown in item.get("unknowns") or []:
            lines.append(f"  - unknown: {unknown}")
    return lines
