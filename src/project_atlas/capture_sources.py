"""AS-OBSIDIAN-CAPTURE-001 — capture source adapters (acquisition only).

Source adapters convert provider-specific input into a canonical
:class:`CaptureRequest`. They own acquisition and nothing else: no
persistence, no deduplication, no Markdown rendering, no Atlas indexing
(architecture §6.1, §53).

Clipboard acquisition uses capability detection over the session's own
tooling (``wl-paste`` / ``xclip`` / ``xsel``) with a fixed argument vector.
Clipboard content is **data only** and is never evaluated as a command
(architecture §22, §64).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field

PACKAGE_ID = "AS-OBSIDIAN-CAPTURE-001"

#: Source types accepted by the capture pipeline (architecture §6.2).
SOURCE_TYPES = (
    "text",
    "conversation",
    "terminal",
    "web",
    "email",
    "document",
    "agent_output",
)

#: Adapters that may originate a request. ``api`` is reserved for the
#: future localhost capture adapter (architecture §23) and is accepted by
#: the service so no schema migration is needed to add it.
SOURCE_ADAPTERS = ("text", "stdin", "clipboard", "api")

#: Maximum raw payload accepted from any adapter (architecture §24).
MAX_CONTENT_BYTES = 4 * 1024 * 1024

#: Seconds a clipboard helper may run before acquisition fails closed.
CLIPBOARD_TIMEOUT_SECONDS = 5


class CaptureSourceError(ValueError):
    """Fail-closed acquisition error carrying a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class CaptureRequest:
    """Canonical capture request produced by every source adapter (§6.2)."""

    content: str
    source_type: str = "text"
    source_application: str = "unknown"
    source_adapter: str = "text"
    project_reference: str | None = None
    title_hint: str | None = None
    source_locator: str = ""
    source_metadata: dict[str, str] = field(default_factory=dict)
    captured_at: str | None = None


@dataclass(frozen=True)
class ClipboardProvider:
    """A detected clipboard reader and the fixed argv used to invoke it."""

    name: str
    argv: tuple[str, ...]


#: Ordered candidates per session type. The first available wins (§22).
_WAYLAND_PROVIDERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("wl-paste", ("wl-paste", "--no-newline")),
    ("xclip", ("xclip", "-selection", "clipboard", "-o")),
    ("xsel", ("xsel", "--clipboard", "--output")),
)
_X11_PROVIDERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("xclip", ("xclip", "-selection", "clipboard", "-o")),
    ("xsel", ("xsel", "--clipboard", "--output")),
    ("wl-paste", ("wl-paste", "--no-newline")),
)


