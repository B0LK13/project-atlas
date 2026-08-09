"""AS-WEB-OPS-HEALTH-001 read-only Ops Health micro-lens gates.

Does NOT claim WEB APPLICATION ACCEPTED. Firewall: apps/web + this test only.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
PAGE = WEB / "src" / "pages" / "production" / "OpsHealthPage.tsx"
APP = WEB / "src" / "App.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
SHELL = WEB / "src" / "components" / "ProdShell.tsx"
CHECKLIST = REPO_ROOT / "docs" / "AS-WEB-ACCEPT-001-checklist.md"


def test_ops_health_route_and_navigation_exist() -> None:
    app = APP.read_text(encoding="utf-8")
    nav = NAV.read_text(encoding="utf-8")
    assert 'path="/ops"' in app
    assert "OpsHealthPage" in app
    assert 'to: "/ops"' in nav


def test_ops_health_is_receipts_oriented_read_only_stub() -> None:
    text = PAGE.read_text(encoding="utf-8").lower()
    assert "receipt evidence" in text
    assert "no live receipt adapter" in text
    assert "receipt_rows=unknown" in text
    assert "read_only=true" in text
    assert "no vault mutation apis" in text


def test_ops_health_enforces_non_authority_invariants() -> None:
    text = PAGE.read_text(encoding="utf-8").lower()
    assert "ui_canonical=false" in text
    assert "graph_authority=false" in text
    assert "unknown≠healthy" in text
    assert "ui ≠ canonical" in text
    assert "graph ≠ authority" in text
    assert "no pilot estate rows" in text


def test_ops_health_keeps_production_skip_link_target() -> None:
    shell = SHELL.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    assert "skip-link" in shell
    assert "Skip to main" in shell
    assert 'id="main"' in page


def test_ops_health_does_not_claim_web_acceptance() -> None:
    checklist = CHECKLIST.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    assert "**WEB APPLICATION ACCEPTED** | **NO**" in checklist
    assert "WEB APPLICATION ACCEPTED = NO" in page
