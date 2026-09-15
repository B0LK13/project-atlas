"""Deterministic routing plans (AS-WP-003 Phase 3).

A plan describes every intended mutation before anything is written.
Plans are serializable, deterministic, validated before execution,
hashable, shown by ``--dry-run``, and embedded in the route receipt.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from internal.event_reader import RoutedEvent
from internal.project_identity import ProjectIdentity

PLAN_SCHEMA_VERSION = 1

KNOWN_OPERATIONS = {
    "place_event",
    "append_project_log",
    "update_work_package",
    "update_project_index",
    "update_routing_state",
    "write_receipt",
}


def event_destination(project_root_rel: str, event: RoutedEvent) -> str:
    year, month, day = event.date_parts
    return f"{project_root_rel}/events/{year}/{month}/{day}/{event.event_id}.md"


def build_plan(
    event: RoutedEvent,
    identity: ProjectIdentity,
    *,
    projects_root: str,
    state_root: str,
    receipts_root: str,
    receipt_id: str,
    work_package_projection: bool,
    project_index_projection: bool,
) -> dict[str, Any]:
    """Build the deterministic routing plan for one accepted event."""
    project_rel = f"{projects_root}/{identity.project_id}"
    operations: list[dict[str, str]] = [
        {
            "operation": "place_event",
            "destination": event_destination(project_rel, event),
        },
        {
            "operation": "append_project_log",
            "destination": f"{project_rel}/project-log.md",
        },
    ]
    if work_package_projection and event.work_package != "unknown":
        operations.append(
            {
                "operation": "update_work_package",
                "destination": f"{project_rel}/work-packages/{event.work_package}.md",
            }
        )
    if project_index_projection:
        operations.append(
            {
                "operation": "update_project_index",
                "destination": f"{project_rel}/index.md",
            }
        )
    operations.extend(
        [
            {
                "operation": "update_routing_state",
                "destination": f"{state_root}/{identity.project_id}.json",
            },
            {
                "operation": "write_receipt",
                "destination": f"{receipts_root}/{receipt_id}.yaml",
            },
        ]
    )
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "event_id": event.event_id,
        "event_kind": event.event_kind,
        "project_id": identity.project_id,
        "identity": identity.as_dict(),
        "source": {
            "raw_event": str(event.raw_event_path),
            "normalized_event": str(event.normalized_path),
            "raw_sha256": event.raw_event_hash,
            "normalized_sha256": event.normalized_sha256,
        },
        "operations": operations,
    }


def plan_hash(plan: dict[str, Any]) -> str:
    canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_plan(plan: dict[str, Any]) -> list[str]:
    """Structural validation; returns a list of problems (empty = valid)."""
    problems: list[str] = []
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        problems.append(f"unsupported plan schema: {plan.get('schema_version')!r}")
    for key in ("event_id", "project_id", "operations", "source"):
        if key not in plan:
            problems.append(f"plan missing {key}")
    destinations: set[str] = set()
    for operation in plan.get("operations", []):
        name = operation.get("operation")
        if name not in KNOWN_OPERATIONS:
            problems.append(f"unexpected operation: {name!r}")
        destination = operation.get("destination", "")
        if not destination or ".." in destination.split("/"):
            problems.append(f"invalid destination: {destination!r}")
        if destination in destinations:
            problems.append(f"duplicate destination: {destination!r}")
        destinations.add(destination)
    return problems
