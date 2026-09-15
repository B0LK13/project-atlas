"""Canonical Graphify relationship records for AS-WP-005."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphEdge:
    relationship_id: str
    project_id: str
    relationship_type: str
    source_entity_id: str | None
    target_entity_id: str | None
    source_graphify_id: str
    target_graphify_id: str
    source_artifact_id: str
    artifact_sha256: str
    graphify_edge_id: str
    record_index: int
    verification_state: str
    confidence: str
    source_documents: tuple[dict[str, str], ...] = ()
    source_relationship_type: str | None = None
    supporting_artifacts: tuple[str, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        return f"{self.project_id}|{self.source_entity_id}|{self.relationship_type}|{self.target_entity_id}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "record_type": "relationship",
            "relationship_id": self.relationship_id,
            "project_id": self.project_id,
            "relationship_type": self.relationship_type,
            "source_entity": {"atlas_entity_id": self.source_entity_id, "graphify_node_id": self.source_graphify_id},
            "target_entity": {"atlas_entity_id": self.target_entity_id, "graphify_node_id": self.target_graphify_id},
            "authority": {"level": "derived", "verification_state": self.verification_state, "confidence": self.confidence},
            "support": {"source_documents": list(self.source_documents)},
            "provenance": {"graphify_artifact_id": self.source_artifact_id, "artifact_sha256": self.artifact_sha256, "graphify_edge_id": self.graphify_edge_id, "record_index": self.record_index},
            "supporting_artifacts": list(self.supporting_artifacts),
            "attributes": self.attributes,
        }
