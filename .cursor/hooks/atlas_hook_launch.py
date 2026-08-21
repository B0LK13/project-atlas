#!/usr/bin/env python3
"""Deterministic Atlas hook interpreter launcher.

Repo-relative only. No machine-specific absolute paths are embedded.
Prefers a repository venv when present, then the current interpreter.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_TARGETS = {
    "stop": "atlas_stop.py",
    "before-submit": "atlas_before_submit.py",
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def select_python(root: Path) -> Path:
    candidates = (
        root / ".venv-win" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        Path(sys.executable),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return Path(sys.executable)


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in _TARGETS:
        print("atlas_hook_launch: expected stop|before-submit", file=sys.stderr)
        return 2
    root = repository_root()
    target = Path(__file__).resolve().parent / _TARGETS[argv[1]]
    python = select_python(root)
    os.execv(str(python), [str(python), str(target), *argv[2:]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
