"""Evidence-backed documentation coverage assessment."""

from __future__ import annotations

from typing import Any

CATEGORIES = (
    "project-overview", "requirements", "architecture", "decisions", "roadmap",
    "implementation-plan", "work-tracking", "validation", "testing", "security",
    "deployment", "operations", "maintenance", "agent-guidance",
)


def assess(inventory: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for category in CATEGORIES:
        matches = [item for item in inventory.get("documents", []) if item.get("classification", {}).get("type") == category]
        eligible = [item for item in matches if item.get("processing", {}).get("eligibility") == "eligible"]
        if not matches:
            status = "missing"
        elif not eligible:
            status = "unverified"
        elif any(item.get("authority", {}).get("level") == "primary" for item in eligible):
            status = "complete"
        else:
            status = "partial"
        results[category] = {
            "status": status,
            "evidence": [item["document_id"] for item in matches],
            "authority": sorted({item.get("authority", {}).get("level", "unknown") for item in matches}),
            "warnings": [] if status in ("complete", "not-applicable") else [f"coverage-{status}"],
            "rule": "classification-and-authority-v1",
        }
    counts = {status: sum(1 for result in results.values() if result["status"] == status) for status in ("complete", "partial", "missing", "stale", "conflicting", "unverified", "not-applicable")}
    return {"schema_version": 1, "categories": results, "counts": counts}
