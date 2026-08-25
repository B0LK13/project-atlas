"""Encoding-safe human-facing stdout rendering.

Decorative glyphs (e.g. U+2192 RIGHTWARDS ARROW) fall back to ASCII when the
target stream encoding cannot represent them. User/content text is preserved
when possible; remaining unencodable characters use backslashreplace (never
errors=\"ignore\"). Machine-readable output (JSON) must not pass through here.
"""

from __future__ import annotations

import sys
from typing import TextIO

# Decorative literals only — not user/project content.
_DECORATIVE_FALLBACKS: dict[str, str] = {
    "\u2192": "->",  # RIGHTWARDS ARROW (atlas attention care_about separator)
}


def _stream_encoding(stream: TextIO) -> str:
    enc = getattr(stream, "encoding", None)
    return enc if enc else "utf-8"


def _strict_encodable(text: str, encoding: str) -> bool:
    try:
        text.encode(encoding, errors="strict")
    except UnicodeEncodeError:
        return False
    return True


def adapt_human_text(text: str, *, encoding: str) -> str:
    """Return ``text`` safe for strict write to a human terminal stream."""
    if _strict_encodable(text, encoding):
        return text
    adapted = text
    for glyph, fallback in _DECORATIVE_FALLBACKS.items():
        adapted = adapted.replace(glyph, fallback)
    if _strict_encodable(adapted, encoding):
        return adapted
    return adapted.encode(encoding, errors="backslashreplace").decode(encoding)


def human_print(
    *parts: object,
    sep: str = " ",
    end: str = "\n",
    file: TextIO | None = None,
    flush: bool = False,
) -> None:
    """Print human-facing text with encoding-aware decorative fallbacks.

    ``flush`` defaults to False to match built-in ``print()``. No repository
    contract requires unconditional per-line flush (SHADOW-C-002).
    """
    stream = file or sys.stdout
    text = sep.join(str(p) for p in parts) + end
    safe = adapt_human_text(text, encoding=_stream_encoding(stream))
    stream.write(safe)
    if flush and getattr(stream, "flush", None):
        stream.flush()
