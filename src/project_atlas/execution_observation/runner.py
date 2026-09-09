"""Bounded, shell-free command execution for live observation (ULT-01b-1).

Every observation subprocess goes through here:

- argv list only, ``shell=False``, ``stdin`` closed, bounded ``timeout``;
- the child environment is **constructed from nothing** — a short pass-through
  list plus fixed locale/git knobs — so ``GIT_DIR``, ``GIT_WORK_TREE``,
  ``GIT_CONFIG_*`` or any other inherited variable cannot redirect what is
  observed, no inherited value can leak into a receipt, and the operator's
  global/system git configuration is disabled (``GIT_CONFIG_GLOBAL`` →
  ``os.devnull``, ``GIT_CONFIG_NOSYSTEM=1``) so ``insteadOf`` rewrites or
  ``core.fsmonitor`` commands cannot shape an observation;
- stdout is captured as bytes, decoded with replacement and capped; stderr is
  discarded (it may echo paths or URLs and is never evidence);
- the executable is resolved to an absolute regular file; on Windows only an
  ``.exe`` is accepted (``.cmd``/``.bat`` wrappers could be anything).

The ``CommandRunner`` protocol is the injection seam tests use: a fixture
runner returns scripted ``CommandResult``s and never touches a process.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

DEFAULT_TIMEOUT_SECONDS: Final[float] = 10.0
MAX_STDOUT_BYTES: Final[int] = 65_536
PASSTHROUGH_ENV: Final[tuple[str, ...]] = (
    "PATH",
    "HOME",
    "USERPROFILE",
    "SystemRoot",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "TMPDIR",
)
FIXED_ENV: Final[dict[str, str]] = {
    "LC_ALL": "C",
    "LANG": "C",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
    # Git reads its configuration files exactly as it would for the operator:
    # content interpretation (core.autocrlf, core.symlinks, safe.directory,
    # ...) is part of how git sees a checkout, and bypassing it made honest
    # Windows checkouts look dirty. What configuration must NOT do is execute
    # a command or rewrite the identity: core.fsmonitor is pinned off here
    # (environment config overrides every file level), the remote is read raw
    # (git.py), and bound content filters are refused before `git status`.
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "core.fsmonitor",
    "GIT_CONFIG_VALUE_0": "false",
}
WINDOWS_EXECUTABLE_SUFFIX: Final[str] = ".exe"


class ObservationError(ValueError):
    """Fail-closed observation error with a stable ``code``. Never echoes values."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    timed_out: bool = False


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult: ...


def build_child_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Construct the child environment: pass-through list + fixed knobs, nothing else."""
    source = os.environ if environ is None else environ
    child: dict[str, str] = {}
    for key in PASSTHROUGH_ENV:
        value = source.get(key)
        if value is not None and "\x00" not in value:
            child[key] = value
    child.update(FIXED_ENV)
    return child


def _creationflags(os_name: str) -> int:
    if os_name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


class SubprocessRunner:
    """The only place observation code launches a process."""

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        os_name: str | None = None,
    ) -> None:
        self._env = build_child_env(environ)
        self._os_name = os.name if os_name is None else os_name

    def run(self, argv: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        if not argv or any(not isinstance(part, str) or "\x00" in part for part in argv):
            raise ObservationError("ARGV_INVALID", "argv must be non-empty NUL-free strings")
        if not (0 < timeout <= 60):
            raise ObservationError("TIMEOUT_INVALID", "timeout must be within (0, 60] seconds")
        try:
            completed = subprocess.run(
                list(argv),
                cwd=str(cwd),
                env=self._env,
                capture_output=True,
                timeout=timeout,
                check=False,
                shell=False,
                stdin=subprocess.DEVNULL,
                creationflags=_creationflags(self._os_name),
            )
        except subprocess.TimeoutExpired:
            return CommandResult(returncode=-1, stdout="", timed_out=True)
        except OSError as exc:
            raise ObservationError(
                "EXECUTABLE_UNAVAILABLE", "the observation executable could not be launched"
            ) from exc
        raw = completed.stdout[:MAX_STDOUT_BYTES] if completed.stdout else b""
        return CommandResult(
            returncode=int(completed.returncode),
            stdout=raw.decode("utf-8", errors="replace"),
        )


def resolve_executable(
    name: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    os_name: str | None = None,
) -> Path:
    """Resolve ``name`` to an absolute regular file; refuse wrappers on Windows."""
    if not name or any(sep in name for sep in ("/", "\\", "\x00")) or name.startswith("-"):
        raise ObservationError("EXECUTABLE_NAME_INVALID", "executable name must be a bare name")
    found = which(name)
    if not found:
        raise ObservationError("GIT_EXECUTABLE_UNAVAILABLE", f"{name} is not available on PATH")
    path = Path(found)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ObservationError(
            "GIT_EXECUTABLE_UNAVAILABLE", f"{name} could not be resolved"
        ) from exc
    if not resolved.is_file():
        raise ObservationError("GIT_EXECUTABLE_UNAVAILABLE", f"{name} is not a regular file")
    effective_os = os.name if os_name is None else os_name
    if effective_os == "nt" and resolved.suffix.lower() != WINDOWS_EXECUTABLE_SUFFIX:
        raise ObservationError(
            "GIT_EXECUTABLE_WRAPPER_REFUSED",
            f"{name} resolves to a wrapper, not a .exe; refusing to observe through it",
        )
    return resolved


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "FIXED_ENV",
    "MAX_STDOUT_BYTES",
    "PASSTHROUGH_ENV",
    "CommandResult",
    "CommandRunner",
    "ObservationError",
    "SubprocessRunner",
    "build_child_env",
    "resolve_executable",
]
