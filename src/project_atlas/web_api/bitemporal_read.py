"""AS-CODER-ALPHA-BITEMPORAL-READ-001 -- vault-scoped bitemporal REPORT READ.

Read-only consume of persisted AS-2.0-TEMPORAL-001 validity catalogs under
``generated/ops/bitemporal/*-validity-catalog.json``. Never invokes
``write_validity_catalog`` / ``build_bitemporal_catalogs`` / kdiff
rematerialize, never writes, and never treats the catalog as Truth Core.

Honesty:
- CATALOG != AUTHORITY
- GRAPH != AUTHORITY
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

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-BITEMPORAL-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-bitemporal-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.bitemporal-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.0-TEMPORAL-001",)
SOURCE_RELATIVE_DIR: Final[str] = "generated/ops/bitemporal"
SOURCE_FILENAME_SUFFIX: Final[str] = "-validity-catalog.json"
SOURCE_COMMAND: Final[str] = "atlas bitemporal-status"
TRUTH_BOUNDARY: Final[str] = (
    "CATALOG != AUTHORITY / GRAPH != AUTHORITY / EMPTY != HEALTHY / "
    "UNKNOWN != HEALTHY / MCP != AUTHORITY / WRITE_APPLIED = false / "
    "VALIDITY CATALOG != TEMPORAL EVALUATOR REWRITE / "
    "src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)
HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "CATALOG != AUTHORITY",
    "GRAPH != AUTHORITY",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "VALIDITY CATALOG != TEMPORAL EVALUATOR REWRITE",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebBitemporalReadError(ValueError):
    """Fail-closed bitemporal REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "catalog_is_authority": False,
        "graph_is_authority": False,
        "auto_execution": False,
        "materialize_invoked": False,
        "derive_invoked": False,
        "write_catalog_invoked": False,
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
        raise WebBitemporalReadError(f"bitemporal-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebBitemporalReadError("bitemporal-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise WebBitemporalReadError("bitemporal-read-symlink-forbidden")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebBitemporalReadError("bitemporal-read-path-escape")
    return resolved


def _ascii_token(value: object) -> str:
    text = str(value).strip()
    return "".join(char if ord(char) < 128 else "?" for char in text)


def _reject_invented_authority(payload: dict[str, Any], *, name: str) -> None:
    if payload.get("authentic_pilot") is True or payload.get("AUTHENTIC_PILOT") is True:
        raise WebBitemporalReadError("bitemporal-read-authentic-pilot-invented")
    if payload.get("MERGE_AUTHORIZATION") in {"GRANTED", "granted", True}:
        raise WebBitemporalReadError(f"bitemporal-read-merge-authority-invented:{name}")
    if (
        payload.get("catalog_is_authority") is True
        or payload.get("lens_is_authority") is True
        or payload.get("graph_is_authority") is True
    ):
        raise WebBitemporalReadError("bitemporal-read-authority-invented")


def _project_id_from_name(name: str) -> str | None:
    if not name.endswith(SOURCE_FILENAME_SUFFIX):
        return None
    token = name[: -len(SOURCE_FILENAME_SUFFIX)]
    if not token or token.startswith(".") or "/" in token or "\\" in token:
        return None
    try:
        return safe_relative_component(token, label="project id")
    except ValueError:
        return None


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebBitemporalReadError(
            f"bitemporal-read-artifact-invalid:{path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise WebBitemporalReadError(f"bitemporal-read-artifact-not-object:{path.name}")
    _reject_invented_authority(payload, name=path.name)
    return payload


def _existing_catalogs(vault: Path) -> dict[str, Any]:
    catalog_dir = vault / SOURCE_RELATIVE_DIR
    rows: list[dict[str, Any]] = []
    skipped_names: list[str] = []
    malformed = 0
    if catalog_dir.exists():
        if catalog_dir.is_symlink():
            raise WebBitemporalReadError("bitemporal-read-symlink-forbidden")
        if not catalog_dir.is_dir():
            raise WebBitemporalReadError("bitemporal-read-catalogs-not-directory")
        _inside(vault, catalog_dir)
        for child in sorted(catalog_dir.iterdir(), key=lambda path: path.name):
            name = child.name
            project_id = _project_id_from_name(name)
            if project_id is None:
                if name.endswith(".json"):
                    skipped_names.append(name)
                continue
            if child.is_symlink():
                raise WebBitemporalReadError("bitemporal-read-symlink-forbidden")
            if not child.is_file():
                raise WebBitemporalReadError(f"bitemporal-read-artifact-not-file:{name}")
            resolved = _inside(vault, child)
            relative = f"{SOURCE_RELATIVE_DIR}/{name}"
            try:
                record = _load_json_object(resolved)
            except WebBitemporalReadError as exc:
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
            declared = str(record.get("catalog_id") or record.get("project_id") or "").strip()
            if declared and declared != project_id:
                raise WebBitemporalReadError(
                    f"bitemporal-read-project-mismatch:{name}:{declared}"
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
        "catalogs_dir_relative": SOURCE_RELATIVE_DIR,
        "artifact_count": len(rows),
        "malformed_count": malformed,
        "skipped_unsafe_names": skipped_names,
        "projects": rows,
        "materialize_invoked": False,
        "derive_invoked": False,
        "write_catalog_invoked": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    count = view.get("artifact_count")
    artifact_count = count if isinstance(count, int) else 0
    malformed = view.get("malformed_count")
    malformed_count = malformed if isinstance(malformed, int) else 0
    if artifact_count == 0:
        return (
            "EMPTY",
            "no existing validity-catalog artifacts; EMPTY != HEALTHY; "
            "CATALOG != AUTHORITY",
            "EMPTY_BITEMPORAL_VIEW",
            False,
        )
    if malformed_count > 0:
        return (
            "UNKNOWN",
            "validity-catalog artifacts exist but integrity is incomplete; "
            "UNKNOWN != HEALTHY; mixed valid+corrupt is not a healthy catalog",
            "UNKNOWN_BITEMPORAL_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing validity catalogs projected; CATALOG != AUTHORITY; "
        "GRAPH != AUTHORITY",
        "BITEMPORAL_VIEW_PROJECTED",
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


def read_bitemporal_view(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing validity catalogs. Never writes."""
    return _envelope(view=_existing_catalogs(_resolve_vault(vault)))


def render_bitemporal_status_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    raw_projects = inner.get("projects")
    projects: list[Any] = raw_projects if isinstance(raw_projects, list) else []
    lines = [
        f"atlas bitemporal-status [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          CATALOG != AUTHORITY; GRAPH != AUTHORITY; "
            "EMPTY != HEALTHY; UNKNOWN != HEALTHY; WRITE_APPLIED = false"
        ),
    ]
    for row in projects:
        if not isinstance(row, dict):
            continue
        raw_record = row.get("record")
        record: dict[str, Any] = raw_record if isinstance(raw_record, dict) else {}
        windows = record.get("window_count")
        summary = _ascii_token(
            f"windows={windows}" if windows is not None else (
                "malformed" if row.get("malformed") else "projected"
            )
        )
        lines.append(f"  - {row.get('project_id')}: {summary or 'UNKNOWN'}")
    return "\n".join(lines) + "\n"
