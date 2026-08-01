#!/usr/bin/env python3
"""Deterministic local inventory/no-op performance baseline for AS-WP-004."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path
from collections.abc import Callable
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(SCRIPT_ROOT))
from internal import document_inventory, ingestion_orchestrator, project_discovery  # noqa: E402


DATASETS = {"small": (12, 1024), "medium": (150, 70 * 1024), "large": (800, 70 * 1024)}


def _fixture(root: Path, count: int, size: int) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".atlas-project.yaml").write_text("schema_version: 1\nproject:\n  id: benchmark\n  name: Benchmark\n", encoding="utf-8")
    payload = ("# deterministic benchmark document\n" + "x" * (size - 36)).encode("utf-8")
    for index in range(count):
        (root / f"document-{index:04d}.md").write_bytes(payload)
    return root


def _sample(function: Callable[[], Any], runs: int) -> list[float]:
    function()
    values = []
    for _ in range(runs):
        start = time.perf_counter()
        function()
        values.append(time.perf_counter() - start)
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)
    if args.runs < 5:
        parser.error("--runs must be at least 5")
    with tempfile.TemporaryDirectory(prefix="atlas-wp004-benchmark-") as temporary:
        base = Path(temporary)
        datasets: dict[str, dict[str, object]] = {}
        result: dict[str, object] = {"schema_version": 1, "runs": args.runs, "python": platform.python_version(), "platform": platform.platform(), "filesystem": str(base.stat()), "datasets": datasets}
        def stats(values: list[float]) -> dict[str, float]:
            return {"min": min(values), "median": statistics.median(values), "max": max(values)}
        for name, (count, size) in DATASETS.items():
            root = _fixture(base / name, count, size)
            project = project_discovery.discover_projects(root, project_root=root)[0]
            inventory: dict[str, object] = {}
            discovery_times = _sample(lambda: project_discovery.discover_projects(root, project_root=root), args.runs)
            inventory_times = _sample(lambda: inventory.update(document_inventory.inventory_project(root, project_id=project.project_id)), args.runs)
            no_op_times = _sample(lambda: document_inventory.inventory_project(root, project_id=project.project_id), args.runs)
            (root / "incremental.md").write_text("# incremental\n", encoding="utf-8")
            incremental_times = _sample(lambda: document_inventory.inventory_project(root, project_id=project.project_id), args.runs)
            ingestion_stats: dict[str, object] = {}
            if name == "small":
                mock = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "bin" / "mda"
                ingestion_times: list[float] = []
                stage_times: list[dict[str, float]] = []
                for index in range(args.runs):
                    vault = base / f"vault-{index}"
                    started = time.perf_counter()
                    ingested = ingestion_orchestrator.ingest_project(
                        project, vault_root=vault, mda_command=str(mock)
                    )
                    ingestion_times.append(time.perf_counter() - started)
                    stage_times.append(ingested["timings"])
                ingestion_stats = {"first_ingestion": stats(ingestion_times), "stage_medians": {key: statistics.median(item[key] for item in stage_times) for key in stage_times[0]}}
            total_bytes = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
            datasets[name] = {"files": count + 1, "bytes": total_bytes, "discovery_inventory": stats([a + b for a, b in zip(discovery_times, inventory_times)]), "no_op_replay": stats(no_op_times), "single_file_incremental": stats(incremental_times), "hash_mib_per_second": total_bytes / (statistics.median(inventory_times) * 1024 * 1024), **ingestion_stats}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
