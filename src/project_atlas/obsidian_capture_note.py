"""AS-OBSIDIAN-CAPTURE-001 — Obsidian Markdown output adapter.

Renders a persisted raw capture into a human-facing Obsidian note. The note
is a **projection**, never the authoritative evidence object (architecture
§12, §13, INV-002): the verbatim raw capture stays in the Atlas capture
store and the note points back at it.

Filesystem safety, YAML serialization, and note-mutation policy follow
architecture §32-§35 and §44-§45, using the canonical Atlas containment
primitives in :mod:`atlas_contracts.paths` rather than a parallel scheme.

Determinism (NFR-001 / ADR-001 §2) takes precedence over the architecture's
illustrative ``created``/``updated`` frontmatter: rendering the same capture
twice produces byte-identical Markdown. No wall-clock value is ever
generated here; ``captured_at`` is emitted only when an operator supplied it.
"""

from __future__ import annotations

import hashlib
import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any

import yaml

from atlas_contracts.identity import (
    ensure_under_root,
    safe_relative_component,
    safe_relative_path,
)
from project_atlas.secrets import redact_text

PACKAGE_ID = "AS-OBSIDIAN-CAPTURE-001"
GENERATOR_ID = "atlas-obsidian-capture-001"
NOTE_SCHEMA_VERSION = 1

#: Managed-region markers. Architecture §45 proposes ``atlas:managed:*``;
#: the repository already ships ``atlas:generated:*`` in
#: :mod:`project_atlas.obsidian_projection`, and repository truth wins so a
#: single marker vocabulary stays valid across every Atlas-written note.
GENERATED_START = "<!-- atlas:generated:start -->"
GENERATED_END = "<!-- atlas:generated:end -->"

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_MAX_SLUG = 64


class ObsidianNoteError(ValueError):
    """Fail-closed Obsidian projection error carrying a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def slugify(title: str) -> str:
    """Deterministic, filesystem-safe slug. Never the sole uniqueness source."""
    folded = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = _SLUG_STRIP.sub("-", folded.lower()).strip("-")[:_MAX_SLUG].strip("-")
    return slug or "capture"


def note_filename(*, title: str, capture_id: str) -> str:
    """``<slug>-<capture_id>.md`` — readable, and collision-safe by id (§33).

    The architecture's ``YYYY-MM-DD-`` prefix is deliberately omitted: a
    generated date is a wall-clock value and NFR-001 forbids those in
    generated content. The capture id already provides uniqueness, so the
    date bought nothing that determinism did not cost more.
    """
    name = f"{slugify(title)}-{capture_id}.md"
    return safe_relative_component(name, label="obsidian note filename")


def _yaml_block(frontmatter: dict[str, Any]) -> str:
    """Serialize frontmatter with a real YAML serializer (§35).

    Never string concatenation: values containing ``:``, ``---``, quotes,
    brackets, ``#``, newlines, or unicode must round-trip safely.
    """
    body = yaml.safe_dump(
        frontmatter,
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
        width=10_000,
    )
    return f"---\n{body}---\n"


def build_frontmatter(record: dict[str, Any]) -> dict[str, Any]:
    """Build the note's frontmatter mapping from a persisted capture record."""
    atlas_block: dict[str, Any] = {
        "package": PACKAGE_ID,
        "capture_id": record["capture_id"],
        "content_hash": record["content_hash"],
        "identity_hash": record["identity_hash"],
        "capture_path": record["content_path"],
        "schema_version": NOTE_SCHEMA_VERSION,
        # Architecture §44: marks the note regenerable by Atlas.
        "managed": True,
        "canonical": False,
    }
    frontmatter: dict[str, Any] = {
        "title": record["title"],
        "atlas": atlas_block,
        "source": {
            "type": record["source_type"],
            "application": record["source_application"],
            "adapter": record["source_adapter"],
        },
        "classification": [record["classification"]],
        # Deliberately not ``lifecycle_state``: the note is rendered *before*
        # the record reaches "rendered", so echoing it here would be both
        # circular and stale. The capture plane is what the note can assert.
        "status": "captured",
        "tags": ["atlas", "capture", record["classification"]],
        "authority": "NON_CANONICAL",
    }
    project_id = record.get("project_id")
    frontmatter["project"] = [project_id] if project_id else []
    locator = record.get("source_locator")
    if locator:
        frontmatter["source"]["locator"] = locator
    captured_at = record.get("captured_at")
    if captured_at:
        # Only ever operator-supplied — never generated here (NFR-001, §39).
        frontmatter["captured_at"] = captured_at
    metadata = record.get("source_metadata") or {}
    if metadata:
        frontmatter["source_metadata"] = dict(sorted(metadata.items()))
    return frontmatter


