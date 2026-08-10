"""AS-2.1-SCHED-LIVE-001 - supervised live scheduler.

Operator must arm the scheduler, then dispatch allow-listed jobs that shell
out to local atlas CLI subcommands. Requires authz scheduler.arm + dispatch.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-SCHED-LIVE-001"
TRUTH_BOUNDARY = "LIVE_SUPERVISED_SCHEDULER != UNSUPERVISED AUTONOMY / != AUTHORITY"
JobKind = Literal["validate", "build-indexes", "version"]


class SchedulerLiveError(ValueError):
    """Fail-closed supervised scheduler error."""


ALLOWED_JOBS: dict[JobKind, tuple[str, ...]] = {
    "validate": ("validate",),
    "build-indexes": ("build-indexes",),
    "version": ("version",),
}


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def arm_scheduler(
    vault: Path,
    *,
    arm_id: str,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Write an arming receipt; required before live dispatch."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("scheduler.arm")
    payload = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "arm_id": arm_id,
        "armed": True,
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    path = vault / "generated" / "ops" / "scheduler" / f"{arm_id}-arm.json"
    _atomic_write_json(path, payload)
    return payload


def dispatch_supervised_job(
    vault: Path,
    *,
    arm_id: str,
    job: JobKind,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Dispatch one allow-listed job under an existing arm receipt."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("scheduler.dispatch")
    arm_path = vault / "generated" / "ops" / "scheduler" / f"{arm_id}-arm.json"
    if not arm_path.is_file():
        raise SchedulerLiveError("scheduler-not-armed")
    arm = json.loads(arm_path.read_text(encoding="utf-8"))
    if arm.get("armed") is not True:
        raise SchedulerLiveError("scheduler-arm-inactive")
    if job not in ALLOWED_JOBS:
        raise SchedulerLiveError(f"scheduler-job-forbidden:{job}")
    args = [sys.executable, "-m", "project_atlas.cli", *ALLOWED_JOBS[job]]
    if job in {"validate", "build-indexes"}:
        args.extend(["--vault", str(vault)])
    proc = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "arm_id": arm_id,
        "job": job,
        "live_supervised_scheduler": True,
        "exit_code": proc.returncode,
        "stdout_sha16": hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest()[:16],
        "stderr_sha16": hashlib.sha256(proc.stderr.encode("utf-8")).hexdigest()[:16],
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "scheduler" / f"{arm_id}-{job}-dispatch.json"
    _atomic_write_json(out, payload)
    return payload
