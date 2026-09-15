"""Normalized-event reading and acceptance (AS-WP-003 Phase 2).

The router accepts only artifacts that satisfy the AS-WP-002 trust
contract: verified normalization, complete provenance, matching raw
hash, supported schema, valid identifiers, and confinement to the
vault root. Rejection is structured and fail-closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from internal import provenance as provenance_mod
from internal import verification
from internal.mda_output_contract import raw_sibling_for

EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
WORK_PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
EVENT_KINDS = {
    "session-start", "plan", "implementation", "refactor", "decision",
    "validation", "issue", "finding", "risk", "research", "deployment",
    "rollback", "migration", "recovery", "documentation", "handoff",
    "completion", "blocked",
}
SUPPORTED_PROVENANCE_SCHEMA = 1

MAX_TITLE = 500
MAX_FIELD = 200


@dataclass(frozen=True)
class RoutedEvent:
    """A verified normalized event accepted for routing."""

    event_id: str
    event_kind: str
    status: str
    occurred_at: str
    agent: str
    session_id: str
    work_package: str
    project_id: str
    project_slug: str
    repository: str
    title: str
    normalized_path: Path
    normalized_sha256: str
    raw_event_path: Path
    raw_event_hash: str
    provenance: dict[str, Any]

    @property
    def date_parts(self) -> tuple[str, str, str]:
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})T", self.occurred_at)
        if not match:
            raise ValueError(f"occurred_at is not ISO-8601: {self.occurred_at!r}")
        return match.group(1), match.group(2), match.group(3)


def parse_normalized_frontmatter(text: str) -> tuple[dict[str, str], dict[str, str]]:
    """Parse normalized frontmatter into (flat keys, atlas_provenance).

    List blocks are skipped; only scalar keys are captured.
    """
    frontmatter, _ = provenance_mod.split_document(text)
    flat: dict[str, str] = {}
    prov: dict[str, str] = {}
    in_provenance = False
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        if line.startswith("atlas_provenance:"):
            in_provenance = True
            continue
        if line.startswith(" ") or line.startswith("- "):
            if in_provenance and line.startswith(" ") and ":" in line:
                key, _, value = line.strip().partition(":")
                prov[key.strip()] = value.strip().strip('"')
            continue
        in_provenance = False
        if ":" in line:
            key, _, value = line.partition(":")
            flat[key.strip()] = value.strip().strip('"')
    return flat, prov


def _raw_resource(text: str, normalized_path: Path) -> Path | None:
    """Locate the raw event: provenance resource reference or sibling convention."""
    match = re.search(r'^\s*resource: "([^"]+)"', text, re.M)
    if match:
        candidate = Path(match.group(1))
        if candidate.is_file():
            return candidate
        resolved = (normalized_path.parent / match.group(1)).resolve()
        if resolved.is_file():
            return resolved
    # Sibling convention: <raw-stem>.restructured.md (current mda-cli 0.2.9)
    # or historical <raw-stem>.normalized.md → <raw-stem>.md
    sibling = raw_sibling_for(normalized_path)
    if sibling is not None and sibling.is_file():
        return sibling
    return None


def read_event(normalized_path: Path, *, vault_root: Path) -> tuple[RoutedEvent | None, list[str]]:
    """Read and acceptance-check one normalized event.

    Returns ``(event, [])`` on acceptance or ``(None, problems)``.
    """
    problems: list[str] = []
    normalized_path = normalized_path.expanduser()
    try:
        verification.ensure_inside_root(vault_root, normalized_path)
    except ValueError as exc:
        return None, [str(exc)]
    if not normalized_path.is_file():
        return None, [f"normalized artifact not found: {normalized_path}"]
    resolved = normalized_path.resolve()

    try:
        text = resolved.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, [f"normalized artifact unreadable: {type(exc).__name__}"]

    try:
        flat, prov = parse_normalized_frontmatter(text)
    except ValueError as exc:
        return None, [str(exc)]

    if flat.get("type") != "Agent Work Event":
        problems.append("artifact is not an Agent Work Event")
    event_id = flat.get("id", "")
    if event_id.startswith("agent-event:"):
        event_id = event_id[len("agent-event:"):]
    if not EVENT_ID_PATTERN.fullmatch(event_id):
        problems.append(f"invalid event id: {flat.get('id')!r}")
    if flat.get("event_kind") not in EVENT_KINDS:
        problems.append(f"unsupported event kind: {flat.get('event_kind')!r}")

    for key in ("title",):
        if len(flat.get(key, "")) > MAX_TITLE:
            problems.append(f"metadata field {key} exceeds {MAX_TITLE} chars")
    for key in ("agent", "session_id", "work_package", "project_id", "project_slug", "occurred_at", "status"):
        if len(flat.get(key, "")) > MAX_FIELD:
            problems.append(f"metadata field {key} exceeds {MAX_FIELD} chars")
    wp = flat.get("work_package", "unknown")
    if wp != "unknown" and not WORK_PACKAGE_PATTERN.fullmatch(wp):
        problems.append(f"unsafe work package id: {wp!r}")

    # Provenance completeness (AS-WP-002 contract).
    if not prov:
        problems.append("missing atlas_provenance block")
    else:
        try:
            schema = int(prov.get("schema_version", "0"))
        except ValueError:
            schema = -1
        if schema != SUPPORTED_PROVENANCE_SCHEMA:
            problems.append(f"unsupported provenance schema: {prov.get('schema_version')!r}")
        if prov.get("raw_event_id") != event_id:
            problems.append("provenance raw_event_id does not match event id")
        raw_hash = prov.get("raw_event_hash", "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", raw_hash):
            problems.append("provenance raw_event_hash missing or malformed")
        verification_status = prov.get("verification_status", "")
        if verification_status != "verified":
            problems.append(f"normalization not verified: {verification_status!r}")
        required = ("normalized_at", "tool", "output_mode")
        for key in required:
            if not prov.get(key):
                problems.append(f"provenance missing {key}")

    # Raw event existence and hash match.
    raw_path: Path | None = None
    raw_hash = prov.get("raw_event_hash", "")
    if not problems and raw_hash:
        raw_path = _raw_resource(text, resolved)
        if raw_path is None:
            problems.append("raw event reference not resolvable")
        else:
            try:
                verification.ensure_inside_root(vault_root, raw_path)
            except ValueError as exc:
                problems.append(str(exc))
            else:
                actual = provenance_mod.sha256_file(raw_path)
                if f"sha256:{actual}" != raw_hash:
                    problems.append("raw event hash does not match provenance")

    if problems:
        return None, problems

    return (
        RoutedEvent(
            event_id=event_id,
            event_kind=flat["event_kind"],
            status=flat.get("status", "unknown"),
            occurred_at=flat.get("occurred_at", "unknown"),
            agent=flat.get("agent", "unknown"),
            session_id=flat.get("session_id", "unknown"),
            work_package=wp,
            project_id=flat.get("project_id", "unknown"),
            project_slug=flat.get("project_slug", "unknown"),
            repository=flat.get("repository", "unknown"),
            title=flat.get("title", ""),
            normalized_path=resolved,
            normalized_sha256=provenance_mod.sha256_file(resolved),
            raw_event_path=raw_path.resolve(),  # type: ignore[union-attr]
            raw_event_hash=raw_hash,
            provenance=dict(prov),
        ),
        [],
    )
