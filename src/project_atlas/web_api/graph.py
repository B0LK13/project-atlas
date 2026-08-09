"""Read-only impact-graph consume for the web shell (AS-WEB-ACCEPT).

Reads ``generated/indexes/impact-graph.json`` when present. Missing → None
(unknown graph, never fabricated edges). Graph ≠ authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

IMPACT_GRAPH_RELATIVE = Path("generated") / "indexes" / "impact-graph.json"


def read_impact_graph(vault: Path) -> dict[str, Any] | None:
    """Return the impact-graph JSON object, or None when absent/unreadable."""
    path = vault / IMPACT_GRAPH_RELATIVE
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    # Defence: never elevate authority markers if a bad file sneaks in.
    if raw.get("authority_plane") not in (None, "none", "derived"):
        return None
    return raw


def impact_graph_summary(vault: Path) -> dict[str, Any]:
    """UI-facing summary — always declares Graph≠authority."""
    graph = read_impact_graph(vault)
    if graph is None:
        return {
            "available": False,
            "node_count": 0,
            "edge_count": 0,
            "graph_authority": False,
            "note": "IMPACT GRAPH ABSENT → UNKNOWN (not authority)",
        }
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    return {
        "available": True,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "graph_authority": False,
        "note": str(graph.get("note") or "IMPACT GRAPH ≠ AUTOMATIC AUTHORITY"),
        "truth_boundary": str(graph.get("truth_boundary") or "Graph≠authority"),
    }
