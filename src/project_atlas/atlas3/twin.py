"""AT3-002 — Project twin node/relationship constructors.

Derived only. Every relationship requires provenance. Graph ≠ authority.
Does not write Truth Core.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import Atlas3Error, honesty_block, safe_project_id
from project_atlas.atlas3.domain import TWIN_NODES, TWIN_RELATIONSHIPS

PACKAGE_ID: Final[str] = "AT3-002"
NODE_SCHEMA: Final[str] = "atlas3.twin-node.v1"
REL_SCHEMA: Final[str] = "atlas3.twin-relationship.v1"


def make_node(
    *,
    node_type: str,
    node_id: str,
    project_id: str,
    evidence_refs: list[str],
    valid_from: str | None = None,
    valid_to: str | None = None,
    observed_at: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    ntype = node_type.strip().lower()
    if ntype not in TWIN_NODES:
        raise Atlas3Error("UNKNOWN_TWIN_NODE", f"unsupported node type {node_type!r}")
    refs = [item.strip() for item in evidence_refs if item.strip()]
    if not refs:
        raise Atlas3Error("PROVENANCE_REQUIRED", "twin nodes require evidence_refs")
    return {
        "schema": NODE_SCHEMA,
        "schema_version": 1,
        "package": PACKAGE_ID,
        "node_type": ntype,
        "node_id": node_id.strip(),
        "project_id": safe_project_id(project_id),
        "evidence_refs": refs,
        "authority": "derived",
        "temporal": {
            "VALID_FROM": valid_from,
            "VALID_TO": valid_to,
            "OBSERVED_AT": observed_at,
            "RECORDED_AT": recorded_at,
        },
        "second_temporal_engine": False,
        "honesty": honesty_block(),
    }


def make_relationship(
    *,
    relationship: str,
    from_id: str,
    to_id: str,
    project_id: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    rel = relationship.strip().upper()
    if rel not in TWIN_RELATIONSHIPS:
        raise Atlas3Error("UNKNOWN_TWIN_RELATIONSHIP", f"unsupported relationship {relationship!r}")
    refs = [item.strip() for item in evidence_refs if item.strip()]
    if not refs:
        raise Atlas3Error(
            "PROVENANCE_REQUIRED",
            "every derived twin relationship requires provenance",
        )
    return {
        "schema": REL_SCHEMA,
        "schema_version": 1,
        "package": PACKAGE_ID,
        "relationship": rel,
        "from_id": from_id.strip(),
        "to_id": to_id.strip(),
        "project_id": safe_project_id(project_id),
        "evidence_refs": refs,
        "authority": "derived",
        "provenance_required": True,
        "graph_is_authority": False,
        "honesty": honesty_block(),
    }
