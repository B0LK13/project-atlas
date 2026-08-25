"""AS-CODER-ALPHA-CONTEXT-PACK-READ-001 -- vault-scoped context-pack REPORT READ.

Read-only consume of existing context-pack artifacts. This module never
calls ``build_context_pack`` or ``compile_context``, never writes pack
state, and never treats a pack as estate facts or Truth Core.

Honesty:
- CONTEXT PACK != ESTATE FACTS
- CONTEXT PACK != PILOT
- PACK != TRUTH CORE
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

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-CONTEXT-PACK-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-context-pack-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.context-pack-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.0-CTX-001", "AS-2.2-RUNTIME-001")
SOURCE_RELATIVES: Final[tuple[str, ...]] = (
    "generated/context",
    "generated/context-compiler",
)
TRUTH_BOUNDARY: Final[str] = (
    "CONTEXT PACK != ESTATE FACTS / CONTEXT PACK != PILOT / PACK != TRUTH CORE / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "CONTEXT PACK != ESTATE FACTS",
    "CONTEXT PACK != PILOT",
    "PACK != TRUTH CORE",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebContextPackReadError(ValueError):
    """Fail-closed context-pack REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "pack_is_estate_facts": False,
        "pack_is_pilot": False,
        "pack_is_truth_core": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "context_pack_written": False,
        "compiler_written": False,
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
        raise WebContextPackReadError(f"context-pack-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebContextPackReadError("context-pack-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebContextPackReadError("context-pack-read-path-escape")
    return resolved


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebContextPackReadError(f"context-pack-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebContextPackReadError(f"context-pack-read-artifact-not-object:{path.name}")
    if payload.get("estate_facts_invented") is True:
        raise WebContextPackReadError("context-pack-read-estate-facts-invented")
    return payload


def _existing_packs(vault: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    malformed = 0
    for relative in SOURCE_RELATIVES:
        directory = vault / Path(relative)
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise WebContextPackReadError(f"context-pack-read-artifact-not-dir:{relative}")
        safe_dir = _inside(vault, directory)
        for path in sorted(safe_dir.glob("*.json")):
            if not path.is_file():
                continue
            _inside(vault, path)
            try:
                payload = _load_json_object(path)
            except WebContextPackReadError as exc:
                if "estate-facts-invented" in str(exc):
                    raise
                malformed += 1
                continue
            records.append({"path": path.relative_to(vault).as_posix(), "record": payload})
    return {
        "schema_version": 1,
        "artifact_count": len(records),
        "malformed_count": malformed,
        "artifacts": records,
        "estate_facts_invented": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    raw_count = view.get("artifact_count")
    raw_malformed = view.get("malformed_count")
    count = raw_count if isinstance(raw_count, int) else 0
    malformed = raw_malformed if isinstance(raw_malformed, int) else 0
    if count == 0 and malformed == 0:
        return (
            "EMPTY",
            "no existing context-pack artifacts; EMPTY != HEALTHY; "
            "CONTEXT PACK != ESTATE FACTS; PACK != TRUTH CORE",
            "EMPTY_CONTEXT_PACK_VIEW",
            False,
        )
    if count == 0 and malformed > 0:
        return (
            "UNKNOWN",
            "context-pack artifacts exist but could not be read; UNKNOWN != HEALTHY",
            "UNKNOWN_CONTEXT_PACK_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing context-pack artifacts projected; CONTEXT PACK != ESTATE FACTS; "
        "PACK != TRUTH CORE",
        "CONTEXT_PACK_VIEW_PROJECTED",
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


def read_context_pack_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing context packs. Never writes."""
    root = _resolve_vault(vault)
    return _envelope(view=_existing_packs(root))


def render_context_pack_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas context-pack report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          CONTEXT PACK != ESTATE FACTS; PACK != TRUTH CORE; "
            "EMPTY != HEALTHY; UNKNOWN != HEALTHY; MCP != AUTHORITY; "
            "WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
