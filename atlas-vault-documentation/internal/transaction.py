"""Per-project routing transactions (AS-WP-003 Phase 8; AS-017).

Mechanism: an optimistic per-project lock file plus a rollback journal.

1. Acquire ``<project>.lock`` (O_CREAT|O_EXCL; bounded wait; stale
   locks older than ``stale_lock_seconds`` are reclaimed with a
   warning).
2. Stage every mutation in memory and validate the staged set.
3. Record original bytes (or absence) of every destination.
4. Verify expected pre-write hashes immediately before promotion.
5. Promote with atomic per-file replace; on any failure, restore
   originals from the journal so no partial project state remains.
6. Only then may the caller write the route receipt.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from internal import provenance


class LockError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class PreconditionError(RuntimeError):
    """An expected pre-write hash did not match (stale transaction)."""


class ProjectLock:
    """Bounded per-project lock file with stale recovery."""

    def __init__(self, lock_path: Path, *, stale_seconds: float = 300,
                 wait_seconds: float = 30, poll_seconds: float = 0.05) -> None:
        self.lock_path = lock_path
        self.stale_seconds = stale_seconds
        self.wait_seconds = wait_seconds
        self.poll_seconds = poll_seconds
        self.reclaimed_stale = False
        self._acquired = False

    def acquire(self) -> None:
        deadline = time.monotonic() + self.wait_seconds
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(f"pid={os.getpid()} acquired={time.time()}\n")
                self._acquired = True
                return
            except FileExistsError:
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                except FileNotFoundError:
                    # Lock released between create-fail and stat — retry.
                    continue
                if age > self.stale_seconds:
                    try:
                        self.lock_path.unlink()
                    except FileNotFoundError:
                        pass
                    self.reclaimed_stale = True
                    continue
                if time.monotonic() >= deadline:
                    raise LockError(
                        "lock-unavailable",
                        f"project lock held and not stale: {self.lock_path}",
                    )
                time.sleep(self.poll_seconds)

    def release(self) -> None:
        if self._acquired:
            self.lock_path.unlink(missing_ok=True)
            self._acquired = False

    def __enter__(self) -> "ProjectLock":
        self.acquire()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()


@dataclass
class PlannedWrite:
    """One staged file mutation."""

    path: Path
    content: str | None  # None means "ensure absent" is not supported; always str in practice
    expected_pre_sha256: str | None  # hash of the file as read during staging; None = must not exist


def _atomic_replace_bytes(path: Path, payload: bytes) -> None:
    import tempfile

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@dataclass
class Transaction:
    """Journal-backed all-or-nothing promotion of staged writes."""

    writes: list[PlannedWrite] = field(default_factory=list)
    _originals: list[tuple[Path, bytes | None]] = field(default_factory=list)

    def stage(self, path: Path, content: str, *, current: str | None) -> None:
        expected = None
        if current is not None:
            import hashlib

            expected = hashlib.sha256(current.encode("utf-8")).hexdigest()
        self.writes.append(PlannedWrite(path=path, content=content, expected_pre_sha256=expected))

    def check_preconditions(self) -> None:
        import hashlib

        for write in self.writes:
            if write.expected_pre_sha256 is None:
                if write.path.exists():
                    raise PreconditionError(
                        f"destination appeared since staging: {write.path}"
                    )
            else:
                if not write.path.is_file():
                    raise PreconditionError(
                        f"destination vanished since staging: {write.path}"
                    )
                actual = hashlib.sha256(write.path.read_bytes()).hexdigest()
                if actual != write.expected_pre_sha256:
                    raise PreconditionError(
                        f"destination modified since staging: {write.path}"
                    )

    def promote(self) -> None:
        """Write every staged file atomically; roll back on failure."""
        self.check_preconditions()
        self._originals = [
            (write.path, write.path.read_bytes() if write.path.is_file() else None)
            for write in self.writes
        ]
        promoted: list[Path] = []
        try:
            for write in self.writes:
                write.path.parent.mkdir(parents=True, exist_ok=True)
                provenance.atomic_replace(write.path, write.content or "")
                promoted.append(write.path)
        except BaseException:
            for path, original in self._originals:
                if path not in promoted:
                    continue
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_replace_bytes(path, original)
            raise
