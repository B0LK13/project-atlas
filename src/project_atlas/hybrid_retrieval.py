"""AS-2.0-RET-HYBRID-001 — deterministic hybrid retrieval plan harness.

Builds a read-only retrieval plan over :mod:`project_atlas.retrieval`
(AS-RET-001 lexical exact/prefix). An optional semantic slot exists in the
schema but remains **DISABLED by default**. This package does **not** invent
or wire an embeddings service.

Bound to the Atlas 1.0 compatibility anchor. Never mutates the vault.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from project_atlas.compat_anchor import (
    SNAPSHOT_ID,
    CompatibilityAnchor,
    require_compatibility_anchor,
)
from project_atlas.retrieval import VaultRetriever
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-RET-HYBRID-001"
PLAN_KIND = "hybrid_retrieval_plan"
SCHEMA_KIND = "hybrid-retrieval-plan"
SCHEMA_VERSION = 1
TRUTH_BOUNDARY = "HYBRID PLAN ≠ EMBEDDINGS SERVICE / ≠ AUTHORITY"
SEMANTIC_DISABLED_REASON = "semantic-slot-disabled-by-default-no-embeddings-service"

RetrievalMode = Literal["exact", "prefix"]
SUPPORTED_KINDS = frozenset(
    {"source", "claim", "concept", "conflict", "authority", "provenance"}
)


class HybridRetrievalError(ValueError):
    """Fail-closed hybrid retrieval plan error."""


def _semantic_slot() -> dict[str, Any]:
    return {
        "enabled": False,
        "status": "disabled",
        "reason": SEMANTIC_DISABLED_REASON,
    }


def build_hybrid_retrieval_plan(
    vault: Path,
    *,
    kind: str,
    value: str,
    mode: RetrievalMode = "exact",
    enable_semantic: bool = False,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Build a deterministic hybrid retrieval plan without writing the vault.

    Lexical exact/prefix slots execute via :class:`VaultRetriever`. The
    semantic slot stays disabled; requesting it is rejected (no embeddings
    service in this package).
    """
    _ = anchor or require_compatibility_anchor()

    if enable_semantic:
        raise HybridRetrievalError(
            "semantic-slot-not-available:"
            "embeddings-service-not-invented-in-AS-2.0-RET-HYBRID-001"
        )

    kind_token = kind.strip()
    if kind_token not in SUPPORTED_KINDS:
        raise HybridRetrievalError(f"hybrid-retrieval-kind-unsupported:{kind_token}")

    query_value = value.strip()
    if not query_value:
        raise HybridRetrievalError("hybrid-retrieval-value-empty")

    if mode not in ("exact", "prefix"):
        raise HybridRetrievalError(f"hybrid-retrieval-mode-invalid:{mode}")

    use_prefix = mode == "prefix"
    retriever = VaultRetriever(vault)
    hits = retriever.lookup(kind_token, query_value, prefix=use_prefix)
    slot_name = "lexical_prefix" if use_prefix else "lexical_exact"

    results = [
        {
            "record_type": hit.record_type,
            "record_id": hit.record_id,
            "slot": slot_name,
        }
        for hit in hits
    ]

    plan: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "plan_kind": PLAN_KIND,
        "query": {
            "kind": kind_token,
            "value": query_value,
            "mode": mode,
        },
        "slots": {
            "lexical_exact": {
                "enabled": not use_prefix,
                "status": "active" if not use_prefix else "idle",
            },
            "lexical_prefix": {
                "enabled": use_prefix,
                "status": "active" if use_prefix else "idle",
            },
            "semantic": _semantic_slot(),
        },
        "results": results,
        "semantic_enabled": False,
        "authority": {
            "level": "derived",
            "note": "Hybrid plan consumes AS-RET-001 lexical indexes; semantic slot disabled",
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(plan, SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise HybridRetrievalError(f"hybrid-retrieval-plan-schema:{exc}") from exc
    return plan


def plan_to_json(plan: dict[str, Any]) -> str:
    """Serialize a hybrid plan deterministically (NFR-001 — no wall-clock)."""
    validate_record(plan, SCHEMA_KIND)
    return json.dumps(plan, indent=2, sort_keys=True) + "\n"
