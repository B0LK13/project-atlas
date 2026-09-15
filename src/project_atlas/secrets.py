"""Conservative content-based secret detection for source ingestion (NFR-004).

CODEX-SEC-006 / NFR-004: findings are metadata-only. Matched secret values are
never returned, logged, or persisted. Use ``redact_text`` when a surrounding
string must be retained after detection.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Fixed placeholder — never includes matched secret material (CODEX-SEC-006).
REDACTED_PLACEHOLDER = "[redacted]"


@dataclass(frozen=True)
class SecretFinding:
    pattern: str
    confidence: str
    redacted_hint: str


_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    # SEC-SCAN-A-021: redact the full PEM block (header + body + footer), not
    # only the BEGIN line — otherwise key material remains after redact_text.
    (
        "private-key",
        "high",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
            r"[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ),
    ("bearer-token", "high", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}")),
    (
        "api-key-assignment",
        "high",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{20,}"
        ),
    ),
    (
        "password-assignment",
        "medium",
        re.compile(r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*[^\s,;]{8,}"),
    ),
    (
        "connection-string",
        "high",
        re.compile(r"(?i)\b(?:postgres|mysql|mongodb(?:\+srv)?|redis)://[^\s]+"),
    ),
    ("cloud-access-key", "high", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)


def _compatibility_view(text: str) -> str:
    """NFKC-fold compatibility lookalikes (AS-SEC-SCAN-NFKC-001).

    Fullwidth Latin (U+FF42..U+FF52 ``bearer``), fullwidth ``=`` / ``_``,
    and ideographic space become the ASCII forms the existing detectors
    already match. Distinct from format-control (Cf) separator folding:
    NFKC does not insert spaces for ZERO WIDTH SPACE, and Cf folding does
    not map fullwidth letters. True confusables (Cyrillic/Greek
    lookalikes) are out of scope.
    """
    return unicodedata.normalize("NFKC", text)


def scan_text(text: str) -> list[SecretFinding]:
    """Return metadata-only findings; matched content is never returned."""
    folded = _compatibility_view(text)
    return [
        SecretFinding(name, confidence, "content redacted")
        for name, confidence, pattern in _PATTERNS
        if pattern.search(text) or pattern.search(folded)
    ]


def redact_text(text: str) -> str:
    """Replace matched secret spans with ``REDACTED_PLACEHOLDER`` (CODEX-SEC-006).

    Safe for persistence of surrounding context. Does not return raw matches.
    Compatibility characters are NFKC-folded first so a fullwidth ``bearer``
    token cannot survive redaction.
    """
    result = _compatibility_view(text)
    for _name, _confidence, pattern in _PATTERNS:
        result = pattern.sub(REDACTED_PLACEHOLDER, result)
    return result
