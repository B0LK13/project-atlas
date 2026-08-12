"""AS-2.1 Ask Atlas live path - read-only query over AppService.

UI != canonical. Graph != authority. Never writes Layer B.
Hardened: health keyword + broader project/knowledge field match.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from project_atlas.app_service import open_app_service
from project_atlas.authz import OperatorProfile, default_operator
from project_atlas.compat_anchor import require_compatibility_anchor

PACKAGE_ID = "AS-2.1-ASK-ATLAS-LIVE-001"
TRUTH_BOUNDARY = "ASK ATLAS LIVE != CANONICAL WRITE / UI!=TRUTH / != AUTHORITY"


class AskAtlasLiveError(ValueError):
    """Fail-closed Ask Atlas live error."""


def ask_atlas_live(
    vault: Path,
    *,
    query: str,
    operator: OperatorProfile | None = None,
) -> dict[str, Any]:
    """Answer a read-only Ask Atlas query from live vault projections."""
    require_compatibility_anchor()
    op = operator or default_operator()
    op.require("web.read")
    q = query.strip()
    if not q or len(q) > 256:
        raise AskAtlasLiveError("ask-query-invalid")
    svc = open_app_service(vault)
    projects = svc.projects()
    knowledge = svc.knowledge()
    health = svc.health()
    q_lower = q.lower()
    matched_projects = [
        p
        for p in projects
        if q_lower in str(p.get("project_id", "")).lower()
        or q_lower in str(p.get("path", "")).lower()
        or q_lower in str(p.get("title", "")).lower()
        or q_lower in str(p.get("name", "")).lower()
    ]
    matched_knowledge = [
        k
        for k in knowledge
        if q_lower in str(k.get("subject") or "").lower()
        or q_lower in str(k.get("answer_id") or "").lower()
        or q_lower in str(k.get("field") or "").lower()
        or q_lower in str(k.get("path") or "").lower()
        or q_lower in str(k.get("title") or "").lower()
        or q_lower in str(k.get("summary") or "").lower()
        or q_lower in str(k.get("value_text") or "").lower()
    ]
    vault_health = health.get("vault_health") or {}
    health_hits: list[str] = []
    for token in ("health", "rollup", "status", "ops"):
        if token in q_lower:
            health_hits.append(token)
    if str(vault_health.get("rollup", "")).lower() in q_lower:
        health_hits.append("rollup-value")
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "query": q,
        "live_ask": True,
        "canonical_write": False,
        "ui_truth": False,
        "graph_authority": False,
        "matches": {
            "projects": matched_projects[:50],
            "knowledge": matched_knowledge[:50],
            "health_keywords": sorted(set(health_hits)),
        },
        "health": vault_health,
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
