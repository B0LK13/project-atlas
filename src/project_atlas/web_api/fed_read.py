"""AS-CODER-ALPHA-FED-READ-001 -- vault-scoped federation REPORT READ.

Read-only consume of existing federation artifacts. This module never
calls ``build_federation_read_lens`` or ``build_join_inventory``, never
writes federation state, and never treats membership visibility as
cross-vault promote or Truth Core.

Honesty:
- FED != AUTHORITY
- FED != CROSS-VAULT PROMOTE
- LENS != TRUTH CORE
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- D149_TOUCHED = NO
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-FED-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-fed-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.fed-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.0-FED-002", "AS-2.0-FED-001")
SOURCE_RELATIVES: Final[tuple[str, ...]] = (
    "generated/ops/federation",
    "generated/federation",
)
TRUTH_BOUNDARY: Final[str] = (
    "FED != AUTHORITY / FED != CROSS-VAULT PROMOTE / LENS != TRUTH CORE / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "FED != AUTHORITY",
    "FED != CROSS-VAULT PROMOTE",
    "LENS != TRUTH CORE",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebFedReadError(ValueError):
    """Fail-closed federation REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "fed_is_authority": False,
        "fed_is_cross_vault_promote": False,
        "lens_is_truth_core": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "federation_state_written": False,
        "join_inventory_written": False,
        "lens_written": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "demo_is_authentic": False,
        "owner_capability_granted": False,
        "D149_TOUCHED": "NO",
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
        "graph_is_authority": False,
        "atlas_opt_wake_gate": "CLOSED",
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebFedReadError(f"fed-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebFedReadError("fed-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebFedReadError("fed-read-path-escape")
    return resolved


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebFedReadError(f"fed-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebFedReadError(f"fed-read-artifact-not-object:{path.name}")
    if payload.get("cross_vault_promote") is True or payload.get("allow_cross_promote") is True:
        raise WebFedReadError("fed-read-cross-promote-forbidden")
    authority = payload.get("authority")
    if isinstance(authority, dict) and authority.get("level") == "canonical":
        raise WebFedReadError("fed-read-canonical-authority-forbidden")
    return payload


def _existing_federation_view(vault: Path) -> dict[str, Any]:
    """Read existing federation artifacts only. Never writes or builds."""
    records: list[dict[str, Any]] = []
    malformed = 0
    for relative in SOURCE_RELATIVES:
        directory = vault / Path(relative)
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise WebFedReadError(f"fed-read-artifact-not-dir:{relative}")
        safe_dir = _inside(vault, directory)
        for path in sorted(safe_dir.glob("*.json")):
            if not path.is_file():
                continue
            _inside(vault, path)
            try:
                payload = _load_json_object(path)
            except WebFedReadError as exc:
                if "cross-promote" in str(exc) or "canonical-authority" in str(exc):
                    raise
                malformed += 1
                continue
            records.append(
                {
                    "path": path.relative_to(vault).as_posix(),
                    "record": payload,
                }
            )
    return {
        "schema_version": 1,
        "artifact_count": len(records),
        "malformed_count": malformed,
        "artifacts": records,
        "cross_vault_promote": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    count = view.get("artifact_count")
    malformed = view.get("malformed_count")
    artifact_count = count if isinstance(count, int) else 0
    malformed_count = malformed if isinstance(malformed, int) else 0
    if artifact_count == 0 and malformed_count == 0:
        return (
            "EMPTY",
            "no existing federation artifacts under generated/ops/federation "
            "or generated/federation; EMPTY != HEALTHY; FED != AUTHORITY",
            "EMPTY_FED_VIEW",
            False,
        )
    if artifact_count == 0 and malformed_count > 0:
        return (
            "UNKNOWN",
            "federation artifacts exist but could not be read; UNKNOWN != HEALTHY; "
            "FED != AUTHORITY; LENS != TRUTH CORE",
            "UNKNOWN_FED_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing consume-only federation artifacts projected; FED != AUTHORITY; "
        "FED != CROSS-VAULT PROMOTE; LENS != TRUTH CORE",
        "FED_VIEW_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_relatives": list(SOURCE_RELATIVES),
        "truth_boundary": TRUTH_BOUNDARY,
        "available": available,
        "status": status,
        "reason": reason,
        "reason_code": reason_code,
        "view": view,
        "honesty": _honesty(),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_fed_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing federation artifacts. Never writes."""
    root = _resolve_vault(vault)
    view = _existing_federation_view(root)
    return _envelope(view=view)


def render_fed_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. Does not invent missing fields. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas federation report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          FED != AUTHORITY; FED != CROSS-VAULT PROMOTE; "
            "LENS != TRUTH CORE; EMPTY != HEALTHY; UNKNOWN != HEALTHY; "
            "MCP != AUTHORITY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
