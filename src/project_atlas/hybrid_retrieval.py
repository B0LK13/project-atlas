"""AS-2.0-RET-HYBRID-001 — deterministic hybrid retrieval plan + RRF P2.

Builds a read-only retrieval plan over :mod:`project_atlas.retrieval`
(AS-RET-001 lexical exact/prefix) and a P2 Lexical/BM25/RRF fusion surface.
An optional semantic slot exists in the schema but remains **DISABLED by
default**. This package does **not** invent or wire an embeddings service.

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
from project_atlas.retrieval_fusion import bm25_rank, ranking_ids, rrf_fuse
from project_atlas.schema import SchemaValidationError, validate_record

PACKAGE_ID = "AS-2.0-RET-HYBRID-001"
PLAN_KIND = "hybrid_retrieval_plan"
SCHEMA_KIND = "hybrid-retrieval-plan"
SCHEMA_VERSION = 1
RRF_ARTIFACT_KIND = "hybrid-retrieval-rrf"
RRF_SCHEMA_KIND = "hybrid-retrieval-rrf"
RRF_SCHEMA_VERSION = 1
TRUTH_BOUNDARY = "HYBRID PLAN ≠ EMBEDDINGS SERVICE / ≠ AUTHORITY"
SEMANTIC_DISABLED_REASON = "semantic-slot-disabled-by-default-no-embeddings-service"
DEFAULT_CAP = 20
MAX_CAP = 100

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


def _require_query(
    *,
    kind: str,
    value: str,
    mode: RetrievalMode,
    enable_semantic: bool,
) -> tuple[str, str]:
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
    return kind_token, query_value


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
    kind_token, query_value = _require_query(
        kind=kind, value=value, mode=mode, enable_semantic=enable_semantic
    )

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


def build_hybrid_rrf_fusion(
    vault: Path,
    *,
    kind: str,
    value: str,
    mode: RetrievalMode = "exact",
    cap: int = DEFAULT_CAP,
    enable_semantic: bool = False,
    anchor: CompatibilityAnchor | None = None,
) -> dict[str, Any]:
    """Lexical + BM25 fused via RRF (P2). Semantic remains disabled / non-authority.

    Empty / whitespace queries fail closed. Results are derived rankings over
    AS-RET-001 substrates — never Layer B writes and never LLM authority.
    """
    _ = anchor or require_compatibility_anchor()
    kind_token, query_value = _require_query(
        kind=kind, value=value, mode=mode, enable_semantic=enable_semantic
    )
    if not isinstance(cap, int) or isinstance(cap, bool):
        raise HybridRetrievalError(f"hybrid-retrieval-cap-invalid:{cap!r}")
    if cap < 1 or cap > MAX_CAP:
        raise HybridRetrievalError(f"hybrid-retrieval-cap-out-of-range:{cap}")

    use_prefix = mode == "prefix"
    lexical_slot = "lexical_prefix" if use_prefix else "lexical_exact"
    retriever = VaultRetriever(vault)
    lexical_hits = retriever.lookup(kind_token, query_value, prefix=use_prefix)
    lexical_ids = [hit.record_id for hit in lexical_hits]

    corpus = retriever.bm25_corpus(kind_token)
    bm25_scored = bm25_rank(query_value, corpus)
    bm25_ids = ranking_ids(bm25_scored)
    bm25_scores = {record_id: score for record_id, score in bm25_scored}

    fused = rrf_fuse({lexical_slot: lexical_ids, "bm25": bm25_ids})
    truncated = len(fused) > cap
    fused = fused[:cap]

    results: list[dict[str, Any]] = []
    for record_id, rrf_score, ranks in fused:
        results.append(
            {
                "record_type": kind_token,
                "record_id": record_id,
                "rrf_score": rrf_score,
                "ranks": ranks,
                "bm25_score": bm25_scores.get(record_id),
                "authority_level": "derived",
            }
        )

    report: dict[str, Any] = {
        "schema_version": RRF_SCHEMA_VERSION,
        "package_id": PACKAGE_ID,
        "compat_snapshot_id": SNAPSHOT_ID,
        "artifact_kind": RRF_ARTIFACT_KIND,
        "query": {
            "kind": kind_token,
            "value": query_value,
            "mode": mode,
            "cap": cap,
        },
        "slots": {
            "lexical_exact": {
                "enabled": not use_prefix,
                "status": "active" if not use_prefix else "idle",
                "hit_count": 0 if use_prefix else len(lexical_ids),
            },
            "lexical_prefix": {
                "enabled": use_prefix,
                "status": "active" if use_prefix else "idle",
                "hit_count": len(lexical_ids) if use_prefix else 0,
            },
            "bm25": {
                "enabled": True,
                "status": "active",
                "hit_count": len(bm25_ids),
            },
            "semantic": _semantic_slot(),
        },
        "fusion": {
            "method": "rrf",
            "k": 60,
            "lists": [lexical_slot, "bm25"],
        },
        "results": results,
        "result_count": len(results),
        "truncated": truncated,
        "semantic_enabled": False,
        "authority": {
            "level": "derived",
            "llm_authority": False,
            "note": (
                "Lexical/BM25/RRF fusion over AS-RET-001; semantic disabled; "
                "≠ embeddings authority"
            ),
        },
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
    try:
        validate_record(report, RRF_SCHEMA_KIND)
    except SchemaValidationError as exc:
        raise HybridRetrievalError(f"hybrid-retrieval-rrf-schema:{exc}") from exc
    return report


def plan_to_json(plan: dict[str, Any]) -> str:
    """Serialize a hybrid plan deterministically (NFR-001 — no wall-clock)."""
    validate_record(plan, SCHEMA_KIND)
    return json.dumps(plan, indent=2, sort_keys=True) + "\n"


def fusion_to_json(report: dict[str, Any]) -> str:
    """Serialize an RRF fusion report deterministically (NFR-001)."""
    validate_record(report, RRF_SCHEMA_KIND)
    return json.dumps(report, indent=2, sort_keys=True) + "\n"
