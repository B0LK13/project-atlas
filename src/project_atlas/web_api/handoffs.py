"""AS-CODER-ALPHA-HANDOFF-MCP-001 — read-only handoff list for MCP/API/Web.

Lists durable Coder Alpha handoff packs already written by ``atlas handoff
create``. Never creates, resumes, or rewrites packs. HANDOFF != AUTHORITY.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas_contracts.identity import safe_relative_component
from project_atlas.agent_handoff import HANDOFF_DIR, PACKAGE_HANDOFF

PACKAGE_ID = "AS-CODER-ALPHA-HANDOFF-MCP-001"
TRUTH_BOUNDARY = (
    "HANDOFF READ != AUTHORITY / MCP != WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL / UI != CANONICAL"
)
_PACK_PREFIX = "handoff-"
_PACK_SUFFIX = ".json"
_LATEST_NAME = "latest.json"


class WebHandoffError(ValueError):
    """Fail-closed handoff read error."""


def _safe_project_id(project_id: str) -> str:
    try:
        return safe_relative_component(project_id.strip(), label="project id")
    except ValueError as exc:
        raise WebHandoffError(str(exc)) from exc


def _handoff_root(vault: Path) -> Path:
    return (vault / HANDOFF_DIR).resolve()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _is_safe_pack(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return False
    if not resolved.is_file():
        return False
    if not resolved.is_relative_to(root):
        return False
    name = resolved.name
    if name == _LATEST_NAME:
        return False
    return name.startswith(_PACK_PREFIX) and name.endswith(_PACK_SUFFIX)


def _summarize_pack(vault: Path, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    context = payload.get("context")
    context_obj = context if isinstance(context, dict) else {}
    purpose = context_obj.get("purpose")
    if not isinstance(purpose, str) or not purpose.strip():
        purpose = "UNKNOWN"
    honesty = payload.get("honesty")
    honesty_obj = dict(honesty) if isinstance(honesty, dict) else {}
    honesty_obj.setdefault("lens_is_authority", False)
    honesty_obj.setdefault("mcp_is_authority", False)
    honesty_obj.setdefault("authentic_pilot", False)
    honesty_obj.setdefault("atlas_opt_wake_gate", "CLOSED")
    note = payload.get("operator_note")
    return {
        "handoff_id": payload.get("handoff_id"),
        "project_id": payload.get("project_id"),
        "path": path.relative_to(vault).as_posix(),
        "purpose": purpose,
        "operator_note": note if isinstance(note, str) else None,
        "latest": False,
        "authority": False,
        "honesty": honesty_obj,
    }


def _contained_handoff_rel(vault: Path, root: Path, rel: str) -> str | None:
    """Return vault-relative pack path only when it stays under HANDOFF_DIR."""
    if not rel.strip() or rel.startswith("/") or "\\" in rel or ".." in Path(rel).parts:
        return None
    try:
        candidate = (vault / rel).resolve()
    except OSError:
        return None
    if not candidate.is_relative_to(root):
        return None
    if candidate.name == _LATEST_NAME:
        return None
    if not candidate.name.startswith(_PACK_PREFIX) or not candidate.name.endswith(_PACK_SUFFIX):
        return None
    return candidate.relative_to(vault).as_posix()


def _latest_pointer(vault: Path, root: Path) -> dict[str, Any] | None:
    pointer_path = root / _LATEST_NAME
    if not pointer_path.is_file():
        return None
    try:
        resolved = pointer_path.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(root):
        return None
    payload = _read_json(resolved)
    if payload is None:
        return None
    handoff_id = payload.get("handoff_id")
    rel = payload.get("path")
    project_id = payload.get("project_id")
    if not isinstance(handoff_id, str) or not handoff_id.strip():
        return None
    if not isinstance(rel, str) or not rel.strip():
        return None
    safe_rel = _contained_handoff_rel(vault, root, rel)
    if safe_rel is None:
        return None
    if not isinstance(project_id, str) or not project_id.strip():
        project_id = None
    else:
        try:
            project_id = _safe_project_id(project_id)
        except WebHandoffError:
            return None
    return {
        "handoff_id": handoff_id,
        "path": safe_rel,
        "project_id": project_id,
    }


def list_handoffs(
    vault: Path,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Read-only vault-scoped handoff inventory. Never invents packs."""
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise WebHandoffError(f"vault is not a directory: {vault}")
    scope: str | None = None
    if project_id is not None and str(project_id).strip():
        scope = _safe_project_id(str(project_id))
    root = _handoff_root(vault)
    rows: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.iterdir(), key=lambda item: item.name):
            if not _is_safe_pack(path, root):
                continue
            payload = _read_json(path.resolve())
            if payload is None:
                continue
            hid = payload.get("handoff_id")
            pid = payload.get("project_id")
            if not isinstance(hid, str) or not hid.strip():
                continue
            if not isinstance(pid, str) or not pid.strip():
                continue
            if scope is not None and pid != scope:
                continue
            rows.append(_summarize_pack(vault, path.resolve(), payload))
    rows.sort(key=lambda row: (str(row.get("project_id") or ""), str(row.get("handoff_id") or "")))
    latest = _latest_pointer(vault, root) if root.is_dir() else None
    if latest is not None:
        for row in rows:
            if row.get("handoff_id") == latest.get("handoff_id"):
                row["latest"] = True
        if scope is not None and latest.get("project_id") != scope:
            latest = None
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "cli_package": PACKAGE_HANDOFF,
        "truth_boundary": TRUTH_BOUNDARY,
        "project_id": scope,
        "handoff_count": len(rows),
        "handoffs": rows,
        "latest": latest,
        "available": bool(rows),
        "generated": {"by": "atlas-coder-alpha-handoff-mcp-001-read"},
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
            "create_or_resume": False,
            "authentic_pilot": False,
            "atlas_opt_wake_gate": "CLOSED",
        },
    }
