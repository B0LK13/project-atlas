"""AS-2.1-PERF-BASELINE-001 - deterministic local performance baselines.

Records reconstructable micro-timings for live read surfaces. Never a
release gate substitute for authentic PILOT. No wall-clock stamps in
payloads (duration_ms only).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from project_atlas.app_service import open_app_service
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.mcp_server import list_mcp_tools
from project_atlas.pilot_auth_prep import scan_known_pilot_roots

PACKAGE_ID = "AS-2.1-PERF-BASELINE-001"
TRUTH_BOUNDARY = (
    "PERF BASELINE != RELEASE GATE / != AUTHENTIC PILOT / UNKNOWN!=HEALTHY"
)


class PerfBaselineError(ValueError):
    """Fail-closed performance baseline error."""


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def _time_ms(fn: Callable[[], Any]) -> tuple[Any, int]:
    start = time.perf_counter()
    result = fn()
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return result, elapsed_ms


def run_perf_baselines(
    vault: Path,
    *,
    baseline_id: str = "live-read",
    iterations: int = 3,
) -> dict[str, Any]:
    """Run bounded local read baselines and persist a receipt."""
    require_compatibility_anchor()
    if iterations < 1 or iterations > 20:
        raise PerfBaselineError("perf-iterations-out-of-range")
    bid = baseline_id.strip()
    if not bid or len(bid) > 64:
        raise PerfBaselineError("perf-baseline-id-invalid")

    svc = open_app_service(vault)
    snap_ms: list[int] = []
    for _ in range(iterations):
        _, ms = _time_ms(svc.snapshot)
        snap_ms.append(ms)

    # Narrow pilot prep (no workspace crawl) for a cheap bounded timing.
    pilot_ms: list[int] = []
    missing = vault / ".atlas-perf-missing-root"
    for _ in range(iterations):
        _, ms = _time_ms(
            lambda: scan_known_pilot_roots(
                candidates=[missing],
                include_workspace_scan=False,
            )
        )
        pilot_ms.append(ms)

    mcp_ms: list[int] = []
    for _ in range(iterations):
        _, ms = _time_ms(list_mcp_tools)
        mcp_ms.append(ms)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "baseline_id": bid,
        "iterations": iterations,
        "measurements": {
            "app_service_snapshot_ms": {
                "samples": snap_ms,
                "max_ms": max(snap_ms),
                "min_ms": min(snap_ms),
            },
            "pilot_prep_narrow_ms": {
                "samples": pilot_ms,
                "max_ms": max(pilot_ms),
                "min_ms": min(pilot_ms),
            },
            "mcp_list_tools_ms": {
                "samples": mcp_ms,
                "max_ms": max(mcp_ms),
                "min_ms": min(mcp_ms),
            },
        },
        "release_blocking": False,
        "authentic_pilot_substitute": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "perf" / f"{bid}-baseline.json"
    _atomic_write_json(out, payload)
    return payload
