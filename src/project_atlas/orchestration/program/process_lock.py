"""TAKEOVER-001: OS-owned exclusion, released on process exit, never PID reuse."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from project_atlas.orchestration.program.models import ProgramError
from project_atlas.orchestration.program.path_safety import checked_path


class ProcessLockError(ProgramError):
    code = "PROCESS_ALREADY_OWNED"


@contextmanager
def exclusive_process_lock(path: Path) -> Iterator[None]:
    """Keep the lock inode: unlinking it would allow two distinct owners."""
    target = checked_path(path)
    checked_path(target.parent).mkdir(parents=True, exist_ok=True)
    fd = os.open(checked_path(target), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        try:
            if os.name == "nt":
                import msvcrt

                # Lock a byte without changing file contents or truncating it.
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ProcessLockError("process root is already owned or cannot be locked") from exc
        yield
    finally:
        os.close(fd)
