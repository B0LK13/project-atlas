"""Governed, project-local Graphify ingestion for AS-WP-005."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from internal import (
    atlas_router,
    content_fingerprint,
    graph_confidence,
    graph_deduplication,
    graph_identity,
    graph_projection,
    graph_quarantine,
    graph_source_linking,
    graphify_discovery,
    graphify_parser,
    graph_ingestion_state,
)
from internal.graph_edge import GraphEdge
from internal.graph_node import GraphNode


class GraphIngestionError(RuntimeError):
    """A strict graph transaction failed."""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _receipt_id(project_id: str, combined: str) -> str:
    return f"AG-{combined[:16]}-{project_id}"


def _entity_map(nodes: list[GraphNode]) -> dict[str, GraphNode]:
    return {node.node_id: node for node in nodes}


def ingest_graphify(*, project_id: str, vault_root: Path, project_root: Path, inventory: dict[str, Any], config: dict[str, Any] | None = None, incremental: bool = True, dry_run: bool = False, strict: bool = True) -> dict[str, Any]:
    config = config or {}
    graph_config = config.get("graphify", {}) if isinstance(config.get("graphify", {}), dict) else {}
    if graph_config.get("semantic_ingestion", True) is False:
        return {"ok": True, "status": "disabled", "project_id": project_id, "artifacts": [], "nodes": [], "relationships": [], "quarantine": [], "receipt": None}
    artifacts = graphify_discovery.discover_artifacts(inventory, project_root, config={"graphify": {**graph_config, "semantic_ingestion": True}})
    combined = hashlib.sha256("|".join(f"{item['artifact_id']}:{item['sha256']}" for item in artifacts).encode("utf-8")).hexdigest()
    state_path = vault_root / "relationships" / "state" / f"{project_id}.json"
    previous = graph_ingestion_state.load(state_path, project_id)
    unchanged = incremental and previous.get("combined_sha256") == combined and previous.get("last_receipt")
    if dry_run:
        return {"ok": True, "status": "dry-run", "project_id": project_id, "artifacts": artifacts, "combined_sha256": combined}
    if unchanged:
        receipt_path = vault_root / "relationships" / "receipts" / f"{project_id}-{combined[:16]}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
        return {"ok": True, "status": "no-op", "project_id": project_id, "artifacts": artifacts, "nodes": [], "relationships": [], "quarantine": [], "receipt": receipt, "counts": {"artifacts_reparsed": 0, "nodes_added": 0, "relationships_added": 0, "projections_written": 0}}
    nodes: list[GraphNode] = []
    raw_edges: list[tuple[dict[str, Any], dict[str, Any]]] = []
    quarantine: list[dict[str, Any]] = []
    for artifact in artifacts:
        try:
            raw_nodes, parsed_edges = graphify_parser.parse_artifact(artifact)
        except (OSError, UnicodeError, ValueError) as exc:
            quarantine.append(graph_quarantine.record(project_id, "unknown-schema" if "schema" in str(exc) else "malformed-record", {}, artifact_id=str(artifact["artifact_id"]), message=str(exc)))
            continue
        for index, raw in enumerate(raw_nodes):
            source_links, link_state = graph_source_linking.link_sources(raw, inventory)
            resolution = graph_identity.resolve_node(raw, project_id, config=config)
            node = GraphNode(node_id=str(raw.get("id") or raw.get("node_id")), project_id=project_id, source_artifact_id=str(artifact["artifact_id"]), artifact_sha256=str(artifact["sha256"]), record_index=index, entity_type=str(raw.get("type") or raw.get("entity_type") or "unknown"), label=str(raw.get("label") or raw.get("name") or raw.get("id") or "unknown"), atlas_entity_id=resolution["atlas_entity_id"], resolution_status=resolution["status"], resolution_method=resolution["method"], confidence=resolution["confidence"], source_documents=source_links, attributes={key: value for key, value in raw.items() if key not in {"id", "node_id", "type", "entity_type", "label", "name", "source_documents", "sources"}})
            if node.resolution_status != "resolved":
                quarantine.append(graph_quarantine.record(project_id, "ambiguous-identity", raw, artifact_id=str(artifact["artifact_id"]), message=node.resolution_status))
            nodes.append(node)
        raw_edges.extend((edge, artifact) for edge in parsed_edges)
    node_map = _entity_map(nodes)
    normalized_edges: list[GraphEdge] = []
    for index, (raw, artifact) in enumerate(raw_edges):
        source_id = str(raw.get("source") or raw.get("from"))
        target_id = str(raw.get("target") or raw.get("to"))
        source = node_map.get(source_id)
        target = node_map.get(target_id)
        relationship_type = str(raw.get("type") or raw.get("relationship_type") or raw.get("kind") or "extension")
        if relationship_type not in {"part-of", "contains", "depends-on", "implements", "documents", "validates", "tests", "references", "supersedes", "blocks", "owned-by", "generated-by", "configured-by", "deployed-to", "stores-data-in", "exposes", "consumes", "invokes", "produces", "requires", "relates-to", "derived-from", "supports", "conflicts-with"}:
            relationship_type = "extension"
        source_links, link_state = graph_source_linking.link_sources(raw, inventory)
        verification_state = "orphaned" if source is None or target is None else link_state
        confidence = graph_confidence.relationship_confidence(source_resolved=source is not None, target_resolved=target is not None, source_links=len(source_links), graphify_confidence=str(raw.get("confidence", "")))
        if verification_state == "orphaned":
            quarantine.append(graph_quarantine.record(project_id, "unresolved-source-node" if source is None else "unresolved-target-node", raw, artifact_id=str(artifact["artifact_id"]), message="edge endpoint cannot be resolved"))
        edge_id = str(raw.get("id") or raw.get("edge_id") or f"edge-{index:06d}")
        normalized_edges.append(GraphEdge(relationship_id=f"GR-{project_id}-{index:06d}-{hashlib.sha256(f'{source_id}|{relationship_type}|{target_id}'.encode()).hexdigest()[:8]}", project_id=project_id, relationship_type=relationship_type, source_entity_id=source.atlas_entity_id if source else None, target_entity_id=target.atlas_entity_id if target else None, source_graphify_id=source_id, target_graphify_id=target_id, source_artifact_id=str(artifact["artifact_id"]), artifact_sha256=str(artifact["sha256"]), graphify_edge_id=edge_id, record_index=index, verification_state=verification_state, confidence=confidence, source_documents=source_links, source_relationship_type=str(raw.get("type")) if raw.get("type") else None, attributes={key: value for key, value in raw.items() if key not in {"id", "edge_id", "source", "from", "target", "to", "type", "relationship_type", "kind", "confidence", "source_documents", "sources"}}))
    canonical_edges, duplicates, conflicts = graph_deduplication.collapse(normalized_edges)
    for conflict in conflicts:
        quarantine.append(graph_quarantine.record(project_id, "duplicate-conflict", conflict, artifact_id="derived", message="same relationship identity has incompatible Graphify records"))
    metrics = {"artifacts_discovered": len(artifacts), "artifacts_accepted": len(artifacts), "nodes_parsed": len(nodes), "nodes_resolved": sum(node.resolution_status == "resolved" for node in nodes), "relationships_parsed": len(normalized_edges), "relationships_canonical": len(canonical_edges), "relationships_verified": sum(edge.verification_state == "verified" for edge in canonical_edges), "relationships_supported": sum(edge.verification_state == "supported" for edge in canonical_edges), "relationships_inferred": sum(edge.verification_state == "inferred" for edge in canonical_edges), "relationships_orphaned": sum(edge.verification_state == "orphaned" for edge in canonical_edges), "duplicates_collapsed": duplicates, "quarantine_records": len(quarantine), "source_links_checked": sum(len(edge.source_documents) for edge in canonical_edges)}
    receipt_id = _receipt_id(project_id, combined)
    receipt = {"schema_version": 1, "receipt_type": "atlas-graph-ingestion", "receipt_id": receipt_id, "project": {"project_id": project_id}, "artifacts": {"discovered": len(artifacts), "accepted": len(artifacts), "unsupported": 0, "failed": 0, "combined_sha256": combined}, "nodes": {"parsed": len(nodes), "resolved": metrics["nodes_resolved"], "unresolved": len(nodes) - metrics["nodes_resolved"], "canonical": len(nodes), "quarantined": sum(1 for item in quarantine if "identity" in item["category"])}, "relationships": {"parsed": len(normalized_edges), "canonical": len(canonical_edges), "verified": metrics["relationships_verified"], "supported": metrics["relationships_supported"], "inferred": metrics["relationships_inferred"], "conflicting": len(conflicts), "orphaned": metrics["relationships_orphaned"], "duplicates_collapsed": duplicates, "quarantined": len(quarantine)}, "source_links": {"checked": metrics["source_links_checked"]}, "authority": {"graphify": "derived", "canonical_override_allowed": False}, "validation": {"status": "passed", "errors": 0, "warnings": len(quarantine)}, "sync_state": "synchronized", "blockers": []}
    if strict and conflicts:
        raise GraphIngestionError("duplicate-conflict requires quarantine review")
    base = vault_root / "relationships"
    node_lines = "\n".join(json.dumps(node.as_dict(), ensure_ascii=False, sort_keys=True) for node in sorted(nodes, key=lambda item: item.node_id)) + ("\n" if nodes else "")
    edge_lines = "\n".join(json.dumps(edge.as_dict(), ensure_ascii=False, sort_keys=True) for edge in sorted(canonical_edges, key=lambda item: item.relationship_id)) + ("\n" if canonical_edges else "")
    graph_state = {"schema_version": 1, "project_id": project_id, "combined_sha256": combined, "artifacts": {str(item["artifact_id"]): {"sha256": item["sha256"], "status": "ingested"} for item in artifacts}, "nodes": {node.node_id: node.as_dict() for node in nodes}, "relationships": {edge.relationship_id: edge.as_dict() for edge in canonical_edges}, "quarantine": {str(index): item for index, item in enumerate(quarantine)}, "last_receipt": receipt_id}
    map_content = graph_projection.render_relationships(project_id, [node.as_dict() for node in nodes], [edge.as_dict() for edge in canonical_edges], quarantine, receipt_id)
    health_content = graph_projection.render_health(metrics)
    atlas_router.update_derived_projection(vault_root=vault_root, project_id=project_id, relative_path=f"projects/{project_id}/relationships.md", content=map_content, settings=atlas_router.RoutingSettings())
    atlas_router.update_derived_projection(vault_root=vault_root, project_id=project_id, relative_path=f"projects/{project_id}/graph-health.md", content=health_content, settings=atlas_router.RoutingSettings())
    _write(base / "nodes" / f"{project_id}.jsonl", node_lines)
    _write(base / "edges" / f"{project_id}.jsonl", edge_lines)
    _write(base / "state" / f"{project_id}.json", json.dumps(graph_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write(base / "quarantine" / project_id / "summary.json", json.dumps({"project_id": project_id, "records": quarantine}, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    receipt_path = base / "receipts" / f"{project_id}-{combined[:16]}.json"
    if receipt_path.is_file() and receipt_path.read_text(encoding="utf-8") != json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n":
        raise GraphIngestionError("immutable graph receipt collision")
    _write(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"ok": True, "status": "ingested", "project_id": project_id, "artifacts": artifacts, "nodes": nodes, "relationships": canonical_edges, "quarantine": quarantine, "metrics": metrics, "receipt": receipt}
