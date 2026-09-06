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
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from atlas_contracts.identity import (
    ensure_under_root,
    safe_relative_component,
    safe_relative_path,
)
from project_atlas.capture_io import is_lexically_under, write_atomic_under_root
from project_atlas.protected_regions import (
    GENERATED_END,
    GENERATED_START,
    ProtectedRegionError,
    extract_human_regions,
)
from project_atlas.protected_regions import merge_protected_regions as _merge_protected_regions
from project_atlas.secrets import redact_text, scan_text

PACKAGE_ID = "AS-OBSIDIAN-CAPTURE-001"
GENERATOR_ID = "atlas-obsidian-capture-001"
NOTE_SCHEMA_VERSION = 1

#: Managed-region markers. Architecture §45 proposes ``atlas:managed:*``;
#: the repository already ships ``atlas:generated:*`` in
#: :mod:`project_atlas.protected_regions` (shared with
#: :mod:`project_atlas.obsidian_projection`), and repository truth wins so a
#: single marker vocabulary -- and a single HUMAN-region merge algorithm,
#: AT-011 -- stays valid across every Atlas-written note.

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
            "<!-- BEGIN HUMAN: notes -->",
            "<!-- END HUMAN: notes -->",
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
    """Contained atomic write of a projected note (§32, §34)."""
    try:
        write_atomic_under_root(path, content, root=root, label="obsidian note directory")
    except ValueError as exc:
        raise ObsidianNoteError("PATH_ESCAPES_VAULT", str(exc)) from exc


def _reject_secret_bearing_regions(existing: str | None) -> None:
    """Refuse to carry a human-authored credential into a regenerated note."""
    if not existing:
        return
    try:
        regions = extract_human_regions(existing)
    except ProtectedRegionError:
        return  # malformed markers are reported by the merge itself
    patterns: set[str] = set()
    for block in regions.values():
        patterns.update(finding.pattern for finding in scan_text(block))
    if patterns:
        raise ObsidianNoteError(
            "SECRET_CONTENT",
            "protected region contains secret-shaped content "
            f"({', '.join(sorted(patterns))}); refusing to re-render the note.",
        )


def write_note(
    record: dict[str, Any],
    *,
    content: str,
    obsidian_root: Path,
    containment_root: Path | None = None,
    include_content: bool = True,
) -> dict[str, Any]:
    """Render and write the note, returning an ``ObsidianArtifact`` mapping.

    ``containment_root`` is the trust anchor every write must stay under. It
    is **not** always ``obsidian_root``: for Atlas's own in-vault projection
    the anchor is the Atlas vault, so a symlink planted under
    ``generated/obsidian`` cannot redefine the boundary by becoming the root
    it is checked against. It defaults to ``obsidian_root`` for an explicit,
    operator-configured external Obsidian vault, which is its own anchor.

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
    anchor = (containment_root or obsidian_root).expanduser()
    try:
        # The projection root must itself be contained by the trust anchor.
        # Self-anchoring here is what let a symlinked default root pass.
        ensure_under_root(anchor, root, label="obsidian projection root")
        resolved_root = ensure_under_root(anchor, root, label="obsidian root")
        resolved_anchor = ensure_under_root(anchor, anchor, label="obsidian anchor")
    except ValueError as exc:
        raise ObsidianNoteError("PATH_ESCAPES_VAULT", str(exc)) from exc

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
    # Fail fast, lexically. A *resolved* check here would run against a
    # directory that may not exist yet, and on Windows ``realpath`` is not
    # stable for a non-existent path whose ancestors are being created
    # concurrently (see project_atlas.capture_io). The authoritative
    # resolved check -- the one that catches a symlink or junction escape --
    # runs inside ``write_atomic_under_root`` against the materialized
    # directory, still before any content is written.
    if not is_lexically_under(resolved_root, target.parent) or not is_lexically_under(
        resolved_anchor, target.parent
    ):
        raise ObsidianNoteError(
            "PATH_ESCAPES_VAULT",
            f"unsafe obsidian note escapes root: {target}",
        )

    if target.is_symlink():
        raise ObsidianNoteError("PATH_ESCAPES_VAULT", f"note path is a symlink: {filename}")
    relative_path = "/".join((*segments, filename))
    existing: str | None = None
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
    # A re-render (``atlas capture retry``, or any second write for the same
    # capture_id) must not silently destroy content a human wrote outside the
    # generated region. AT-011 already establishes the contract for the
    # living project projection: anything wrapped in a named
    # ``<!-- BEGIN HUMAN: name --> ... <!-- END HUMAN: name -->`` block is
    # spliced back into the fresh render byte-for-byte, at the same named
    # position (or appended if the new render dropped that section). This is
    # the one merge implementation (project_atlas.protected_regions) shared
    # with obsidian_projection.py, not a second, divergent heuristic.
    #
    # A malformed marker pair in the existing file fails closed here rather
    # than risk silently dropping or misplacing human content: the retry
    # itself fails (OBSIDIAN_NOTE_CONFLICT), the raw capture is untouched,
    # and the caller can inspect and fix the note by hand before retrying.
    try:
        # A human can type a credential straight into the protected region.
        # Merging carries that block forward verbatim, so Atlas would re-persist
        # a plaintext secret into generated output on every refresh. Atlas
        # cannot unwrite what the human already saved, but it must not
        # propagate it (NFR-004 / AT-014); fail closed and leave the file alone.
        _reject_secret_bearing_regions(existing)
        rendered = _merge_protected_regions(
            existing=existing,
            rendered=rendered,
            path=relative_path,
        )
    except ProtectedRegionError as exc:
        raise ObsidianNoteError("OBSIDIAN_NOTE_CONFLICT", str(exc)) from exc
    encoded = rendered.encode("utf-8")
    # Atomic write is contained by the *anchor*: for the default projection
    # that is the Atlas vault, so a symlink under generated/obsidian cannot
    # widen the boundary it is checked against.
    _write_atomic(target, encoded, root=resolved_anchor)

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