def _neutralize_markers(text: str) -> str:
    """Defang Atlas region markers appearing inside captured content (§64)."""
    for marker in (
        GENERATED_START,
        GENERATED_END,
        "<!-- BEGIN HUMAN:",
        "<!-- END HUMAN:",
    ):
        text = text.replace(marker, marker.replace("<!--", "<!-\u200b-", 1))
    return text


def render_note(
    record: dict[str, Any],
    *,
    content: str,
    include_content: bool = True,
) -> str:
    """Render the full Markdown note for a persisted capture.

    ``content`` is the verbatim raw capture. When secret-shaped material was
    detected, the *projection* is redacted while the raw evidence stays
    intact (architecture §38): redaction is applied to the derived human
    artifact, never to the preserved original.
    """
    projected = redact_text(content) if record["secret_scan"]["findings"] else content
    # Captured content is untrusted data (architecture §64). Neutralize Atlas
    # region markers so a payload cannot forge a managed/human region boundary
    # in its own projection. The raw evidence keeps the original bytes.
    projected = _neutralize_markers(projected)
    lines: list[str] = [
        _yaml_block(build_frontmatter(record)),
        GENERATED_START,
        "",
        f"# {record['title']}",
        "",
        "> Atlas capture projection. This note is derived presentation, not "
        "Truth Core authority.",
        "> CAPTURE != AUTHORITY. PROJECTION != SOURCE. MODEL OUTPUT != AUTHORITY.",
        "",
        "## Capture",
        "",
        f"- capture_id: `{record['capture_id']}`",
        f"- project: `{record.get('project_id') or 'UNKNOWN'}`",
        f"- source: `{record['source_application']}` / `{record['source_type']}`"
        f" (adapter `{record['source_adapter']}`)",
        f"- classification: `{record['classification']}`",
        f"- content_hash: `{record['content_hash']}`",
        "- raw evidence: `persisted`",
        "",
    ]
    if record["secret_scan"]["findings"]:
        patterns = ", ".join(sorted(record["secret_scan"]["findings"]))
        lines.extend(
            [
                "## Redaction notice",
                "",
                f"- Secret-shaped content detected ({patterns}).",
                "- This projection is redacted; the raw capture is preserved unmodified.",
                "",
            ]
        )
    if include_content:
        lines.extend(["## Captured content", "", projected.rstrip("\n"), ""])
    else:
        lines.extend(
            [
                "## Captured content",
                "",
                "Content projection is disabled; the verbatim capture is preserved at "
                f"`{record['content_path']}`.",
                "",
            ]
        )
    lines.extend(
        [
            "## Summary",
            "",
            "UNKNOWN (no deterministic summarizer; enrichment is a later work package).",
            "",
            "## Decisions",
            "",
            "UNKNOWN",
            "",
            "## Actions",
            "",
            "UNKNOWN",
            "",
            "## Related",
            "",
        ]
    )
    project_id = record.get("project_id")
    if project_id:
        lines.append(f"- [[{project_id}]]")
    lines.extend(
        [
            f"- [[{PACKAGE_ID}]]",
            "",
            "## Source",
            "",
            f"- Atlas capture: `{record['capture_id']}`",
            f"- Raw evidence: `{record['content_path']}`",
            f"- generated.by: `{GENERATOR_ID}`",
            "",
            GENERATED_END,
            "",
        ]
    )
    return "\n".join(lines)


