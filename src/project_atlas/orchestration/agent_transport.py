"""AS-ORCH-001D Cursor CLI process transport (fresh current-main reconstruction).

Starts one target process from a trusted argv array. Cursor prose cannot
choose a route, executable, or privilege. Windows ``.cmd`` launchers are
wrapped through trusted ``cmd.exe``; the prompt travels on stdin only.

GENERAL_AGENT_DISPATCH_RUNTIME = IMPLEMENTED
WINDOWS_CMD_WRAPPER_SUPPORTED = YES
UNTRUSTED_TEXT_REACHES_WINDOWS_COMMAND_STRING = NO
CURSOR_PROSE_CAN_CHOOSE_NEXT_ROUTE = NO
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

PACKAGE_ID = "AS-ORCH-001D"
LOGICAL_EXECUTABLE_NAMES = frozenset({"agent", "cursor-agent"})
WINDOWS_WRAPPER_EXTENSIONS = frozenset({".cmd"})
WINDOWS_DIRECT_EXTENSIONS = frozenset({"", ".exe"})
READ_ONLY_CURSOR_FLAGS: tuple[str, ...] = ("--print", "--output-format", "json", "--mode", "ask")
FORBIDDEN_CURSOR_FLAGS = frozenset({"--force", "--force-allow-http", "-f"})
DEFAULT_TIMEOUT_SECONDS = 600
MAX_CAPTURED_BYTES = 64 * 1024
MAX_PROMPT_CHARS = 8_192
MAX_RESULT_CANDIDATE_BYTES = 256 * 1024
_SAFE_META_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_CURSOR_OMIT_ENV: frozenset[str] = frozenset({"ATLAS_MDA_COMMAND", "MDA_MOCK_MODE"})


class TransportError(ValueError):
    """Process-transport failure. Not an authority grant."""

    code: str = "TRANSPORT_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class CursorOutputKind(StrEnum):
    TERMINAL_SUCCESS = "terminal_success"
    MALFORMED = "malformed"
    MISSING = "missing"
    CURSOR_ERROR = "cursor_error"


class LauncherKind(StrEnum):
    DIRECT = "direct"
    WINDOWS_CMD_WRAPPER = "windows_cmd_wrapper"


class CursorStructuredResult(BaseModel):
    """Bounded structured process output. ``result`` prose is never a route."""

    model_config = ConfigDict(extra="forbid")

    kind: CursorOutputKind
    session_id: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)
    result_text_digest: str | None = Field(default=None, min_length=64, max_length=64)
    is_error: bool = False


class ResolvedCursorExecutable(BaseModel):
    """Trusted launcher identity. Envelope content cannot populate this."""

    model_config = ConfigDict(extra="forbid")

    logical_name: Literal["agent", "cursor-agent"]
    path: str = Field(min_length=1, max_length=4096)
    launcher_kind: LauncherKind


class CursorLaunchPlan(BaseModel):
    """Trusted CreateProcess plan. Prompt is stdin-only."""

    model_config = ConfigDict(extra="forbid")

    logical_name: Literal["agent", "cursor-agent"]
    physical_path: str = Field(min_length=1, max_length=4096)
    launcher_kind: LauncherKind
    create_process_executable: str = Field(min_length=1, max_length=4096)
    argv: tuple[str, ...]
    stdin_payload: str = Field(min_length=1, max_length=MAX_PROMPT_CHARS)
    cwd: str = Field(min_length=1, max_length=4096)
    timeout_seconds: int = Field(ge=1, le=86_400)
    cursor_mode: Literal["ask"] = "ask"
    uses_force: Literal[False] = False


@dataclass(frozen=True, slots=True)
class ProcessRunRequest:
    """Trusted argv invocation. Never a shell string."""

    argv: tuple[str, ...]
    cwd: Path
    timeout_seconds: int
    env: Mapping[str, str]
    stdin: bytes | None = None


@dataclass(frozen=True, slots=True)
class ProcessRunOutcome:
    """Terminal process facts. Exit 0 is not task success."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    duration_ms: int


class ProcessRunner(Protocol):
    """Injected runner. Tests use a fake; production uses subprocess."""

    def run(self, request: ProcessRunRequest) -> ProcessRunOutcome: ...


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bound_captured_bytes(data: bytes) -> bytes:
    return data[:MAX_CAPTURED_BYTES]


