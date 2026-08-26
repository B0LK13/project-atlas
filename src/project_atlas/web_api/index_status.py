"""AS-CODER-ALPHA-INDEX-STATUS-001 -- vault-scoped lexical index REPORT READ.

Read-only consume of persisted AS-RET-001 artifacts under
``generated/indexes/*.json``. This module never invokes
``build_indexes`` / ``canonical_index_payloads`` / ``_promote``, never
writes, and never treats index presence as validate-pass, freshness, or
authority.

Honesty:
- INDEX_STATUS != AUTHORITY
- PRESENCE != VALIDATE
- PRESENCE != FRESH
- EMPTY != HEALTHY
- UNKNOWN != HEALTHY
- MCP != AUTHORITY
- WRITE_APPLIED = false
- obsolete ``indexes/`` is never authoritative
- src/project_atlas/atlas3/** UNTOUCHED
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Literal

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-INDEX-STATUS-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-index-status-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.index-status.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-RET-001",)
SOURCE_RELATIVE_DIR: Final[str] = "generated/indexes"
LEGACY_RELATIVE_DIR: Final[str] = "indexes"
SOURCE_COMMAND: Final[str] = "atlas index-status"
EXPECTED_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "authority.json",
        "claims.json",
        "concepts.json",
        "conflicts.json",
        "provenance.json",
        "reviews.json",
        "sources.json",
    }
)
TRUTH_BOUNDARY: Final[str] = (
    "INDEX_STATUS != AUTHORITY / PRESENCE != VALIDATE / PRESENCE != FRESH / "
    "EMPTY != HEALTHY / UNKNOWN != HEALTHY / MCP != AUTHORITY / "
    "WRITE_APPLIED = false / obsolete indexes/ never authoritative / "
    "src/project_atlas/atlas3/** UNTOUCHED / "
    "MERGE_AUTHORIZATION = NOT_GRANTED"
)
HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "INDEX_STATUS != AUTHORITY",
    "PRESENCE != VALIDATE",
    "PRESENCE != FRESH",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "obsolete indexes/ never authoritative",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebIndexStatusError(ValueError):
    """Fail-closed index-status REPORT READ error."""


def _honesty(*, legacy_indexes_present: bool) -> dict[str, bool | str]:
    return {
        "index_status_is_authority": False,
        "presence_is_validate": False,
        "presence_is_fresh": False,
        "legacy_indexes_authoritative": False,
        "legacy_indexes_present": legacy_indexes_present,
        "auto_execution": False,
        "materialize_invoked": False,
        "derive_invoked": False,
        "build_indexes_invoked": False,
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
        raise WebIndexStatusError(f"index-status-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebIndexStatusError("index-status-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise WebIndexStatusError("index-status-symlink-forbidden")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebIndexStatusError("index-status-path-escape")
    return resolved


def _ascii_token(value: object) -> str:
    text = str(value).strip()
    return "".join(char if ord(char) < 128 else "?" for char in text)


def _reject_invented_authority(payload: dict[str, Any], *, name: str) -> None:
    if payload.get("authentic_pilot") is True or payload.get("AUTHENTIC_PILOT") is True:
        raise WebIndexStatusError("index-status-authentic-pilot-invented")
    if payload.get("MERGE_AUTHORIZATION") in {"GRANTED", "granted", True}:
        raise WebIndexStatusError(f"index-status-merge-authority-invented:{name}")
    if (
        payload.get("index_status_is_authority") is True
        or payload.get("lens_is_authority") is True
        or payload.get("presence_is_validate") is True
    ):
        raise WebIndexStatusError("index-status-authority-invented")


def _safe_filename(name: str) -> bool:
    if not name.endswith(".json") or not name or name.startswith("."):
        return False
    return not ("/" in name or "\\" in name or ".." in name)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebIndexStatusError(f"index-status-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebIndexStatusError(f"index-status-artifact-not-object:{path.name}")
    _reject_invented_authority(payload, name=path.name)
    return payload


def _legacy_indexes_present(vault: Path) -> bool:
    legacy = vault / LEGACY_RELATIVE_DIR
    return legacy.exists()


def _existing_index_artifacts(vault: Path) -> dict[str, Any]:
    index_dir = vault / SOURCE_RELATIVE_DIR
    rows: list[dict[str, Any]] = []
    skipped_names: list[str] = []
    malformed = 0
    if index_dir.exists():
        if index_dir.is_symlink():
            raise WebIndexStatusError("index-status-symlink-forbidden")
        if not index_dir.is_dir():
            raise WebIndexStatusError("index-status-indexes-not-directory")
        _inside(vault, index_dir)
        for child in sorted(index_dir.iterdir(), key=lambda path: path.name):
            name = child.name
            if not _safe_filename(name):
                if name.endswith(".json"):
                    skipped_names.append(name)
                continue
            if child.is_symlink():
                raise WebIndexStatusError("index-status-symlink-forbidden")
            if not child.is_file():
                raise WebIndexStatusError(f"index-status-artifact-not-file:{name}")
            resolved = _inside(vault, child)
            relative = f"{SOURCE_RELATIVE_DIR}/{name}"
            try:
                record = _load_json_object(resolved)
            except WebIndexStatusError as exc:
                if "invented" in str(exc) or "symlink" in str(exc) or "escape" in str(exc):
                    raise
                malformed += 1
                rows.append(
                    {
                        "name": name,
                        "relative": relative,
                        "expected": name in EXPECTED_FILENAMES,
                        "present": True,
                        "malformed": True,
                        "key_count": 0,
                        "record": None,
                    }
                )
                continue
            rows.append(
                {
                    "name": name,
                    "relative": relative,
                    "expected": name in EXPECTED_FILENAMES,
                    "present": True,
                    "malformed": False,
                    "key_count": len(record),
                    "record": record,
                }
            )

    present_names = {str(row["name"]) for row in rows}
    missing_expected = sorted(EXPECTED_FILENAMES - present_names)
    return {
        "schema_version": 1,
        "index_dir_relative": SOURCE_RELATIVE_DIR,
        "legacy_dir_relative": LEGACY_RELATIVE_DIR,
        "legacy_indexes_present": _legacy_indexes_present(vault),
        "legacy_indexes_consumed": False,
        "artifact_count": len(rows),
        "malformed_count": malformed,
        "expected_count": len(EXPECTED_FILENAMES),
        "missing_expected": missing_expected,
        "skipped_unsafe_names": skipped_names,
        "artifacts": rows,
        "materialize_invoked": False,
        "derive_invoked": False,
        "build_indexes_invoked": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    count = view.get("artifact_count")
    artifact_count = count if isinstance(count, int) else 0
    malformed = view.get("malformed_count")
    malformed_count = malformed if isinstance(malformed, int) else 0
    if artifact_count == 0:
        return (
            "EMPTY",
            "no existing generated/indexes artifacts; EMPTY != HEALTHY; "
            "INDEX_STATUS != AUTHORITY; PRESENCE != VALIDATE",
            "EMPTY_INDEX_VIEW",
            False,
        )
    if malformed_count > 0:
        return (
            "UNKNOWN",
            "index artifacts exist but integrity is incomplete; "
            "UNKNOWN != HEALTHY; mixed valid+corrupt is not a healthy "
            "index lens; PRESENCE != VALIDATE",
            "UNKNOWN_INDEX_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing lexical index artifacts projected; "
        "INDEX_STATUS != AUTHORITY; PRESENCE != VALIDATE; PRESENCE != FRESH",
        "INDEX_VIEW_PROJECTED",
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
        "honesty": _honesty(
            legacy_indexes_present=bool(view.get("legacy_indexes_present"))
        ),
        "honesty_statements": list(HONESTY_STATEMENTS),
        "generated": {"by": GENERATOR_ID},
    }


def read_index_status(vault: Path) -> dict[str, Any]:
    """Read-only consume of existing lexical indexes. Never writes."""
    return _envelope(view=_existing_index_artifacts(_resolve_vault(vault)))


def render_index_status_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    raw_artifacts = inner.get("artifacts")
    artifacts: list[Any] = raw_artifacts if isinstance(raw_artifacts, list) else []
    lines = [
        f"atlas index-status [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        f"  missing_expected: {len(inner.get('missing_expected') or [])}",
        (
            "  honesty:          INDEX_STATUS != AUTHORITY; PRESENCE != VALIDATE; "
            "PRESENCE != FRESH; EMPTY != HEALTHY; UNKNOWN != HEALTHY; "
            "WRITE_APPLIED = false"
        ),
    ]
    for row in artifacts:
        if not isinstance(row, dict):
            continue
        raw_record = row.get("record")
        record: dict[str, Any] = raw_record if isinstance(raw_record, dict) else {}
        summary = _ascii_token(
            record.get("summary")
            or (
                f"keys={row.get('key_count', 0)}"
                if not row.get("malformed")
                else "malformed"
            )
        )
        lines.append(f"  - {row.get('name')}: {summary or 'UNKNOWN'}")
    return "\n".join(lines) + "\n"
