#!/usr/bin/env python3
"""Shared Atlas Cursor hook bootstrap. No routing or owner policy."""

from __future__ import annotations

import sys
from pathlib import Path

HOOK_ADAPTER_VERSION = "D081-1"


def repository_root() -> Path:
    """Repo root from this file path. Hook cwd is not assumed to be the root."""
    return Path(__file__).resolve().parents[2]


def bind_worktree_src() -> tuple[Path, Path]:
    """Force current worktree ``src`` ahead of any installed Project Atlas."""
    root = repository_root()
    src = (root / "src").resolve()
    for name in list(sys.modules):
        if name == "project_atlas" or name.startswith("project_atlas."):
            del sys.modules[name]
    src_key = str(src)
    sys.path[:] = [entry for entry in sys.path if _resolved(entry) != src]
    sys.path.insert(0, src_key)
    return root, src


def _resolved(entry: str) -> Path | None:
    try:
        return Path(entry).resolve()
    except OSError:
        return None


def module_root_match(module_file: str, src: Path) -> bool:
    try:
        Path(module_file).resolve().relative_to(src)
    except ValueError:
        return False
    return True
