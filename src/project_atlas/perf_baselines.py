"""AS-2.1-PERF-BASELINE-001 / AS-2.1-OBS-PERF-001 - local performance baselines.

Records reconstructable micro-timings for live read surfaces across API,
MCP, query, and sync scaffolds. Never a release gate substitute for
authentic PILOT. No wall-clock stamps in payloads (duration_ms only).

Deepen (OBS-PERF): additive lane measurements only — no shared schema
mutation, no api_server/authz dual-own.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from project_atlas.app_service import open_app_service
from project_atlas.ask_atlas_live import ask_atlas_live
from project_atlas.compat_anchor import SNAPSHOT_ID, require_compatibility_anchor
from project_atlas.mcp_server import invoke_mcp_tool, list_mcp_tools
from project_atlas.pilot_auth_prep import scan_known_pilot_roots
from project_atlas.query_plan import build_query_plan
from project_atlas.sync_plan import build_dry_run_sync_plan

PACKAGE_ID = "AS-2.1-PERF-BASELINE-001"
DEEPEN_PACKAGE_ID = "AS-2.1-OBS-PERF-001"
TRUTH_BOUNDARY = (
    "PERF BASELINE != RELEASE GATE / != AUTHENTIC PILOT / UNKNOWN!=HEALTHY"
)

_UUID_A = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


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


def _stats(samples: list[int]) -> dict[str, Any]:
    return {
        "samples": samples,
        "max_ms": max(samples),
        "min_ms": min(samples),
    }


def _fixture_sync_registry() -> dict[str, Any]:
    """Minimal in-memory dry-run registry (no estate scan / no PILOT invent)."""
    return {
        "schema_version": 1,
        "schema": "atlas.workspace_registry.dry_run.v1",
        "truth_plane": "operational",
        "authority_plane": "none",
        "note": "PERF FIXTURE REGISTRY != AS-SYNC CERTIFIED / != PILOT PASS",
        "package": "AS-SYNC-001-SCAFFOLD",
        "production_sync_certified": False,
        "estate_pilot_passed": False,
        "registry_id": "perf-fixture-registry",
        "vault_identity": "perf-fixture-vault",
        "allowed_root_prefixes": ["/fixture"],
        "workspaces": [],
        "projects": [
            {
                "project_uuid": _UUID_A,
                "source_lineage_id": None,
                "root_id": "root-0000",
                "project_root": "/fixture/a",
                "enabled": True,
                "display_name": "A",
                "policy": None,
                "graphify_opt_in": False,
                "portfolio_opt_in": True,
            }
        ],
        "quarantine": [],
        "policy_defaults": {
            "include_globs": [],
            "exclude_globs": [],
            "sync_eligible": True,
            "priority": 100,
            "max_file_bytes": None,
            "max_files_per_sync": None,
            "sensitive_defaults": "exclude",
        },
        "generated": {"by": "project-atlas"},
    }


def _fixture_query_projects() -> list[dict[str, Any]]:
    return [
        {
            "project_id": "perf-fixture-project",
            "items": [
                {
                    "shape": "point",
                    "kind": "authoritative",
                    "subject": "perf-subject",
                    "field": "status",
                }
            ],
        }
    ]


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

    mcp_list_ms: list[int] = []
    for _ in range(iterations):
        _, ms = _time_ms(list_mcp_tools)
        mcp_list_ms.append(ms)

    # --- AS-2.1-OBS-PERF-001 deepen: API / MCP invoke / query / sync ---
    api_health_ms: list[int] = []
    for _ in range(iterations):
        _, ms = _time_ms(svc.health)
        api_health_ms.append(ms)

    api_projects_ms: list[int] = []
    for _ in range(iterations):
        _, ms = _time_ms(svc.projects)
        api_projects_ms.append(ms)

    mcp_invoke_ms: list[int] = []
    for _ in range(iterations):
        _, ms = _time_ms(
            lambda: invoke_mcp_tool(vault, "atlas.ops.health.read")
        )
        mcp_invoke_ms.append(ms)

    ask_ms: list[int] = []
    for _ in range(iterations):
        _, ms = _time_ms(
            lambda: ask_atlas_live(vault, query="vault health status")
        )
        ask_ms.append(ms)

    query_plan_ms: list[int] = []
    q_projects = _fixture_query_projects()
    for _ in range(iterations):
        _, ms = _time_ms(lambda: build_query_plan(q_projects))
        query_plan_ms.append(ms)

    sync_plan_ms: list[int] = []
    registry = _fixture_sync_registry()
    for _ in range(iterations):
        _, ms = _time_ms(lambda: build_dry_run_sync_plan(registry))
        sync_plan_ms.append(ms)

    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "deepen_package_id": DEEPEN_PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "baseline_id": bid,
        "iterations": iterations,
        "lanes_covered": ["api", "mcp", "query", "sync", "app_service", "pilot_prep"],
        "measurements": {
            "app_service_snapshot_ms": _stats(snap_ms),
            "pilot_prep_narrow_ms": _stats(pilot_ms),
            "mcp_list_tools_ms": _stats(mcp_list_ms),
            "api_health_read_ms": _stats(api_health_ms),
            "api_projects_read_ms": _stats(api_projects_ms),
            "mcp_invoke_health_ms": _stats(mcp_invoke_ms),
            "ask_atlas_query_ms": _stats(ask_ms),
            "query_plan_build_ms": _stats(query_plan_ms),
            "sync_plan_dry_run_ms": _stats(sync_plan_ms),
        },
        "release_blocking": False,
        "authentic_pilot_substitute": False,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    out = vault / "generated" / "ops" / "perf" / f"{bid}-baseline.json"
    _atomic_write_json(out, payload)
    return payload
