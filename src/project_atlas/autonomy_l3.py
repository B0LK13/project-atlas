"""AS-2.1-AUTONOMY-L3-001 - bounded L3 autonomy enablement.

Enables autonomy level 3 only when operator has ``autonomy.l3`` and an
active supervised scheduler arm exists. Never enables L4/L5. Never
promotes Layer B authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-AUTONOMY-L3-001"
TRUTH_BOUNDARY = (
    "L3_BOUNDED_AUTONOMY != L4/L5 / != UNSUPERVISED PROMOTE / != AUTHORITY"
)


class AutonomyL3Error(ValueError):
    """Fail-closed L3 autonomy error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def enable_bounded_l3(
    vault: Path,
    *,
    policy_id: str,
    arm_id: str,
    operator: OperatorProfile | None = None,
    max_jobs: int = 3,
) -> dict[str, Any]:
    """Enable L3 bounded autonomy under AUTHZ + armed scheduler receipt."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("autonomy.l3")
    if max_jobs < 1 or max_jobs > 10:
        raise AutonomyL3Error("autonomy-l3-max-jobs-out-of-range")
    arm_path = vault / "generated" / "ops" / "scheduler" / f"{arm_id}-arm.json"
    if not arm_path.is_file():
        raise AutonomyL3Error("autonomy-l3-scheduler-not-armed")
    arm = json.loads(arm_path.read_text(encoding="utf-8"))
    if arm.get("armed") is not True:
        raise AutonomyL3Error("autonomy-l3-scheduler-arm-inactive")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "policy_id": policy_id,
        "level": 3,
        "l3_bounded_autonomy": True,
        "levels_enabled": {"0": True, "1": True, "2": True, "3": True, "4": False, "5": False},
        "max_jobs_per_arm": max_jobs,
        "allowed_jobs": ["validate", "build-indexes", "version"],
        "arm_id": arm_id,
        "operator_id": op.operator_id,
        "vault_write_enabled": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "authority": {
            "level": "derived",
            "note": "L3 bounded ops jobs only; never Layer B promote",
        },
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "autonomy" / f"{policy_id}-l3-policy.json"
    _atomic_write_json(out, payload)
    return payload
