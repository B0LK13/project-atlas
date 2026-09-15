"""AS-PILOT fixture-only owner waiver guards (never authentic estate pilot)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAIVER = ROOT / "docs" / "AS-PILOT-FIXTURE-ONLY-WAIVER.md"


def test_pilot_fixture_only_waiver_present_and_honest() -> None:
    assert WAIVER.is_file()
    text = WAIVER.read_text(encoding="utf-8")
    assert "pilot_mode" in text
    assert "FIXTURE_ONLY_OWNER_WAIVER" in text
    assert "owner_authorized" in text
    assert "`true`" in text or "true" in text
    assert "D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001" in text
    assert "FIXTURE-ONLY CERTIFICATION UNDER OWNER WAIVER" in text
    assert "ESTATE PILOT PASSED (authentic / production) | **NO**" in text
    # Never claim authentic / production estate pilot
    assert "REAL / AUTHENTIC / PRODUCTION estate pilot" in text
    assert "never" in text.lower() or "not" in text.lower()
