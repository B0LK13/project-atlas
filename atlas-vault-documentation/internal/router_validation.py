"""Strict route validation (AS-WP-003 Phase 9; validate_routes).

Checks the consistency of routing state, projections, receipts, and
links for one project (or all projects). Human-readable pages are
projections; this validator proves they match the machine state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from internal import (
    atlas_links,
    generated_regions,
    routing_state,
)


@dataclass
class RouteValidationReport:
    projects_checked: int = 0
    events_checked: int = 0
    receipts_checked: int = 0
    logs_checked: int = 0
    work_packages_checked: int = 0
    regions_checked: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "projects_checked": self.projects_checked,
            "events_checked": self.events_checked,
            "route_receipts_checked": self.receipts_checked,
            "project_logs_checked": self.logs_checked,
            "work_packages_checked": self.work_packages_checked,
            "generated_regions_checked": self.regions_checked,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _check_file_links(
    rel: str, text: str, vault_root: Path, report: RouteValidationReport
) -> None:
    for link in atlas_links.extract_links(text):
        target = atlas_links.resolve_link(link, rel)
        if target.startswith("../") or target.startswith("/"):
            report.errors.append(f"{rel}: link escapes vault root: {link}")
        elif not (vault_root / target).is_file():
            report.errors.append(f"{rel}: unresolved link: {link}")


def validate_project(
    vault_root: Path,
    project_id: str,
    *,
    projects_root: str = "projects",
    state_root: str = "routing/state",
    receipts_root: str = "routing/receipts",
) -> RouteValidationReport:
    """Validate every routing artifact of one project."""
    report = RouteValidationReport(projects_checked=1)
    vault_root = vault_root.resolve()
    project_rel = f"{projects_root}/{project_id}"
    project_dir = vault_root / project_rel

    try:
        state = routing_state.load_state(vault_root / state_root, project_id)
    except (ValueError, OSError, KeyError) as exc:
        report.errors.append(f"{project_id}: routing state unreadable: {exc}")
        return report

    # --- routed events: pages, receipts, hashes ----------------------------
    for event_id, record in sorted(state.routed_events.items()):
        report.events_checked += 1
        year, month, day = (
            record.occurred_at[:4], record.occurred_at[5:7], record.occurred_at[8:10],
        )
        page = project_dir / "events" / year / month / day / f"{event_id}.md"
        if not page.is_file():
            report.errors.append(f"{project_id}: missing event page for {event_id}")
        if not (vault_root / record.raw_path).is_file():
            report.errors.append(f"{project_id}: missing raw event for {event_id}")
        if not (vault_root / record.normalized_path).is_file():
            report.errors.append(f"{project_id}: missing normalized event for {event_id}")
        receipt = vault_root / receipts_root / f"{record.route_receipt}.yaml"
        report.receipts_checked += 1
        if not receipt.is_file():
            report.errors.append(f"{project_id}: missing route receipt {record.route_receipt}")
        elif event_id not in receipt.read_text(encoding="utf-8"):
            report.errors.append(
                f"{project_id}: receipt {record.route_receipt} does not reference {event_id}"
            )

    # --- project log: uniqueness + links ------------------------------------
    log_path = project_dir / "project-log.md"
    if state.routed_events and not log_path.is_file():
        report.errors.append(f"{project_id}: missing project-log.md")
    if log_path.is_file():
        report.logs_checked += 1
        text = log_path.read_text(encoding="utf-8")
        # Duplicate detection uses stable event-page links, never text
        # matching: each routed event must be linked exactly once.
        log_rel = f"{project_rel}/project-log.md"
        links = atlas_links.extract_links(text)
        for event_id, record in state.routed_events.items():
            year, month, day = (
                record.occurred_at[:4], record.occurred_at[5:7], record.occurred_at[8:10],
            )
            event_rel = f"{project_rel}/events/{year}/{month}/{day}/{event_id}.md"
            expected_link = atlas_links.relative_link(event_rel, log_rel)
            count = links.count(expected_link)
            if count == 0:
                report.errors.append(f"{project_id}: log missing entry for {event_id}")
            elif count > 1:
                report.errors.append(
                    f"{project_id}: duplicate log entries for {event_id} ({count})"
                )
        try:
            regions = generated_regions.parse_regions(text)
            report.regions_checked += len(regions)
        except generated_regions.RegionError as exc:
            report.errors.append(f"{project_id}: project-log.md {exc}")
        _check_file_links(f"{project_rel}/project-log.md", text, vault_root, report)

    # --- work packages --------------------------------------------------------
    for wp in sorted(state.work_packages):
        report.work_packages_checked += 1
        wp_path = project_dir / "work-packages" / f"{wp}.md"
        if not wp_path.is_file():
            report.errors.append(f"{project_id}: missing work package page {wp}")
            continue
        text = wp_path.read_text(encoding="utf-8")
        try:
            regions = generated_regions.parse_regions(text)
            report.regions_checked += len(regions)
        except generated_regions.RegionError as exc:
            report.errors.append(f"{project_id}: work package {wp}: {exc}")
        _check_file_links(f"{project_rel}/work-packages/{wp}.md", text, vault_root, report)

    # --- index ------------------------------------------------------------------
    index_path = project_dir / "index.md"
    if state.routed_events and index_path.is_file():
        text = index_path.read_text(encoding="utf-8")
        try:
            regions = generated_regions.parse_regions(text)
            report.regions_checked += len(regions)
        except generated_regions.RegionError as exc:
            report.errors.append(f"{project_id}: index.md {exc}")
        _check_file_links(f"{project_rel}/index.md", text, vault_root, report)
    elif state.routed_events:
        report.warnings.append(f"{project_id}: no index.md projection")

    # --- event pages: regions + links -------------------------------------------
    for page in sorted(project_dir.glob("events/**/*.md")) if project_dir.is_dir() else []:
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(vault_root).as_posix()
        try:
            regions = generated_regions.parse_regions(text)
            report.regions_checked += len(regions)
        except generated_regions.RegionError as exc:
            report.errors.append(f"{rel}: {exc}")
        _check_file_links(rel, text, vault_root, report)

    return report


def discover_projects(vault_root: Path, state_root: str = "routing/state") -> list[str]:
    root = vault_root / state_root
    if not root.is_dir():
        return []
    return sorted(path.stem for path in root.glob("*.json"))
