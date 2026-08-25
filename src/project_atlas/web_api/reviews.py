"""AS-CODER-ALPHA-REVIEW-MCP-001 — read-only pending-review inventory.

Lists ``review/pending`` and recorded ``state/human-decisions`` artifacts.
Never calls ``atlas review decide``. REVIEW READ != AUTHORITY.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component

PACKAGE_ID = "AS-CODER-ALPHA-REVIEW-MCP-001"
TRUTH_BOUNDARY = (
    "REVIEW READ != AUTHORITY / MCP != DECIDE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL / UI != CANONICAL"
)
PENDING_DIR = Path("review") / "pending"
DECISIONS_DIR = Path("state") / "human-decisions"
_PENDING_STATUSES = frozenset({"pending", "open", "needs_review", ""})


class WebReviewError(ValueError):
    """Fail-closed review read error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id.strip(), label="project id")
    except ValueError as exc:
        raise WebReviewError(str(exc)) from exc


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _safe_project_file(path: Path, root: Path) -> str | None:
    try:
        resolved = path.resolve()
    except OSError:
        return None
    if not resolved.is_file() or not resolved.is_relative_to(root):
        return None
    if not resolved.name.endswith(".json"):
        return None
    token = resolved.name[: -len(".json")]
    try:
        return safe_relative_component(token, label="project id")
    except ValueError:
        return None


def _pending_rows(vault: Path, scope: str | None) -> list[dict[str, Any]]:
    root = (vault / PENDING_DIR).resolve()
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        project_id = _safe_project_file(path, root)
        if project_id is None:
            continue
        if scope is not None and project_id != scope:
            continue
        payload = _read_json(path.resolve())
        if payload is None:
            continue
        entries = payload.get("entries")
        if not isinstance(entries, list):
            continue
        rel = path.resolve().relative_to(vault).as_posix()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            status = str(entry.get("status") or "pending")
            if status not in _PENDING_STATUSES:
                continue
            review_id = entry.get("review_id")
            if not isinstance(review_id, str) or not review_id.strip():
                continue
            rows.append(
                {
                    "review_id": review_id,
                    "project_id": project_id,
                    "subject": entry.get("subject") or entry.get("subject_id"),
                    "field": entry.get("field") or entry.get("category"),
                    "reason": entry.get("reason") or entry.get("summary") or "UNKNOWN",
                    "status": status or "pending",
                    "path": rel,
                    "authority": False,
                    "decided": False,
                }
            )
    rows.sort(key=lambda row: (str(row["project_id"]), str(row["review_id"])))
    return rows


def _decision_rows(vault: Path, scope: str | None) -> list[dict[str, Any]]:
    root = (vault / DECISIONS_DIR).resolve()
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        project_id = _safe_project_file(path, root)
        if project_id is None:
            continue
        if scope is not None and project_id != scope:
            continue
        payload = _read_json(path.resolve())
        if payload is None:
            continue
        decisions = payload.get("decisions")
        if not isinstance(decisions, list):
            continue
        rel = path.resolve().relative_to(vault).as_posix()
        for entry in decisions:
            if not isinstance(entry, dict):
                continue
            review_id = entry.get("review_id")
            if not isinstance(review_id, str) or not review_id.strip():
                continue
            rows.append(
                {
                    "review_id": review_id,
                    "project_id": project_id,
                    "decision": entry.get("decision") or "UNKNOWN",
                    "reason": entry.get("reason") or "UNKNOWN",
                    "status": entry.get("status") or "human_recorded",
                    "path": rel,
                    "authority": False,
                    "verified": entry.get("decision") == "accept",
                }
            )
    rows.sort(key=lambda row: (str(row["project_id"]), str(row["review_id"])))
    return rows


def list_reviews(
    vault: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Read-only vault-scoped review inventory. Never decides."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise WebReviewError(f"vault is not a directory: {vault}")
    scope: str | None = None
    if project_id is not None and str(project_id).strip():
        scope = _safe_project_id(str(project_id))
    pending = _pending_rows(vault, scope)
    decided = _decision_rows(vault, scope)
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "project_id": scope,
        "pending_count": len(pending),
        "pending_reviews": pending,
        "human_decision_count": len(decided),
        "human_decisions": decided,
        "available": bool(pending or decided),
        "generated": {"by": "atlas-coder-alpha-review-mcp-001-read"},
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
            "decide_or_promote": False,
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
        },
    }
