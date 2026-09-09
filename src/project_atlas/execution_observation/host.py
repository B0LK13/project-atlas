"""Host environment and toolchain observation (ULT-01b-1).

Environment: three in-process facts — ``platform.system()``,
``platform.machine()`` and the interpreter version — normalized to a fixed
vocabulary. An architecture outside the normalization table leaves the whole
block ``UNKNOWN`` (the contract is all-or-nothing), never a guessed value.

Toolchain: only what ``importlib.metadata`` reports for a declared set of
distributions, plus the git version the git observer parsed. A module
``__version__`` attribute is never consulted (self-declaration), a missing
distribution is recorded as absent (``UNKNOWN != FAILURE``), and raw
executable paths are never recorded (owner decision O5).
"""

from __future__ import annotations

import platform
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import metadata
from typing import Final

from atlas_contracts.attestation import VERSION_PATTERN

# Owner decision O4: canonical architecture vocabulary. Unmapped -> UNKNOWN.
ARCH_NORMALIZATION: Final[dict[str, str]] = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "x64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
    "i386": "x86",
    "i686": "x86",
    "x86": "x86",
}
OS_NORMALIZATION: Final[dict[str, str]] = {
    "linux": "Linux",
    "windows": "Windows",
    "darwin": "Darwin",
}
# Owner decision O5: declared toolchain set. "git" is observed by the git
# observer (``git --version``); the rest by installed-distribution metadata.
DECLARED_TOOLCHAIN: Final[tuple[str, ...]] = (
    "PyYAML",
    "git",
    "jsonschema",
    "mypy",
    "project-atlas",
    "pydantic",
    "pytest",
    "ruff",
)
OBSERVER_DISTRIBUTION: Final[str] = "project-atlas"
_VERSION_RE: Final[re.Pattern[str]] = re.compile(VERSION_PATTERN)
_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


@dataclass(frozen=True)
class EnvironmentObservation:
    status: str
    os: str | None
    arch: str | None
    python: str | None
    arch_raw: str | None
    reason: str | None


@dataclass(frozen=True)
class ToolchainObservation:
    status: str
    tools: tuple[tuple[str, str], ...]
    declared: tuple[str, ...]
    absent: tuple[str, ...]
    reason: str | None


def observe_environment(
    *,
    system: Callable[[], str] = platform.system,
    machine: Callable[[], str] = platform.machine,
    version_info: tuple[int, int, int] | None = None,
) -> EnvironmentObservation:
    try:
        raw_os = str(system() or "")
        raw_arch = str(machine() or "")
    except Exception:
        return EnvironmentObservation("UNKNOWN", None, None, None, None, "PLATFORM_UNOBSERVABLE")
    arch_raw = raw_arch if _TOKEN_RE.fullmatch(raw_arch) else None
    os_token = OS_NORMALIZATION.get(raw_os.strip().lower())
    arch_token = ARCH_NORMALIZATION.get(raw_arch.strip().lower())
    if version_info is None:
        info = sys.version_info
        version_info = (info.major, info.minor, info.micro)
    python = ".".join(str(int(part)) for part in version_info[:3])
    if os_token is None:
        return EnvironmentObservation("UNKNOWN", None, None, None, arch_raw, "OS_UNMAPPED")
    if arch_token is None:
        return EnvironmentObservation("UNKNOWN", None, None, None, arch_raw, "ARCH_UNMAPPED")
    if not _TOKEN_RE.fullmatch(python):
        return EnvironmentObservation("UNKNOWN", None, None, None, arch_raw, "PYTHON_UNOBSERVABLE")
    return EnvironmentObservation("OBSERVED", os_token, arch_token, python, arch_raw, None)


def _metadata_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def observe_toolchain(
    *,
    declared: Sequence[str] = DECLARED_TOOLCHAIN,
    version_of: Callable[[str], str | None] = _metadata_version,
    git_version: str | None = None,
) -> ToolchainObservation:
    names = tuple(sorted(set(declared)))
    tools: list[tuple[str, str]] = []
    absent: list[str] = []
    for name in names:
        if name == "git":
            version = git_version
        else:
            try:
                version = version_of(name)
            except Exception:
                version = None
        if version is None or not _VERSION_RE.fullmatch(str(version)):
            absent.append(name)
            continue
        tools.append((name, str(version)))
    if not tools:
        return ToolchainObservation("UNKNOWN", (), names, tuple(absent), "TOOLCHAIN_UNOBSERVABLE")
    return ToolchainObservation("OBSERVED", tuple(tools), names, tuple(absent), None)


def observe_observer_version(
    *, version_of: Callable[[str], str | None] = _metadata_version
) -> tuple[str, str]:
    """The observer's own version: distribution metadata or the token UNKNOWN."""
    try:
        version = version_of(OBSERVER_DISTRIBUTION)
    except Exception:
        version = None
    if version is None or not _VERSION_RE.fullmatch(str(version)):
        return ("UNKNOWN", "UNKNOWN")
    return (str(version), "OBSERVED")


__all__ = [
    "ARCH_NORMALIZATION",
    "DECLARED_TOOLCHAIN",
    "OBSERVER_DISTRIBUTION",
    "OS_NORMALIZATION",
    "EnvironmentObservation",
    "ToolchainObservation",
    "observe_environment",
    "observe_observer_version",
    "observe_toolchain",
]
