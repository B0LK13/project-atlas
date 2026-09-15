"""Pure OKF v0.2 rendering for canonical concept records."""

from __future__ import annotations

from typing import Any

import yaml

from project_atlas.domain.concepts import ConceptRecord


def _relationship_map(concept: ConceptRecord) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for relationship in concept.relationships:
        result.setdefault(relationship.type.value, []).append(relationship.target)
    return {key: sorted(values) for key, values in sorted(result.items())}


def okf_frontmatter(concept: ConceptRecord, resource: str) -> dict[str, Any]:
    """Build deterministic OKF frontmatter without performing I/O."""
    lifecycle = (
        concept.lifecycle.model_dump(mode="json")
        if concept.lifecycle
        else {
            "status": concept.status.value,
            "phase": concept.phase,
            "started": concept.started.isoformat() if concept.started else None,
        }
    )
    generated = (
        concept.generated.model_dump(mode="json")
        if concept.generated
        else {"by": concept.generated_by or "agent:project-atlas", "at": None}
    )
    verified = (
        concept.verified.model_dump(mode="json")
        if concept.verified
        else {"by": None, "at": None}
    )
    portfolio = (
        concept.portfolio.model_dump(mode="json")
        if concept.portfolio
        else {"domain": None, "strategic_role": None, "priority": None}
    )
    return {
        "schema_version": concept.schema_version,
        "concept_id": concept.concept_id,
        "type": concept.type.value,
        "title": concept.title,
        "description": concept.description or "",
        "resource": resource,
        "tags": sorted(concept.tags),
        "project_id": concept.project_id,
        "aliases": sorted(concept.aliases),
        "portfolio": portfolio,
        "lifecycle": lifecycle,
        "knowledge_state": concept.knowledge_state.value,
        "review_state": concept.review_state.value,
        "maturity": concept.maturity.value if concept.maturity else None,
        "generated": generated,
        "verified": verified,
        "stale_after": concept.stale_after.isoformat() if concept.stale_after else None,
        "sources": [source.model_dump(mode="json") for source in concept.sources],
        "relationships": _relationship_map(concept),
    }


def render_concept_note(concept: ConceptRecord, resource: str) -> str:
    """Render one deterministic Markdown + YAML OKF concept note."""
    frontmatter = yaml.safe_dump(
        okf_frontmatter(concept, resource),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip()
    return "\n".join(
        [
            "---",
            frontmatter,
            "---",
            "",
            "<!-- atlas:generated:start -->",
            f"# {concept.title}",
            "",
            concept.description or "_No description._",
            "",
            f"Knowledge state: `{concept.knowledge_state.value}`",
            "",
            "<!-- atlas:generated:end -->",
            "",
        ]
    )
