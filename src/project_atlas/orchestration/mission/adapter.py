"""AS-MISSION-VERTICAL-SLICE-001, DEVELOPMENT -- the agent-adapter
boundary: one real, bounded reference implementation, not a mock, so the
diff/test evidence this produces is genuinely inspectable.

`MissionAdapter` is intentionally minimal (one method, one result shape)
so a future real coding-agent adapter (ACP-based or otherwise) can satisfy
it without this package needing to know anything about that adapter's own
internals -- this is the seam, not the implementation of every adapter
Atlas might eventually have.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass(frozen=True)
class AdapterResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    duration_sec: float
    command_repr: str


class MissionAdapter(Protocol):
    """One real unit of work, run inside an already-isolated workspace."""

    def run(self, *, workspace: Path, timeout_sec: float) -> AdapterResult: ...


@dataclass(frozen=True)
class ShellCommandAdapter:
    """Reference adapter: runs one bounded shell command inside the
    workspace. Real subprocess, real exit code, real stdout/stderr --
    genuinely inspectable evidence, not a simulation. Every invocation
    uses `no_window_creationflags`-equivalent behavior on Windows (no
    visible console window) and is bounded by `timeout_sec`, matching the
    discipline established throughout this session's own subprocess work.
    """

    command: tuple[str, ...]

    def run(self, *, workspace: Path, timeout_sec: float) -> AdapterResult:
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                list(self.command),
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
                creationflags=_NO_WINDOW,
            )
            duration = time.perf_counter() - start
            return AdapterResult(
                ok=proc.returncode == 0,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_sec=duration,
                command_repr=" ".join(self.command),
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - start
            return AdapterResult(
                ok=False,
                returncode=-1,
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr=f"TIMEOUT after {timeout_sec}s",
                duration_sec=duration,
                command_repr=" ".join(self.command),
            )
