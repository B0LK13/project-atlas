"""AT3-044 — Memory freshness / invalidation."""

from __future__ import annotations

import re
from typing import Any, Final

from project_atlas.atlas3.contracts import Atlas3Error

PACKAGE_ID: Final[str] = "AT3-044"
_PG = re.compile(r"postgresql?\s*(\d+)", re.I)
FRESHNESS_STATES: Final[frozenset[str]] = frozenset(
    {"CURRENT", "STALE", "CONTESTED", "UNKNOWN"}
)


def freshness_capability() -> dict[str, Any]:
    return {
        "package": PACKAGE_ID,
        "stale_is_not_current": True,
        "unknown_stays_unknown": True,
        "historical_memory_is_not_current_truth": True,
        "auto_promote_to_truth_core": False,
    }


def classify_freshness(
    item: dict[str, Any],
    *,
    stronger_evidence: list[dict[str, Any]] | None = None,
) -> str:
    """Compare conversational memory to stronger project evidence when present."""
    if not isinstance(item, dict):
        raise Atlas3Error("FRESHNESS_INVALID", "item is not an object")
    text = str(item.get("text") or "")
    evidence = stronger_evidence or []
    if not isinstance(evidence, list):
        raise Atlas3Error("FRESHNESS_INVALID", "stronger_evidence must be a list")
    for row in evidence:
        if not isinstance(row, dict):
            raise Atlas3Error("FRESHNESS_INVALID", "evidence row is not an object")
    claim_match = _PG.search(text)
    if not claim_match:
        if any(row.get("invalidates") for row in evidence):
            return "STALE"
        return "UNKNOWN"
    claimed = claim_match.group(1)
    current_state = None
    for row in evidence:
        if row.get("kind") in {"deployment", "repository", "config", "current_state"}:
            found = _PG.search(str(row.get("text") or ""))
            if found:
                current_state = found.group(1)
    if current_state and current_state != claimed:
        return "STALE"
    if current_state and current_state == claimed:
        return "CURRENT"
    if any(row.get("contested") for row in evidence):
        return "CONTESTED"
    return "UNKNOWN"


def apply_freshness(
    items: list[dict[str, Any]],
    *,
    stronger_evidence: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise Atlas3Error("FRESHNESS_INVALID", "items must be a list")
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise Atlas3Error("FRESHNESS_INVALID", "item is not an object")
        row = dict(item)
        row["freshness"] = classify_freshness(row, stronger_evidence=stronger_evidence)
        if row["freshness"] not in FRESHNESS_STATES:
            raise Atlas3Error("FRESHNESS_INVALID", row["freshness"])
        out.append(row)
    return out
