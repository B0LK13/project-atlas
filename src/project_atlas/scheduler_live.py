"""AS-2.1-SCHED-LIVE-001 - supervised live scheduler.

Operator must arm the scheduler, then dispatch allow-listed jobs that shell
out to local atlas CLI subcommands. Requires authz scheduler.arm + dispatch.
Hardened: bounded timeout + timed_out receipt fields.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Literal

from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor

PACKAGE_ID = "AS-2.1-SCHED-LIVE-001"
TRUTH_BOUNDARY = "LIVE_SUPERVISED_SCHEDULER != UNSUPERVISED AUTONOMY / != AUTHORITY"
JobKind = Literal["validate", "build-indexes", "version"]
DEFAULT_TIMEOUT_S = 120
MAX_TIMEOUT_S = 600

# arm_id is interpolated into generated/ops/scheduler/{arm_id}-*.json; require a
# bare safe token so it can never steer a receipt read/write outside that dir.
_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def _require_arm_id(arm_id: str) -> str:
    if not isinstance(arm_id, str) or not _ID_RE.match(arm_id):
        raise SchedulerLiveError("scheduler-arm-id-invalid")
    return arm_id


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
    default_timeout_s: int = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Write an arming receipt; required before live dispatch."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("scheduler.arm")
    arm_id = _require_arm_id(arm_id)
    if default_timeout_s < 1 or default_timeout_s > MAX_TIMEOUT_S:
        raise SchedulerLiveError("scheduler-timeout-out-of-range")
    payload = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "arm_id": arm_id,
        "armed": True,
        "default_timeout_s": default_timeout_s,
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
    timeout_s: int | None = None,
) -> dict[str, Any]:
    """Dispatch one allow-listed job under an existing arm receipt."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("scheduler.dispatch")
    arm_id = _require_arm_id(arm_id)
    arm_path = vault / "generated" / "ops" / "scheduler" / f"{arm_id}-arm.json"
    if not arm_path.is_file():
        raise SchedulerLiveError("scheduler-not-armed")
    arm = json.loads(arm_path.read_text(encoding="utf-8"))
    if arm.get("armed") is not True:
        raise SchedulerLiveError("scheduler-arm-inactive")
    if job not in ALLOWED_JOBS:
        raise SchedulerLiveError(f"scheduler-job-forbidden:{job}")
    arm_timeout = int(arm.get("default_timeout_s") or DEFAULT_TIMEOUT_S)
    limit = arm_timeout if timeout_s is None else timeout_s
    if limit < 1 or limit > MAX_TIMEOUT_S:
        raise SchedulerLiveError("scheduler-timeout-out-of-range")
    args = [sys.executable, "-m", "project_atlas.cli", *ALLOWED_JOBS[job]]
    if job in {"validate", "build-indexes"}:
        args.extend(["--vault", str(vault)])
    timed_out = False
    start = time.perf_counter()
    stdout = ""
    stderr = ""
    exit_code = 1
    try:
        proc = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=limit,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        # text=True => stdout/stderr are str | None
        stdout = "" if exc.stdout is None else str(exc.stdout)
        stderr = "" if exc.stderr is None else str(exc.stderr)
    duration_ms = int((time.perf_counter() - start) * 1000)
    payload = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "arm_id": arm_id,
        "job": job,
        "live_supervised_scheduler": True,
        "timeout_s": limit,
        "timed_out": timed_out,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "stdout_sha16": hashlib.sha256(stdout.encode("utf-8")).hexdigest()[:16],
        "stderr_sha16": hashlib.sha256(stderr.encode("utf-8")).hexdigest()[:16],
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "scheduler" / f"{arm_id}-{job}-dispatch.json"
    _atomic_write_json(out, payload)
    return payload
