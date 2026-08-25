"""AT3-047 — Privacy / secret gate for Atlas 3 memory."""

from __future__ import annotations

from typing import Any

from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.secrets import scan_text


def apply_privacy(text: str, *, privacy_class: str = "include") -> str:
    if privacy_class == "exclude":
        raise Atlas3Error("PRIVACY_EXCLUDE", "message excluded by privacy policy")
    findings = scan_text(text)
    if findings:
        names = ",".join(sorted({item.pattern for item in findings}))
        raise Atlas3Error("SECRET_CONTENT", f"secret-shaped content ({names})")
    if privacy_class == "redact":
        return "[REDACTED]"
    if privacy_class == "quarantine":
        return text
    return text


def scan_or_raise(*texts: str) -> None:
    for text in texts:
        if not text:
            continue
        findings = scan_text(text)
        if findings:
            names = ",".join(sorted({item.pattern for item in findings}))
            raise Atlas3Error("SECRET_CONTENT", f"secret-shaped content ({names})")


def privacy_defaults() -> dict[str, Any]:
    return {
        "package": "AT3-047",
        "raw_full_transcript_retention": "MINIMIZED",
        "default_network_access": False,
        "silent_billing": False,
        "secret_persistence": False,
        "automatic_canonical_promotion": False,
    }
