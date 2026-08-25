"""AT3-044 — Memory freshness / invalidation."""

from __future__ import annotations

import re
from typing import Any

_PG = re.compile(r"postgresql?\s*(\d+)", re.I)


def classify_freshness(
    item: dict[str, Any],
    *,
    stronger_evidence: list[dict[str, Any]] | None = None,
) -> str:
    """Compare conversational memory to stronger project evidence when present."""
    text = str(item.get("text") or "")
    evidence = stronger_evidence or []
    claim_match = _PG.search(text)
    if not claim_match:
        if any(row.get("invalidates") for row in evidence):
            return "STALE"
        return "CURRENT" if not evidence else "UNKNOWN"
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
    out: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        row["freshness"] = classify_freshness(row, stronger_evidence=stronger_evidence)
        out.append(row)
    return out
