"""AS-DEMO-2.1-BROWSER-E2E-001 — isolated BROWSER_E2E_MISSING package presence."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "docs" / "demo" / "browser-e2e"
FX = PKG / "fixtures"


def test_browser_e2e_package_docs_present() -> None:
    required = [
        "AS-DEMO-2.1-BROWSER-E2E-001.md",
        "ARCHITECTURE.md",
        "CONTRACT.md",
        "INVARIANTS.md",
        "FIXTURE-PLAN.md",
        "README.md",
        "checklists/browser-e2e.md",
    ]
    for name in required:
        assert (PKG / name).is_file(), name


def test_browser_e2e_honesty_phrases() -> None:
    card = (PKG / "AS-DEMO-2.1-BROWSER-E2E-001.md").read_text(encoding="utf-8")
    inv = (PKG / "INVARIANTS.md").read_text(encoding="utf-8")
    blob = (card + "\n" + inv).upper()
    assert "BROWSER_E2E_MISSING" in card
    assert "NOT RELEASE CERTIFIED" in card or "ATLAS_2_1_RELEASE_CERTIFIED" in card
    assert "NOT AUTHENTIC PILOT PASS" in card or "PILOT PASS" in card
    assert "PACKAGE ALONE DOES NOT VERIFY TECHNICAL DEMO" in card
    assert "NO_PACKAGE_ALONE_VERIFIED" in inv
    assert "NO_INVENT_PATH_A" in inv
    assert "**NO**" in card


def test_browser_e2e_missing_receipt_fixture() -> None:
    receipt = json.loads(
        (FX / "browser-e2e-missing.receipt.sample.json").read_text(encoding="utf-8")
    )
    assert receipt["status"] == "BROWSER_E2E_MISSING"
    assert receipt["path_a_chips_observed"] is False
    assert receipt["release_certified"] is False
    assert receipt["pilot_pass"] is False
    assert receipt["technical_demo_verified_from_this_package_alone"] is False
    assert receipt["playwright_cypress_in_repo"] is False


def test_browser_e2e_negative_fixtures_present() -> None:
    for name in (
        "negative-invent-verified.expect.json",
        "negative-invent-path-a-observed.expect.json",
        "negative-release-certified.expect.json",
    ):
        data = json.loads((FX / name).read_text(encoding="utf-8"))
        assert data["expect"] == "reject"


def test_frontend_suite_points_at_isolated_package() -> None:
    text = (ROOT / "docs" / "demo" / "FRONTEND-SUITE.md").read_text(encoding="utf-8")
    assert "browser-e2e/AS-DEMO-2.1-BROWSER-E2E-001.md" in text
    assert "BROWSER_E2E_MISSING" in text
