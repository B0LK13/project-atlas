"""Explicit valid-time helpers for derived intelligence.

Never invents wall-clock ``now``. Callers must supply evidenced instants.
Mirrors AS-2.0-TEMPORAL-001 fail-closed parsing without writing catalogs.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

_WALL_CLOCK = frozenset({"now", "today", "utcnow", "utc-now"})

TemporalApplicability = Literal[
    "applicable",
    "stale",
    "not-yet-valid",
    "unknown",
    "unspecified",
]

WindowRelation = Literal["overlapping", "non-overlapping", "succession", "unknown"]


class IntelligenceTimeError(ValueError):
    """Fail-closed valid-time parse / comparison error."""


def parse_instant(raw: str, *, field: str) -> datetime:
    """Parse an evidenced instant. Rejects wall-clock sentinel language."""
    text = raw.strip()
    if not text:
        raise IntelligenceTimeError(f"intel-{field}-empty")
    if text.lower() in _WALL_CLOCK:
        raise IntelligenceTimeError(f"intel-{field}-wall-clock-forbidden")
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            return datetime.combine(date.fromisoformat(text), datetime.min.time())
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntelligenceTimeError(f"intel-{field}-invalid:{text}") from exc


def window_applicability(
    *,
    as_of_valid_time: str | None,
    valid_from: str | None,
    valid_to: str | None,
) -> TemporalApplicability:
    """Classify a claim window against an explicit as-of instant."""
    if as_of_valid_time is None:
        return "unspecified"
    as_of = parse_instant(as_of_valid_time, field="as-of")
    if valid_from is None and valid_to is None:
        return "unknown"
    start = parse_instant(valid_from, field="valid-from") if valid_from else None
    end = parse_instant(valid_to, field="valid-to") if valid_to else None
    if start is not None and end is not None and end < start:
        raise IntelligenceTimeError("intel-window-inverted")
    if start is not None and as_of < start:
        return "not-yet-valid"
    if end is not None and as_of > end:
        return "stale"
    return "applicable"


def windows_relation(
    left_from: str | None,
    left_to: str | None,
    right_from: str | None,
    right_to: str | None,
) -> WindowRelation:
    """Compare two validity windows without inventing missing bounds.

    Succession is proven only when one window has an evidenced end that is
    strictly before the other window's evidenced start. Overlap is proven
    only when both starts and both ends are evidenced and the closed
    intervals intersect. Anything else stays ``unknown``.
    """
    if left_from is None or right_from is None:
        return "unknown"
    start_a = parse_instant(left_from, field="valid-from")
    start_b = parse_instant(right_from, field="valid-from")
    end_a = parse_instant(left_to, field="valid-to") if left_to else None
    end_b = parse_instant(right_to, field="valid-to") if right_to else None
    if end_a is not None and end_a < start_a:
        raise IntelligenceTimeError("intel-window-inverted")
    if end_b is not None and end_b < start_b:
        raise IntelligenceTimeError("intel-window-inverted")
    if end_a is not None and end_a < start_b:
        return "succession"
    if end_b is not None and end_b < start_a:
        return "succession"
    if end_a is None or end_b is None:
        return "unknown"
    if start_a <= end_b and start_b <= end_a:
        return "overlapping"
    return "non-overlapping"
