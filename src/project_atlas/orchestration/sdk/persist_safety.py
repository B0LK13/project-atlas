"""Omit decoded secret-shaped scalars from SDK runtime persist.

AS-SEC-SCAN-ORCH-SDK-RUNTIME-PERSIST-JSON-ESC-001: ``json.loads`` decodes
JSON ``\\u`` escapes that ``scan_text`` misses on raw bytes. Incremental
SDK stores must not rewrite those tokens as object keys or values.
"""

from __future__ import annotations

import re
from typing import Any

_FALLBACK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
)


def has_secret(text: str) -> bool:
    try:
        from project_atlas.secrets import scan_text
    except ImportError:
        return any(pattern.search(text) for pattern in _FALLBACK_PATTERNS)
    return bool(scan_text(text))


def safe_persist_text(raw: str) -> str:
    return "UNKNOWN" if has_secret(raw) else raw


def safe_persist(payload: Any) -> Any:
    """Walk persist payloads: omit secret keys, replace secret strings."""
    if isinstance(payload, str):
        return safe_persist_text(payload)
    if isinstance(payload, dict):
        return {
            key: safe_persist(value)
            for key, value in payload.items()
            if not (isinstance(key, str) and has_secret(key))
        }
    if isinstance(payload, list):
        return [safe_persist(value) for value in payload]
    return payload
