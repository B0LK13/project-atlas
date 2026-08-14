"""Read-only estate discovery projection for the web shell (D-049 / Lane G).

Exposes categorized discovery results. Never invents estate rows and never
ingests. UI categories answer: "What did Atlas find that I should care about?"
No UI-side matching — projects the same report semantics as CLI/API.
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
            "authorized_root_mode": None,
            "volume_root_authorized": False,
            "volume_root_kind": "NONE",
            "counts": {
                "projects": 0,
                "knowledge": 0,
                "ignored": 0,
                "required_review": 0,
                "connected": 0,
            },
            "scan": {
                "scan_complete": False,
                "truncation_reason": "report_absent",
                "truncation_causes": ["report_absent"],
                "depth_limit_reached": False,
                "max_depth": None,
                "project_limit_reached": False,
                "knowledge_limit_reached": False,
                "permission_errors": [],
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
    scan_raw = report.get("scan")
    scan: dict[str, Any] = scan_raw if isinstance(scan_raw, dict) else {}
    return {
        "package_id": PACKAGE_ID,
        "truth_boundary": TRUTH_BOUNDARY,
        "present": True,
        "authorized_root": report.get("authorized_root"),
        "authorized_root_mode": report.get("authorized_root_mode"),
        "volume_root_authorized": bool(report.get("volume_root_authorized", False)),
        "volume_root_kind": report.get("volume_root_kind") or "NONE",
        "counts": {
            "projects": int(counts.get("projects") or 0),
            "knowledge": int(counts.get("knowledge") or 0),
            "ignored": int(counts.get("ignored") or 0),
            "required_review": int(counts.get("required_review") or 0),
            "connected": int(counts.get("connected") or 0),
        },
        "scan": {
            "scan_complete": bool(scan.get("scan_complete", True)),
            "truncation_reason": scan.get("truncation_reason"),
            "truncation_causes": list(scan.get("truncation_causes") or []),
            "depth_limit_reached": bool(scan.get("depth_limit_reached", False)),
            "max_depth": scan.get("max_depth"),
            "project_limit_reached": bool(scan.get("project_limit_reached", False)),
            "knowledge_limit_reached": bool(
                scan.get("knowledge_limit_reached", False)
            ),
            "permission_errors": list(scan.get("permission_errors") or []),
            "candidate_selection_policy": scan.get("candidate_selection_policy"),
            "project_candidates_seen": scan.get("project_candidates_seen"),
            "project_candidates_emitted": scan.get("project_candidates_emitted"),
            "project_candidates_suppressed": scan.get(
                "project_candidates_suppressed"
            ),
            "knowledge_candidates_seen": scan.get("knowledge_candidates_seen"),
            "knowledge_candidates_emitted": scan.get("knowledge_candidates_emitted"),
            "knowledge_candidates_suppressed": scan.get(
                "knowledge_candidates_suppressed"
            ),
        },
        "categories": merged,
        "primary_question": "What did Atlas find that I should care about?",
        "invariant": report.get("invariant", TRUTH_BOUNDARY),
        "security": report.get("security"),
        "discovery_identity_source_of_truth": report.get(
            "discovery_identity_source_of_truth"
        ),
    }
