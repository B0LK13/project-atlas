"""Deterministic value and identity helpers for derived intelligence."""

from __future__ import annotations

_UNKNOWN_VALUES = frozenset({"unknown"})


def normalize_value(value: str, normalized_text: str | None = None) -> str:
    """Collapse whitespace and case. Prefer an already-normalized claim field."""
    raw = normalized_text if normalized_text is not None else value
    return " ".join(raw.split()).lower()


def is_unknown_value(value: str, normalized_text: str | None = None) -> bool:
    """Return True only for an explicit UNKNOWN token. Absence is not UNKNOWN."""
    return normalize_value(value, normalized_text) in _UNKNOWN_VALUES


def lineage_key(source_lineage_id: str | None, source_id: str | None) -> str:
    """Stable observation identity. Lineage wins; path is never used."""
    if source_lineage_id:
        return f"lineage:{source_lineage_id}"
    if source_id:
        return f"source:{source_id}"
    return "unknown-identity"


def group_key(project_id: str | None, subject: str, field: str) -> str:
    """Project-scoped subject+field bucket. Cross-project groups never form."""
    project = project_id or ""
    return f"{project}\x1f{subject}\x1f{field}"
