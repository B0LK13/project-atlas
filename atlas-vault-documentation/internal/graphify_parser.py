"""Deterministic Graphify JSON and JSONL parser."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from internal import graphify_schema


def _records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise graphify_schema.GraphSchemaError(f"malformed-jsonl:{index}") from exc
            if not isinstance(value, dict):
                raise graphify_schema.GraphSchemaError(f"malformed-record:{index}")
            records.append(value)
        return records
    value = json.loads(path.read_text(encoding="utf-8"))
    graphify_schema.schema_for(value)
    if isinstance(value, dict) and isinstance(value.get("nodes"), list):
        return [item for item in value["nodes"] if isinstance(item, dict)]
    if isinstance(value, dict) and isinstance(value.get("edges"), list):
        return [item for item in value["edges"] if isinstance(item, dict)]
    return [value] if isinstance(value, dict) else []


def parse_artifact(artifact: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = Path(str(artifact["path"]))
    if path.name.lower() in {"metadata.json", "metadata.yaml", "metadata.yml"}:
        return [], []
    records = _records(path)
    name = path.name.lower()
    if name in {"edges.json", "edges.jsonl"} or "edge" in name:
        for item in records:
            graphify_schema.validate_record(item, kind="edge")
        return [], records
    if name in {"nodes.json", "nodes.jsonl"} or "node" in name:
        for item in records:
            graphify_schema.validate_record(item, kind="node")
        return records, []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            nodes = [item for item in value.get("nodes", []) if isinstance(item, dict)]
            edges = [item for item in value.get("edges", []) if isinstance(item, dict)]
    for item in nodes:
        graphify_schema.validate_record(item, kind="node")
    for item in edges:
        graphify_schema.validate_record(item, kind="edge")
    return nodes, edges