def sanitize_inherited_env(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy process env. Never log secrets. Test MDA path is not inherited."""
    env = dict(os.environ if source is None else source)
    for key in _CURSOR_OMIT_ENV:
        env.pop(key, None)
    return env


def _is_windows(os_name: str | None) -> bool:
    return (os_name if os_name is not None else os.name) == "nt"


def _reject_raw_text(raw: str) -> None:
    if not raw or raw.strip() != raw:
        raise TransportError("executable path is empty or padded", code="EXECUTABLE_REJECTED")
    if "\n" in raw or "\r" in raw or "\x00" in raw:
        raise TransportError(
            "executable path contains a control character",
            code="EXECUTABLE_REJECTED",
        )
    if "://" in raw:
        raise TransportError("executable path is not a local binary", code="EXECUTABLE_REJECTED")


def _is_absolute(raw: str, *, windows: bool) -> bool:
    if Path(raw).is_absolute():
        return True
    if windows:
        return PureWindowsPath(raw).is_absolute() or bool(_WINDOWS_DRIVE_RE.match(raw))
    return False


def _basename(raw: str, *, windows: bool) -> str:
    return PureWindowsPath(raw).name if windows else PurePosixPath(raw).name


def _logical_identity(name: str, *, windows: bool) -> tuple[str, LauncherKind] | None:
    parsed = PureWindowsPath(name) if windows else PurePosixPath(name)
    if parsed.name != name:
        return None
    stem = parsed.stem
    suffix = parsed.suffix
    logical = stem.lower() if windows else stem
    if logical not in LOGICAL_EXECUTABLE_NAMES:
        return None
    if windows:
        extension = suffix.lower()
        if extension in WINDOWS_DIRECT_EXTENSIONS:
            return logical, LauncherKind.DIRECT
        if extension in WINDOWS_WRAPPER_EXTENSIONS:
            return logical, LauncherKind.WINDOWS_CMD_WRAPPER
        return None
    if name in LOGICAL_EXECUTABLE_NAMES:
        return name, LauncherKind.DIRECT
    return None


def _default_exists(path: str) -> bool:
    try:
        return Path(path).is_file()
    except OSError:
        return False


def resolve_cursor_transport(
    configured: str | Path | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
    os_name: str | None = None,
    exists: Callable[[str], bool] | None = None,
) -> ResolvedCursorExecutable:
    """Resolve logical ``agent`` / ``cursor-agent`` only. Envelope cannot choose this."""
    windows = _is_windows(os_name)
    file_exists = exists if exists is not None else _default_exists
    if configured is not None:
        return _resolve_configured(
            str(configured),
            which=which,
            windows=windows,
            file_exists=file_exists,
        )
    for name in ("agent", "cursor-agent"):
        found = which(name)
        if found is None:
            continue
        try:
            return _accept_discovered(found, windows=windows, file_exists=file_exists)
        except TransportError:
            continue
    raise TransportError("Cursor CLI executable was not found", code="CURSOR_EXECUTABLE_NOT_FOUND")


def resolve_cursor_executable(
    configured: str | Path | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
    os_name: str | None = None,
    exists: Callable[[str], bool] | None = None,
) -> Path:
    """Compatibility wrapper returning the physical launcher path."""
    resolved = resolve_cursor_transport(
        configured,
        which=which,
        os_name=os_name,
        exists=exists,
    )
    return Path(resolved.path)


def _resolve_configured(
    raw: str,
    *,
    which: Callable[[str], str | None],
    windows: bool,
    file_exists: Callable[[str], bool],
) -> ResolvedCursorExecutable:
    _reject_raw_text(raw)
    if _is_absolute(raw, windows=windows):
        if not file_exists(raw):
            raise TransportError(
                "configured executable does not exist",
                code="EXECUTABLE_REJECTED",
            )
        return _accept_discovered(raw, windows=windows, file_exists=file_exists)
    if raw != _basename(raw, windows=windows):
        raise TransportError(
            "relative executable must be a bare name",
            code="EXECUTABLE_REJECTED",
        )
    identity = _logical_identity(raw, windows=windows)
    if identity is None:
        raise TransportError(
            "executable basename is not a supported Cursor transport",
            code="EXECUTABLE_REJECTED",
        )
    found = which(raw)
    if found is None and windows:
        found = which(identity[0])
    if found is None:
        raise TransportError("configured executable was not found", code="EXECUTABLE_REJECTED")
    return _accept_discovered(found, windows=windows, file_exists=file_exists)


def _accept_discovered(
    raw: str,
    *,
    windows: bool,
    file_exists: Callable[[str], bool],
) -> ResolvedCursorExecutable:
    _reject_raw_text(raw)
    name = _basename(raw, windows=windows)
    identity = _logical_identity(name, windows=windows)
    if identity is None:
        raise TransportError(
            "resolved executable basename is not a supported Cursor transport",
            code="EXECUTABLE_REJECTED",
        )
    logical, kind = identity
    if not file_exists(raw):
        raise TransportError("resolved executable does not exist", code="EXECUTABLE_REJECTED")
    native = Path(raw)
    if native.exists():
        physical = str(native.expanduser().resolve())
    elif windows:
        physical = str(PureWindowsPath(raw))
    else:
        physical = raw
    return ResolvedCursorExecutable(
        logical_name=logical,  # type: ignore[arg-type]
        path=physical,
        launcher_kind=kind,
    )


def resolve_windows_comspec(
    configured: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    exists: Callable[[str], bool] | None = None,
) -> str:
    """Resolve trusted ``cmd.exe``. Attacker-controlled ComSpec is rejected."""
    env = dict(os.environ if environ is None else environ)
    file_exists = exists if exists is not None else _default_exists
    candidates: list[str] = []
    if configured is not None:
        candidates.append(configured)
    system_root = env.get("SystemRoot") or env.get("SYSTEMROOT")
    if system_root:
        candidates.append(str(Path(system_root) / "System32" / "cmd.exe"))
        candidates.append(str(PureWindowsPath(system_root) / "System32" / "cmd.exe"))
    comspec = env.get("ComSpec") or env.get("COMSPEC")
    if comspec:
        candidates.append(comspec)
    for raw in candidates:
        try:
            _reject_raw_text(raw)
        except TransportError:
            continue
        names = {PureWindowsPath(raw).name.lower(), Path(raw).name.lower()}
        parents = {
            PureWindowsPath(raw).parent.name.lower(),
            Path(raw).parent.name.lower(),
        }
        if "cmd.exe" not in names or "system32" not in parents:
            continue
        if (
            not PureWindowsPath(raw).is_absolute()
            and not Path(raw).is_absolute()
            and not _WINDOWS_DRIVE_RE.match(raw)
        ):
            continue
        if not file_exists(raw):
            continue
        native = Path(raw)
        return str(native.resolve()) if native.exists() else str(PureWindowsPath(raw))
    raise TransportError("trusted Windows ComSpec was not found", code="COMSPEC_REJECTED")


def _quote_windows_path(path: str) -> str:
    if '"' in path or "%" in path or "!" in path or "^" in path:
        raise TransportError(
            "wrapper path contains unsafe cmd metacharacters",
            code="EXECUTABLE_REJECTED",
        )
    if any(token in path for token in ("&", "|", ">", "<", "(", ")")):
        raise TransportError(
            "wrapper path contains unsafe cmd metacharacters",
            code="EXECUTABLE_REJECTED",
        )
    return f'"{path}"'


def build_launch_plan(
    executable: ResolvedCursorExecutable | Path | str,
    prompt: str,
    *,
    cwd: Path,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    os_name: str | None = None,
    comspec: str | None = None,
    environ: Mapping[str, str] | None = None,
    exists: Callable[[str], bool] | None = None,
) -> CursorLaunchPlan:
    """Build a trusted launch plan. Prompt is stdin-only. No ``--force``."""
    if not isinstance(prompt, str) or not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise TransportError("dispatch prompt is missing or oversized", code="PROMPT_REJECTED")
    if "\x00" in prompt:
        raise TransportError("dispatch prompt contains a NUL", code="PROMPT_REJECTED")
    resolved = (
        executable
        if isinstance(executable, ResolvedCursorExecutable)
        else resolve_cursor_transport(executable, os_name=os_name, exists=exists)
    )
    workspace = cwd.expanduser().resolve()
    if not workspace.is_dir():
        raise TransportError("process cwd is not a directory", code="WORKSPACE_UNSAFE")
    flags = READ_ONLY_CURSOR_FLAGS
    if resolved.launcher_kind is LauncherKind.DIRECT:
        argv = (resolved.path, *flags)
        create_process = resolved.path
    else:
        launcher = resolve_windows_comspec(
            comspec,
            environ=environ,
            exists=exists,
        )
        # Reject cmd metacharacters, then pass path and flags as separate
        # argv tokens. A pre-quoted command string is re-quoted by
        # subprocess list2cmdline and authentic cmd.exe cannot start it.
        _quote_windows_path(resolved.path)
        argv = (launcher, "/d", "/c", resolved.path, *flags)
        create_process = launcher
    if any(flag in argv for flag in FORBIDDEN_CURSOR_FLAGS):
        raise TransportError("launch plan contains a forbidden flag", code="ARGV_REJECTED")
    if prompt in argv or any(prompt in token for token in argv):
        raise TransportError("prompt leaked into process argv", code="PROMPT_REJECTED")
    return CursorLaunchPlan(
        logical_name=resolved.logical_name,
        physical_path=resolved.path,
        launcher_kind=resolved.launcher_kind,
        create_process_executable=create_process,
        argv=argv,
        stdin_payload=prompt,
        cwd=str(workspace),
        timeout_seconds=timeout_seconds,
    )


def build_print_argv(
    executable: Path | ResolvedCursorExecutable | str,
    prompt: str,
    *,
    cwd: Path | None = None,
    os_name: str | None = None,
    exists: Callable[[str], bool] | None = None,
) -> list[str]:
    """Fresh-session print argv. Prompt is not placed on the command line."""
    workspace = cwd if cwd is not None else Path.cwd()
    plan = build_launch_plan(
        executable,
        prompt,
        cwd=workspace,
        os_name=os_name,
        exists=exists,
    )
    return list(plan.argv)


def _safe_meta(value: object) -> str | None:
    if not isinstance(value, str) or not _SAFE_META_RE.fullmatch(value):
        return None
    return value


def _digest_result_text(value: object) -> str | None:
    if isinstance(value, str) and value:
        return digest_bytes(value.encode("utf-8"))
    if isinstance(value, dict):
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return digest_bytes(encoded)
    return None


def _from_cursor_object(payload: object) -> CursorStructuredResult | None:
    if not isinstance(payload, dict):
        return None
    if payload.get("is_error") is True:
        return CursorStructuredResult(
            kind=CursorOutputKind.CURSOR_ERROR,
            session_id=_safe_meta(payload.get("session_id")),
            request_id=_safe_meta(payload.get("request_id")),
            result_text_digest=_digest_result_text(payload.get("result")),
            is_error=True,
        )
    kind = payload.get("type")
    if kind is not None and kind != "result":
        return None
    if kind == "result" or "result" in payload:
        return CursorStructuredResult(
            kind=CursorOutputKind.TERMINAL_SUCCESS,
            session_id=_safe_meta(payload.get("session_id")),
            request_id=_safe_meta(payload.get("request_id")),
            result_text_digest=_digest_result_text(payload.get("result")),
            is_error=False,
        )
    return None


def parse_structured_cursor_output(stdout: bytes) -> CursorStructuredResult:
    """Parse Cursor JSON output. Prose is hashed only; missing/malformed fail closed."""
    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return CursorStructuredResult(kind=CursorOutputKind.MISSING)
    candidates: list[object] = []
    try:
        parsed: object = json.loads(text)
        candidates.append(parsed)
    except json.JSONDecodeError:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                candidates.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not candidates:
            return CursorStructuredResult(kind=CursorOutputKind.MALFORMED)
    for item in reversed(candidates):
        if isinstance(item, list):
            for entry in reversed(item):
                parsed_entry = _from_cursor_object(entry)
                if parsed_entry is not None:
                    return parsed_entry
            continue
        parsed_item = _from_cursor_object(item)
        if parsed_item is not None:
            return parsed_item
    return CursorStructuredResult(kind=CursorOutputKind.MALFORMED)


class SubprocessProcessRunner:
    """Real argv runner. ``shell`` is never enabled."""

    def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
        if not request.argv:
            raise TransportError("process argv is empty", code="ARGV_REJECTED")
        if request.timeout_seconds < 1 or request.timeout_seconds > 86_400:
            raise TransportError("timeout is out of bounds", code="TIMEOUT_REJECTED")
        cwd = request.cwd.expanduser().resolve()
        if not cwd.is_dir():
            raise TransportError("process cwd is not a directory", code="WORKSPACE_UNSAFE")
        try:
            completed = subprocess.run(
                list(request.argv),
                cwd=cwd,
                env=dict(request.env),
                input=request.stdin,
                capture_output=True,
                text=False,
                timeout=request.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = bound_captured_bytes(exc.stdout or b"")
            stderr = bound_captured_bytes(exc.stderr or b"")
            return ProcessRunOutcome(
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                duration_ms=request.timeout_seconds * 1000,
            )
        stdout = bound_captured_bytes(completed.stdout or b"")
        stderr = bound_captured_bytes(completed.stderr or b"")
        return ProcessRunOutcome(
            exit_code=int(completed.returncode),
            stdout=stdout,
            stderr=stderr,
            timed_out=False,
            duration_ms=0,
        )
