"""AT3-013 — PR / commit / test / build nodes from the Atlas 3 ledger.

Derived twin nodes only. Does not invent git history. Graph != authority.
Does not write Truth Core. Reuses AT3-014 list_events integrity.
"""

from __future__ import annotations

from typing import Any, Final

from project_atlas.atlas3.contracts import (
    TRUTH_BOUNDARY,
    honesty_block,
    require_project,
    require_vault,
)
from project_atlas.atlas3.ledger import list_events
from project_atlas.atlas3.twin import make_node

PACKAGE_ID: Final[str] = "AT3-013"
EVENT_TO_NODE: Final[dict[str, str]] = {
    "COMMIT_CREATED": "commit",
    "PR_OPENED": "pr",
    "PR_REVIEWED": "pr",
    "PR_MERGED": "pr",
    "TEST_STARTED": "test",
    "TEST_FAILED": "test",
    "TEST_PASSED": "test",
    "BUILD_STARTED": "build",
    "BUILD_FINISHED": "build",
}


def compile_engineering_nodes(vault: Any, project_id: str) -> dict[str, Any]:
    root = require_vault(vault)
    pid = require_project(root, project_id)
    events = list_events(root, pid)
    nodes: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("event_type") or "")
        node_type = EVENT_TO_NODE.get(event_type)
        if node_type is None:
            continue
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue
        raw_refs = event.get("evidence_refs") or []
        refs = [str(item).strip() for item in raw_refs if str(item).strip()]
        if not refs:
            refs = [f"ledger:{event_id}"]
        nodes.append(
            make_node(
                node_type=node_type,
                node_id=str(event.get("source_id") or event_id),
                project_id=pid,
                evidence_refs=refs,
                observed_at=str(event.get("observed_at") or "") or None,
                valid_from=str(event.get("valid_from") or event.get("valid_time") or "") or None,
            )
        )
    counts = {
        "commit": sum(1 for node in nodes if node["node_type"] == "commit"),
        "pr": sum(1 for node in nodes if node["node_type"] == "pr"),
        "test": sum(1 for node in nodes if node["node_type"] == "test"),
        "build": sum(1 for node in nodes if node["node_type"] == "build"),
    }
    return {
        "package": PACKAGE_ID,
        "project_id": pid,
        "nodes": nodes,
        "counts": counts,
        "status": "derived" if nodes else "UNKNOWN",
        "reason": "LEDGER_EVENTS" if nodes else "NO_LEDGER_EVENTS",
        "invented_from_git": False,
        "graph_is_authority": False,
        "promoted_to_truth_core": 0,
        "truth_boundary": TRUTH_BOUNDARY,
        "honesty": honesty_block(),
    }
