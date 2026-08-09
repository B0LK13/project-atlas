"""AS-WEB-ACCEPT-005 governor evidence guards (acceptance remains human)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = "ac1cee723f368154334815dade33212e593fc88c"
TREE = "e0ed54782830df036cc439fa127ff5a16c5d8915"


def test_as_web_accept_005_evidence_is_pinned_and_non_accepting() -> None:
    evidence = ROOT / "docs" / "AS-WEB-ACCEPT-005-governor-evidence.md"
    assert evidence.is_file()
    text = evidence.read_text(encoding="utf-8")
    assert MAIN in text
    assert TREE in text
    assert "WEB APPLICATION ACCEPTED = **NO**" in text
    assert "Governor decision = **PENDING**" in text


def test_as_web_accept_005_governor_decision_remains_pending() -> None:
    signoff = (ROOT / "docs" / "AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md").read_text(
        encoding="utf-8"
    )
    assert MAIN in signoff
    assert TREE in signoff
    assert "Governor decision | **PENDING**" in signoff
    governor_checks = [line for line in signoff.splitlines() if line.startswith("- [")]
    assert governor_checks, "governor checklist must be present"
    assert all(line.startswith("- [ ]") for line in governor_checks)
    assert "WEB APPLICATION ACCEPTED** | **NO**" in signoff


def test_as_web_accept_005_checklist_pin_and_item_10_stay_open() -> None:
    checklist = (ROOT / "docs" / "AS-WEB-ACCEPT-001-checklist.md").read_text(
        encoding="utf-8"
    )
    assert MAIN in checklist
    assert TREE in checklist
    assert "| 10 | Governor sign-off artifact + tip pin recorded" in checklist
    assert "| **open** |" in checklist
    assert "**WEB APPLICATION ACCEPTED** | **NO**" in checklist
