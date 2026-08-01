"""Deterministic duplicate collapse for graph relationships."""

from __future__ import annotations

from typing import Any

from internal.graph_edge import GraphEdge


def collapse(edges: list[GraphEdge]) -> tuple[list[GraphEdge], int, list[dict[str, Any]]]:
    canonical: dict[str, GraphEdge] = {}
    duplicates = 0
    conflicts: list[dict[str, Any]] = []
    for edge in sorted(edges, key=lambda item: (item.fingerprint(), item.graphify_edge_id, item.source_artifact_id)):
        prior = canonical.get(edge.fingerprint())
        if prior is None:
            canonical[edge.fingerprint()] = edge
        elif prior.graphify_edge_id == edge.graphify_edge_id and prior.relationship_type == edge.relationship_type:
            duplicates += 1
            canonical[edge.fingerprint()] = GraphEdge(**{**prior.__dict__, "supporting_artifacts": tuple(sorted(set(prior.supporting_artifacts + (edge.source_artifact_id,))))})
        else:
            conflicts.append({"type": "duplicate-conflict", "relationship_id": edge.relationship_id, "existing": prior.as_dict(), "incoming": edge.as_dict()})
    return list(canonical.values()), duplicates, conflicts
