"""AS-CODER-ALPHA-RUNTIME-READ-001 -- vault-scoped runtime REPORT READ.

Read-only inventory of the existing AS-2.2-RUNTIME-001 substrate
(``generated/indexes`` plus optional ``generated/ops/runtime`` artifacts).
This module never calls ``hybrid_retrieve`` or ``compile_context``, never
writes compiler/pack state, and never treats indexes as Truth Core.

Honesty:
- RUNTIME != AUTHORITY
- INDEXES != TRUTH CORE
- HYBRID != AUTHORITY
- COMPILED CONTEXT != TRUTH
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

PACKAGE_ID: Final[str] = "AS-CODER-ALPHA-RUNTIME-READ-001"
GENERATOR_ID: Final[str] = "atlas-coder-alpha-runtime-read-001"
SCHEMA_ID: Final[str] = "atlas.coder-alpha.runtime-read.v1"
SOURCE_PACKAGES: Final[tuple[str, ...]] = ("AS-2.2-RUNTIME-001",)
INDEX_RELATIVE: Final[str] = "generated/indexes"
RUNTIME_OPS_RELATIVE: Final[str] = "generated/ops/runtime"
SOURCE_COMMAND: Final[str] = "atlas runtime report"
TRUTH_BOUNDARY: Final[str] = (
    "RUNTIME != AUTHORITY / INDEXES != TRUTH CORE / HYBRID != AUTHORITY / "
    "COMPILED CONTEXT != TRUTH / EMPTY != HEALTHY / UNKNOWN != HEALTHY / "
    "MCP != AUTHORITY / WRITE_APPLIED = false / D149_TOUCHED = NO / "
    "src/project_atlas/atlas3/** UNTOUCHED / MERGE_AUTHORIZATION = NOT_GRANTED"
)

HONESTY_STATEMENTS: Final[tuple[str, ...]] = (
    "RUNTIME != AUTHORITY",
    "INDEXES != TRUTH CORE",
    "HYBRID != AUTHORITY",
    "COMPILED CONTEXT != TRUTH",
    "EMPTY != HEALTHY",
    "UNKNOWN != HEALTHY",
    "MCP != AUTHORITY",
    "WRITE_APPLIED = false",
    "D149_TOUCHED = NO",
    "src/project_atlas/atlas3/** UNTOUCHED",
    "MERGE_AUTHORIZATION = NOT_GRANTED",
)

StatusRollup = Literal["UNKNOWN", "EMPTY", "PRESENT"]


class WebRuntimeReadError(ValueError):
    """Fail-closed runtime REPORT READ error."""


def _honesty() -> dict[str, bool | str]:
    return {
        "runtime_is_authority": False,
        "indexes_are_truth_core": False,
        "hybrid_is_authority": False,
        "compiled_context_is_truth": False,
        "empty_is_healthy": False,
        "unknown_is_healthy": False,
        "mcp_is_authority": False,
        "write_applied": False,
        "WRITE_APPLIED": False,
        "runtime_state_written": False,
        "compiler_written": False,
        "hybrid_invoked": False,
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
        raise WebRuntimeReadError(f"runtime-read-vault-unreadable:{exc}") from exc
    if not root.is_dir():
        raise WebRuntimeReadError("runtime-read-vault-missing")
    return root


def _inside(root: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise WebRuntimeReadError("runtime-read-path-escape")
    return resolved


def _count_index_files(vault: Path) -> int:
    directory = vault / Path(INDEX_RELATIVE)
    if not directory.exists():
        return 0
    if not directory.is_dir():
        raise WebRuntimeReadError("runtime-read-indexes-not-dir")
    safe_dir = _inside(vault, directory)
    count = 0
    for path in sorted(safe_dir.rglob("*")):
        if path.is_file():
            _inside(vault, path)
            count += 1
    return count


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        raise WebRuntimeReadError(f"runtime-read-artifact-invalid:{path.name}") from exc
    if not isinstance(payload, dict):
        raise WebRuntimeReadError(f"runtime-read-artifact-not-object:{path.name}")
    return payload


def _existing_runtime_ops(vault: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    malformed = 0
    directory = vault / Path(RUNTIME_OPS_RELATIVE)
    if not directory.exists():
        return records, malformed
    if not directory.is_dir():
        raise WebRuntimeReadError("runtime-read-ops-not-dir")
    safe_dir = _inside(vault, directory)
    for path in sorted(safe_dir.glob("*.json")):
        if not path.is_file():
            continue
        _inside(vault, path)
        try:
            payload = _load_json_object(path)
        except WebRuntimeReadError:
            malformed += 1
            continue
        records.append({"path": path.relative_to(vault).as_posix(), "record": payload})
    return records, malformed


def _existing_runtime(vault: Path) -> dict[str, Any]:
    index_count = _count_index_files(vault)
    artifacts, malformed = _existing_runtime_ops(vault)
    return {
        "schema_version": 1,
        "index_relative": INDEX_RELATIVE,
        "ops_relative": RUNTIME_OPS_RELATIVE,
        "index_file_count": index_count,
        "artifact_count": len(artifacts),
        "malformed_count": malformed,
        "artifacts": artifacts,
        "hybrid_invoked": False,
        "compiler_invoked": False,
    }


def _rollup(view: dict[str, Any]) -> tuple[StatusRollup, str, str, bool]:
    indexes = view.get("index_file_count")
    count = view.get("artifact_count")
    malformed = view.get("malformed_count")
    index_n = indexes if isinstance(indexes, int) else 0
    art_n = count if isinstance(count, int) else 0
    bad_n = malformed if isinstance(malformed, int) else 0
    if index_n == 0 and art_n == 0 and bad_n == 0:
        return (
            "EMPTY",
            "no existing runtime indexes or ops artifacts; EMPTY != HEALTHY; "
            "RUNTIME != AUTHORITY; INDEXES != TRUTH CORE",
            "EMPTY_RUNTIME_VIEW",
            False,
        )
    if index_n == 0 and art_n == 0 and bad_n > 0:
        return (
            "UNKNOWN",
            "runtime ops artifacts exist but could not be read; UNKNOWN != HEALTHY",
            "UNKNOWN_RUNTIME_VIEW",
            False,
        )
    return (
        "PRESENT",
        "existing runtime substrate projected; RUNTIME != AUTHORITY; "
        "INDEXES != TRUTH CORE; HYBRID != AUTHORITY",
        "RUNTIME_VIEW_PROJECTED",
        True,
    )


def _envelope(*, view: dict[str, Any]) -> dict[str, Any]:
    status, reason, reason_code, available = _rollup(view)
    return {
        "schema_version": 1,
        "schema": SCHEMA_ID,
        "package_id": PACKAGE_ID,
        "source_packages": list(SOURCE_PACKAGES),
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


def read_runtime_view(vault: Path) -> dict[str, Any]:
    """Read-only inventory of runtime substrate. Never writes or retrieves."""
    root = _resolve_vault(vault)
    return _envelope(view=_existing_runtime(root))


def render_runtime_text(view: dict[str, Any]) -> str:
    """Human CLI rendering. ASCII only."""
    inner: dict[str, Any] = {}
    raw_view = view.get("view")
    if isinstance(raw_view, dict):
        inner = raw_view
    lines = [
        f"atlas runtime report [{view.get('status', 'UNKNOWN')}]",
        f"  available:        {view.get('available')}",
        f"  reason:           {view.get('reason_code')}",
        f"  index_file_count: {inner.get('index_file_count', 0)}",
        f"  artifact_count:   {inner.get('artifact_count', 0)}",
        f"  malformed_count:  {inner.get('malformed_count', 0)}",
        (
            "  honesty:          RUNTIME != AUTHORITY; INDEXES != TRUTH CORE; "
            "HYBRID != AUTHORITY; EMPTY != HEALTHY; UNKNOWN != HEALTHY; "
            "MCP != AUTHORITY; WRITE_APPLIED = false"
        ),
    ]
    return "\n".join(lines) + "\n"
