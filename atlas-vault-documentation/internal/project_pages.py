"""Project event pages and the project index projection (Phases 4, 9).

Event pages are *reference* pages: metadata, hashes, and links to the
immutable raw/normalized artifacts — no uncontrolled content copies.
The project index renders identity, current status, recent events,
work packages, and routing health from routing state only; unknown
information stays ``unknown``.
"""

from __future__ import annotations

from typing import Any

from internal import atlas_links, frontmatter, generated_regions
from internal.project_identity import ProjectIdentity
from internal.routing_state import ProjectRoutingState, RoutedEventRecord

EVENT_REGION = "event-reference"
STATUS_REGION = "project-status"
RECENT_REGION = "recent-events"
WP_REGION = "work-packages"
HEALTH_REGION = "routing-health"

RECENT_LIMIT = 10


def event_page_rel(project_rel: str, record: RoutedEventRecord) -> str:
    year, month, day = (
        record.occurred_at[:4],
        record.occurred_at[5:7],
        record.occurred_at[8:10],
    )
    return f"{project_rel}/events/{year}/{month}/{day}/{record.event_id}.md"


def render_event_page(
    record: RoutedEventRecord,
    *,
    state: ProjectRoutingState,
    project_rel: str,
    from_file_rel: str,
) -> str:
    """Render the deterministic reference page for one routed event."""
    lines = [
        f"- **Event ID:** {record.event_id}",
        f"- **Type:** {record.event_kind}",
        f"- **Occurred:** {record.occurred_at}",
        f"- **Agent:** {record.agent}",
    ]
    if record.work_package_id != "unknown":
        wp_rel = f"{project_rel}/work-packages/{record.work_package_id}.md"
        lines.append(
            f"- **Work package:** "
            f"{atlas_links.markdown_link(record.work_package_id, wp_rel, from_file_rel)}"
        )
    lines.extend(
        [
            f"- **Raw event:** "
            f"{atlas_links.markdown_link('raw source', record.raw_path, from_file_rel)}",
            f"- **Raw SHA-256:** `{record.raw_sha256}`",
            f"- **Normalized event:** "
            f"{atlas_links.markdown_link('normalized', record.normalized_path, from_file_rel)}",
            f"- **Normalized SHA-256:** `{record.normalized_sha256}`",
            f"- **Verification:** verified (see normalized artifact provenance)",
            f"- **Route receipt:** `{record.route_receipt}`",
            f"- **Project log:** "
            f"{atlas_links.markdown_link('project log', f'{project_rel}/project-log.md', from_file_rel)}",
        ]
    )
    managed = [
        ("type", "Agent Work Event Reference"),
        ("schema_version", "1"),
        ("event_id", record.event_id),
        ("event_kind", record.event_kind),
        ("occurred_at", record.occurred_at),
        ("agent", record.agent),
        ("work_package", record.work_package_id),
        ("project_id", state.project_id),
        ("route_receipt", record.route_receipt),
        ("verification_status", "verified"),
    ]
    title = record.title or record.event_id
    return (
        frontmatter.render(managed)
        + "\n\n"
        + f"# {title}\n\n"
        + generated_regions.render_region(EVENT_REGION, "\n".join(lines))
        + "\n"
    )


def _current_status(state: ProjectRoutingState) -> str:
    if not state.routed_events:
        return "unknown"
    latest = max(
        state.routed_events.values(), key=lambda r: (r.occurred_at, r.event_id)
    )
    if latest.event_kind == "blocked":
        return "blocked"
    return "active"


def render_index_page(
    state: ProjectRoutingState,
    identity: ProjectIdentity,
    *,
    project_rel: str,
    from_file_rel: str,
    existing: str | None,
) -> str:
    """Render the project index from routing state (Phase 9)."""
    records = sorted(
        state.routed_events.values(),
        key=lambda r: (r.occurred_at, r.event_id),
        reverse=True,
    )

    status_lines = [f"- **Current status:** {_current_status(state)}"]
    active_wp = None
    for wp, summary in sorted(state.work_packages.items()):
        if summary.get("status") not in ("completed", "cancelled"):
            active_wp = wp
    if active_wp:
        wp_rel = f"{project_rel}/work-packages/{active_wp}.md"
        status_lines.append(
            f"- **Active work package:** "
            f"{atlas_links.markdown_link(active_wp, wp_rel, from_file_rel)}"
        )
    else:
        status_lines.append("- **Active work package:** none")
    milestones = [
        r for r in records if r.event_kind == "completion"
    ]
    if milestones:
        status_lines.append(
            "- **Most recent validated milestone:** "
            + atlas_links.markdown_link(
                milestones[0].event_id,
                event_page_rel(project_rel, milestones[0]),
                from_file_rel,
            )
        )
    else:
        status_lines.append("- **Most recent validated milestone:** unknown")
    status_lines.append("- **Documentation state:** event-routed (AS-WP-003)")
    status_content = "\n".join(status_lines)

    recent_lines = ["## Recent events", ""]
    for record in records[:RECENT_LIMIT]:
        recent_lines.append(
            f"- {record.occurred_at[:10]} — {record.event_kind} — "
            + atlas_links.markdown_link(
                record.event_id, event_page_rel(project_rel, record), from_file_rel
            )
        )
    if not records:
        recent_lines.append("- No events routed yet.")
    recent_content = "\n".join(recent_lines)

    wp_lines = ["## Work packages", ""]
    if state.work_packages:
        for wp, summary in sorted(state.work_packages.items()):
            wp_rel = f"{project_rel}/work-packages/{wp}.md"
            wp_lines.append(
                f"- {atlas_links.markdown_link(wp, wp_rel, from_file_rel)}"
                f" — {summary.get('status', 'unknown')}"
            )
    else:
        wp_lines.append("- None recorded.")
    wp_content = "\n".join(wp_lines)

    health_lines = [
        "## Routing health",
        "",
        f"- Routed events: {len(state.routed_events)}",
        f"- Last transaction: {state.last_successful_transaction or 'none'}",
        "- Log: "
        + atlas_links.markdown_link("project log", f"{project_rel}/project-log.md", from_file_rel),
    ]
    health_content = "\n".join(health_lines)

    managed = [
        ("type", "Project"),
        ("schema_version", "1"),
        ("project_id", state.project_id),
        ("title", identity.display_name),
        ("identity_source", identity.source),
        ("identity_confidence", identity.confidence),
    ]
    regions = {
        STATUS_REGION: status_content,
        RECENT_REGION: recent_content,
        WP_REGION: wp_content,
        HEALTH_REGION: health_content,
    }
    if existing is None:
        body = f"# {identity.display_name}\n\n"
        body += generated_regions.render_region(STATUS_REGION, status_content)
        for region in (RECENT_REGION, WP_REGION, HEALTH_REGION):
            body += "\n\n" + generated_regions.render_region(region, regions[region])
        return frontmatter.render(managed) + "\n\n" + body + "\n"
    text = generated_regions.update_regions(existing, regions)
    return frontmatter.replace_frontmatter(text, managed)
