"""Human-readable derived Graphify projections."""

from __future__ import annotations

from typing import Any


def render_relationships(project_id: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], quarantine: list[dict[str, Any]], receipt_id: str) -> str:
    sections: dict[str, list[dict[str, Any]]] = {"verified": [], "supported": [], "inferred": [], "conflicting": [], "orphaned": []}
    for edge in edges:
        sections.setdefault(str(edge.get("authority", {}).get("verification_state", "inferred")), []).append(edge)
    lines = [f"# Relationships — {project_id}", "", "> Derived projection. Graphify authority is always `derived`.", "", "## Graph ingestion", "", f"- Receipt: `{receipt_id}`", f"- Nodes: {len(nodes)}", f"- Canonical relationships: {len(edges)}", f"- Quarantine records: {len(quarantine)}", ""]
    for name in ("verified", "supported", "inferred", "conflicting", "orphaned"):
        lines.extend([f"## {name.title()} relationships", ""])
        for edge in sorted(sections.get(name, []), key=lambda value: str(value.get("relationship_id", ""))):
            source = edge.get("source_entity", {}).get("atlas_entity_id") or edge.get("source_entity", {}).get("graphify_node_id", "unknown")
            target = edge.get("target_entity", {}).get("atlas_entity_id") or edge.get("target_entity", {}).get("graphify_node_id", "unknown")
            lines.append(f"- `{source}` **{edge.get('relationship_type', 'unknown')}** `{target}` — `{edge.get('relationship_id', 'unknown')}`")
        if not sections.get(name):
            lines.append("- None")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_health(metrics: dict[str, Any]) -> str:
    lines = ["# Graph Health", "", "> Derived metrics; not a subjective quality score.", ""]
    for key in sorted(metrics):
        lines.append(f"- {key}: {metrics[key]}")
    return "\n".join(lines) + "\n"
