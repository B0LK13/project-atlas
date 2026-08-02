"""Conservative content-based secret detection for source ingestion (NFR-004)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretFinding:
    pattern: str
    confidence: str
    redacted_hint: str


_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("private-key", "high", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer-token", "high", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    ("api-key-assignment", "high", re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{20,}")),
    ("password-assignment", "medium", re.compile(r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*[^\s,;]{8,}")),
    ("connection-string", "high", re.compile(r"(?i)\b(?:postgres|mysql|mongodb(?:\+srv)?|redis)://[^\s]+")),
    ("cloud-access-key", "high", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)


def scan_text(text: str) -> list[SecretFinding]:
    """Return metadata-only findings; matched content is never returned."""
    return [
        SecretFinding(name, confidence, "content redacted")
        for name, confidence, pattern in _PATTERNS
        if pattern.search(text)
    ]
