"""AS-2.0-FINAL-CERT-PILOT-WAIVER - fixture-only final-cert pilot pin.

Clears PILOT as a 2.0 release blocker under FIXTURE_ONLY_OWNER_WAIVER.
Never claims authentic estate PILOT PASSED.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

WAIVER_MODE = "FIXTURE_ONLY_OWNER_WAIVER"
HONEST_LABEL = (
    "PILOT PASS — FIXTURE-ONLY UNDER EXPLICIT OWNER FINAL-CERT WAIVER"
)
PACKAGE_ID = "AS-2.0-FINAL-CERT-PILOT-WAIVER"


class FinalCertPilotError(ValueError):
    """Fail-closed final-cert pilot waiver error."""


@lru_cache(maxsize=1)
def load_final_cert_pilot_waiver(
    path: Path | None = None,
) -> dict[str, Any]:
    """Load the shipped final-cert fixture pilot waiver pin."""
    if path is not None:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    else:
        # Prefer docs path relative to package parents when running from source.
        repo = Path(__file__).resolve().parents[2]
        doc = repo / "docs" / "releases" / "2.0.0" / "final-cert-pilot-waiver.json"
        if doc.is_file():
            raw = json.loads(doc.read_text(encoding="utf-8"))
        else:
            raise FinalCertPilotError("final-cert-pilot-waiver-missing")
    if raw.get("atlas_2_0_final_cert_pilot_mode") != WAIVER_MODE:
        raise FinalCertPilotError("final-cert-pilot-mode-mismatch")
    if raw.get("authentic_estate_pilot") is not False:
        raise FinalCertPilotError("final-cert-authentic-pilot-must-be-false")
    if raw.get("owner_waived") is not True:
        raise FinalCertPilotError("final-cert-owner-waived-required")
    return raw


def require_final_cert_pilot_waiver(
    path: Path | None = None,
) -> dict[str, Any]:
    """Require the owner final-cert fixture waiver (unlocks SYNC/TWIN prod)."""
    return load_final_cert_pilot_waiver(path)


def waiver_flags() -> dict[str, Any]:
    """Stable flags for production receipts under the waiver."""
    pin = require_final_cert_pilot_waiver()
    return {
        "pilot_mode": WAIVER_MODE,
        "authentic_estate_pilot": False,
        "owner_waived": True,
        "honest_label": HONEST_LABEL,
        "waiver_tip_at_approval": pin.get("tip_at_approval"),
    }
