"""AS-ORCH-001D Cursor CLI process transport.

Starts one target process from a trusted argv array. Cursor prose is
diagnostic only and cannot choose a route, executable, or privilege.

CURSOR_CLI_PROCESS_TRANSPORT = IMPLEMENTED
CURSOR_PROSE_CAN_CHOOSE_NEXT_ROUTE = NO
UNTRUSTED_INPUT_CAN_CHOOSE_EXECUTABLE = NO
FRESH_AGENT_SESSION = YES
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
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

PACKAGE_ID = "AS-ORCH-001D"
SUPPORTED_EXECUTABLE_NAMES = frozenset({"agent", "cursor-agent"})
DEFAULT_TIMEOUT_SECONDS = 600
MAX_CAPTURED_BYTES = 64 * 1024
MAX_PROMPT_CHARS = 8_192
_SAFE_META_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_UNSAFE_EXECUTABLE_RE = re.compile(r"""[\s;&|`$<>(){}#!*?\\'"]""")


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


class CursorStructuredResult(BaseModel):
    """Bounded structured process output. ``result`` prose is never a route."""

    model_config = ConfigDict(extra="forbid")

    kind: CursorOutputKind
    session_id: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=128)
    result_text_digest: str | None = Field(default=None, min_length=64, max_length=64)
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class ProcessRunRequest:
    """Trusted argv invocation. Never a shell string."""

    argv: tuple[str, ...]
    cwd: Path
    timeout_seconds: int
    env: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ProcessRunOutcome:
    """Terminal process facts. Exit 0 is not task success."""

    exit_code: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    duration_ms: int


class ProcessRunner(Protocol):
    """Injected runner. Cloud tests use a fake; production uses subprocess."""

    def run(self, request: ProcessRunRequest) -> ProcessRunOutcome: ...


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bound_captured_bytes(data: bytes) -> bytes:
    return data[:MAX_CAPTURED_BYTES]


def sanitize_inherited_env(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy the process environment. Never log or persist secret values."""
    env = dict(os.environ if source is None else source)
    return env


def resolve_cursor_executable(
    configured: str | Path | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> Path:
    """Resolve ``agent`` / ``cursor-agent`` only. Envelope content cannot choose this."""
    if configured is not None:
        raw = str(configured).strip()
        if not raw:
            raise TransportError("executable path is empty", code="EXECUTABLE_REJECTED")
        if "\n" in raw or "\r" in raw or "://" in raw:
            raise TransportError(
                "executable path is not a local binary",
                code="EXECUTABLE_REJECTED",
            )
        if _UNSAFE_EXECUTABLE_RE.search(raw):
            raise TransportError(
                "executable path contains unsafe characters",
                code="EXECUTABLE_REJECTED",
            )
        path = Path(raw)
        if path.name not in SUPPORTED_EXECUTABLE_NAMES:
            raise TransportError(
                "executable basename is not a supported Cursor transport",
                code="EXECUTABLE_REJECTED",
            )
        if path.is_absolute():
            resolved = path.expanduser().resolve()
            if resolved.name not in SUPPORTED_EXECUTABLE_NAMES:
                raise TransportError(
                    "absolute executable basename is not supported",
                    code="EXECUTABLE_REJECTED",
                )
            if not resolved.is_file():
                raise TransportError(
                    "configured executable does not exist",
                    code="EXECUTABLE_REJECTED",
                )
            return resolved
        if raw != path.name:
            raise TransportError(
                "relative executable must be a bare name",
                code="EXECUTABLE_REJECTED",
            )
        found = which(raw)
        if found is None:
            raise TransportError("configured executable was not found", code="EXECUTABLE_REJECTED")
        resolved = Path(found).resolve()
        if resolved.name not in SUPPORTED_EXECUTABLE_NAMES:
            raise TransportError(
                "resolved executable basename is not supported",
                code="EXECUTABLE_REJECTED",
            )
        return resolved

    for name in ("agent", "cursor-agent"):
        found = which(name)
        if found is None:
            continue
        resolved = Path(found).resolve()
        if resolved.name in SUPPORTED_EXECUTABLE_NAMES:
            return resolved
    raise TransportError("Cursor CLI executable was not found", code="CURSOR_EXECUTABLE_NOT_FOUND")


def build_print_argv(executable: Path, prompt: str) -> list[str]:
    """Fresh-session print invocation. No resume, no force, no shell."""
    if executable.name not in SUPPORTED_EXECUTABLE_NAMES:
        raise TransportError(
            "argv executable is not a supported transport",
            code="EXECUTABLE_REJECTED",
        )
    if not isinstance(prompt, str) or not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise TransportError("dispatch prompt is missing or oversized", code="PROMPT_REJECTED")
    if "\x00" in prompt:
        raise TransportError("dispatch prompt contains a NUL", code="PROMPT_REJECTED")
    return [str(executable), "--print", "--output-format", "json", prompt]


def _safe_meta(value: object) -> str | None:
    if not isinstance(value, str) or not _SAFE_META_RE.fullmatch(value):
        return None
    return value


def _digest_result_text(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return digest_bytes(value.encode("utf-8"))


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
