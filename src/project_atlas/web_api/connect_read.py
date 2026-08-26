"""AS-CODER-ALPHA-CONNECT-READ-001 -- vault-scoped connect REPORT READ.

Read-only consume of existing connect bind/manifest/receipt artifacts.
This module never calls ``connect_project``, never writes connect state,
and never treats a bind as PILOT or Truth Core.

Honesty:
- CONNECT != PILOT
- MANIFEST != TRUTH CORE
- RECEIPT != AUTHORITY
- SKIP != AUTHORITY
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

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-CONNECT-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-connect-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.connect-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-CODER-ALPHA-CONNECT-001",)
SOURCE_RELATIVES: Final[tuple[str, ...]] = (
    ".atlas/connect.json",
    "generated/ops/connect-manifest.json",
    "generated/ops/connect-receipt.json",
)
SOURCE_COMMAND: Final[str] = "atlas connect-status report"
TRUTH_BOUNDARY: Final[str] = (
    "CONNECT != PILOT / MANIFEST != TRUTH CORE / RECEIPT != AUTHORITY / "
    "SKIP != AUTHORITY / EMPTY != HEALTHY / UNKNOWN != HEALTHY / "
    "MCP != AUTHORITY / WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "CONNECT != PILOT",
    "MANIFEST != TRUTH CORE",
    "RECEIPT != AUTHORITY",
    "SKIP != AUTHORITY",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebConnectReadError(ValueError):
    """Fail-closed connect REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "connect_is_pilot": False,
        "manifest_is_truth_core": False,
        "receipt_is_authority": False,
        "skip_is_authority": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "connect_state_written": False,
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
        raise WebConnectReadError(f"connect-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebConnectReadError("connect-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebConnectReadError("connect-read-path-escape")
    return resolved


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebConnectReadError(f"connect-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebConnectReadError(f"connect-read-artifact-not-object:{path.name}")
    if payload.get("authentic_pilot") is True:
        raise WebConnectReadError("connect-read-authentic-pilot-invented")
    if payload.get("AUTHENTIC_PILOT") is True:
        raise WebConnectReadError("connect-read-authentic-pilot-invented")
    if payload.get("estate_pilot_passed") is True:
        raise WebConnectReadError("connect-read-estate-pilot-invented")
    return payload


def _existing_connect(vault: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    malformed = 0
    for relative in SOURCE_RELATIVES:
        path = vault / Path(relative)
        if not path.exists():
            continue
        if not path.is_file():
            raise WebConnectReadError(f"connect-read-artifact-not-file:{relative}")
        _inside(vault, path)
        try:
            payload = _load_json_object(path)
        except WebConnectReadError as exc:
            if "invented" in str(exc):
                raise
            malformed += 1
            continue
        records.append({"path": relative, "record": payload})
    return {
        "schema_version": 1,
        "artifact_count": len(records),
        "malformed_count": malformed,
        "artifacts": records,
        "authentic_pilot": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    raw_count = view.get("artifact_count")
    raw_malformed = view.get("malformed_count")
    count = raw_count if isinstance(raw_count, int) else 0
    malformed = raw_malformed if isinstance(raw_malformed, int) else 0
    if count == 0 and malformed == 0:
        return (
            "EMPTY",
            "no existing connect bind/manifest/receipt; EMPTY != HEALTHY; "
            "CONNECT != PILOT; MANIFEST != TRUTH CORE",
            "EMPTY_CONNECT_VIEW",
            False,
        )
    if count == 0 and malformed > 0:
        return (
            "UNKNOWN",
            "connect artifacts exist but could not be read; UNKNOWN != HEALTHY",
            "UNKNOWN_CONNECT_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing connect artifacts projected; CONNECT != PILOT; "
        "MANIFEST != TRUTH CORE; RECEIPT != AUTHORITY",
        "CONNECT_VIEW_PROJECTED",
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
        "source_command": SOURCE_COMMAND,
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


def read_connect_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing connect artifacts. Never writes."""
    root = _resolve_vault(vault)
    return _envelope(view=_existing_connect(root))


def render_connect_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas connect-status report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          CONNECT != PILOT; MANIFEST != TRUTH CORE; "
            "RECEIPT != AUTHORITY; EMPTY != HEALTHY; UNKNOWN != HEALTHY; "
            "MCP != AUTHORITY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