def _session_providers(
    environ: dict[str, str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Order clipboard candidates by the detected desktop session (§22)."""
    session = (environ.get("XDG_SESSION_TYPE") or "").strip().lower()
    if session == "wayland" or environ.get("WAYLAND_DISPLAY"):
        return _WAYLAND_PROVIDERS
    return _X11_PROVIDERS


def detect_clipboard_provider(
    environ: dict[str, str] | None = None,
    *,
    which: object = None,
) -> ClipboardProvider:
    """Select an available clipboard provider or fail with actionable advice.

    ``which`` is injectable for tests; it defaults to :func:`shutil.which`.
    """
    env = dict(os.environ if environ is None else environ)
    lookup = shutil.which if which is None else which
    for name, argv in _session_providers(env):
        if lookup(argv[0]):  # type: ignore[operator]
            return ClipboardProvider(name=name, argv=argv)
    raise CaptureSourceError(
        "CLIPBOARD_UNAVAILABLE",
        "no clipboard provider found; install one of wl-paste (wl-clipboard), "
        "xclip, or xsel — or pass --text/--stdin instead",
    )


def read_clipboard_text(
    *,
    environ: dict[str, str] | None = None,
    runner: object = None,
    which: object = None,
) -> str:
    """Read clipboard text as data. The content is never executed (§22, §64)."""
    provider = detect_clipboard_provider(environ, which=which)
    run = subprocess.run if runner is None else runner
    try:
        completed = run(  # type: ignore[operator]
            list(provider.argv),
            capture_output=True,
            timeout=CLIPBOARD_TIMEOUT_SECONDS,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CaptureSourceError(
            "CLIPBOARD_READ_FAILED",
            f"clipboard provider {provider.name} failed: {exc}",
        ) from exc
    if getattr(completed, "returncode", 1) != 0:
        raise CaptureSourceError(
            "CLIPBOARD_READ_FAILED",
            f"clipboard provider {provider.name} exited non-zero",
        )
    raw = getattr(completed, "stdout", b"") or b""
    if isinstance(raw, str):
        return raw
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaptureSourceError(
            "CLIPBOARD_NOT_TEXT",
            "clipboard does not contain UTF-8 text",
        ) from exc


def read_stdin_text(stream: object = None) -> str:
    """Read a capture payload from standard input."""
    handle = sys.stdin if stream is None else stream
    try:
        text = handle.read()  # type: ignore[union-attr]
    except (OSError, UnicodeError) as exc:
        raise CaptureSourceError("STDIN_READ_FAILED", f"stdin is not readable: {exc}") from exc
    if not isinstance(text, str):
        raise CaptureSourceError("STDIN_READ_FAILED", "stdin did not yield text")
    return text


def _clean_token(value: str | None, *, label: str, max_len: int) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).strip()
    if len(text) > max_len:
        raise CaptureSourceError(
            "CAPTURE_INPUT_TOO_LARGE",
            f"{label} exceeds {max_len} characters",
        )
    return text


def build_capture_request(
    *,
    content: str,
    source_type: str = "text",
    source_application: str = "unknown",
    source_adapter: str = "text",
    project_reference: str | None = None,
    title_hint: str | None = None,
    source_locator: str = "",
    source_metadata: dict[str, str] | None = None,
    captured_at: str | None = None,
) -> CaptureRequest:
    """Validate adapter output into a canonical :class:`CaptureRequest`.

    ``content`` is the only mandatory field (architecture §6.2). It is kept
    verbatim here; canonicalization happens only for identity, in the
    capture service.
    """
    if not isinstance(content, str):
        raise CaptureSourceError("MALFORMED_REQUEST", "content must be text")
    if not content.strip():
        raise CaptureSourceError("EMPTY_CONTENT", "capture content is empty")
    encoded_len = len(content.encode("utf-8"))
    if encoded_len > MAX_CONTENT_BYTES:
        raise CaptureSourceError(
            "CAPTURE_INPUT_TOO_LARGE",
            f"capture content is {encoded_len} bytes; limit is {MAX_CONTENT_BYTES}",
        )
    stype = _clean_token(source_type, label="source_type", max_len=32).lower() or "text"
    if stype not in SOURCE_TYPES:
        raise CaptureSourceError("UNSUPPORTED_SOURCE_TYPE", f"unsupported source_type {stype!r}")
    adapter = _clean_token(source_adapter, label="source_adapter", max_len=32).lower() or "text"
    if adapter not in SOURCE_ADAPTERS:
        raise CaptureSourceError(
            "UNSUPPORTED_SOURCE_ADAPTER",
            f"unsupported source_adapter {adapter!r}",
        )
    app = _clean_token(source_application, label="source_application", max_len=32).lower()
    app = app or "unknown"

    metadata: dict[str, str] = {}
    for key, value in sorted((source_metadata or {}).items()):
        safe_key = _clean_token(key, label="source_metadata key", max_len=64)
        if not safe_key:
            continue
        metadata[safe_key] = _clean_token(value, label="source_metadata value", max_len=2048)

    return CaptureRequest(
        content=content,
        source_type=stype,
        source_application=app,
        source_adapter=adapter,
        project_reference=(project_reference or None),
        title_hint=(title_hint or None),
        source_locator=_clean_token(source_locator, label="source_locator", max_len=2048),
        source_metadata=metadata,
        captured_at=(_clean_token(captured_at, label="captured_at", max_len=64) or None),
    )
