"""Conflict helpers for Graphify-derived records."""

from __future__ import annotations

from typing import Any


def duplicate_conflict(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    return {"type": "duplicate-conflict", "existing": existing, "incoming": incoming, "automatic_resolution": False}
