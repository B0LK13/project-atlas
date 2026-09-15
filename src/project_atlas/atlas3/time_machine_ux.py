"""AT3-093 — Isolated Time Machine UX reuse.

Reuses the landed AS-2.2-KDIFF-001 engine. Does not instantiate a second
clock. Does not call knowledge_diff writers. Wall-clock is not valid-time.
As-of is not authority. Missing stays UNKNOWN. No new CLI.
MERGE_AUTHORIZATION = NOT_GRANTED.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    OPS_RELATIVE,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
    require_project,
    require_vault,
)

PACKAGE_ID: Final[str] = "AT3-093"
GENERATOR_ID: Final[str] = "atlas3-time-machine-ux-093"
KDIFF_PACKAGE_ID: Final[str] = "AS-2.2-KDIFF-001"
UX_SURFACE: Final[str] = "time-machine"
ALLOWED_ENGINES: Final[frozenset[str]] = frozenset({KDIFF_PACKAGE_ID, "kdiff"})


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "time-machine" / project_id / "declared.json"


def _read_object(path: Path, *, corrupt_code: str, label: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise Atlas3Error(corrupt_code, f"{label} must be a regular file")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(corrupt_code, f"{label} is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise Atlas3Error(corrupt_code, f"{label} must be an object")
    return raw


def _reject_authority_claims(payload: dict[str, Any], *, label: str) -> None:
    if payload.get("trust_score") is not None:
        raise Atlas3Error("TRUST_SCORE_FORBIDDEN", f"{label} must not carry a trust score")
    if payload.get("graph_is_authority") is True or payload.get("graph_winner") is not None:
        raise Atlas3Error("GRAPH_WINNER_FORBIDDEN", f"{label} must not select a graph winner")
    if payload.get("winner") is not None:
        raise Atlas3Error("WINNER_SELECTED", f"{label} must not pick a winner")
    if payload.get("as_of_is_authority") is True or payload.get("kdiff_is_authority") is True:
        raise Atlas3Error("AS_OF_AUTHORITY", f"{label} as-of is not authority")
    if payload.get("wall_clock_is_valid_time") is True:
        raise Atlas3Error("WALL_CLOCK_AS_VALID_TIME", f"{label} wall-clock is not valid-time")
    if payload.get("observed_at_is_valid_time") is True:
        raise Atlas3Error("WALL_CLOCK_AS_VALID_TIME", f"{label} observed_at is not valid-time")
    if payload.get("second_temporal_engine") is True or payload.get("second_clock") is True:
        raise Atlas3Error("SECOND_CLOCK", f"{label} must not instantiate a second clock")
    engine = payload.get("engine") or payload.get("temporal_engine") or payload.get("clock")
    if engine is not None and str(engine) not in ALLOWED_ENGINES:
        raise Atlas3Error("SECOND_CLOCK", f"{label} engine {engine!r} is not {KDIFF_PACKAGE_ID}")
    if payload.get("merge_authorization") in {"GRANTED", "granted", True}:
        raise Atlas3Error("MERGE_CLAIM_FORBIDDEN", f"{label} must not grant merge")


def _walk_reject(payload: Any, *, label: str) -> None:
    if isinstance(payload, dict):
        _reject_authority_claims(payload, label=label)
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                _walk_reject(value, label=f"{label}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            if isinstance(item, (dict, list)):
                _walk_reject(item, label=f"{label}[{index}]")


def compile_time_machine_ux(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compose Time Machine UX over declared kdiff reuse. No second clock."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    declared = _read_object(
        _declared_path(root, pid),
        corrupt_code="TIME_MACHINE_CORRUPT",
        label="time-machine",
    )
    snapshots: list[dict[str, Any]] = []
    if declared is not None:
        declared_pid = str(declared.get("project_id") or pid).strip()
        if declared_pid and declared_pid != pid:
            raise Atlas3Error("CROSS_PROJECT", "time-machine project_id must match request")
        _walk_reject(declared, label="time-machine")
        raw = declared.get("snapshots") or declared.get("as_of") or []
        if raw and not isinstance(raw, list):
            raise Atlas3Error("TIME_MACHINE_CORRUPT", "snapshots must be a list")
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    raise Atlas3Error("TIME_MACHINE_CORRUPT", "snapshot row must be an object")
                _walk_reject(item, label="snapshot")
                valid_time = str(item.get("valid_time") or item.get("as_of") or "").strip()
                if not valid_time:
                    raise Atlas3Error(
                        "VALID_TIME_REQUIRED",
                        "snapshot requires document-declared valid_time",
                    )
                snapshots.append(
                    {
                        "valid_time": valid_time,
                        "kind": str(item.get("kind") or "kdiff-as-of-snapshot"),
                        "engine": KDIFF_PACKAGE_ID,
                        "as_of_is_authority": False,
                        "wall_clock_is_valid_time": False,
                    }
                )

    status = "derived" if snapshots or declared is not None else "UNKNOWN"
    reason = "COMPOSED_KDIFF_REUSE" if status == "derived" else "NO_KDIFF_PROJECTION"
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "data_package_id": KDIFF_PACKAGE_ID,
        "ux_surface": UX_SURFACE,
        "project_id": pid,
        "engine": KDIFF_PACKAGE_ID,
        "snapshots": snapshots,
        "counts": {"snapshots": len(snapshots)},
        "status": status,
        "reason": reason,
        "second_temporal_engine": False,
        "wall_clock_is_valid_time": False,
        "as_of_is_authority": False,
        "graph_is_authority": False,
        "new_cli_command": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
