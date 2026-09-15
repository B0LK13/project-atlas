"""AS-SEC-SCAN-CF-001 — Unicode format chars must not hide bearer tokens.

``scan_text`` used a raw ``bearer\\s+`` pattern. A ZERO WIDTH SPACE (Cf)
between ``bearer`` and the token produced zero findings, so ingest could
persist credential-shaped material (NFR-004 / AT-014).

Synthetic token only. Findings remain metadata-only.
"""

from __future__ import annotations

import json

from project_atlas.secrets import REDACTED_PLACEHOLDER, redact_text, scan_text

# Synthetic — never a live credential.
_SYNTH = "A" * 32


def test_plain_bearer_still_detected() -> None:
    findings = scan_text(f"Authorization: bearer {_SYNTH}")
    assert any(item.pattern == "bearer-token" for item in findings)
    dumped = json.dumps([item.__dict__ for item in findings], sort_keys=True)
    assert _SYNTH not in dumped


def test_zwsp_between_bearer_and_token_is_detected() -> None:
    text = f"Authorization: bearer\u200b{_SYNTH}"
    findings = scan_text(text)
    assert any(item.pattern == "bearer-token" for item in findings)
    dumped = json.dumps([item.__dict__ for item in findings], sort_keys=True)
    assert _SYNTH not in dumped


def test_zwsp_bearer_is_redacted() -> None:
    redacted = redact_text(f"Authorization: bearer\u200b{_SYNTH}")
    assert _SYNTH not in redacted
    assert REDACTED_PLACEHOLDER in redacted


def test_soft_hyphen_between_bearer_and_token_is_detected() -> None:
    text = f"Authorization: bearer\u00ad{_SYNTH}"
    findings = scan_text(text)
    assert any(item.pattern == "bearer-token" for item in findings)
