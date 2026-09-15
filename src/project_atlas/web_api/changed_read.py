"""AS-CODER-ALPHA-CHANGED-READ-001 -- vault-scoped What Changed REPORT READ.

Read-only consume of persisted AS-CODER-ALPHA-CHANGED-001 answer artifacts
under generated/answers/ans-changed-*.json. This module never invokes
materialize_changed_lenses, never writes, and never treats the lens as
live-estate current or as authority.

Honesty:
- CHANGED != AUTHORITY
- CHANGED != LIVE ESTATE
- STALE != CURRENT
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

from atlas_contracts.identity import safe_relative_component

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-CHANGED-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-changed-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.changed-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-CODER-ALPHA-CHANGED-001",)
SOURCE_RELATIVE_DIR: Final[str] = "generated/answers"
SOURCE_FILENAME_PREFIX: Final[str] = "ans-changed-"
SOURCE_FILENAME_SUFFIX: Final[str] = ".json"
SOURCE_COMMAND: Final[str] = "atlas changed-status"
TRUTH_BOUNDARY: Final[str] = (
    "CHANGED != AUTHORITY / CHANGED != LIVE ESTATE / STALE != CURRENT / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)
HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "CHANGED != AUTHORITY",
    "CHANGED != LIVE ESTATE",
    "STALE != CURRENT",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebChangedReadError(ValueError):
    """Fail-closed What Changed REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "changed_is_authority": False,
        "changed_is_live_estate": False,
        "stale_is_current": False,
        "auto_execution": False,
        "materialize_invoked": False,
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
        raise WebChangedReadError(f"changed-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebChangedReadError("changed-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise WebChangedReadError("changed-read-symlink-forbidden")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebChangedReadError("changed-read-path-escape")
    return resolved


def _ascii_token(value: object) -> str:
    text = str(value).strip()
    return "".join(char if ord(char) < 128 else "?" for char in text)


def _reject_invented_authority(payload: dict[str, Any], *, name: str) -> None:
    if payload.get("authentic_pilot") is True or payload.get("AUTHENTIC_PILOT") is True:
        raise WebChangedReadError("changed-read-authentic-pilot-invented")
    if payload.get("MERGE_AUTHORIZATION") in {"GRANTED", "granted", True}:
        raise WebChangedReadError(f"changed-read-merge-authority-invented:{name}")
    if (
        payload.get("changed_is_authority") is True
        or payload.get("lens_is_authority") is True
    ):
        raise WebChangedReadError("changed-read-authority-invented")
    if payload.get("stale_is_current") is True or payload.get("auto_execution") is True:
        raise WebChangedReadError("changed-read-current-invented")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebChangedReadError(f"changed-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebChangedReadError(f"changed-read-artifact-not-object:{path.name}")
    _reject_invented_authority(payload, name=path.name)
    return payload


def _project_id_from_name(name: str) -> str | None:
    if not name.startswith(SOURCE_FILENAME_PREFIX):
        return None
    if not name.endswith(SOURCE_FILENAME_SUFFIX):
        return None
    token = name[len(SOURCE_FILENAME_PREFIX) : -len(SOURCE_FILENAME_SUFFIX)]
    if not token or token.startswith(".") or "/" in token or "\\" in token:
        return None
    try:
        return safe_relative_component(token, label="project id")
    except ValueError:
        return None


def _existing_changed_answers(vault: Path) -> dict[str, Any]:
    answers_dir = vault / SOURCE_RELATIVE_DIR
    rows: list[dict[str, Any]] = []
    skipped_names: list[str] = []
    malformed = 0
    if answers_dir.exists():
        if answers_dir.is_symlink():
            raise WebChangedReadError("changed-read-symlink-forbidden")
        if not answers_dir.is_dir():
            raise WebChangedReadError("changed-read-answers-not-directory")
        _inside(vault, answers_dir)
        for child in sorted(answers_dir.iterdir(), key=lambda path: path.name):
            name = child.name
            project_id = _project_id_from_name(name)
            if project_id is None:
                if name.startswith(SOURCE_FILENAME_PREFIX):
                    skipped_names.append(name)
                continue
            if child.is_symlink():
                raise WebChangedReadError("changed-read-symlink-forbidden")
            if not child.is_file():
                raise WebChangedReadError(f"changed-read-artifact-not-file:{name}")
            resolved = _inside(vault, child)
            relative = f"{SOURCE_RELATIVE_DIR}/{name}"
            try:
                record = _load_json_object(resolved)
            except WebChangedReadError as exc:
                if "invented" in str(exc) or "symlink" in str(exc) or "escape" in str(exc):
                    raise
                malformed += 1
                rows.append(
                    {
                        "project_id": project_id,
                        "relative": relative,
                        "present": True,
                        "malformed": True,
                        "record": None,
                    }
                )
                continue
            declared = str(record.get("project_id") or "").strip()
            if declared and declared != project_id:
                raise WebChangedReadError(
                    f"changed-read-project-mismatch:{name}:{declared}"
                )
            rows.append(
                {
                    "project_id": project_id,
                    "relative": relative,
                    "present": True,
                    "malformed": False,
                    "record": record,
                }
            )

    return {
        "schema_version": 1,
        "answers_dir_relative": SOURCE_RELATIVE_DIR,
        "artifact_count": len(rows),
        "malformed_count": malformed,
        "skipped_unsafe_names": skipped_names,
        "projects": rows,
        "materialize_invoked": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    count = view.get("artifact_count")
    artifact_count = count if isinstance(count, int) else 0
    malformed = view.get("malformed_count")
    malformed_count = malformed if isinstance(malformed, int) else 0
    if artifact_count == 0:
        return (
            "EMPTY",
            "no existing ans-changed artifacts; EMPTY != HEALTHY; "
            "CHANGED != AUTHORITY",
            "EMPTY_CHANGED_VIEW",
            False,
        )
    if malformed_count > 0:
        return (
            "UNKNOWN",
            "ans-changed artifacts exist but integrity is incomplete; "
            "UNKNOWN != HEALTHY; mixed valid+corrupt is not a healthy changed lens",
            "UNKNOWN_CHANGED_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing What Changed answers projected; CHANGED != AUTHORITY; "
        "CHANGED != LIVE ESTATE; STALE != CURRENT",
        "CHANGED_VIEW_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
        "source_relative_dir": SOURCE_RELATIVE_DIR,
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


def read_changed_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing ans-changed artifacts. Never writes."""
    return _envelope(view=_existing_changed_answers(_resolve_vault(vault)))


def render_changed_status_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    raw_projects = inner.get("projects")
    projects: list[Any] = raw_projects if isinstance(raw_projects, list) else []
    lines = [
        f"atlas changed-status [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          CHANGED != AUTHORITY; CHANGED != LIVE ESTATE; "
            "STALE != CURRENT; EMPTY != HEALTHY; WRITE_APPLIED = false"
        ),
    ]
    for row in projects:
        if not isinstance(row, dict):
            continue
        raw_record = row.get("record")
        record: dict[str, Any] = raw_record if isinstance(raw_record, dict) else {}
        summary = _ascii_token(record.get("summary") or record.get("value") or "UNKNOWN")
        raw_status = record.get("status") or record.get("rollup")
        if not raw_status and row.get("malformed"):
            raw_status = "malformed"
        status = _ascii_token(raw_status or "UNKNOWN")
        raw_delta = record.get("delta")
        delta: dict[str, Any] = raw_delta if isinstance(raw_delta, dict) else {}
        added = delta.get("added_count", "?")
        removed = delta.get("removed_count", "?")
        modified = delta.get("modified_count", "?")
        lines.append(
            f"  - {row.get('project_id')}: [{status}] "
            f"added={added} removed={removed} modified={modified} "
            f"{summary or 'UNKNOWN'}"
        )
    return "\n".join(lines) + "\n"
