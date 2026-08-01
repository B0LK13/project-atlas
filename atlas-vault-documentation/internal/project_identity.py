"""Canonical project identity resolution (AS-WP-003 Phase 1).

Precedence:

    verified event project_id/project_slug
    → configured project mapping (config ``projects:`` section)
    → repository identity
    → deterministic root-derived identity

Every resolution records the chosen identity, its source, confidence,
and conflicting candidates. Ambiguous or unsafe identities fail closed;
projects are never merged because names look similar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

SAFE_PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
SAFE_PRJ_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

MAX_FIELD = 200


class IdentityError(ValueError):
    """Fail-closed identity resolution error with a category."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class ProjectIdentity:
    """Resolved, auditable project identity."""

    project_id: str  # canonical slug used for vault paths
    display_name: str
    source: str  # verified-event | configured-mapping | repository | root-derived
    confidence: str  # authoritative | configured | derived
    external_id: str | None = None  # e.g. PRJ-ATLAS from event metadata
    aliases: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    resolution_rule: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "display_name": self.display_name,
            "source": self.source,
            "confidence": self.confidence,
            "external_id": self.external_id,
            "aliases": list(self.aliases),
            "conflicts": list(self.conflicts),
            "resolution_rule": self.resolution_rule,
        }


def _display_name(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def _configured_projects(config: Mapping[str, Any]) -> Mapping[str, Any]:
    section = config.get("projects")
    return section if isinstance(section, Mapping) else {}


def resolve_identity(
    *,
    event_project_id: str | None,
    event_project_slug: str | None,
    repository: str | None,
    config: Mapping[str, Any],
) -> ProjectIdentity:
    """Resolve the canonical identity for one event.

    ``event_project_id`` is the external ID from verified event metadata
    (e.g. ``PRJ-ATLAS``); ``event_project_slug`` is its slug form. The
    config ``projects:`` section may map slugs to display names and
    aliases, and ``projects_by_external_id:`` may pin PRJ-IDs to slugs.
    """
    conflicts: list[str] = []
    configured = _configured_projects(config)
    by_external = config.get("projects_by_external_id")
    by_external = by_external if isinstance(by_external, Mapping) else {}

    external_id = None
    slug = None
    source = ""
    confidence = ""
    rule = ""

    if event_project_id and event_project_id != "unknown":
        if not SAFE_PRJ_ID.fullmatch(event_project_id):
            raise IdentityError("invalid-project-id", f"unsafe project id: {event_project_id!r}")
        if len(event_project_id) > MAX_FIELD:
            raise IdentityError("oversized-metadata", "project id exceeds size limit")
        external_id = event_project_id
        mapped = by_external.get(event_project_id)
        if mapped:
            slug = str(mapped)
            rule = f"projects_by_external_id[{event_project_id}]"
        elif event_project_slug and event_project_slug != "unknown":
            slug = event_project_slug
            rule = "event project_slug"
        else:
            slug = event_project_id.lower()
            rule = "lower-cased event project_id"
        source = "verified-event"
        confidence = "authoritative"
        if event_project_slug and event_project_slug != "unknown" and slug != event_project_slug:
            conflicts.append(
                f"event slug {event_project_slug!r} differs from mapped slug {slug!r}"
            )
    elif event_project_slug and event_project_slug != "unknown":
        slug = event_project_slug
        source = "verified-event"
        confidence = "authoritative"
        rule = "event project_slug"
    elif repository and repository != "unknown":
        # Repository identity: use the repository name segment.
        candidate = repository.rstrip("/").split("/")[-1].lower()
        candidate = re.sub(r"[^a-z0-9-]", "-", candidate).strip("-")
        if candidate:
            slug = candidate
            source = "repository"
            confidence = "derived"
            rule = "repository name segment"

    if slug is None:
        raise IdentityError(
            "unresolvable-identity",
            "no project_id, project_slug, or repository identity available",
        )
    if not SAFE_PROJECT_ID.fullmatch(slug):
        raise IdentityError("invalid-slug", f"unsafe project slug: {slug!r}")
    if source == "":
        source = "root-derived"
        confidence = "derived"

    entry = configured.get(slug)
    display = _display_name(slug)
    aliases: tuple[str, ...] = ()
    if isinstance(entry, Mapping):
        if entry.get("display_name"):
            display = str(entry["display_name"])
        raw_aliases = entry.get("aliases")
        if isinstance(raw_aliases, str):
            aliases = tuple(a.strip() for a in raw_aliases.split(",") if a.strip())
        if source == "verified-event" and entry:
            rule = f"configured mapping for {slug!r} ({rule})"

    return ProjectIdentity(
        project_id=slug,
        display_name=display,
        source=source,
        confidence=confidence,
        external_id=external_id,
        aliases=aliases,
        conflicts=tuple(conflicts),
        resolution_rule=rule,
    )
