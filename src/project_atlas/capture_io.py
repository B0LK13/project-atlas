"""AS-OBSIDIAN-CAPTURE-001 — contained atomic writes shared by the capture lane.

One implementation for both the raw evidence store and the Obsidian output
adapter, so the containment ordering and the Windows concurrency handling
cannot drift apart between them.

Windows behaviour (established by the exact-head CI matrix for this package,
run ``33956239428``; the same code passed on ubuntu-latest 3.12 and 3.13):

* ``os.path.realpath`` -- which :func:`atlas_contracts.paths.ensure_under_root`
  uses -- is **not** stable for a path that does not exist yet while another
  thread is creating its ancestors. Windows falls back to non-strict
  resolution, can leave the tail unresolved, and the result then fails the
  containment check against an otherwise-identical root. Eight concurrent
  captures produced four such spurious
  ``unsafe capture store escapes root: ...\\generated\\ops\\raw-captures``
  errors. The fix is ordering, not tolerance: the authoritative containment
  check runs on a directory that already exists, where ``realpath`` is
  deterministic and a junction/symlink still resolves out of the root and
  fails closed. Retrying a containment check until it passed would have
  masked it.
* ``os.replace`` and ``mkdir`` can transiently raise ``PermissionError``
  (WinError 5, ``Access is denied``) when another thread momentarily holds
  the destination -- observed twice in the same run. That is a scheduling
  artifact, not a different outcome, so it is retried with a small bound.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

from atlas_contracts.identity import ensure_under_root

#: Attempts for an operation that can lose a benign Windows race.
MAX_ATTEMPTS = 5
#: Base backoff; attempt N waits N * this, so worst case is 150ms.
RETRY_BACKOFF_SECONDS = 0.01


def is_lexically_under(root: Path, candidate: Path) -> bool:
    """Purely lexical containment. No filesystem access, so no race."""
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _mkdir_p(directory: Path) -> None:
    """``mkdir -p`` that tolerates a concurrent creator of the same directory."""
    for attempt in range(MAX_ATTEMPTS):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            return
        except FileExistsError:
            return
        except PermissionError:
            # Windows can report EACCES rather than EEXIST when another
            # thread is creating the same directory. If it now exists, the
            # intent is satisfied.
            if directory.is_dir():
                return
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))


def _replace(tmp: Path, path: Path) -> None:
    """``os.replace`` with a bounded retry that preserves atomicity.

    ``os.replace`` is atomic on POSIX and Windows alike: each attempt either
    replaces the destination wholly or leaves it untouched, so a retry can
    never publish a partial file. Every writer of a content-addressed path
    writes identical bytes, so a retry cannot change the published content
    either -- idempotency is preserved.
    """
    for attempt in range(MAX_ATTEMPTS):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))


def write_atomic_under_root(
    path: Path,
    content: bytes,
    *,
    root: Path,
    label: str,
) -> None:
    """Write ``content`` to ``path``, atomically, proven to stay under ``root``.

    Raises :class:`ValueError` (from ``ensure_under_root``) if the resolved
    target escapes ``root`` -- including through a pre-planted symlink or
    junction. No content is written in that case.
    """
    parent = path.parent
    # 1. Lexical check first: cheap, deterministic, and enough to guarantee we
    #    never create directories outside the root because of a constructed
    #    path bug. It cannot see symlinks, which is what step 3 is for.
    if not is_lexically_under(root, parent):
        raise ValueError(f"unsafe {label} escapes root: {path}")

    # 2. Materialize the directory so the authoritative check below runs
    #    against a stable, existing path.
    _mkdir_p(parent)

    # 3. Authoritative containment: resolves symlinks/junctions and fails
    #    closed. Runs before any content is written.
    ensure_under_root(root, parent, label=label)

    # 4. Per-writer temp name -- never a shared ``<name>.tmp``, or two
    #    concurrent writers of the same content-addressed path would race on
    #    one temp file and the loser's replace would fail with ENOENT.
    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}-{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_bytes(content)
        _replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def materialize_under_root(root: Path, relative: Path, *, label: str) -> Path:
    """Create ``root/relative`` without ever following a planted symlink.

    Each component is created (or accepted if already present) and then
    checked with ``lstat`` -- never ``realpath`` -- so the walk stops at the
    first symlinked component *before* descending through it. That ordering
    matters: a symlink at ``generated/obsidian`` would otherwise let
    ``mkdir(parents=True)`` create the leaf on the far side of the link, which
    is already a write outside the trust boundary.

    ``lstat`` is also deterministic for a path that is being created
    concurrently, unlike ``realpath`` -- so this stays safe on Windows without
    reintroducing the spurious-containment-failure class documented above.

    A final authoritative :func:`ensure_under_root` runs against the fully
    materialized directory, where resolution is stable on every platform.

    Security failures are never retried; only the benign concurrent-creation
    races inside :func:`_mkdir_p` are.
    """
    if relative.is_absolute():
        raise ValueError(f"unsafe {label}: {relative} must be vault-relative")
    current = root
    for segment in relative.parts:
        current = current / segment
        if not is_lexically_under(root, current):
            raise ValueError(f"unsafe {label} escapes root: {current}")
        _mkdir_p(current)
        if current.is_symlink():
            raise ValueError(
                f"unsafe {label} escapes root: {current} is a symlink"
            )
    return ensure_under_root(root, current, label=label)
