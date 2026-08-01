"""Protected Atlas paths that agents must not mutate directly."""

from __future__ import annotations

from pathlib import Path


PROTECTED_PREFIXES = ("projects/", "routing/state/", "routing/receipts/", "relationships/state/", "relationships/edges/", "relationships/nodes/")


def is_protected(relative_path: str) -> bool:
    normalized = Path(relative_path).as_posix()
    return any(normalized.startswith(prefix) for prefix in PROTECTED_PREFIXES)
