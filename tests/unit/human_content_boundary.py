"""A runtime integrity boundary for operator-owned bytes.

AS-OBSIDIAN-CAPTURE-001-F18. Support module, not a test module.

**Why this exists.** F16 derives the set of modules that can splice human regions
by reading imports. Its own adversarial work proved that set is not closed: a
hand-rolled splice using ``Path.read_bytes`` and its own regex reaches operator
bytes while naming none of the protected-region primitives, and no import-graph
analysis can see it. `STATIC_DISCOVERY != ARCHITECTURAL_ENFORCEMENT`.

**The architectural observation this rests on.** However a writer computes its
content, the destination path receives bytes through a very small set of
OS-level primitives. Every note writer in this repository lands its payload via
``os.replace(tmp, dest)``; direct writes go through ``Path.write_bytes`` or
``Path.write_text``. Those are chokepoints in the *operating system interface*,
not in Atlas's import graph, so a check installed there is **independent of how
the writer is spelled** -- renamed imports, re-exports, dynamic imports, wrappers
and hand-rolled splices all arrive at the same place.

**What is checked.** Not the route -- the outcome. On every write to a path that
*already contains* human regions, the regions in the new content must be
byte-identical to the regions in the old. A writer may reach that outcome through
``merge_protected_regions`` or by any other means; what it may not do is succeed
while silently altering bytes the operator owns.

    SUCCESSFUL_WRITE != AUTHORITY_TO_REWRITE_HUMAN_BYTES

**What this is not.** It is not a production guard: it is installed by tests, so
it observes writes that tests actually execute. A production code path never
exercised by any test is outside it. That boundary is stated exactly rather than
implied away, and :mod:`test_as_obsidian_capture_001_f18_write_boundary` records
the residual classes it cannot see.
"""

from __future__ import annotations

import builtins
import contextlib
import os
import pathlib
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from human_content_attribution import AttributionLedger

from project_atlas.protected_regions import (
    ProtectedRegionError,
    extract_human_regions,
)

#: The marker that makes a note "human-protected". A file without it is not
#: something this boundary has any opinion about.
HUMAN_MARKER = b"<!-- BEGIN HUMAN:"


@dataclass
class Violation:
    """A write that altered operator-owned bytes."""

    path: str
    primitive: str
    before: dict[str, str]
    after: dict[str, str]
    stack: str
    #: The file that invoked the write primitive, as a repo-relative-ish path.
    origin: str = ""

    @property
    def landed_via_atlas_helper(self) -> bool:
        """Did the bytes reach disk through an Atlas helper, or directly?

        **This is plumbing, not responsibility, and must never be used as a
        gate.** An earlier revision called this `from_atlas` and the session-wide
        hook failed the run on it. That was wrong, and measuring it both ways is
        what showed the error:

            a caller handing already-damaged bytes to `capture_io`
                -> innermost frame is `src/project_atlas/capture_io.py`
            a caller writing the same damaged bytes directly
                -> innermost frame is the caller

        Both are the same act with different plumbing. The innermost non-boundary
        frame identifies whichever helper landed the bytes -- an atomic writer
        has no preservation duty, it writes what it is given -- so this cannot
        say who authored the damage. It is kept only to make a report readable.
        """
        return f"{os.sep}src{os.sep}project_atlas{os.sep}" in self.origin

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        who = "via atlas helper" if self.landed_via_atlas_helper else "direct"
        lost = sorted(set(self.before) - set(self.after))
        changed = sorted(
            k for k in set(self.before) & set(self.after) if self.before[k] != self.after[k]
        )
        return (
            f"[{who}] {self.primitive} -> {self.path}: "
            f"regions lost={lost} changed={changed}\n"
            f"{self.stack}"
        )


