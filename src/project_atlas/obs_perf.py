"""AS-2.1-OBS-PERF-001 - combined observability + perf deepen receipt.

Owns the deepen package envelope only. Consumes obs_live + perf_baselines
as library callables. Never mutates shared JSON schemas, api_server,
authz, or ops_receipts writers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.obs_live import build_live_observability_receipt
from project_atlas.perf_baselines import run_perf_baselines

PACKAGE_ID = "AS-2.1-OBS-PERF-001"
TRUTH_BOUNDARY = (
    "OBS-PERF DEEPEN != AUTHORITY / != RELEASE GATE / "
    "!= AUTHENTIC PILOT / UNKNOWN!=HEALTHY"
)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)


def build_obs_perf_receipt(
    vault: Path,
    *,
    receipt_id: str = "obs-perf",
    baseline_id: str = "obs-perf-lanes",
    iterations: int = 2,
) -> dict[str, Any]:
    """Build lane observability + perf baseline deepen receipt."""
    require_compatibility_anchor()
    rid = receipt_id.strip()
    if not rid or len(rid) > 64:
        raise ValueError("obs-perf-receipt-id-invalid")
    obs = build_live_observability_receipt(vault, receipt_id=f"{rid}-obs")
    perf = run_perf_baselines(
        vault, baseline_id=baseline_id, iterations=iterations
    )
    lanes_raw = obs.get("lanes")
    lanes: dict[str, Any] = lanes_raw if isinstance(lanes_raw, dict) else {}
    measurements_raw = perf.get("measurements")
    measurements: dict[str, Any] = (
        measurements_raw if isinstance(measurements_raw, dict) else {}
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "receipt_id": rid,
        "obs_receipt_id": obs.get("receipt_id"),
        "perf_baseline_id": perf.get("baseline_id"),
        "lanes_present": sorted(str(k) for k in lanes),
        "measurement_keys": sorted(str(k) for k in measurements),
        "rollup": "unknown",
        "release_blocking": False,
        "authentic_pilot_substitute": False,
        "shared_schema_mutated": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "obs-perf" / f"{rid}.json"
    _atomic_write_json(out, payload)
    return payload
