"""AT3-100 — Isolated twin health.

Derived health signals only. Health != authority.
Estate availability != owner authorization. Missing stays UNKNOWN.
Never writes Truth Core. MERGE_AUTHORIZATION remains NOT_GRANTED.
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

PACKAGE_ID: Final[str] = "AT3-100"
GENERATOR_ID: Final[str] = "atlas3-twin-health-100"
DECLARED_NAME: Final[str] = "declared.json"
ALLOWED_STATES: Final[frozenset[str]] = frozenset({"CURRENT", "STALE", "UNKNOWN"})


def _declared_path(vault: Path, project_id: str) -> Path:
    return vault / OPS_RELATIVE / "twin-health" / project_id / DECLARED_NAME


def _load_declared(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error(
            "TWIN_HEALTH_CORRUPT",
            "declared twin health is not readable JSON",
        ) from exc
    if not isinstance(raw, dict):
        raise Atlas3Error("TWIN_HEALTH_CORRUPT", "declared twin health must be an object")
    return raw


def _signals(raw: object) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Atlas3Error("TWIN_HEALTH_CORRUPT", "signals must be a list")
    rows: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise Atlas3Error("TWIN_HEALTH_CORRUPT", "signals row is not an object")
        signal_id = str(item.get("signal_id") or item.get("id") or "").strip()
        if not signal_id:
            raise Atlas3Error("SIGNAL_ID_REQUIRED", "twin health signal requires signal_id")
        state = str(item.get("state") or "UNKNOWN").strip().upper()
        if state not in ALLOWED_STATES:
            raise Atlas3Error("SIGNAL_STATE_UNKNOWN", f"unsupported signal state {state!r}")
        evidence = item.get("evidence_refs") or item.get("evidence")
        if not isinstance(evidence, list):
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{signal_id} requires evidence_refs")
        refs = [str(ref).strip() for ref in evidence if str(ref).strip()]
        if not refs:
            raise Atlas3Error("PROVENANCE_REQUIRED", f"{signal_id} requires evidence_refs")
        rows.append(
            {
                "signal_id": signal_id,
                "state": state,
                "evidence_refs": refs,
                "is_authority": False,
            }
        )
    return rows


def compile_twin_health(vault: Path | str, project_id: str) -> dict[str, Any]:
    """Compile derived twin health. Missing evidence stays UNKNOWN."""
    root = require_vault(vault)
    pid = require_project(root, project_id)
    path = _declared_path(root, pid)
    if not path.is_file():
        return {
            "schema_version": 1,
            "package_id": PACKAGE_ID,
            "generated": {"by": GENERATOR_ID},
            "project_id": pid,
            "signals": [],
            "counts": {"signals": 0},
            "status": "UNKNOWN",
            "reason": "NO_DECLARED_TWIN_HEALTH",
            "health_is_authority": False,
            "estate_available": False,
            "estate_availability_is_authorization": False,
            "certified_for_merge": False,
            "merge_authorization": "NOT_GRANTED",
            "promoted_to_truth_core": 0,
            "write_applied": False,
            "truth_boundary": TRUTH_BOUNDARY,
            "honesty": honesty_block(),
        }
    declared = _load_declared(path)
    declared_project = str(declared.get("project_id") or "").strip()
    if declared_project and declared_project != pid:
        raise Atlas3Error(
            "CROSS_PROJECT",
            "declared twin health project_id does not match request",
        )
    if declared.get("health_is_authority") is True:
        raise Atlas3Error(
            "HEALTH_AUTHORITY_CLAIMED",
            "twin health must not claim authority",
        )
    if declared.get("estate_availability_is_authorization") is True:
        raise Atlas3Error(
            "ESTATE_IS_NOT_AUTHORIZATION",
            "estate availability is not owner authorization",
        )
    signals = _signals(declared.get("signals"))
    estate_available = bool(declared.get("estate_available"))
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "signals": signals,
        "counts": {"signals": len(signals)},
        "status": "derived",
        "reason": "DECLARED_TWIN_HEALTH",
        "health_is_authority": False,
        "estate_available": estate_available,
        "estate_availability_is_authorization": False,
        "certified_for_merge": False,
        "merge_authorization": "NOT_GRANTED",
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