@dataclass
class HumanContentBoundary:
    """Intercepts the OS primitives through which note bytes reach disk."""

    violations: list[Violation] = field(default_factory=list)
    checked: int = 0
    protected_writes: int = 0
    #: F19. Every protected write is classified against the lease bound to the
    #: execution that made it, so the boundary reports *who* alongside *what*.
    ledger: AttributionLedger = field(default_factory=AttributionLedger)
    _saved: dict[str, Any] = field(default_factory=dict)
    _suppressed: list[str] = field(default_factory=list)
    #: fd -> (path, regions-before), for writes that never touch `pathlib`.
    _open_fds: dict[int, tuple[str, dict[str, str]]] = field(default_factory=dict)

    # ---------------------------------------------------------------- checking
    @staticmethod
    def _regions(raw: bytes) -> dict[str, str] | None:
        if HUMAN_MARKER not in raw:
            return None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
        try:
            found = extract_human_regions(text)
        except (ProtectedRegionError, ValueError):
            # A prior note whose markers do not parse has no regions this
            # boundary can claim to protect. The writers' own refusal path
            # covers that case; inventing an opinion here would produce
            # violations for documents Atlas already declines to merge.
            return None
        return {"/".join(k): v for k, v in found.items()} or None

    def _check(self, primitive: str, dest: Any, new_bytes: bytes | None) -> None:
        if self._suppressed:
            return
        try:
            path = pathlib.Path(dest)
            if not path.is_file():
                return
            before_raw = path.read_bytes()
        except (OSError, ValueError, TypeError):
            return
        before = self._regions(before_raw)
        if before is None:
            return
        self.protected_writes += 1
        if new_bytes is None:
            return
        self.checked += 1
        after = self._regions(new_bytes) or {}
        altered = after != before
        # Recorded for *every* protected write, not only damaging ones: the
        # governance question is which execution touched operator content at
        # all, and a clean write under an unauthorized lease is still a
        # finding.
        self.ledger.record(path, primitive, altered=altered)
        if altered:
            self.violations.append(self._violation(primitive, str(path), before, after))

    def _before(self, dest: Any) -> dict[str, str] | None:
        """The protected regions on disk right now, or `None` if unprotected."""
        try:
            path = pathlib.Path(dest)
            if not path.is_file():
                return None
            return self._regions(path.read_bytes())
        except (OSError, ValueError, TypeError):
            return None

    def _check_landed(self, primitive: str, dest: Any, before: dict[str, str] | None) -> None:
        """Compare against what is on disk AFTER the write.

        Stronger than inspecting the payload, because it cannot be fooled by
        anything the write layer does to the bytes on the way down -- newline
        translation being the case that was actually missed.
        """
        if self._suppressed or before is None:
            return
        self.protected_writes += 1
        self.checked += 1
        try:
            after = self._regions(pathlib.Path(dest).read_bytes()) or {}
        except (OSError, ValueError, TypeError):
            return
        altered = after != before
        self.ledger.record(pathlib.Path(dest), primitive, altered=altered)
        if altered:
            self.violations.append(self._violation(primitive, str(dest), before, after))

    def _violation(
        self, primitive: str, path: str, before: dict[str, str], after: dict[str, str]
    ) -> Violation:
        frames = [f for f in traceback.extract_stack()[:-1] if __file__ not in f.filename]
        return Violation(
            path=path,
            primitive=primitive,
            before=before,
            after=after,
            stack="".join(traceback.format_stack(limit=12)[:-2]),
            origin=frames[-1].filename if frames else "",
        )

    # ------------------------------------------------------------- installation
    def install(self) -> None:
        if self._saved:
            raise RuntimeError("boundary already installed")
        boundary = self
        self._saved = {
            "os.replace": os.replace,
            "os.rename": os.rename,
            "os.open": os.open,
            "os.close": os.close,
            "os.fdopen": os.fdopen,
            "builtins.open": builtins.open,
            "Path.write_bytes": pathlib.Path.write_bytes,
            "Path.write_text": pathlib.Path.write_text,
        }
        real = self._saved

        def replace(src: Any, dst: Any, *a: Any, **k: Any) -> Any:
            try:
                payload = pathlib.Path(src).read_bytes()
            except (OSError, ValueError, TypeError):
                payload = None
            boundary._check("os.replace", dst, payload)
            return real["os.replace"](src, dst, *a, **k)

        def rename(src: Any, dst: Any, *a: Any, **k: Any) -> Any:
            try:
                payload = pathlib.Path(src).read_bytes()
            except (OSError, ValueError, TypeError):
                payload = None
            boundary._check("os.rename", dst, payload)
            return real["os.rename"](src, dst, *a, **k)

        def write_bytes(self: pathlib.Path, data: Any) -> Any:
            boundary._check("Path.write_bytes", self, bytes(data))
            return real["Path.write_bytes"](self, data)

        def write_text(self: pathlib.Path, data: str, *a: Any, **k: Any) -> Any:
            # Text mode is NOT byte-transparent: it translates newlines to the
            # platform ending, so the payload handed in here is not what lands
            # on disk. Checking the payload alone missed exactly that damage --
            # a translating write rewrites operator line endings while every
            # word still matches. So capture the prior regions, do the write,
            # then compare against the bytes that actually landed.
            before = boundary._before(self)
            result = real["Path.write_text"](self, data, *a, **k)
            boundary._check_landed("Path.write_text", self, before)
            return result

        def os_open(path: Any, flags: int, *a: Any, **k: Any) -> int:
            # A raw descriptor bypasses `pathlib` AND `os.replace`, so the write
            # is invisible to every other hook here. Capture the prior regions at
            # open time and compare when the descriptor closes -- the only point
            # at which the resulting bytes are on disk and attributable.
            before: dict[str, str] | None = None
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_TRUNC | os.O_APPEND):
                try:
                    target = pathlib.Path(path)
                    if target.is_file():
                        before = boundary._regions(target.read_bytes())
                except (OSError, ValueError, TypeError):
                    before = None
            fd = real["os.open"](path, flags, *a, **k)
            if before is not None:
                boundary._open_fds[fd] = (str(path), before)
            return fd  # type: ignore[no-any-return]

        def _verify_fd(fd: int) -> None:
            entry = boundary._open_fds.pop(fd, None)
            if entry is None or boundary._suppressed:
                return
            path_str, before = entry
            boundary.protected_writes += 1
            boundary.checked += 1
            try:
                after_raw = pathlib.Path(path_str).read_bytes()
            except OSError:
                return
            after = boundary._regions(after_raw) or {}
            if after != before:
                boundary.violations.append(
                    boundary._violation("raw file descriptor", path_str, before, after)
                )

        def os_fdopen(fd: int, *a: Any, **k: Any) -> Any:
            # `os.fdopen` closes the descriptor at the C level, so the patched
            # `os.close` never runs. The check has to hang off the returned
            # file object instead. The fd -> path map comes from `os_open`
            # above, so this stays portable -- an earlier attempt used
            # /proc/self/fd, which would have worked on Linux CI and silently
            # not on the Windows job.
            handle = real["os.fdopen"](fd, *a, **k)
            if fd not in boundary._open_fds:
                return handle
            inner_close = handle.close

            def close(*ca: Any, **ck: Any) -> Any:
                result = inner_close(*ca, **ck)
                _verify_fd(fd)
                return result

            handle.close = close
            return handle

        def os_close(fd: int) -> None:
            real["os.close"](fd)
            _verify_fd(fd)

        def builtin_open(file: Any, mode: str = "r", *a: Any, **k: Any) -> Any:
            # The last route, and the one that closes `shutil.copyfile` with it,
            # since that opens the destination itself. Hooked only for write
            # modes and only when the target already carries human regions, so
            # the overwhelming majority of opens in a test run pay one `"r" in
            # mode` check and nothing else.
            if boundary._suppressed or not any(c in mode for c in "wax+"):
                return real["builtins.open"](file, mode, *a, **k)
            before: dict[str, str] | None = None
            path_str: str | None = None
            try:
                target = pathlib.Path(file)
                if target.is_file():
                    before = boundary._regions(target.read_bytes())
                    path_str = str(target)
            except (OSError, ValueError, TypeError):
                before = None
            handle = real["builtins.open"](file, mode, *a, **k)
            if before is None or path_str is None:
                return handle
            boundary.protected_writes += 1
            inner_close = handle.close

            def close(*ca: Any, **ck: Any) -> Any:
                result = inner_close(*ca, **ck)
                if boundary._suppressed:
                    return result
                boundary.checked += 1
                try:
                    after_raw = pathlib.Path(path_str).read_bytes()
                except OSError:
                    return result
                after = boundary._regions(after_raw) or {}
                if after != before:
                    boundary.violations.append(
                        boundary._violation(f"open(mode={mode!r})", path_str, before, after)
                    )
                return result

            with contextlib.suppress(AttributeError):  # exotic file objects
                handle.close = close
            return handle

        builtins.open = builtin_open
        os.open = os_open
        os.fdopen = os_fdopen
        os.close = os_close
        os.replace = replace
        os.rename = rename
        pathlib.Path.write_bytes = write_bytes  # type: ignore[method-assign]
        pathlib.Path.write_text = write_text  # type: ignore[method-assign]

    def uninstall(self) -> None:
        if not self._saved:
            return
        builtins.open = self._saved["builtins.open"]
        os.open = self._saved["os.open"]
        os.fdopen = self._saved["os.fdopen"]
        os.close = self._saved["os.close"]
        os.replace = self._saved["os.replace"]
        os.rename = self._saved["os.rename"]
        pathlib.Path.write_bytes = self._saved["Path.write_bytes"]  # type: ignore[method-assign]
        pathlib.Path.write_text = self._saved["Path.write_text"]  # type: ignore[method-assign]
        self._saved = {}

    # ---------------------------------------------------------------- exceptions
    @contextmanager
    def authorized(self, reason: str) -> Iterator[None]:
        """An explicitly authorised rewrite of operator bytes.

        This is how an exception is *represented*: a named reason, scoped to a
        block, recorded rather than silent. A test that deliberately corrupts a
        protected note in order to prove a guard fires uses this; production code
        should never need it.
        """
        if not reason.strip():
            raise ValueError("an authorised rewrite must state a reason")
        self._suppressed.append(reason)
        try:
            yield
        finally:
            self._suppressed.pop()


@contextmanager
def enforced() -> Iterator[HumanContentBoundary]:
    """Install the boundary for the duration of the block."""
    boundary = HumanContentBoundary()
    boundary.install()
    try:
        yield boundary
    finally:
        boundary.uninstall()
