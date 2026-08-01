"""Work-package projection (AS-WP-003 Phase 6).

One canonical page per work package, rendered from routing state.
Every projected claim links to the event IDs that support it.

Status lifecycle (computed as a projection over events ordered by
(occurred_at, event_id)):

    planned → in-progress → completed
                  ↕             |
               blocked      later non-completion event → reopened
                               (status returns to in-progress)

A completion event never erases earlier evidence: all events remain
listed. Multiple completion events are recorded as an explicit
conflict, never silently merged.
"""

from __future__ import annotations

from typing import Any

from internal import atlas_links, frontmatter, generated_regions
from internal.routing_state import ProjectRoutingState, RoutedEventRecord

STATUS_REGION = "work-package-status"
EVENTS_REGION = "work-package-events"

SIGNIFICANT_KINDS = {"plan", "completion", "blocked", "validation"}


def compute_work_package(
    events: list[RoutedEventRecord],
) -> dict[str, Any]:
    """Compute the deterministic work-package summary from its events."""
    ordered = sorted(events, key=lambda r: (r.occurred_at, r.event_id))
    status = "planned"
    validation_status = "unknown"
    validation_event = None
    completion_events: list[str] = []
    reopened = False
    for record in ordered:
        if record.event_kind == "plan":
            if status == "planned":
                status = "planned"
        elif record.event_kind == "blocked":
            status = "blocked"
        elif record.event_kind == "validation":
            validation_event = record.event_id
            validation_status = "passed" if record.status == "completed" else record.status
            if status == "planned":
                status = "in-progress"
        elif record.event_kind == "completion":
            completion_events.append(record.event_id)
            status = "completed"
        else:  # implementation, refactor, issue, risk, ...
            if status in ("planned", "blocked"):
                status = "in-progress"
            elif status == "completed":
                status = "in-progress"
                reopened = True
    conflicts: list[str] = []
    if len(completion_events) > 1:
        conflicts.append(
            "multiple completion events: " + ", ".join(completion_events)
        )
    return {
        "status": status,
        "validation_status": validation_status,
        "validation_event": validation_event,
        "completion_event": completion_events[0] if completion_events else None,
        "completion_events": completion_events,
        "reopened": reopened,
        "first_seen": ordered[0].occurred_at if ordered else None,
        "last_updated": ordered[-1].occurred_at if ordered else None,
        "conflicts": conflicts,
    }


def _event_link(record: RoutedEventRecord, project_rel: str, from_file_rel: str) -> str:
    year, month, day = (
        record.occurred_at[:4],
        record.occurred_at[5:7],
        record.occurred_at[8:10],
    )
    event_rel = f"{project_rel}/events/{year}/{month}/{day}/{record.event_id}.md"
    return atlas_links.markdown_link(record.event_id, event_rel, from_file_rel)


def render_work_package_page(
    wp_id: str,
    summary: dict[str, Any],
    events: list[RoutedEventRecord],
    *,
    state: ProjectRoutingState,
    project_rel: str,
    from_file_rel: str,
    existing: str | None,
) -> str:
    """Render one work-package page, preserving human regions."""
    ordered = sorted(events, key=lambda r: (r.occurred_at, r.event_id))

    status_lines = [
        f"- **Status:** {summary['status']}",
        f"- **Validation:** {summary['validation_status']}",
    ]
    if summary["validation_event"]:
        record = next(e for e in ordered if e.event_id == summary["validation_event"])
        status_lines[-1] += f" (evidence: {_event_link(record, project_rel, from_file_rel)})"
    if summary["completion_event"]:
        record = next(e for e in ordered if e.event_id == summary["completion_event"])
        status_lines.append(
            f"- **Completion:** {_event_link(record, project_rel, from_file_rel)}"
        )
    if summary["reopened"]:
        status_lines.append("- **Reopened:** yes (later activity followed completion)")
    for conflict in summary["conflicts"]:
        status_lines.append(f"- **Conflict:** {conflict} (unresolved, needs human review)")
    status_content = "\n".join(status_lines)

    event_lines = ["## Events", ""]
    for record in ordered:
        event_lines.append(
            f"- {record.occurred_at} — {record.event_kind} — "
            f"{_event_link(record, project_rel, from_file_rel)}"
            + (f" — {record.title}" if record.title else "")
        )
    events_content = "\n".join(event_lines)

    managed = [
        ("type", "Work Package"),
        ("schema_version", "1"),
        ("work_package_id", wp_id),
        ("project_id", state.project_id),
        ("title", wp_id),
        ("status", str(summary["status"])),
        ("validation_status", str(summary["validation_status"])),
        ("first_seen", str(summary["first_seen"])),
        ("last_updated", str(summary["last_updated"])),
        ("completion_event", summary["completion_event"] or "null"),
    ]
    if existing is None:
        return (
            frontmatter.render(managed)
            + "\n\n"
            + f"# {wp_id}\n\n"
            + generated_regions.render_region(STATUS_REGION, status_content)
            + "\n\n"
            + generated_regions.render_region(EVENTS_REGION, events_content)
            + "\n"
        )
    text = generated_regions.update_regions(
        existing, {STATUS_REGION: status_content, EVENTS_REGION: events_content}
    )
    # Router-managed frontmatter keys are refreshed deterministically;
    # human-added keys are preserved.
    return frontmatter.replace_frontmatter(text, managed)
