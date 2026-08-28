"""AT3-112 — Isolated federation reuse honesty.

Consumes landed federation inventory / read-lens artifacts. Federation is
not authority. Does not cross-vault promote. Does not call federation
writers. Missing stays UNKNOWN. No new CLI.
MERGE_AUTHORIZATION = NOT_GRANTED.
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

PACKAGE_ID: Final[str] = "AT3-112"
GENERATOR_ID: Final[str] = "atlas3-federation-reuse-112"
FED_INVENTORY_PACKAGE_ID: Final[str] = "AS-2.0-FED-001"
FED_LENS_PACKAGE_ID: Final[str] = "AS-2.0-FED-002"


def _declared_path(vault: Path) -> Path:
    return vault / OPS_RELATIVE / "federation" / "declared.json"


def _read_object(path: Path, *, corrupt_code: str, label: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise Atlas3Error(corrupt_code, f"{label} must be a regular file")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(corrupt_code, f"{label} is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise Atlas3Error(corrupt_code, f"{label} must be an object")
    return raw


def _reject_authority_claims(payload: dict[str, Any], *, label: str) -> None:
    if payload.get("trust_score") is not None:
        raise Atlas3Error("TRUST_SCORE_FORBIDDEN", f"{label} must not carry a trust score")
    if payload.get("graph_is_authority") is True or payload.get("graph_winner") is not None:
        raise Atlas3Error("GRAPH_WINNER_FORBIDDEN", f"{label} must not select a graph winner")
    if payload.get("federation_is_authority") is True:
        raise Atlas3Error("FEDERATION_AUTHORITY", f"{label} federation is not authority")
    if payload.get("cross_vault_promote") is True or payload.get("allow_cross_promote") is True:
        raise Atlas3Error("CROSS_VAULT_PROMOTE", f"{label} must not cross-vault promote")
    authority = payload.get("authority")
    if isinstance(authority, dict):
        level = str(authority.get("level") or "")
        if level in {"authoritative", "truth-core", "owner", "merge"}:
            raise Atlas3Error("FEDERATION_AUTHORITY", f"{label} authority level is forbidden")
    if payload.get("merge_authorization") in {"GRANTED", "granted", True}:
        raise Atlas3Error("MERGE_CLAIM_FORBIDDEN", f"{label} must not grant merge")


def _walk_reject(payload: Any, *, label: str) -> None:
    if isinstance(payload, dict):
        _reject_authority_claims(payload, label=label)
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                _walk_reject(value, label=f"{label}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            if isinstance(item, (dict, list)):
                _walk_reject(item, label=f"{label}[{index}]")


def _member_rows(raw: object) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("FEDERATION_CORRUPT", "members must be a list")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            mid = safe_project_id(item.strip())
            item = {"member_id": mid, "project_id": mid}
        if not isinstance(item, dict):
            raise Atlas3Error("FEDERATION_CORRUPT", "member row must be an object")
        mid = str(item.get("member_id") or item.get("project_id") or item.get("id") or "").strip()
        if not mid:
            raise Atlas3Error("FEDERATION_CORRUPT", "member_id required")
        safe = safe_project_id(mid)
        if safe in seen:
            raise Atlas3Error("FEDERATION_DUPLICATE", f"duplicate member_id {safe}")
        seen.add(safe)
        _walk_reject(item, label=f"member.{safe}")
        rows.append(
            {
                "member_id": safe,
                "project_id": str(item.get("project_id") or safe),
                "federation_is_authority": False,
                "cross_vault_promote": False,
            }
        )
    return rows


def compile_federation_reuse(
    vault: Path | str,
    requested_project_id: str | None = None,
) -> dict[str, Any]:
    """Compose federation reuse honesty. Federation is not authority."""
    root = require_vault(vault)
    requested = None
    if requested_project_id is not None:
        requested = require_project(root, requested_project_id)

    declared = _read_object(
        _declared_path(root),
        corrupt_code="FEDERATION_CORRUPT",
        label="federation-declared",
    )
    members: list[dict[str, Any]] = []
    federation_id = None
    if declared is not None:
        _walk_reject(declared, label="federation-declared")
        federation_id = declared.get("federation_id") or declared.get("id")
        members = _member_rows(declared.get("members") or declared.get("members_visible"))

    if requested is not None and members:
        scoped = [row for row in members if row["project_id"] == requested]
        if not scoped:
            raise Atlas3Error(
                "PROJECT_NOT_IN_FEDERATION",
                f"{requested} is not a federation member",
            )
        members = scoped

    status = "derived" if declared is not None else "UNKNOWN"
    reason = "COMPOSED_FEDERATION_REUSE" if status == "derived" else "NO_FEDERATION_PROJECTION"
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "data_package_ids": [FED_INVENTORY_PACKAGE_ID, FED_LENS_PACKAGE_ID],
        "ux_surface": "federation",
        "project_id": requested,
        "federation_id": federation_id,
        "members": members,
        "counts": {"members": len(members)},
        "status": status,
        "reason": reason,
        "federation_is_authority": False,
        "cross_vault_promote": False,
        "new_cli_command": False,
        "graph_is_authority": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
