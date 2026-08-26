"""AT3-054 — Consume-only memory context compiler.

Ranks reconciled memory for later 2.x context-compiler consumption.
Does not rewrite the certified 2.x compiler. Does not write Truth Core.
Stale memory is never current truth. UNKNOWN stays UNKNOWN.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from project_atlas.atlas3.contracts import (
    MERGE_AUTHORIZATION,
    TRUTH_BOUNDARY,
    Atlas3Error,
    honesty_block,
)
from project_atlas.atlas3.memory.compiler import RANK_ORDER, rank_context_layers
from project_atlas.atlas3.memory.routing import assert_items_project_scope

PACKAGE_ID: Final[str] = "AT3-054"
GENERATOR_ID: Final[str] = "atlas3-context-compiler-054"
FRESHNESS_REQUIREMENTS: Final[frozenset[str]] = frozenset(
    {"CURRENT", "ALLOW_STALE_HISTORICAL", "UNKNOWN"}
)
_AUTHORITY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "trust_score",
        "graph_winner",
        "winner",
        "resolved_winner",
    }
)


def context_compiler_capability() -> dict[str, Any]:
    """Honest consume-only capability. Certified 2.x compiler stays untouched."""
    return {
        "package": PACKAGE_ID,
        "consume_only": True,
        "rewrites_certified_compiler": False,
        "certified_compiler_write": False,
        "ask2_replaced": False,
        "writes_truth_core": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "stale_as_current": False,
        "cross_project": False,
        "new_cli_command": True,
        "certified_for_merge": False,
        "merge_authorization": MERGE_AUTHORIZATION,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def _require_item_list(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise Atlas3Error("CONTEXT_INVALID", "items must be a list")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise Atlas3Error("CONTEXT_INVALID", f"item[{index}] must be an object")
        rows.append(item)
    return rows


def _reject_authority_claims(item: dict[str, Any], *, label: str) -> None:
    for key in _AUTHORITY_KEYS:
        if item.get(key) is not None:
            raise Atlas3Error(
                "AUTHORITY_CLAIM_FORBIDDEN",
                f"{label} must not carry {key}",
            )
    if item.get("graph_is_authority") is True:
        raise Atlas3Error("GRAPH_WINNER_FORBIDDEN", f"{label} graph is not authority")
    if item.get("promoted_to_truth_core") not in {None, 0}:
        raise Atlas3Error("TRUTH_CORE_WRITE", f"{label} must not promote to Truth Core")
    if item.get("write_applied") is True:
        raise Atlas3Error("CONTEXT_WRITE_CLAIMED", f"{label} is consume-only")
    if item.get("stale_as_current") is True or item.get("stale_is_current") is True:
        raise Atlas3Error("STALE_AS_CURRENT", f"{label} must not treat stale as current")
    freshness = str(item.get("freshness") or "")
    status = str(item.get("status") or "")
    if freshness == "STALE" and status in {"CURRENT", "current", "verified"}:
        raise Atlas3Error("STALE_AS_CURRENT", f"{label} stale item marked current")


def compile_memory_context(
    items: object,
    *,
    project_id: str,
    project_evidence: list[str] | None = None,
    derived_truth: list[str] | None = None,
    accepted_decisions: list[str] | None = None,
    include_stale_historical: bool = False,
    freshness_requirement: str = "UNKNOWN",
) -> dict[str, Any]:
    """Rank reconciled memory. Never presents stale memory as current truth."""
    freshness = freshness_requirement.strip().upper() or "UNKNOWN"
    if freshness not in FRESHNESS_REQUIREMENTS:
        raise Atlas3Error(
            "UNKNOWN_FRESHNESS_REQUIREMENT",
            f"unsupported freshness requirement {freshness_requirement!r}",
        )
    if freshness == "CURRENT" and include_stale_historical:
        raise Atlas3Error(
            "STALE_AS_CURRENT",
            "CURRENT freshness cannot include stale historical memory",
        )
    rows = _require_item_list(items)
    pid = assert_items_project_scope(rows, project_id=project_id)
    for index, item in enumerate(rows):
        _reject_authority_claims(item, label=f"item[{index}]")
    ranked = rank_context_layers(
        project_evidence=project_evidence,
        derived_truth=derived_truth,
        accepted_decisions=accepted_decisions,
        reconciled_items=rows,
        include_stale_historical=include_stale_historical,
    )
    raw_layers = ranked.get("layers")
    layers: dict[str, Any] = raw_layers if isinstance(raw_layers, dict) else {}
    current = layers.get("current_reconciled_memory") or []
    if not isinstance(current, list):
        raise Atlas3Error("CONTEXT_INVALID", "current layer must be a list")
    for index, item in enumerate(current):
        if not isinstance(item, dict):
            raise Atlas3Error("CONTEXT_INVALID", f"current[{index}] must be an object")
        if str(item.get("freshness") or "") == "STALE":
            raise Atlas3Error("STALE_AS_CURRENT", "stale item leaked into current layer")
        if str(item.get("freshness") or "") == "UNKNOWN" and freshness == "CURRENT":
            raise Atlas3Error(
                "UNKNOWN_AS_CURRENT",
                "UNKNOWN must stay UNKNOWN under CURRENT freshness",
            )
    unknowns = [
        item
        for item in rows
        if isinstance(item, dict)
        and (
            str(item.get("freshness") or "") == "UNKNOWN"
            or item.get("item_type") == "open_question"
        )
    ]
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "freshness_requirement": freshness,
        "rank_order": list(RANK_ORDER),
        "layers": layers,
        "ranked": ranked,
        "unknown_count": len(unknowns),
        "unknown_stays_unknown": True,
        "stale_presented_as_current": False,
        "recent_llm_outranks_project_evidence": False,
        "consume_only": True,
        "rewrites_certified_compiler": False,
        "ask2_replaced": False,
        "promoted_to_truth_core": 0,
        "write_applied": False,
        "certified_for_merge": False,
        "merge_authorization": MERGE_AUTHORIZATION,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }


def load_item_list(source: Path) -> list[dict[str, Any]]:
    """Read a JSON item list. Mixed valid+corrupt fails closed."""
    if not source.is_file():
        raise Atlas3Error("CONTEXT_NOT_FOUND", f"item list not found: {source}")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Atlas3Error("CONTEXT_INVALID", "item list is not readable JSON") from exc
    return _require_item_list(payload)

