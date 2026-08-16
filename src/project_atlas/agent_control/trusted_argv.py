"""Trusted executable argv construction (shared launch identity).

This is the single ``resolve_executable_argv`` implementation used by:

- MDA version probing (``project_atlas.agent_control.runtime``)
- MDA normalization execution (``internal.process_runner``)

It does **not** grant execution authority. Callers must authorize the
command first. A shebang never grants authority by itself.

TRUSTED_EXECUTABLE_ARGV_IMPLEMENTATIONS = 1
ARBITRARY_SHEBANG_INTERPRETER_EXECUTION = NO
PYTHON_SHELL_TRUE = NO
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_executable_argv(command: str) -> list[str]:
    """Return argv for an *already-authorized* ``command``.

    Absolute Python shebang scripts are wrapped with ``sys.executable`` for
    Win32 compatibility. Relative paths, path traversal, and unexpected
    interpreter substitution are refused here as defense in depth.
    """
    if not command or command != command.strip() or "\x00" in command:
        raise ValueError(f"refusing unsafe executable command: {command!r}")
    if command.startswith((".", "~")) or ".." in Path(command).parts:
        raise ValueError(f"refusing relative/traversing executable: {command!r}")
    is_absolute = os.path.isabs(command) or command.startswith("/")
    if not is_absolute and ("/" in command or "\\" in command):
        raise ValueError(f"refusing non-absolute path-shaped executable: {command!r}")

    path = Path(command)
    if not path.is_file():
        return [command]
    try:
        first = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
    except OSError:
        return [command]
    if not first or not first[0].startswith("#!"):
        return [command]
    shebang = first[0]
    lowered = shebang.lower()
    if "python" not in lowered:
        # Unexpected interpreter: do not substitute an alternate runtime.
        return [command]
    body = shebang[2:].strip().split()
    if not body:
        return [command]
    interpreter_name = Path(body[0]).name.lower()
    if interpreter_name == "env":
        if len(body) < 2 or not Path(body[1]).name.lower().startswith("python"):
            raise ValueError(f"refusing unexpected env interpreter shebang: {shebang!r}")
    elif not interpreter_name.startswith("python"):
        raise ValueError(f"refusing unexpected interpreter shebang: {shebang!r}")
    return [sys.executable, str(path.resolve())]