def _existing_capture_id(text: str) -> str | None:
    """Read the ``atlas.capture_id`` of an existing note, if it has one."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    try:
        loaded = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    atlas = loaded.get("atlas")
    if not isinstance(atlas, dict):
        return None
    if atlas.get("managed") is not True:
        return None
    capture_id = atlas.get("capture_id")
    return capture_id if isinstance(capture_id, str) else None


def _write_atomic(path: Path, content: bytes, *, root: Path) -> None:
    """Atomic write with a post-resolution containment re-check (§32, §34)."""
    try:
        ensure_under_root(root, path.parent, label="obsidian note directory")
    except ValueError as exc:
        raise ObsidianNoteError("PATH_ESCAPES_VAULT", str(exc)) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        ensure_under_root(root, path.parent, label="obsidian note directory")
    except ValueError as exc:
        raise ObsidianNoteError("PATH_ESCAPES_VAULT", str(exc)) from exc
    # A per-writer temp name, not a shared ``<name>.tmp``: two concurrent
    # writers of the same content-addressed path would otherwise race on one
    # temp file and the loser's ``os.replace`` would fail with ENOENT
    # (architecture §49). ``os.replace`` itself is atomic, so identical
    # concurrent captures converge instead of colliding.
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}-{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def write_note(
    record: dict[str, Any],
    *,
    content: str,
    obsidian_root: Path,
    include_content: bool = True,
) -> dict[str, Any]:
    """Render and write the note, returning an ``ObsidianArtifact`` mapping.

    Fails closed rather than overwriting a note Atlas does not manage
    (architecture §44). Re-writing the *same* capture is idempotent
    (INV-006).
    """
    root = obsidian_root.expanduser()
    if not root.is_dir():
        raise ObsidianNoteError(
            "OBSIDIAN_ROOT_NOT_FOUND",
            f"obsidian root is not a directory: {root}",
        )
    resolved_root = ensure_under_root(root, root, label="obsidian root")

    destination = record["routing"]["destination"]
    try:
        segments = safe_relative_path(destination, label="obsidian routing segment")
    except ValueError as exc:
        raise ObsidianNoteError("ROUTING_UNSAFE", str(exc)) from exc

    filename = note_filename(title=record["title"], capture_id=record["capture_id"])
    target = resolved_root
    for segment in segments:
        target = target / segment
    target = target / filename
    try:
        ensure_under_root(resolved_root, target.parent, label="obsidian note")
    except ValueError as exc:
        raise ObsidianNoteError("PATH_ESCAPES_VAULT", str(exc)) from exc

    if target.is_symlink():
        raise ObsidianNoteError("PATH_ESCAPES_VAULT", f"note path is a symlink: {filename}")
    if target.is_file():
        try:
            existing = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ObsidianNoteError(
                "OBSIDIAN_NOTE_CONFLICT",
                f"existing note is unreadable: {filename}",
            ) from exc
        owner = _existing_capture_id(existing)
        if owner != record["capture_id"]:
            raise ObsidianNoteError(
                "OBSIDIAN_NOTE_CONFLICT",
                f"refusing to overwrite a note Atlas does not manage: {filename}",
            )

    rendered = render_note(record, content=content, include_content=include_content)
    encoded = rendered.encode("utf-8")
    _write_atomic(target, encoded, root=resolved_root)

    relative_path = "/".join((*segments, filename))
    note_hash = "sha256:" + hashlib.sha256(encoded).hexdigest()
    artifact_id = "art-" + hashlib.sha256(
        f"obsidian_note:{record['capture_id']}:{relative_path}".encode()
    ).hexdigest()[:16]
    return {
        "artifact_id": artifact_id,
        "artifact_type": "obsidian_note",
        "capture_id": record["capture_id"],
        "vault_root": str(resolved_root),
        "relative_path": relative_path,
        "content_hash": note_hash,
        "processor": GENERATOR_ID,
        "canonical": False,
    }
