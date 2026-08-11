"""Shared identity helpers; implementations remain subsystem-owned."""

from __future__ import annotations

# CODEX-SEC-004/014/017/018: single canonical implementation lives in paths.py.
from atlas_contracts.paths import (
    ensure_under_root,
    join_under_root,
    resolve_under_root,
    safe_relative_component,
    safe_relative_path,
)

__all__ = [
    "ensure_under_root",
    "join_under_root",
    "resolve_under_root",
    "safe_relative_component",
    "safe_relative_path",
]
