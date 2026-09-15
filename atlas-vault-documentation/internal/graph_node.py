"""Canonical Graphify node records for AS-WP-005."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    project_id: str
    source_artifact_id: str
    artifact_sha256: str
    record_index: int
    entity_type: str
    label: str
    atlas_entity_id: str | None
    resolution_status: str
    resolution_method: str
    confidence: str
    source_documents: tuple[dict[str, str], ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "record_type": "graph-node",
            "node_id": self.node_id,
            "project_id": self.project_id,
            "source": {"graphify_artifact_id": self.source_artifact_id, "graphify_node_id": self.node_id, "artifact_sha256": self.artifact_sha256, "record_index": self.record_index},
            "entity": {"type": self.entity_type, "label": self.label},
            "identity": {"atlas_entity_id": self.atlas_entity_id, "resolution_status": self.resolution_status, "resolution_method": self.resolution_method, "confidence": self.confidence},
            "authority": {"level": "derived", "verification_state": "supported" if self.resolution_status == "resolved" else "orphaned"},
            "source_documents": list(self.source_documents),
            "attributes": self.attributes,
        }
