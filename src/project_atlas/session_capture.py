"""AS-CODER-ALPHA-CAPTURE-001 — meaningful session capture defaults.

Explicit ``atlas capture record`` writes durable session-memory receipts under
``generated/ops/session-captures/``. Handoff create can semi-auto capture.
Captures are ops receipts (not Layer B authority). UNKNOWN stays UNKNOWN.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component

PACKAGE_ID = "AS-CODER-ALPHA-CAPTURE-001"
GENERATOR_ID = "atlas-coder-alpha-capture-001"
CAPTURE_DIR = Path("generated") / "ops" / "session-captures"
ALLOWED_KINDS = frozenset({"milestone", "decision", "blocker", "note", "handoff"})


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
) -> dict[str, Any]:
    """Record a meaningful session capture receipt (ops, not authority)."""
    vault = vault.expanduser().resolve()
    project_id = _safe_project_id(project_id)
    if not vault.is_dir():
        raise SessionCaptureError(f"vault is not a directory: {vault}")
    summary_text = (summary or "").strip()
    if not summary_text:
        raise SessionCaptureError("summary is required for meaningful capture")
    kind_norm = (kind or "milestone").strip().lower()
    if kind_norm not in ALLOWED_KINDS:
        raise SessionCaptureError(
            f"unsupported capture kind {kind_norm!r}; "
            f"allowed: {', '.join(sorted(ALLOWED_KINDS))}"
        )
    source_norm = (source or "explicit").strip().lower()
    if source_norm not in {"explicit", "handoff-auto", "semi-auto"}:
        raise SessionCaptureError(f"unsupported capture source: {source_norm!r}")

    body = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.session-capture.v1",
        "package": PACKAGE_ID,
        "project_id": project_id,
        "kind": kind_norm,
        "source": source_norm,
        "summary": summary_text,
        "decisions": _normalize_list(decisions),
        "changes": _normalize_list(changes),
        "next_work": _normalize_list(next_work),
        "unknowns": _normalize_list(unknowns),
        "authority": {
            "level": "ops-receipt",
            "note": "Session capture is not Layer B authority; requires connect/ingest to promote.",
        },
        "honesty": {
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
            "lens_is_authority": False,
            "invented_facts": False,
        },
        "generated": {"by": GENERATOR_ID},
    }
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
        "package": PACKAGE_ID,
        "status": "ok",
        "capture_id": capture_id,
        "project_id": project_id,
        "path": path.relative_to(vault).as_posix(),
        "latest_path": latest.relative_to(vault).as_posix(),
        "kind": kind_norm,
        "source": source_norm,
        "summary": summary_text,
        "generated": {"by": GENERATOR_ID},
    }


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
                "summary": payload.get("summary"),
                "path": path.relative_to(vault).as_posix(),
                "decisions": payload.get("decisions") or [],
                "changes": payload.get("changes") or [],
                "next_work": payload.get("next_work") or [],
                "unknowns": payload.get("unknowns") or [],
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
        lines.append(f"- [{kind}] {summary} (`{cid}`)")
        for decision in item.get("decisions") or []:
            lines.append(f"  - decision: {decision}")
        for change in item.get("changes") or []:
            lines.append(f"  - change: {change}")
        for nxt in item.get("next_work") or []:
            lines.append(f"  - next: {nxt}")
        for unknown in item.get("unknowns") or []:
            lines.append(f"  - unknown: {unknown}")
    return lines
