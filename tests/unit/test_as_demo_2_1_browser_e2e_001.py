"""AS-DEMO-2.1-BROWSER-E2E-001 — isolated BROWSER_E2E_MISSING honesty phrases."""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PKG = _REPO_ROOT / "docs" / "demo" / "browser-e2e"
_FIXTURES = _PKG / "fixtures"

_REQUIRED_DOC_PHRASES = (
    "BROWSER_E2E_MISSING",
    "NOT RELEASE CERTIFIED",
    "NOT AUTHENTIC PILOT PASS",
)

_REQUIRED_DOC_FILES = (
    "AS-DEMO-2.1-BROWSER-E2E-001.md",
    "ARCHITECTURE.md",
    "CONTRACT.md",
    "INVARIANTS.md",
    "FIXTURE-PLAN.md",
    "checklists/browser-e2e.md",
)

_REQUIRED_FIXTURES = (
    "browser-e2e-missing.receipt.sample.json",
    "negative-invent-verified.expect.json",
    "negative-invent-path-a-observed.expect.json",
    "negative-release-certified.expect.json",
)


def _read(rel: str) -> str:
    path = _PKG / rel
    assert path.is_file(), f"missing package file: {path}"
    return path.read_text(encoding="utf-8")


def test_as_demo_2_1_browser_e2e_001_package_files_exist() -> None:
    assert _PKG.is_dir(), f"missing package dir: {_PKG}"
    for rel in _REQUIRED_DOC_FILES:
        assert (_PKG / rel).is_file(), f"missing {rel}"
    for name in _REQUIRED_FIXTURES:
        assert (_FIXTURES / name).is_file(), f"missing fixtures/{name}"


def test_as_demo_2_1_browser_e2e_001_docs_honesty_phrases() -> None:
    joined = "\n".join(_read(rel) for rel in _REQUIRED_DOC_FILES)
    for phrase in _REQUIRED_DOC_PHRASES:
        assert phrase in joined, f"missing honesty phrase {phrase!r}"
    # Package alone must not claim VERIFIED is already earned.
    assert "package alone" in joined.lower() or "≠ VERIFIED" in joined or (
        "does not" in joined.lower() and "VERIFIED" in joined
    )
    assert "NOT RELEASE CERTIFIED" in joined
    assert "NOT AUTHENTIC PILOT PASS" in joined


def test_as_demo_2_1_browser_e2e_001_package_card_not_pre_verified() -> None:
    card = _read("AS-DEMO-2.1-BROWSER-E2E-001.md")
    assert "BROWSER_E2E_MISSING" in card
    assert "NOT RELEASE CERTIFIED" in card
    assert "NOT AUTHENTIC PILOT PASS" in card
    # Must explicitly deny pre-verify / auto-stamp; must not affirm VERIFIED=YES.
    assert "TECHNICAL DEMO — VERIFIED = YES" not in card
    assert "is **not** already earned" in card or "is not already earned" in card.lower()
    assert "does **not** auto-stamp VERIFIED" in card or "does not auto-stamp" in card.lower()


def test_as_demo_2_1_browser_e2e_001_missing_receipt_fixture() -> None:
    raw = (_FIXTURES / "browser-e2e-missing.receipt.sample.json").read_text(
        encoding="utf-8"
    )
    data = json.loads(raw)
    assert data["status"] == "BROWSER_E2E_MISSING"
    assert data["path_a_chips_observed"] is False
    assert data["release_certified"] is False
    assert data["pilot_pass"] is False
    assert data["technical_demo_verified"] is False
    assert data["atlas_2_1_release_certified"] is False
    non_claims = "\n".join(data.get("non_claims", []))
    assert "NOT RELEASE CERTIFIED" in non_claims
    assert "NOT AUTHENTIC PILOT PASS" in non_claims
    assert "VERIFIED" in non_claims


def test_as_demo_2_1_browser_e2e_001_negative_fixtures() -> None:
    verified = json.loads(
        (_FIXTURES / "negative-invent-verified.expect.json").read_text(encoding="utf-8")
    )
    assert verified["expected_error"] == "browser-e2e-invent-verified-forbidden"
    assert verified["technical_demo_verified"] is False

    path_a = json.loads(
        (_FIXTURES / "negative-invent-path-a-observed.expect.json").read_text(
            encoding="utf-8"
        )
    )
    assert path_a["expected_error"] == "browser-e2e-invent-path-a-observed-forbidden"
    assert path_a["path_a_chips_observed"] is False

    release = json.loads(
        (_FIXTURES / "negative-release-certified.expect.json").read_text(encoding="utf-8")
    )
    assert release["expected_error"] == "browser-e2e-release-certified-forbidden"
    assert release["release_certified"] is False
    assert release["atlas_2_1_release_certified"] is False


def test_as_demo_2_1_browser_e2e_001_frontend_suite_links_package() -> None:
    suite = (_REPO_ROOT / "docs" / "demo" / "FRONTEND-SUITE.md").read_text(
        encoding="utf-8"
    )
    assert "BROWSER_E2E_MISSING" in suite
    assert "browser-e2e/AS-DEMO-2.1-BROWSER-E2E-001.md" in suite
