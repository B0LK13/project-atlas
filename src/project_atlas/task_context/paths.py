"""Path containment for task-context source reads.

Uses existing Atlas path guards. Symlinks and ``..`` must not escape allowed
source roots. Never executes paths as commands.
"""

from __future__ import annotations

from pathlib import Path

from atlas_contracts.paths import resolve_under_root
from project_atlas.task_context.models import TaskContextError


def resolve_source_file(root: Path, relative: str) -> Path:
    """Resolve ``relative`` under ``root`` fail-closed."""
    try:
        return resolve_under_root(root, relative, label="source path")
    except (OSError, ValueError) as exc:
        raise TaskContextError(
            f"source path escapes or is unreadable under root: {relative}",
            code="PATH_OUTSIDE_ROOT",
        ) from exc


def read_text_under_root(
    root: Path, relative: str, *, max_bytes: int = 200_000
) -> tuple[str, bytes]:
    """Read a text file under root. Does not execute content."""
    path = resolve_source_file(root, relative)
    if not path.is_file():
        raise TaskContextError(f"missing source: {relative}", code="SOURCE_MISSING")
    # Reject symlink escape: resolved path must still be under root.
    root_resolved = root.resolve()
    try:
        path.resolve().relative_to(root_resolved)
    except ValueError as exc:
        raise TaskContextError(
            f"symlink or resolve escape: {relative}", code="PATH_SYMLINK_ESCAPE"
        ) from exc
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[:max_bytes]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return text, data
