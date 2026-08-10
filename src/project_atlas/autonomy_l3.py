"""AS-2.1-AUTONOMY-L3-001 - bounded L3 autonomy enablement.

Enables autonomy level 3 only when operator has ``autonomy.l3`` and an
active supervised scheduler arm exists. Never enables L4/L5. Never
promotes Layer B authority. Hardened: job timeout bound + disable receipt.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.scheduler_live import dispatch_supervised_job

PACKAGE_ID = "AS-2.1-AUTONOMY-L3-001"
TRUTH_BOUNDARY = (
    "L3_BOUNDED_AUTONOMY != L4/L5 / != UNSUPERVISED PROMOTE / != AUTHORITY"
)
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ALLOWED_L3_JOBS: frozenset[str] = frozenset(
    {"validate", "build-indexes", "version"}
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
    job_timeout_s: int = 120,
) -> dict[str, Any]:
    """Enable L3 bounded autonomy under AUTHZ + armed scheduler receipt."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("autonomy.l3")
    pid = policy_id.strip()
    if not _ID_RE.fullmatch(pid):
        raise AutonomyL3Error("autonomy-l3-policy-id-invalid")
    if max_jobs < 1 or max_jobs > 10:
        raise AutonomyL3Error("autonomy-l3-max-jobs-out-of-range")
    if job_timeout_s < 1 or job_timeout_s > 600:
        raise AutonomyL3Error("autonomy-l3-timeout-out-of-range")
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
        "policy_id": pid,
        "level": 3,
        "l3_bounded_autonomy": True,
        "enabled": True,
        "levels_enabled": {
            "0": True,
            "1": True,
            "2": True,
            "3": True,
            "4": False,
            "5": False,
        },
        "max_jobs_per_arm": max_jobs,
        "job_timeout_s": job_timeout_s,
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
    out = vault / "generated" / "ops" / "autonomy" / f"{pid}-l3-policy.json"
    _atomic_write_json(out, payload)
    return payload


def disable_bounded_l3(
    vault: Path,
    *,
    policy_id: str,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Write a disable receipt for an existing L3 policy (fail-closed if missing)."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("autonomy.l3")
    pid = policy_id.strip()
    if not _ID_RE.fullmatch(pid):
        raise AutonomyL3Error("autonomy-l3-policy-id-invalid")
    path = vault / "generated" / "ops" / "autonomy" / f"{pid}-l3-policy.json"
    if not path.is_file():
        raise AutonomyL3Error("autonomy-l3-policy-missing")
    prior = json.loads(path.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "policy_id": pid,
        "level": 3,
        "l3_bounded_autonomy": False,
        "enabled": False,
        "prior_enabled": bool(prior.get("enabled", True)),
        "arm_id": prior.get("arm_id"),
        "operator_id": op.operator_id,
        "vault_write_enabled": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "authority": {
            "level": "derived",
            "note": "L3 disabled; never Layer B promote",
        },
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "autonomy" / f"{pid}-l3-disabled.json"
    _atomic_write_json(out, payload)
    # Flip policy enabled flag in place for reconstructable state.
    prior["enabled"] = False
    prior["l3_bounded_autonomy"] = False
    _atomic_write_json(path, prior)
    return payload


def run_bounded_l3_loop(
    vault: Path,
    *,
    policy_id: str,
    jobs: list[str],
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Run a bounded policy→dispatch loop under L3 + armed scheduler.

    Requires ``autonomy.l3`` and ``scheduler.dispatch``. Never promotes
    Layer B. Caps job count by policy ``max_jobs_per_arm``.
    """
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("autonomy.l3")
    op.require("scheduler.dispatch")
    pid = policy_id.strip()
    if not _ID_RE.fullmatch(pid):
        raise AutonomyL3Error("autonomy-l3-policy-id-invalid")
    path = vault / "generated" / "ops" / "autonomy" / f"{pid}-l3-policy.json"
    if not path.is_file():
        raise AutonomyL3Error("autonomy-l3-policy-missing")
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("enabled") is not True or policy.get("l3_bounded_autonomy") is not True:
        raise AutonomyL3Error("autonomy-l3-policy-disabled")
    arm_id = str(policy.get("arm_id") or "")
    if not arm_id:
        raise AutonomyL3Error("autonomy-l3-arm-id-missing")
    max_jobs = int(policy.get("max_jobs_per_arm") or 0)
    timeout_s = int(policy.get("job_timeout_s") or 120)
    if not jobs:
        raise AutonomyL3Error("autonomy-l3-jobs-empty")
    if len(jobs) > max_jobs:
        raise AutonomyL3Error("autonomy-l3-jobs-exceed-max")
    results: list[dict[str, Any]] = []
    for raw_job in jobs:
        job = raw_job.strip()
        if job not in ALLOWED_L3_JOBS:
            raise AutonomyL3Error(f"autonomy-l3-job-forbidden:{job}")
        dispatch = dispatch_supervised_job(
            vault,
            arm_id=arm_id,
            job=job,  # type: ignore[arg-type]
            operator=op,
            timeout_s=timeout_s,
        )
        results.append(
            {
                "job": job,
                "exit_code": dispatch.get("exit_code"),
                "timed_out": dispatch.get("timed_out"),
                "duration_ms": dispatch.get("duration_ms"),
            }
        )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "policy_id": pid,
        "arm_id": arm_id,
        "l3_loop": True,
        "jobs_requested": list(jobs),
        "jobs_run": results,
        "vault_write_enabled": False,
        "promoted": False,
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "authority": {
            "level": "derived",
            "note": "L3 loop dispatches supervised jobs only; never Layer B",
        },
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "autonomy" / f"{pid}-l3-loop.json"
    _atomic_write_json(out, payload)
    return payload
