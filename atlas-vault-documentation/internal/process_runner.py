"""Untrusted external process execution (AS-WP-002, Priority 1).

mda-cli is an external dependency that can fail in arbitrary ways. This
module runs it with explicit argument arrays (never a shell), enforces
timeouts, captures output with secret redaction, and classifies every
failure into a small, structured taxonomy instead of leaking raw
exceptions.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

#: Failure categories emitted by :func:`run_command`.
CATEGORY_EXECUTABLE_MISSING = "executable-missing"
CATEGORY_PERMISSION_DENIED = "permission-denied"
CATEGORY_TIMEOUT = "timeout"
CATEGORY_PROCESS_FAILED = "process-failed"


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
        [executable, "--version"], timeout_seconds=timeout_seconds, redact=redact
    )
    if result.ok and result.stdout.strip():
        return result.stdout.strip().splitlines()[0][:200]
    return "unknown"
