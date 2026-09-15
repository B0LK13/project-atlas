"""Untrusted external process execution (AS-WP-002, Priority 1).

mda-cli is an external dependency that can fail in arbitrary ways. This
module runs it with explicit argument arrays (never a shell), enforces
timeouts, captures output with secret redaction, and classifies every
failure into a small, structured taxonomy instead of leaking raw
exceptions.

CODEX-SEC-021: ``shell=False`` is mandatory but not sufficient. Callers that
select a normalizer executable must authorize it through
``internal.trusted_exec`` before building argv. :func:`resolve_executable_argv`
only performs shebang wrapping for already-authorized absolute script paths;
it does not grant execution authority.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

#: Failure categories emitted by :func:`run_command`.
CATEGORY_EXECUTABLE_MISSING = "executable-missing"
CATEGORY_PERMISSION_DENIED = "permission-denied"
CATEGORY_TIMEOUT = "timeout"
CATEGORY_PROCESS_FAILED = "process-failed"


def resolve_executable_argv(command: str) -> list[str]:
    """Return argv for an *already-authorized* ``command``.

    Absolute Python shebang scripts are wrapped with ``sys.executable`` for
    Win32 compatibility. Relative paths, path traversal, and unexpected
    interpreter substitution are refused here as defense in depth; primary
    selection policy lives in ``internal.trusted_exec`` (CODEX-SEC-021).
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


@dataclass(frozen=True)
class ProcessResult:
    """Outcome of one external command execution."""

    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    category: str | None = None  # None means the process ran successfully
    attempts: int = 1
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.category is None and self.returncode == 0


def _truncate(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"... [truncated {len(value) - limit} chars]"


def run_command(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
    redact: Callable[[str], str],
    retries: int = 0,
    retry_categories: tuple[str, ...] = (CATEGORY_TIMEOUT, CATEGORY_PROCESS_FAILED),
) -> ProcessResult:
    """Run ``argv`` (no shell) with timeout, redaction, and bounded retries.

    ``redact`` is the shared secret-redaction callable applied to all
    captured output. Retries apply only to transient categories
    (timeout, non-zero exit); missing executables and permission errors
    are never retried.
    """
    attempts = 0
    start = time.monotonic()
    while True:
        attempts += 1
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,  # mandatory; not sufficient alone (CODEX-SEC-021)
            )
        except FileNotFoundError:
            return ProcessResult(
                argv=tuple(argv), returncode=None, stdout="", stderr="",
                duration_seconds=time.monotonic() - start,
                category=CATEGORY_EXECUTABLE_MISSING, attempts=attempts,
            )
        except PermissionError:
            return ProcessResult(
                argv=tuple(argv), returncode=None, stdout="", stderr="",
                duration_seconds=time.monotonic() - start,
                category=CATEGORY_PERMISSION_DENIED, attempts=attempts,
            )
        except subprocess.TimeoutExpired:
            result = ProcessResult(
                argv=tuple(argv), returncode=None, stdout="", stderr="",
                duration_seconds=time.monotonic() - start,
                category=CATEGORY_TIMEOUT, attempts=attempts,
            )
        except OSError as exc:
            # Unexpected OS-level failure: sanitize the message.
            return ProcessResult(
                argv=tuple(argv), returncode=None, stdout="",
                stderr=redact(str(exc)),
                duration_seconds=time.monotonic() - start,
                category=CATEGORY_PROCESS_FAILED, attempts=attempts,
                extra={"os_error": type(exc).__name__},
            )
        else:
            category = None if completed.returncode == 0 else CATEGORY_PROCESS_FAILED
            result = ProcessResult(
                argv=tuple(argv),
                returncode=completed.returncode,
                stdout=redact(_truncate(completed.stdout or "")),
                stderr=redact(_truncate(completed.stderr or "")),
                duration_seconds=time.monotonic() - start,
                category=category,
                attempts=attempts,
            )
        if result.category not in retry_categories or attempts > retries:
            return result


def command_version(
    executable: str, *, timeout_seconds: float, redact: Callable[[str], str]
) -> str:
    """Best-effort ``<executable> --version`` probe; never raises."""
    result = run_command(
        [*resolve_executable_argv(executable), "--version"],
        timeout_seconds=timeout_seconds,
        redact=redact,
    )
    if result.ok and result.stdout.strip():
        return result.stdout.strip().splitlines()[0][:200]
    return "unknown"
