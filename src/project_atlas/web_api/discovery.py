"""Read-only estate discovery projection for the web shell (D-049 / Lane G).

Exposes categorized discovery results. Never invents estate rows and never
ingests. UI categories answer: "What did Atlas find that I should care about?"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.estate_discovery import REPORT_RELATIVE

PACKAGE_ID = "AS-CODER-ALPHA-KNOWLEDGE-ESTATE-DISCOVERY-001"
TRUTH_BOUNDARY = "DISCOVER != INGEST != TRUST != AUTHORITY / UI != AUTHORITY"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def load_estate_discovery_view(vault: Path) -> dict[str, Any]:
    """Return the latest estate discovery report projection for Web.

    Missing report → honest empty categories (not invented pilot roots).
    """
    report = _read_json(vault / REPORT_RELATIVE)
    empty_categories: dict[str, list[Any]] = {
        "DISCOVERED_PROJECTS": [],
        "NEW_KNOWLEDGE": [],
        "AMBIGUOUS_MATCHES": [],
        "UNMATCHED_KNOWLEDGE": [],
        "IGNORED": [],
        "CONNECTED": [],
    }
    if report is None:
        return {
            "package_id": PACKAGE_ID,
            "truth_boundary": TRUTH_BOUNDARY,
            "present": False,
            "authorized_root": None,
            "counts": {
                "projects": 0,
                "knowledge": 0,
                "ignored": 0,
                "required_review": 0,
            },
            "categories": empty_categories,
            "primary_question": "What did Atlas find that I should care about?",
            "note": (
                "No estate-discovery-report.json yet. Run: "
                "atlas discover --root <authorized-root> --vault <vault>"
            ),
        }

    categories_raw = report.get("categories")
    categories: dict[str, Any] = (
        categories_raw if isinstance(categories_raw, dict) else empty_categories
    )
    merged = {key: list(categories.get(key) or []) for key in empty_categories}
    counts_raw = report.get("counts")
    counts: dict[str, Any] = counts_raw if isinstance(counts_raw, dict) else {}
    return {
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "present": True,
        "authorized_root": report.get("authorized_root"),
        "counts": {
            "projects": int(counts.get("projects") or 0),
            "knowledge": int(counts.get("knowledge") or 0),
            "ignored": int(counts.get("ignored") or 0),
            "required_review": int(counts.get("required_review") or 0),
        },
        "categories": merged,
        "primary_question": "What did Atlas find that I should care about?",
        "invariant": report.get("invariant", TRUTH_BOUNDARY),
        "security": report.get("security"),
    }
