"""Read-only project conflict projection for the web shell (AS-WEB-001).

Surfaces the unresolved conflicts the knowledge compiler persisted under
``review/conflicts/<project>.json`` so the UI can show *two incompatible
claims* honestly. Never resolves a conflict, never picks a winner, never
mutates canonical state.

Normative:
- UI ≠ canonical; conflicts are objective, unresolved signals.
- No invented resolution: the payload only projects persisted claim values,
  sources, authority and freshness — it never selects a current value.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypedDict

from project_atlas.secrets import scan_text

# Project ids index vault-relative paths; keep them bare safe tokens.
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")

# NFR-004 defence-in-depth: never echo a secret-shaped claim value to a UI
# reader, even though ingestion quarantines secret-bearing sources upstream.
# Mirrors the kdiff surface (`knowledge_diff._value_sketch`).
_REDACTED_CLAIM = "[redacted: secret-shaped value]"


def _safe_claim_value(value: str) -> str:
    return _REDACTED_CLAIM if scan_text(value) else value


class ConflictClaimRow(TypedDict):
    """One competing claim inside a conflict (non-authoritative)."""

    claim: str
    source_id: str | None


class ConflictRow(TypedDict):
    """One unresolved conflict projected for UI display."""

    conflict_id: str
    subject: str
    field: str
    conflict_type: str
    claims: list[ConflictClaimRow]


def _safe_project_id(project_id: str) -> str:
    token = (project_id or "").strip()
    if not _ID_RE.match(token):
        raise ValueError("web-conflicts-project-id-invalid")
    return token


def list_project_conflicts(vault: Path, project_id: str) -> dict[str, Any]:
    """Return unresolved conflicts for one project (read-only, fail-closed).

    Absent ``review/conflicts/<project>.json`` yields an empty, honest list
    (no conflicts recorded — never a fabricated resolution).
    """
    token = _safe_project_id(project_id)
    path = vault / "review" / "conflicts" / f"{token}.json"
    rows: list[ConflictRow] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            data = {}
        entries = data.get("entries") if isinstance(data, dict) else None
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                claims: list[ConflictClaimRow] = []
                for claim in entry.get("claims") or []:
                    if isinstance(claim, dict):
                        claims.append(
                            {
                                "claim": _safe_claim_value(str(claim.get("claim") or "")),
                                "source_id": (
                                    str(claim["source_id"])
                                    if claim.get("source_id")
                                    else None
                                ),
                            }
                        )
                rows.append(
                    {
                        "conflict_id": str(entry.get("conflict_id") or ""),
                        "subject": str(entry.get("subject") or ""),
                        "field": str(entry.get("field") or ""),
                        "conflict_type": str(entry.get("conflict_type") or "unknown"),
                        "claims": claims,
                    }
                )
    rows.sort(key=lambda r: (r["subject"], r["field"], r["conflict_id"]))
    return {
        "package_id": "AS-WEB-001",
        "truth_boundary": "CONFLICT PROJECTION != AUTHORITY / != RESOLUTION",
        "project_id": token,
        "conflict_count": len(rows),
        "conflicts": rows,
        "authority": "derived",
    }


INDEX_PACKAGE_ID = "AS-CODER-ALPHA-CONFLICTS-MCP-001"
INDEX_TRUTH_BOUNDARY = (
    "CONFLICT INDEX != AUTHORITY / != RESOLUTION / UNKNOWN VALID / NO WRITE / "
    "VAULT-SCOPED != PORTFOLIO IMPLICIT-ALL"
)


def list_vault_conflicts(vault: Path) -> dict[str, Any]:
    """Zero-arg vault-scoped conflict index (read-only, no resolution).

    Iterates ``projects/`` only. Missing or unreadable conflict files stay
    empty — never fabricated, never resolved. Does not grant owner capability.
    """
    from project_atlas.web_api.projects import list_projects

    rows: list[dict[str, Any]] = []
    skipped_invalid_ids = 0
    for project in list_projects(vault):
        pid = str(project.get("project_id") or "").strip()
        if not pid:
            continue
        if not _ID_RE.match(pid):
            skipped_invalid_ids += 1
            continue
        projection = list_project_conflicts(vault, pid)
        rows.append(
            {
                "project_id": pid,
                "conflict_count": int(projection.get("conflict_count") or 0),
                "conflicts": list(projection.get("conflicts") or []),
                "available": True,
                "honesty": {
                    "unknown_is_valid": True,
                    "lens_is_authority": False,
                    "conflict_is_resolution": False,
                    "fabricated_fields": False,
                },
            }
        )
    rows.sort(key=lambda row: str(row["project_id"]))
    total = sum(int(row["conflict_count"]) for row in rows)
    return {
        "schema_version": 1,
        "package_id": INDEX_PACKAGE_ID,
        "truth_boundary": INDEX_TRUTH_BOUNDARY,
        "project_count": len(rows),
        "conflict_count": total,
        "projects": rows,
        "skipped_invalid_ids": skipped_invalid_ids,
        "authority": "derived",
        "honesty": {
            "lens_is_authority": False,
            "mcp_is_authority": False,
            "conflict_is_resolution": False,
            "unknown_is_valid": True,
            "fabricated_fields": False,
            "request_contains_project": False,
            "zero_arg_vault_scope": True,
            "portfolio_implicit_all": False,
            "canonical_write": False,
            "auto_execution": False,
            "owner_capability_granted": False,
            "authentic_pilot": False,
        },
        "generated": {"by": "project-atlas"},
    }
