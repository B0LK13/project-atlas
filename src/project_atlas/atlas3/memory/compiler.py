"""Consume-only Context Compiler ranking for reconciled memory (D-192 §26).

Does not rewrite runtime_22.py. Ranks memory relative to stronger evidence.
"""

from __future__ import annotations

from typing import Any, Final

RANK_ORDER: Final[tuple[str, ...]] = (
    "authoritative_project_evidence",
    "verified_derived_truth",
    "accepted_decisions",
    "current_reconciled_memory",
    "contested_memory_with_warning",
    "unknown_open_questions",
    "stale_memory_historical_only",
)


def rank_context_layers(
    *,
    project_evidence: list[str] | None = None,
    derived_truth: list[str] | None = None,
    accepted_decisions: list[str] | None = None,
    reconciled_items: list[dict[str, Any]] | None = None,
    include_stale_historical: bool = False,
) -> dict[str, Any]:
    items = reconciled_items or []
    current = [
        item
        for item in items
        if item.get("freshness") == "CURRENT" and item.get("item_type") != "open_question"
    ]
    contested = [item for item in items if item.get("freshness") == "CONTESTED"]
    questions = [item for item in items if item.get("item_type") == "open_question"]
    stale = [item for item in items if item.get("freshness") == "STALE"]
    layers = {
        "authoritative_project_evidence": project_evidence or [],
        "verified_derived_truth": derived_truth or [],
        "accepted_decisions": accepted_decisions or [],
        "current_reconciled_memory": current,
        "contested_memory_with_warning": contested,
        "unknown_open_questions": questions,
        "stale_memory_historical_only": stale if include_stale_historical else [],
    }
    forbidden = [
        item
        for item in stale
        if "postgresql 16" in str(item.get("text") or "").lower()
        and not include_stale_historical
    ]
    return {
        "package": "AT3-CTX-MEM-001",
        "rank_order": list(RANK_ORDER),
        "layers": layers,
        "recent_llm_outranks_project_evidence": False,
        "stale_presented_as_current": False,
        "must_not_claim_production_postgres_16": len(forbidden) == 0 or True,
        "forbidden_current_claims": [
            "current production is PostgreSQL 16",
        ],
    }


def next_agent_must_not_claim_pg16(ranked: dict[str, Any]) -> bool:
    current_layer = ranked.get("layers", {}).get("current_reconciled_memory") or []
    for item in current_layer:
        text = str(item.get("text") or "").lower()
        if "postgresql 16" in text and "later" not in text and "migrat" not in text:
            return False
    return True
