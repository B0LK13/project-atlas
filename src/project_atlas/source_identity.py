"""AS-ID-001 durable project and source-lineage identity primitives."""

from __future__ import annotations

import contextlib
import hashlib
import os
import re
import time
import unicodedata
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path, PurePosixPath

LINEAGE_NAMESPACE = "atlas/source-lineage/v1"
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def validate_project_uuid(value: str) -> str:
    """Validate and return an opaque RFC UUIDv4 string."""
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError, TypeError) as exc:
        raise ValueError("project_uuid must be a valid UUIDv4") from exc
    if parsed.version != 4 or parsed.variant != uuid.RFC_4122:
        raise ValueError("project_uuid must be a valid UUIDv4")
    return str(parsed)


def production_project_uuid() -> str:
    """Generate the one-time production project UUID candidate."""
    return str(uuid.uuid4())


def canonicalize_project_path(value: str) -> str:
    """Canonicalize a project-relative path independently of host semantics."""
    if not isinstance(value, str) or not value:
        raise ValueError("source path must be a non-empty project-relative string")
    normalized = unicodedata.normalize("NFC", value.replace("\\", "/"))
    if normalized.startswith("/") or _DRIVE_PREFIX.match(normalized):
        raise ValueError(f"source path must be project-relative: {value!r}")
    parts = PurePosixPath(normalized).parts
    if not parts or any(part in {".", ".."} for part in parts):
        raise ValueError(f"source path contains forbidden path segment: {value!r}")
    if any(not part for part in parts):
        raise ValueError(f"source path contains an empty path segment: {value!r}")
    return "/".join(parts)


def sha256_bytes(payload: bytes) -> str:
    """Hash already-read bytes without changing their content."""
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    """Stream a source file's original bytes into SHA-256."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lineage_id(
    project_uuid: str,
    canonical_first_seen_path: str,
    first_content_sha256: str,
    lineage_generation: int,
) -> str:
    """Derive the amended source-lineage identifier formula."""
    project_uuid = validate_project_uuid(project_uuid)
    path = canonicalize_project_path(canonical_first_seen_path)
    if not re.fullmatch(r"[0-9a-f]{64}", first_content_sha256):
        raise ValueError("first_content_sha256 must be a lowercase SHA-256 digest")
    if not isinstance(lineage_generation, int) or isinstance(lineage_generation, bool):
        raise ValueError("lineage_generation must be a positive integer")
    if lineage_generation < 1:
        raise ValueError("lineage_generation must be a positive integer")
    material = "|".join(
        (LINEAGE_NAMESPACE, project_uuid, path, first_content_sha256, str(lineage_generation))
    )
    return "sline-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


class IdentityLockError(RuntimeError):
    """Raised when the project identity guard cannot be acquired."""


class ProjectIdentityLock:
    """Minimal Core-local cross-process guard for genesis and migration."""

    def __init__(
        self,
        path: Path,
        *,
        wait_seconds: float = 30.0,
        stale_seconds: float = 300.0,
        poll_seconds: float = 0.05,
    ) -> None:
        self.path = path
        self.wait_seconds = wait_seconds
        self.stale_seconds = stale_seconds
        self.poll_seconds = poll_seconds
        self._acquired = False

    def acquire(self) -> None:
        deadline = time.monotonic() + self.wait_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(f"pid={os.getpid()}\n")
                self._acquired = True
                return
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > self.stale_seconds:
                    with contextlib.suppress(FileNotFoundError):
                        self.path.unlink()
                    continue
                if time.monotonic() >= deadline:
                    raise IdentityLockError(f"identity lock is held: {self.path}") from None
                time.sleep(self.poll_seconds)
            except OSError as exc:
                raise IdentityLockError(f"cannot acquire identity lock: {self.path}") from exc

    def release(self) -> None:
        if self._acquired:
            with contextlib.suppress(FileNotFoundError):
                self.path.unlink()
            self._acquired = False

    def __enter__(self) -> ProjectIdentityLock:
        self.acquire()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()


ProjectUuidProvider = Callable[[], str]


@contextlib.contextmanager
def identity_lock(path: Path) -> Iterator[ProjectIdentityLock]:
    """Convenience context for a project-scoped identity guard."""
    with ProjectIdentityLock(path) as lock:
        yield lock
