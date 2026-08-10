"""AS-2.1 Ask Atlas live path - read-only query over AppService.

UI != canonical. Graph != authority. Never writes Layer B.
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
    q_lower = q.lower()
    matched_projects = [
        p
        for p in projects
        if q_lower in str(p.get("project_id", "")).lower()
        or q_lower in str(p.get("path", "")).lower()
    ]
    matched_knowledge = [
        k
        for k in knowledge
        if q_lower in str(k.get("subject") or "").lower()
        or q_lower in str(k.get("answer_id") or "").lower()
    ]
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
        },
        "health": svc.health()["vault_health"],
        "operator_id": op.operator_id,
        "truth_boundary": TRUTH_BOUNDARY,
        "generated": {"by": "project-atlas"},
    }
