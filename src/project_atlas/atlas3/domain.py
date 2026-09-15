"""AT3-002 — Digital twin domain vocabulary.

Derived aliases over landed graph + Truth Core types. Graph ≠ authority.
"""

from __future__ import annotations

from typing import Final

from project_atlas.atlas3.contracts import TRUTH_BOUNDARY

PACKAGE_ID: Final[str] = "AT3-002"
AUTHORITY: Final[str] = "derived"

TWIN_NODES: Final[frozenset[str]] = frozenset(
    {
        "project",
        "repository",
        "component",
        "service",
        "file",
        "symbol",
        "claim",
        "decision",
        "requirement",
        "task",
        "agent",
        "pr",
        "commit",
        "test",
        "build",
        "deployment",
        "incident",
        "artifact",
        "environment",
    }
)

TWIN_RELATIONSHIPS: Final[frozenset[str]] = frozenset(
    {
        "CONTAINS",
        "IMPLEMENTS",
        "DEPENDS_ON",
        "CLAIMS",
        "CONTRADICTS",
        "SUPERSEDES",
        "VALIDATES",
        "INVALIDATES",
        "CAUSED_BY",
        "DECIDED_BY",
        "DEPLOYED_AS",
        "OBSERVED_IN",
        "OWNED_BY",
        "DERIVED_FROM",
        "BLOCKS",
    }
)

GRAPH_REUSE: Final[dict[str, str]] = {
    "CONTAINS": "part-of",
    "DEPENDS_ON": "depends-on",
    "SUPERSEDES": "supersedes",
    "VALIDATES": "validates",
    "CONTRADICTS": "conflicts-with",
    "DERIVED_FROM": "derived-from",
}

TEMPORAL_FIELDS: Final[tuple[str, ...]] = (
    "VALID_FROM",
    "VALID_TO",
    "OBSERVED_AT",
    "RECORDED_AT",
)


def domain_catalog() -> dict[str, object]:
    return {
        "package": PACKAGE_ID,
        "authority": AUTHORITY,
        "truth_boundary": TRUTH_BOUNDARY,
        "nodes": sorted(TWIN_NODES),
        "relationships": sorted(TWIN_RELATIONSHIPS),
        "graph_reuse": dict(sorted(GRAPH_REUSE.items())),
        "temporal_fields": list(TEMPORAL_FIELDS),
        "temporal_engine": "AS-2.0-TEMPORAL-001",
        "second_temporal_engine": False,
        "graph_is_authority": False,
        "reused_components": [
            "project_atlas.graph_relationships.MVP_RELATIONSHIP_TYPES",
            "project_atlas.bitemporal",
            "project_atlas.domain.claims",
        ],
        "new_components": [
            "symbol node",
            "INVALIDATES",
            "CAUSED_BY",
            "DECIDED_BY",
            "DEPLOYED_AS",
            "OBSERVED_IN",
            "OWNED_BY",
            "BLOCKS",
        ],
        "migration_required": False,
        "compatibility_risk": "LOW",
    }
