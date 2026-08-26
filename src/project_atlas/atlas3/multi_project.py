"""AT3-110 — Isolated multi-project twin.

Declared sibling project rows only. Federation is not authority.
Does not mint org identity. Missing stays UNKNOWN.
CROSS_PROJECT_LEAK_COUNT = 0. MERGE_AUTHORIZATION = NOT_GRANTED.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    require_project,
    require_vault,
    safe_project_id,
)

PACKAGE_ID: Final[str] = "AT3-110"
GENERATOR_ID: Final[str] = "atlas3-multi-project-110"
DECLARED_NAME: Final[str] = "declared.json"


def _declared_path(vault: Path) -> Path:
    return vault / OPS_RELATIVE / "multi-project" / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "MULTI_PROJECT_CORRUPT",
            "declared multi-project twin is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("MULTI_PROJECT_CORRUPT", "declared multi-project twin must be an object")
    return raw


def _rows(raw: object) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("MULTI_PROJECT_CORRUPT", "projects must be a list")
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("MULTI_PROJECT_CORRUPT", "projects row is not an object")
        pid = safe_project_id(str(item.get("project_id") or item.get("id") or "").strip())
        if pid in seen:
            raise Atlas3Error("MULTI_PROJECT_DUPLICATE", f"duplicate project_id {pid}")
        seen.add(pid)
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{pid} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        if not refs:
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{pid} requires evidence_refs")
        rows.append(
            {
                "project_id": pid,
                "evidence_refs": refs,
                "authority": "derived",
                "federation_is_authority": False,
            }
        )
    return rows


def compile_multi_project_twin(
    vault: Path | str,
    requested_project_id: str | None = None,
) -> dict[str, Any]:
    """Compile declared multi-project twin. Missing stays UNKNOWN."""
    root = require_vault(vault)
    requested = None
    if requested_project_id is not None and str(requested_project_id).strip():
        requested = require_project(root, requested_project_id)
    path = _declared_path(root)
    unknown = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "requested_project_id": requested,
        "projects": [],
        "counts": {"projects": 0, "cross_project_leak": 0},
        "status": "UNKNOWN",
        "reason": "NO_DECLARED_MULTI_PROJECT",
        "federation_is_authority": False,
        "org_identity_minted": False,
        "estate_is_authorization": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
    if not path.is_file():
        return unknown
    declared = _load_declared(path)
    if declared.get("federation_is_authority") is True:
        raise Atlas3Error(
            "FEDERATION_AUTHORITY_CLAIMED",
            "multi-project twin must not treat federation as authority",
        )
    if declared.get("org_identity_minted") is True:
        raise Atlas3Error("ORG_IDENTITY_MINTED", "multi-project twin must not mint org identity")
    if declared.get("estate_is_authorization") is True:
        raise Atlas3Error(
            "ESTATE_AUTHORIZATION_CLAIMED",
            "estate availability is not owner authorization",
        )
    rows = _rows(declared.get("projects"))
    if requested is not None:
        ids = {row["project_id"] for row in rows}
        if requested not in ids:
            raise Atlas3Error(
                "CROSS_PROJECT",
                "requested project is not in the declared multi-project set",
            )
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "requested_project_id": requested,
        "projects": rows,
        "counts": {"projects": len(rows), "cross_project_leak": 0},
        "status": "derived",
        "reason": "DECLARED_MULTI_PROJECT",
        "federation_is_authority": False,
        "org_identity_minted": False,
        "estate_is_authorization": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
