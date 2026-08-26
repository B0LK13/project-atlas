"""AS-CODER-ALPHA-HANDOFF-READ-001 -- vault-scoped handoff REPORT READ.

Read-only consume of persisted handoff packs under generated/ops/handoffs/.
This module never calls create_handoff or resume_handoff, never writes, and
never treats a pack as authority.

Honesty:
- HANDOFF REPORT != AUTHORITY
- PACK != TRUTH CORE
- RESUME != THIS SURFACE
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-HANDOFF-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-handoff-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.handoff-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-CODER-ALPHA-HANDOFF-001",)
SOURCE_RELATIVES: Final[tuple[str, ...]] = ("generated/ops/handoffs",)
SOURCE_COMMAND: Final[str] = "atlas handoff-status report"
TRUTH_BOUNDARY: Final[str] = (
    "HANDOFF REPORT != AUTHORITY / PACK != TRUTH CORE / RESUME != THIS SURFACE / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)
HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "HANDOFF REPORT != AUTHORITY",
    "PACK != TRUTH CORE",
    "RESUME != THIS SURFACE",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebHandoffReadError(ValueError):
    """Fail-closed handoff REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "handoff_report_is_authority": False,
        "pack_is_truth_core": False,
        "resume_invoked": False,
        "create_invoked": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
        "ui_is_canonical": False,
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebHandoffReadError(f"handoff-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebHandoffReadError("handoff-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise WebHandoffReadError("handoff-read-symlink-forbidden")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebHandoffReadError("handoff-read-path-escape")
    return resolved


def _ascii_token(value: object) -> str:
    text = str(value).strip()
    return "".join(char if ord(char) < 128 else "?" for char in text)


def _reject_invented_authority(payload: dict[str, Any], *, name: str) -> None:
    if payload.get("authentic_pilot") is True or payload.get("AUTHENTIC_PILOT") is True:
        raise WebHandoffReadError("handoff-read-authentic-pilot-invented")
    if payload.get("MERGE_AUTHORIZATION") in {"GRANTED", "granted", True}:
        raise WebHandoffReadError(f"handoff-read-merge-authority-invented:{name}")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebHandoffReadError(f"handoff-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebHandoffReadError(f"handoff-read-artifact-not-object:{path.name}")
    _reject_invented_authority(payload, name=path.name)
    return payload


def _handoff_dir(vault: Path) -> Path | None:
    path = vault / "generated" / "ops" / "handoffs"
    if not path.exists():
        return None
    if path.is_symlink():
        raise WebHandoffReadError("handoff-read-symlink-forbidden")
    if not path.is_dir():
        raise WebHandoffReadError("handoff-read-artifact-not-dir:generated/ops/handoffs")
    return _inside(vault, path)


def _existing_handoffs(vault: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    malformed = 0
    seen_ids: dict[str, str] = {}
    project_ids: set[str] = set()
    latest: dict[str, Any] | None = None
    handoff_dir = _handoff_dir(vault)
    if handoff_dir is None:
        return {
            "schema_version": 1,
            "artifact_count": 0,
            "malformed_count": 0,
            "project_ids": [],
            "latest": None,
            "artifacts": [],
            "create_invoked": False,
            "resume_invoked": False,
        }
    latest_path = handoff_dir / "latest.json"
    if latest_path.exists():
        if latest_path.is_symlink():
            raise WebHandoffReadError("handoff-read-symlink-forbidden")
        if not latest_path.is_file():
            raise WebHandoffReadError("handoff-read-latest-not-file")
        try:
            latest = _load_json_object(_inside(vault, latest_path))
        except WebHandoffReadError as exc:
            if "invented" in str(exc):
                raise
            malformed += 1
            latest = None
    for path in sorted(handoff_dir.iterdir(), key=lambda item: item.name):
        if path.is_symlink():
            raise WebHandoffReadError("handoff-read-symlink-forbidden")
        if not path.is_file() or path.suffix != ".json" or path.name == "latest.json":
            continue
        relative = path.relative_to(vault).as_posix()
        try:
            payload = _load_json_object(_inside(vault, path))
        except WebHandoffReadError as exc:
            if "invented" in str(exc):
                raise
            malformed += 1
            continue
        handoff_id = str(payload.get("handoff_id") or payload.get("id") or "").strip()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if handoff_id:
            prior = seen_ids.get(handoff_id)
            if prior is not None and prior != canonical:
                raise WebHandoffReadError(f"handoff-read-id-collision:{handoff_id}")
            seen_ids[handoff_id] = canonical
        project_id = str(payload.get("project_id") or "").strip()
        if project_id:
            project_ids.add(project_id)
        records.append({"path": relative, "handoff_id": handoff_id or None, "record": payload})
    records.sort(key=lambda row: str(row["path"]))
    return {
        "schema_version": 1,
        "artifact_count": len(records),
        "malformed_count": malformed,
        "project_ids": sorted(project_ids),
        "latest": latest,
        "artifacts": records,
        "create_invoked": False,
        "resume_invoked": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    raw_count = view.get("artifact_count")
    raw_malformed = view.get("malformed_count")
    count = raw_count if isinstance(raw_count, int) else 0
    malformed = raw_malformed if isinstance(raw_malformed, int) else 0
    if count == 0 and malformed == 0:
        return (
            "EMPTY",
            "no existing handoff packs; EMPTY != HEALTHY; HANDOFF REPORT != AUTHORITY",
            "EMPTY_HANDOFF_VIEW",
            False,
        )
    if malformed > 0:
        return (
            "UNKNOWN",
            "handoff artifacts exist but integrity is incomplete; "
            "UNKNOWN != HEALTHY; mixed valid+corrupt is not a healthy report",
            "UNKNOWN_HANDOFF_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing handoff packs projected; HANDOFF REPORT != AUTHORITY; PACK != TRUTH CORE",
        "HANDOFF_VIEW_PROJECTED",
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


def read_handoff_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing handoff packs. Never writes."""
    return _envelope(view=_existing_handoffs(_resolve_vault(vault)))


def show_handoff_view(vault: Path, *, handoff_id: str | None = None) -> dict[str, Any]:
    """Show one persisted pack without resume. Missing stays UNKNOWN."""
    report = read_handoff_view(vault)
    view = report["view"]
    artifacts = view.get("artifacts") if isinstance(view.get("artifacts"), list) else []
    selected: dict[str, Any] | None = None
    wanted = (handoff_id or "").strip()
    if wanted:
        if "/" in wanted or "\\" in wanted or wanted in {".", ".."}:
            raise WebHandoffReadError(f"handoff-read-unsafe-id:{wanted}")
        for row in artifacts:
            if isinstance(row, dict) and str(row.get("handoff_id") or "") == wanted:
                selected = row
                break
        if selected is None:
            report["status"] = "UNKNOWN"
            report["available"] = False
            report["reason_code"] = "UNKNOWN_HANDOFF_ID"
            report["reason"] = "requested handoff id is not present; UNKNOWN stays UNKNOWN"
            report["view"] = {**view, "selected": None, "requested_handoff_id": wanted}
            return report
    elif artifacts:
        latest = view.get("latest") if isinstance(view.get("latest"), dict) else None
        latest_id = str((latest or {}).get("handoff_id") or "").strip()
        if latest_id:
            for row in artifacts:
                if isinstance(row, dict) and str(row.get("handoff_id") or "") == latest_id:
                    selected = row
                    break
        if selected is None:
            first = artifacts[0]
            selected = first if isinstance(first, dict) else None
    report["view"] = {**view, "selected": selected, "requested_handoff_id": wanted or None}
    return report


def render_handoff_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    project_ids = inner.get("project_ids")
    project_text = (
        ",".join(_ascii_token(item) for item in project_ids)
        if isinstance(project_ids, list)
        else ""
    )
    lines = [
        f"atlas handoff-status report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        f"  project_ids:      {project_text or '(none)'}",
        (
            "  honesty:          HANDOFF REPORT != AUTHORITY; PACK != TRUTH CORE; "
            "RESUME != THIS SURFACE; EMPTY != HEALTHY; UNKNOWN != HEALTHY; "
            "WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
