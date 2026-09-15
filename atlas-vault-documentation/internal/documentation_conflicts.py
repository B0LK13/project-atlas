"""Conservative metadata conflict detection."""

from __future__ import annotations

import re
from typing import Any


def detect(inventory: dict[str, Any], project_root: str) -> list[dict[str, Any]]:
    statuses: dict[str, list[dict[str, str]]] = {}
    for item in inventory.get("documents", []):
        if item.get("processing", {}).get("eligibility") != "eligible":
            continue
        path = __import__("pathlib").Path(project_root) / str(item["relative_path"])
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for match in re.finditer(r"(?im)^\s*(?:status|project_status)\s*:\s*['\"]?([a-z][a-z -]+)", text):
            statuses.setdefault(match.group(1).strip().lower(), []).append({"document_id": str(item["document_id"]), "claim": f"status={match.group(1).strip().lower()}"})
    if len(statuses) <= 1:
        return []
    records = [record for values in statuses.values() for record in values]
    likely = max(statuses.items(), key=lambda pair: len(pair[1]))[0]
    return [{
        "conflict_id": f"AC-{inventory['project_id']}-0001", "project_id": inventory["project_id"],
        "type": "status-conflict", "severity": "medium", "records": records,
        "assessment": {"likely_current": likely, "basis": ["evidence-backed-metadata"], "automatic_resolution": False},
    }]
