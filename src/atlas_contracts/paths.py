"""Canonical path-component and containment helpers (CODEX-SEC-004/014/017/018).

Shared fail-closed primitives for every Atlas surface that joins untrusted
identifiers into filesystem paths or opens/writes under an approved root.

Windows semantics are enforced explicitly and on all platforms so Linux CI
cannot silently accept identifiers that escape on Windows hosts.
"""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

# Device / reserved basenames (with or without extension), case-insensitive.
_WIN_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
_WIN_RESERVED_BASENAME = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$",
    re.IGNORECASE,
)
_DRIVE_RELATIVE = re.compile(r"^[A-Za-z]:")
_CONTROL_OR_NUL = re.compile(r"[\x00-\x1f]")


def safe_relative_component(value: str, *, label: str) -> str:
    """Validate one path segment before it is joined under an approved root.

    Rejects: empty/``.``/`..`, separators, absolute paths, drive-relative
    forms (``C:foo``), UNC/NT prefixes, alternate-data-stream colons,
    Windows reserved device names, trailing dots/spaces, and controls.
    """
    if not isinstance(value, str):
        raise ValueError(f"unsafe {label}: {value!r}")
    if not value or value in {".", ".."}:
        raise ValueError(f"unsafe {label}: {value!r}")
    if "/" in value or "\\" in value or "\x00" in value:
        raise ValueError(f"unsafe {label}: {value!r}")
    if _CONTROL_OR_NUL.search(value):
        raise ValueError(f"unsafe {label}: {value!r}")
    # Colon: Windows drive-relative (C:foo), ADS (file:stream), NT prefixes.
    if ":" in value:
        raise ValueError(f"unsafe {label}: {value!r}")
    if value.startswith(("\\\\", "//", "\\\\?\\", "\\\\.\\")):
        raise ValueError(f"unsafe {label}: {value!r}")
    if value.endswith((" ", ".")):
        raise ValueError(f"unsafe {label}: {value!r}")
    if _WIN_RESERVED_BASENAME.match(value) or value.upper() in _WIN_RESERVED:
        raise ValueError(f"unsafe {label}: {value!r}")

    as_path = Path(value)
    if as_path.is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError(f"unsafe {label}: {value!r}")
    # Path("C:foo").is_absolute() is False but .drive is set — reject.
    if as_path.drive or PureWindowsPath(value).drive:
        raise ValueError(f"unsafe {label}: {value!r}")
    if as_path.anchor or PureWindowsPath(value).anchor:
        raise ValueError(f"unsafe {label}: {value!r}")
    if len(as_path.parts) != 1 or as_path.parts[0] != value:
        raise ValueError(f"unsafe {label}: {value!r}")
    return value


def safe_relative_path(value: str, *, label: str = "path") -> tuple[str, ...]:
    """Validate a project-relative path and return safe POSIX segments."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"unsafe {label}: {value!r}")
    if "\x00" in value or _CONTROL_OR_NUL.search(value):
        raise ValueError(f"unsafe {label}: {value!r}")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or _DRIVE_RELATIVE.match(normalized):
        raise ValueError(f"unsafe {label}: {value!r}")
    if normalized.startswith("//"):
        raise ValueError(f"unsafe {label}: {value!r}")
    if ":" in normalized:
        raise ValueError(f"unsafe {label}: {value!r}")
    parts = PurePosixPath(normalized).parts
    if not parts or parts == (".",):
        raise ValueError(f"unsafe {label}: {value!r}")
    return tuple(safe_relative_component(part, label=label) for part in parts)


def _realpath(path: Path) -> Path:
    """Resolve symlinks / Windows reparse points to a physical path."""
    return Path(os.path.realpath(path))


def _is_contained(root: Path, candidate: Path) -> bool:
    """True when ``candidate`` is ``root`` or a descendant (post-resolve)."""
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def ensure_under_root(
    root: Path,
    candidate: Path,
    *,
    label: str = "path",
) -> Path:
    """Resolve ``candidate`` and require it remain under ``root``.

    Containment is checked on the fully resolved target (symlink / junction /
    reparse escape fails closed). Call immediately before sensitive open/write.
    """
    try:
        resolved_root = _realpath(root.expanduser())
    except OSError as exc:
        raise ValueError(f"unsafe {label} root {root}: {exc}") from exc
    try:
        # Resolve existing parents; final component may not exist yet.
        resolved_candidate = _realpath(candidate.expanduser())
    except OSError as exc:
        raise ValueError(f"unsafe {label}: {candidate}: {exc}") from exc

    # Drive-relative leftovers (C:foo) never share the approved root.
    if not resolved_candidate.is_absolute():
        raise ValueError(f"unsafe {label} escapes root: {candidate}")
    if (
        resolved_root.drive
        and resolved_candidate.drive
        and resolved_root.drive.lower() != resolved_candidate.drive.lower()
    ):
        raise ValueError(f"unsafe {label} escapes root: {candidate}")

    if not _is_contained(resolved_root, resolved_candidate):
        raise ValueError(f"unsafe {label} escapes root: {candidate}")
    return resolved_candidate


def resolve_under_root(
    root: Path,
    relative: str | PurePath,
    *,
    label: str = "path",
) -> Path:
    """Join a relative path under ``root`` with component + containment checks.

    Segments are validated before join so Windows drive-relative components
    (``C:foo``) cannot discard the approved root during ``Path`` concatenation.
    """
    relative_text = relative.as_posix() if isinstance(relative, PurePath) else relative
    segments = safe_relative_path(relative_text, label=label)
    # Build via joinpath only after per-segment validation — never trust
    # pathlib's handling of drive-relative or absolute right-hand operands.
    joined = root.expanduser()
    for segment in segments:
        joined = joined.joinpath(segment)
    return ensure_under_root(root, joined, label=label)


def join_under_root(
    root: Path,
    *components: str,
    label: str = "path",
) -> Path:
    """Join already-separated components under ``root`` with full checks."""
    if not components:
        return ensure_under_root(root, root, label=label)
    safe = tuple(safe_relative_component(part, label=label) for part in components)
    joined = root.expanduser()
    for segment in safe:
        joined = joined.joinpath(segment)
    return ensure_under_root(root, joined, label=label)
