"""Provenance for normalized agent work events (AS-WP-002, Priority 2).

Every normalized document must answer, automatically:

- which raw event produced it (ID + SHA-256);
- which command, arguments, skill, and provider produced it;
- which output mode was used;
- whether the output was verified, and when.

Provenance is injected into the normalized document's YAML frontmatter
as an ``atlas_provenance`` block. Raw events are never modified.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

PROVENANCE_SCHEMA_VERSION = 1
NORMALIZATION_VERSION = "as-wp-002.1"

_CHUNK = 1024 * 1024


def sha256_file(path: str | Path) -> str:
    """Streaming SHA-256 of a file (never loads it fully into memory)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:  # noqa: PTH123 - explicit binary stream
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Provenance:
    """Verifiable provenance metadata for one normalized document."""

    raw_event_id: str
    raw_event_hash: str
    normalized_at: str
    tool: str
    command_version: str
    command_arguments: tuple[str, ...] | None  # None when record_command=false
    skill: str
    provider: str
    output_mode: str
    verification_status: str
    verified_at: str | None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "normalization_version": NORMALIZATION_VERSION,
            "raw_event_id": self.raw_event_id,
            "raw_event_hash": f"sha256:{self.raw_event_hash}",
            "normalized_at": self.normalized_at,
            "tool": self.tool,
            "command_version": self.command_version,
            "skill": self.skill,
            "provider": self.provider,
            "output_mode": self.output_mode,
            "verification_status": self.verification_status,
        }
        if self.command_arguments is not None:
            data["command_arguments"] = json.dumps(list(self.command_arguments))
        if self.verified_at is not None:
            data["verified_at"] = self.verified_at
        return data


def render_provenance_block(provenance: Provenance) -> str:
    """Render provenance as YAML frontmatter lines (two-level subset)."""
    lines = ["atlas_provenance:"]
    for key, value in provenance.as_dict().items():
        if isinstance(value, int):
            lines.append(f"  {key}: {value}")
        else:
            lines.append(f"  {key}: {json.dumps(str(value), ensure_ascii=False)}")
    return "\n".join(lines)


def split_document(text: str) -> tuple[str, str]:
    """Split a Markdown document into (frontmatter, body).

    Raises :class:`ValueError` when the frontmatter is missing or
    unterminated. Handles an optional outer four-backtick fence
    (mda-cli output convention) by stripping it first.
    """
    stripped = text.strip("\n")
    if stripped.startswith("````"):
        first_newline = stripped.find("\n")
        last_fence = stripped.rfind("\n````")
        if first_newline > 0 and last_fence > first_newline:
            stripped = stripped[first_newline + 1 : last_fence].strip("\n")
    if not stripped.startswith("---\n"):
        raise ValueError("normalized output missing YAML frontmatter")
    end = stripped.find("\n---\n", 4)
    if end < 0:
        if stripped.endswith("\n---"):
            end = len(stripped) - 4
        else:
            raise ValueError("normalized output has unterminated YAML frontmatter")
    return stripped[4:end], stripped[end + 5 :]


def inject_provenance(text: str, provenance: Provenance) -> str:
    """Return ``text`` with the provenance block added to its frontmatter.

    Any existing ``atlas_provenance`` block is replaced so re-runs stay
    idempotent. The four-backtick wrapper, if present, is stripped:
    the stored artifact is plain Markdown.
    """
    frontmatter, body = split_document(text)
    kept = []
    skip = False
    for line in frontmatter.splitlines():
        if line.startswith("atlas_provenance:"):
            skip = True
            continue
        if skip and (line.startswith(" ") or line.startswith("-")):
            continue
        skip = False
        kept.append(line)
    new_frontmatter = "\n".join(kept) + "\n" + render_provenance_block(provenance)
    return f"---\n{new_frontmatter}\n---\n{body}"


def atomic_replace(path: str | Path, content: str) -> None:
    """Atomically replace ``path`` with ``content`` (temp file + rename)."""
    import os
    import tempfile
    target = Path(path)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
