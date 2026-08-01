"""Project marker and conservative exclusion rules."""

from __future__ import annotations

from pathlib import Path

DEFAULT_MARKERS = (".atlas-project.yaml", ".git", "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "README.md")
DEFAULT_EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".next", "dist", "build",
    "target", "coverage", "vendor", "tmp", "temp", ".cache", ".tmp",
}


def has_marker(path: Path, markers: tuple[str, ...] = DEFAULT_MARKERS) -> bool:
    return any((path / marker).exists() for marker in markers)


def is_excluded_dir(name: str) -> bool:
    return name in DEFAULT_EXCLUDED_DIRS
