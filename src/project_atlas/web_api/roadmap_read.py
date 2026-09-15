"""AS-CODER-ALPHA-ROADMAP-READ-001 -- vault-scoped Roadmap answers REPORT READ.

Read-only consume of persisted AS-PROJECT-ROADMAP-001 answer artifacts
under generated/answers/ans-roadmap-*.json. This module never invokes
materialize_roadmap_lenses / build_roadmap_lens, never writes, and never
treats the lens as Truth Core or as canonical roadmap truth.

Honesty:
- ROADMAP != AUTHORITY
- ROADMAP != CANONICAL_TRUTH
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

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-ROADMAP-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-roadmap-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.roadmap-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-PROJECT-ROADMAP-001",)
SOURCE_RELATIVE_DIR: Final[str] = "generated/answers"
SOURCE_FILENAME_PREFIX: Final[str] = "ans-roadmap-"
SOURCE_FILENAME_SUFFIX: Final[str] = ".json"
SOURCE_COMMAND: Final[str] = "atlas roadmap-status"
TRUTH_BOUNDARY: Final[str] = (
    "ROADMAP != AUTHORITY / ROADMAP != CANONICAL_TRUTH / EMPTY != HEALTHY / "
    "UNKNOWN != HEALTHY / MCP != AUTHORITY / WRITE_APPLIED = false / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)
HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "ROADMAP != AUTHORITY",
    "ROADMAP != CANONICAL_TRUTH",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebRoadmapAnswersReadError(ValueError):
    """Fail-closed Roadmap answers REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "roadmap_is_authority": False,
        "roadmap_is_canonical": False,
        "roadmap_is_healthy": False,
        "auto_execution": False,
        "materialize_invoked": False,
        "empty_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "pilot_invented": False,
        "authentic_pilot": False,
        "owner_capability_granted": False,
        "atlas3_untouched": "src/project_atlas/atlas3/** UNTOUCHED",
        "MERGE_AUTHORIZATION": "NOT_GRANTED",
        "lens_is_authority": False,
    }


def _resolve_vault(vault: Path) -> Path:
    root = vault.expanduser()
    try:
        root = root.resolve()
    except OSError as exc:
        raise WebRoadmapAnswersReadError(f"roadmap-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebRoadmapAnswersReadError("roadmap-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise WebRoadmapAnswersReadError("roadmap-read-symlink-forbidden")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebRoadmapAnswersReadError("roadmap-read-path-escape")
    return resolved


def _ascii_token(value: object) -> str:
    text = str(value).strip()
    return "".join(char if ord(char) < 128 else "?" for char in text)


def _reject_invented_authority(payload: dict[str, Any], *, name: str) -> None:
    if payload.get("authentic_pilot") is True or payload.get("AUTHENTIC_PILOT") is True:
        raise WebRoadmapAnswersReadError("roadmap-read-authentic-pilot-invented")
    if payload.get("MERGE_AUTHORIZATION") in {"GRANTED", "granted", True}:
        raise WebRoadmapAnswersReadError(f"roadmap-read-merge-authority-invented:{name}")
    if (
        payload.get("roadmap_is_authority") is True
        or payload.get("roadmap_is_canonical") is True
        or payload.get("roadmap_is_healthy") is True
        or payload.get("lens_is_authority") is True
    ):
        raise WebRoadmapAnswersReadError("roadmap-read-authority-invented")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebRoadmapAnswersReadError(f"roadmap-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebRoadmapAnswersReadError(f"roadmap-read-artifact-not-object:{path.name}")
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


def _existing_roadmap_answers(vault: Path) -> dict[str, Any]:
    answers_dir = vault / SOURCE_RELATIVE_DIR
    rows: list[dict[str, Any]] = []
    skipped_names: list[str] = []
    malformed = 0
    if answers_dir.exists():
        if answers_dir.is_symlink():
            raise WebRoadmapAnswersReadError("roadmap-read-symlink-forbidden")
        if not answers_dir.is_dir():
            raise WebRoadmapAnswersReadError("roadmap-read-answers-not-directory")
        _inside(vault, answers_dir)
        for child in sorted(answers_dir.iterdir(), key=lambda path: path.name):
            name = child.name
            project_id = _project_id_from_name(name)
            if project_id is None:
                if name.startswith(SOURCE_FILENAME_PREFIX):
                    skipped_names.append(name)
                continue
            if child.is_symlink():
                raise WebRoadmapAnswersReadError("roadmap-read-symlink-forbidden")
            if not child.is_file():
                raise WebRoadmapAnswersReadError(f"roadmap-read-artifact-not-file:{name}")
            resolved = _inside(vault, child)
            relative = f"{SOURCE_RELATIVE_DIR}/{name}"
            try:
                record = _load_json_object(resolved)
            except WebRoadmapAnswersReadError as exc:
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
                raise WebRoadmapAnswersReadError(
                    f"roadmap-read-project-mismatch:{name}:{declared}"
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
            "no existing ans-roadmap artifacts; EMPTY != HEALTHY; "
            "ROADMAP != AUTHORITY",
            "EMPTY_ROADMAP_VIEW",
            False,
        )
    if malformed_count > 0:
        return (
            "UNKNOWN",
            "ans-roadmap artifacts exist but integrity is incomplete; "
            "UNKNOWN != HEALTHY; mixed valid+corrupt is not a healthy roadmap-answers view",
            "UNKNOWN_ROADMAP_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing Roadmap answers answers projected; ROADMAP != AUTHORITY; "
        "ROADMAP != CANONICAL_TRUTH",
        "ROADMAP_VIEW_PROJECTED",
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


def read_roadmap_answers_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing ans-roadmap artifacts. Never writes."""
    return _envelope(view=_existing_roadmap_answers(_resolve_vault(vault)))


def render_roadmap_status_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    raw_projects = inner.get("projects")
    projects: list[Any] = raw_projects if isinstance(raw_projects, list) else []
    lines = [
        f"atlas roadmap-status [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          ROADMAP != AUTHORITY; ROADMAP != CANONICAL_TRUTH; "
            "EMPTY != HEALTHY; UNKNOWN != HEALTHY; WRITE_APPLIED = false"
        ),
    ]
    for row in projects:
        if not isinstance(row, dict):
            continue
        raw_record = row.get("record")
        record: dict[str, Any] = raw_record if isinstance(raw_record, dict) else {}
        summary = _ascii_token(record.get("summary") or record.get("value") or "UNKNOWN")
        raw_status = record.get("status")
        if not raw_status and row.get("malformed"):
            raw_status = "malformed"
        status = _ascii_token(raw_status or "UNKNOWN")
        lines.append(
            f"  - {row.get('project_id')}: [{status}] {summary or 'UNKNOWN'}"
        )
    return "\n".join(lines) + "\n"
