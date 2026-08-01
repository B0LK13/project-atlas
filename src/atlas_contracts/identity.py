"""Shared identity helpers; implementations remain subsystem-owned."""

from __future__ import annotations

from pathlib import Path


def safe_relative_component(value: str, *, label: str) -> str:
    """Validate one logical identifier before it is used in a path."""
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"unsafe {label}: {value!r}")
    if Path(value).is_absolute() or "\x00" in value:
        raise ValueError(f"unsafe {label}: {value!r}")
    return value
