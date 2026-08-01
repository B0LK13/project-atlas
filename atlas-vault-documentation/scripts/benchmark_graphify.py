#!/usr/bin/env python3
"""Offline Graphify adapter benchmark with deterministic synthetic graphs."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import tempfile
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from internal import content_fingerprint, graph_ingestion, graphify_parser  # noqa: E402

DATASETS = {"small": (25, 50), "medium": (500, 2000), "large": (5000, 25000)}


def _make(root: Path, nodes: int, edges: int) -> tuple[Path, dict[str, object]]:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "graphify-out" / "graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"schema_version": 1, "nodes": [{"id": f"node-{index}", "type": "component", "label": f"Component {index}"} for index in range(nodes)], "edges": [{"id": f"edge-{index}", "source": f"node-{index % nodes}", "target": f"node-{(index + 1) % nodes}", "type": "depends-on"} for index in range(edges)]}
    path.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    artifact = {"artifact_id": "benchmark:graphify-out/graph.json", "relative_path": "graphify-out/graph.json", "path": str(path), "sha256": content_fingerprint.sha256_file(path), "size_bytes": path.stat().st_size}
    return path, artifact


def _stats(values: list[float]) -> dict[str, float]:
    return {"min": min(values), "median": statistics.median(values), "max": max(values)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)
    if args.runs < 5:
        parser.error("--runs must be at least 5")
    datasets: dict[str, dict[str, object]] = {}
    result: dict[str, object] = {"schema_version": 1, "runs": args.runs, "python": platform.python_version(), "platform": platform.platform(), "datasets": datasets}
    with tempfile.TemporaryDirectory(prefix="atlas-wp005-benchmark-") as temp:
        base = Path(temp)
        for name, (node_count, edge_count) in DATASETS.items():
            root = base / name
            _path, artifact = _make(root, node_count, edge_count)
            parsed_times = []
            for _ in range(args.runs + 1):
                started = time.perf_counter()
                graphify_parser.parse_artifact(artifact)
                parsed_times.append(time.perf_counter() - started)
            parsed_times = parsed_times[1:]
            ingestion_times = []
            noop_times = []
            for index in range(args.runs + 1):
                started = time.perf_counter()
                graph_ingestion.ingest_graphify(project_id="benchmark", vault_root=base / f"vault-{name}-{index}", project_root=root, inventory={"project_id": "benchmark", "documents": [{"document_id": "benchmark:graphify-out/graph.json", "relative_path": "graphify-out/graph.json", "sha256": artifact["sha256"], "classification": {"type": "graphify-output"}, "authority": {"level": "derived"}}]}, config={"graphify": {"semantic_ingestion": True}}, strict=False)
                ingestion_times.append(time.perf_counter() - started)
                started = time.perf_counter()
                graph_ingestion.ingest_graphify(project_id="benchmark", vault_root=base / f"vault-{name}-{index}", project_root=root, inventory={"project_id": "benchmark", "documents": [{"document_id": "benchmark:graphify-out/graph.json", "relative_path": "graphify-out/graph.json", "sha256": artifact["sha256"], "classification": {"type": "graphify-output"}, "authority": {"level": "derived"}}]}, config={"graphify": {"semantic_ingestion": True}}, strict=False)
                noop_times.append(time.perf_counter() - started)
            ingestion_times = ingestion_times[1:]
            noop_times = noop_times[1:]
            datasets[name] = {"nodes": node_count, "edges": edge_count, "bytes": artifact["size_bytes"], "parse": _stats(parsed_times), "first_ingestion": _stats(ingestion_times), "no_op_replay": _stats(noop_times), "nodes_per_second": node_count / statistics.median(ingestion_times), "edges_per_second": edge_count / statistics.median(ingestion_times)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
