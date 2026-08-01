"""Explainable categorical confidence for Graphify records."""

from __future__ import annotations


def relationship_confidence(*, source_resolved: bool, target_resolved: bool, source_links: int, graphify_confidence: str | None = None, conflicting: bool = False) -> str:
    if conflicting or not source_resolved or not target_resolved:
        return "unknown"
    if source_links and graphify_confidence in {"high", "1", "1.0"}:
        return "high"
    if source_links:
        return "medium"
    return "low"
