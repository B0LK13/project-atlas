"""Human-facing documentation-map projection content."""

from __future__ import annotations

from typing import Any


SECTIONS = {
    "project-overview": "Project overview", "requirements": "Requirements", "architecture": "Architecture",
    "architecture-decision": "Decisions", "roadmap": "Planning and roadmaps", "work-package": "Work packages",
    "implementation-plan": "Implementation records", "validation-report": "Validation and testing",
    "test-report": "Validation and testing", "security": "Security", "threat-model": "Security",
    "deployment": "Deployment and operations", "operations": "Deployment and operations",
    "agent-instruction": "Agent instructions and skills", "skill-definition": "Agent instructions and skills",
    "graphify-output": "Generated and derived artifacts", "unknown": "Unsupported or review-required",
}


def render_map(inventory: dict[str, Any], coverage: dict[str, Any], conflicts: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in inventory.get("documents", []):
        kind = str(item.get("classification", {}).get("type", "unknown"))
        grouped.setdefault(SECTIONS.get(kind, "Other"), []).append(item)
    lines = [f"# Documentation map — {inventory['project_id']}", "", "Generated from the deterministic AS-WP-004 inventory.", ""]
    for section in sorted(grouped):
        lines.extend([f"## {section}", ""])
        for item in sorted(grouped[section], key=lambda value: str(value["relative_path"]).casefold()):
            classification = item.get("classification", {})
            authority = item.get("authority", {})
            processing = item.get("processing", {})
            warning = " ⚠" if processing.get("eligibility") != "eligible" or authority.get("level") == "derived" else ""
            lines.append(f"- **{item['relative_path']}** — {classification.get('type', 'unknown')} / {authority.get('level', 'unknown')} / {processing.get('state', 'unknown')}{warning} (`{item['sha256']}`)")
        lines.append("")
    lines.extend(["## Coverage", "", "| Category | Status | Evidence |", "|---|---|---|"])
    for category, result in sorted(coverage.get("categories", {}).items()):
        lines.append(f"| {category} | {result['status']} | {', '.join(result['evidence']) or 'none'} |")
    lines.extend(["", "## Conflicts", ""])
    if conflicts:
        for conflict in conflicts:
            lines.append(f"- `{conflict['conflict_id']}` — {conflict['type']} ({conflict['severity']}); automatic resolution: no")
    else:
        lines.append("- None detected.")
    return "\n".join(lines) + "\n"
