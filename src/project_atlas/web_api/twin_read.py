"""AS-CODER-ALPHA-TWIN-READ-001 -- vault-scoped twin-fixture REPORT READ.

Read-only consume of existing disposable twin-fixture artifacts. This
module never calls ``build_twin_projection_fixture``,
``build_twin_production_projection``, or ``build_twin_fixture_scenario``,
never writes twin state, and never treats a fixture as PILOT or
production-ready Twin.

Honesty:
- TWIN FIXTURE != PILOT
- TWIN FIXTURE != TWIN PRODUCTION READY
- TWIN FIXTURE != AUTHENTIC TWIN
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

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-TWIN-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-twin-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.twin-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = (
    "AS-2.0-TWIN-FIXTURE-001",
    "AS-2.0-TWIN-FIXTURE-002",
)
SOURCE_RELATIVES: Final[tuple[str, ...]] = (
    "generated/ops/twin-fixtures",
    "generated/ops/twin",
)
SOURCE_COMMAND: Final[str] = "atlas twin-fixture report"
TRUTH_BOUNDARY: Final[str] = (
    "TWIN FIXTURE != PILOT / TWIN FIXTURE != TWIN PRODUCTION READY / "
    "TWIN FIXTURE != AUTHENTIC TWIN / EMPTY != HEALTHY / UNKNOWN != HEALTHY / "
    "MCP != AUTHORITY / WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "TWIN FIXTURE != PILOT",
    "TWIN FIXTURE != TWIN PRODUCTION READY",
    "TWIN FIXTURE != AUTHENTIC TWIN",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebTwinReadError(ValueError):
    """Fail-closed twin-fixture REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "fixture_is_pilot": False,
        "fixture_is_twin_production_ready": False,
        "fixture_is_authentic_twin": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "twin_state_written": False,
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
        raise WebTwinReadError(f"twin-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebTwinReadError("twin-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebTwinReadError("twin-read-path-escape")
    return resolved


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebTwinReadError(f"twin-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebTwinReadError(f"twin-read-artifact-not-object:{path.name}")
    if payload.get("estate_pilot_passed") is True:
        raise WebTwinReadError("twin-read-estate-pilot-invented")
    if payload.get("twin_production_ready") is True:
        raise WebTwinReadError("twin-read-twin-production-ready-invented")
    if payload.get("claim_production_ready") is True:
        raise WebTwinReadError("twin-read-claim-production-ready-invented")
    return payload


def _existing_fixtures(vault: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    malformed = 0
    for relative in SOURCE_RELATIVES:
        directory = vault / Path(relative)
        if not directory.exists():
            continue
        if not directory.is_dir():
            raise WebTwinReadError(f"twin-read-artifact-not-dir:{relative}")
        safe_dir = _inside(vault, directory)
        for path in sorted(safe_dir.glob("*.json")):
            if not path.is_file():
                continue
            _inside(vault, path)
            try:
                payload = _load_json_object(path)
            except WebTwinReadError as exc:
                if "invented" in str(exc):
                    raise
                malformed += 1
                continue
            records.append({"path": path.relative_to(vault).as_posix(), "record": payload})
    return {
        "schema_version": 1,
        "artifact_count": len(records),
        "malformed_count": malformed,
        "artifacts": records,
        "estate_pilot_passed": False,
        "twin_production_ready": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    raw_count = view.get("artifact_count")
    raw_malformed = view.get("malformed_count")
    count = raw_count if isinstance(raw_count, int) else 0
    malformed = raw_malformed if isinstance(raw_malformed, int) else 0
    if count == 0 and malformed == 0:
        return (
            "EMPTY",
            "no existing twin-fixture artifacts; EMPTY != HEALTHY; "
            "TWIN FIXTURE != PILOT; TWIN FIXTURE != TWIN PRODUCTION READY",
            "EMPTY_TWIN_VIEW",
            False,
        )
    if count == 0 and malformed > 0:
        return (
            "UNKNOWN",
            "twin-fixture artifacts exist but could not be read; UNKNOWN != HEALTHY",
            "UNKNOWN_TWIN_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing twin-fixture artifacts projected; TWIN FIXTURE != PILOT; "
        "TWIN FIXTURE != TWIN PRODUCTION READY",
        "TWIN_VIEW_PROJECTED",
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


def read_twin_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing twin fixtures. Never writes."""
    root = _resolve_vault(vault)
    return _envelope(view=_existing_fixtures(root))


def render_twin_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas twin-fixture report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          TWIN FIXTURE != PILOT; "
            "TWIN FIXTURE != TWIN PRODUCTION READY; EMPTY != HEALTHY; "
            "UNKNOWN != HEALTHY; MCP != AUTHORITY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
