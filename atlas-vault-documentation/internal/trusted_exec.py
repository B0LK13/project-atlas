"""Trusted executable selection for normalization (CODEX-SEC-021).

Property enforced:

    UNTRUSTED_REPOSITORY_CONFIG != EXECUTION_AUTHORITY

Repository-discovered YAML (upward ``atlas-agent.yaml`` walk) may configure
non-execution settings, but must never select the normalizer executable.
Executable authority is limited to operator-trusted inputs (CLI, process
environment, or an explicitly named configuration file) plus the built-in
allowlisted default basename.

``shell=False`` is retained at the process boundary but is not treated as a
sufficient control: selection, allowlisting, path shape, and digest binding
are enforced before any argv reaches ``subprocess``.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

#: Basenames permitted without an absolute-path + digest binding.
ALLOWED_BASENAMES: Final[frozenset[str]] = frozenset({"mda", "mda-cli"})

#: SHA-256 hex digest pattern for optional command binding.
_SHA256_HEX = re.compile(r"^[0-9a-fA-F]{64}$")

CommandSource = Literal["cli", "env", "explicit-config", "default"]


class TrustedExecError(ValueError):
    """Raised when executable selection violates the trusted boundary."""


@dataclass(frozen=True)
class TrustedExecutable:
    """Canonical, approved executable identity ready for argv construction."""

    command: str
    source: CommandSource
    resolved_path: Path | None
    digest_sha256: str | None
    argv_prefix: tuple[str, ...]


def config_grants_execution_authority(
    explicit_config: Path | None,
    *,
    env: Mapping[str, str] | None = None,
    config_env_var: str = "ATLAS_AGENT_CONFIG",
) -> bool:
    """Return True when the operator named the config file (CLI or env).

    Upward discovery alone never grants execution authority.
    """
    if explicit_config is not None:
        return True
    environ = env if env is not None else os.environ
    return bool(str(environ.get(config_env_var, "")).strip())


def _is_absolute_command(command: str) -> bool:
    """Return True for OS-absolute paths and POSIX ``/…`` forms on Windows."""
    if os.path.isabs(command):
        return True
    # Preserve Unix absolute identity when evaluating on Win32 hosts.
    return command.startswith("/")


def _looks_like_path(command: str) -> bool:
    if _is_absolute_command(command):
        return True
    if "/" in command or "\\" in command:
        return True
    return command.startswith((".", "~"))


def _reject_relative_or_traversal(command: str) -> None:
    if command != command.strip() or not command:
        raise TrustedExecError("executable command must be a non-empty stripped string")
    if "\x00" in command:
        raise TrustedExecError("executable command must not contain NUL")
    # Relative path forms and traversal are never execution-authoritative.
    if command.startswith((".", "~")) or ".." in Path(command).parts:
        raise TrustedExecError(
            "relative or traversing executable paths are not permitted "
            f"(got {command!r})"
        )
    if not _is_absolute_command(command) and ("/" in command or "\\" in command):
        raise TrustedExecError(
            "non-absolute path-shaped executable commands are not permitted "
            f"(got {command!r})"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _python_shebang(path: Path) -> bool:
    try:
        first = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
    except OSError as exc:
        raise TrustedExecError(f"unable to read executable for shebang check: {exc}") from exc
    if not first:
        return False
    line = first[0]
    if not line.startswith("#!"):
        return False
    lowered = line.lower()
    if "python" not in lowered:
        # Unexpected interpreter in shebang — refuse auto-wrapping; caller
        # may still execute the path directly only if OS can spawn it.
        return False
    # Reject shebangs that smuggle an unexpected interpreter binary path
    # alongside a python token (e.g. "#!/evil/python-wrapper").
    body = line[2:].strip()
    tokens = body.split()
    if not tokens:
        return False
    interpreter = Path(tokens[0]).name.lower()
    if interpreter in {"env"}:
        if len(tokens) < 2:
            return False
        target = Path(tokens[1]).name.lower()
        return target.startswith("python")
    return interpreter.startswith("python")


def _argv_for_approved_path(path: Path) -> tuple[str, ...]:
    """Build argv prefix for an approved on-disk executable.

    Windows cannot spawn shebang scripts as Win32 apps; wrap approved Python
    scripts with ``sys.executable`` only. Unexpected interpreters are left as
    a single-path argv (no auto-substitution of an alternate interpreter).
    """
    if _python_shebang(path):
        return (sys.executable, str(path))
    return (str(path),)


def authorize_executable(
    command: str,
    *,
    source: CommandSource,
    expected_sha256: str | None = None,
) -> TrustedExecutable:
    """Authorize ``command`` from a trusted ``source``.

    Rules:
    - allowlisted basenames (``mda``, ``mda-cli``) may be used as PATH names;
    - absolute paths require a readable file; explicit-config absolute paths
      additionally require a matching ``expected_sha256`` digest binding;
    - relative / traversing / path-substitution forms are rejected;
    - ``python`` / unexpected interpreters as the command itself are rejected
      unless they appear only as the shebang wrapper for an already-approved
      script path (never as the selected command basename).
    """
    _reject_relative_or_traversal(command)

    if not _looks_like_path(command):
        basename = Path(command).name
        if basename != command:
            raise TrustedExecError(f"unapproved executable identity: {command!r}")
        if command not in ALLOWED_BASENAMES:
            raise TrustedExecError(
                f"unapproved executable basename {command!r}; "
                f"allowed: {sorted(ALLOWED_BASENAMES)}"
            )
        return TrustedExecutable(
            command=command,
            source=source,
            resolved_path=None,
            digest_sha256=None,
            argv_prefix=(command,),
        )

    # Absolute path branch.
    if not _is_absolute_command(command):
        raise TrustedExecError(f"executable path must be absolute: {command!r}")

    path = Path(command)
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise TrustedExecError(f"unable to resolve executable path: {exc}") from exc

    # Path substitution: the resolved form must remain absolute and must not
    # reintroduce relative segments after expansion.
    if ".." in resolved.parts:
        raise TrustedExecError(f"executable path resolves through traversal: {command!r}")
    if not resolved.is_file():
        # Missing file is authorized as identity but execution will classify
        # executable-missing; still reject non-files that exist.
        if resolved.exists():
            raise TrustedExecError(f"executable path is not a regular file: {command!r}")
        if source == "explicit-config":
            raise TrustedExecError(
                "explicit-config absolute executable must exist for digest binding"
            )
        return TrustedExecutable(
            command=str(resolved),
            source=source,
            resolved_path=resolved,
            digest_sha256=None,
            argv_prefix=(str(resolved),),
        )

    digest = _sha256_file(resolved)
    if source == "explicit-config":
        if expected_sha256 is None or not _SHA256_HEX.fullmatch(expected_sha256):
            raise TrustedExecError(
                "absolute executable from explicit config requires "
                "normalization.command_sha256 (64 hex chars)"
            )
        if digest.lower() != expected_sha256.lower():
            raise TrustedExecError(
                "executable digest mismatch for normalization.command "
                "(CODEX-SEC-021 digest binding)"
            )
    elif expected_sha256 is not None:
        if not _SHA256_HEX.fullmatch(expected_sha256):
            raise TrustedExecError("command_sha256 must be a 64-character hex digest")
        if digest.lower() != expected_sha256.lower():
            raise TrustedExecError(
                "executable digest mismatch for normalization.command "
                "(CODEX-SEC-021 digest binding)"
            )

    return TrustedExecutable(
        command=str(resolved),
        source=source,
        resolved_path=resolved,
        digest_sha256=digest,
        argv_prefix=_argv_for_approved_path(resolved),
    )


def resolve_normalization_command(
    *,
    cli_value: str | None,
    env_var: str = "ATLAS_MDA_COMMAND",
    config: Mapping[str, Mapping[str, object]],
    config_grants_execution: bool,
    default: str = "mda",
    environ: Mapping[str, str] | None = None,
) -> TrustedExecutable:
    """Resolve the normalizer executable under the trusted-exec boundary.

    Precedence for *execution authority*: CLI > environment > explicit-config
    > allowlisted default. Values found only in upward-discovered repository
    configuration are ignored for executable selection.
    """
    env = environ if environ is not None else os.environ

    if cli_value is not None and str(cli_value).strip() != "":
        return authorize_executable(str(cli_value), source="cli")

    env_value = str(env.get(env_var, "")).strip()
    if env_value:
        return authorize_executable(env_value, source="env")

    if config_grants_execution:
        section = config.get("normalization")
        if isinstance(section, Mapping):
            raw = section.get("command")
            digest_raw = section.get("command_sha256")
            expected = str(digest_raw).strip() if digest_raw not in (None, "") else None
            if raw not in (None, ""):
                return authorize_executable(
                    str(raw),
                    source="explicit-config",
                    expected_sha256=expected,
                )

    return authorize_executable(default, source="default")
