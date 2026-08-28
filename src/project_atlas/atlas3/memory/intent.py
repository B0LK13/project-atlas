"""AT3-043 — Conversation decision + intent extraction.

Fail-closed owner_origin. Intent is never collapsed into current state.
LLM/assistant claims are not owner decisions. Isolated Atlas 3 memory
plane only — never writes Truth Core / Layer B.

Honesty:
- INTENT != CURRENT STATE
- MODEL != OWNER
- CONFIRMED OWNER DECISION requires owner_origin
- MEMORY != TRUTH CORE
- MERGE_AUTHORIZATION = NOT_GRANTED
"""

from __future__ import annotations

from typing import Any, Final, Literal

from project_atlas.atlas3.contracts import Atlas3Error

PACKAGE_ID: Final[str] = "AT3-043"
GENERATOR_ID: Final[str] = "atlas3-intent-043"
TRUTH_BOUNDARY: Final[str] = (
    "INTENT != CURRENT STATE / MODEL != OWNER / "
    "CONFIRMED OWNER DECISION REQUIRES OWNER_ORIGIN / "
    "MEMORY != TRUTH CORE / MERGE_AUTHORIZATION = NOT_GRANTED"
)

Layer = Literal["intent", "decision", "current_state", "history", "unknown"]

_INTENT_TYPES = frozenset({"proposed_decision", "next_step", "idea", "action_item"})
_DECISION_TYPES = frozenset({"confirmed_owner_decision"})
_HISTORY_TYPES = frozenset({"failed_approach", "lesson_learned", "session_note"})
_STATE_TYPES = frozenset({"claim_candidate", "constraint", "observation", "research_finding"})


def _valid_owner_origin(origin: dict[str, Any] | None) -> bool:
    if not isinstance(origin, dict):
        return False
    return (
        origin.get("evidence_kind") == "explicit_owner_statement"
        and str(origin.get("origin") or "").lower() == "owner"
        and bool(str(origin.get("statement") or "").strip())
    )


def _item_origin(item: dict[str, Any], fallback: dict[str, Any] | None) -> dict[str, Any] | None:
    raw = item.get("owner_origin")
    if isinstance(raw, dict):
        return raw
    return fallback


def _layer_for(item_type: str) -> Layer:
    if item_type in _DECISION_TYPES:
        return "decision"
    if item_type in _INTENT_TYPES:
        return "intent"
    if item_type in _HISTORY_TYPES:
        return "history"
    if item_type in _STATE_TYPES:
        return "current_state"
    if item_type == "open_question":
        return "unknown"
    return "unknown"


def extract_intent_report(
    items: list[dict[str, Any]],
    *,
    requested_project_id: str,
    owner_origin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Separate intent / decision / current-state. Never writes."""
    pid = requested_project_id.strip()
    if not pid:
        raise Atlas3Error("PROJECT_REQUIRED", "requested_project_id is required")

    layers: dict[str, list[dict[str, Any]]] = {
        "intent": [],
        "decision": [],
        "current_state": [],
        "history": [],
        "unknown": [],
    }
    for raw in items:
        if not isinstance(raw, dict):
            raise Atlas3Error("INTENT_ITEM_INVALID", "memory item is not an object")
        item_project = str(raw.get("project_id") or "").strip()
        if item_project != pid:
            raise Atlas3Error(
                "CROSS_PROJECT",
                f"REQUESTED_PROJECT_ID={pid} ITEM_PROJECT_ID={item_project or 'missing'}",
            )
        item_type = str(raw.get("item_type") or "").strip()
        if item_type == "confirmed_owner_decision":
            origin = _item_origin(raw, owner_origin)
            if not _valid_owner_origin(origin):
                raise Atlas3Error(
                    "FALSE_OWNER_DECISION",
                    "confirmed_owner_decision requires explicit owner_origin",
                )
        layer = _layer_for(item_type)
        if layer == "current_state" and item_type in _INTENT_TYPES:
            raise Atlas3Error(
                "INTENT_COLLAPSED_TO_STATE",
                "intent item must not be classified as current_state",
            )
        row = {
            "item_type": item_type,
            "layer": layer,
            "project_id": pid,
            "text": raw.get("text"),
            "authority": "NON_CANONICAL",
            "promoted_to_truth_core": False,
        }
        if item_type == "confirmed_owner_decision":
            row["owner_origin"] = {
                "evidence_kind": "explicit_owner_statement",
                "origin": "owner",
            }
        layers[layer].append(row)

    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "generated": {"by": GENERATOR_ID},
        "project_id": pid,
        "truth_boundary": TRUTH_BOUNDARY,
        "counts": {name: len(rows) for name, rows in layers.items()},
        "layers": layers,
        "honesty": {
            "intent_is_current_state": False,
            "model_is_owner": False,
            "memory_is_truth_core": False,
            "promoted_to_truth_core": False,
            "write_applied": False,
            "MERGE_AUTHORIZATION": "NOT_GRANTED",
            "unknown_stays_unknown": True,
        },
    }
