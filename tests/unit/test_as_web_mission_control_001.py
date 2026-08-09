"""AS-WEB-MISSION-001 Mission Control lens gates.

Does NOT claim WEB APPLICATION ACCEPTED. Firewall: apps/web + this test only.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
PAGE = WEB / "src" / "pages" / "production" / "MissionControlPage.tsx"
APP = WEB / "src" / "App.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
SHELL = WEB / "src" / "components" / "ProdShell.tsx"
STUB = WEB / "public" / "sample-mission-control.json"
CHECKLIST = REPO_ROOT / "docs" / "AS-WEB-ACCEPT-001-checklist.md"


def test_mission_control_page_exists() -> None:
    assert PAGE.is_file()


def test_app_registers_mission_control_route() -> None:
    text = APP.read_text(encoding="utf-8")
    assert "/mission-control" in text
    assert "MissionControlPage" in text


def test_prod_nav_links_mission_control() -> None:
    text = NAV.read_text(encoding="utf-8")
    assert "/mission-control" in text
    assert "Mission Control" in text


def test_mission_control_enforces_invariant_banners() -> None:
    text = PAGE.read_text(encoding="utf-8").lower()
    assert "ui" in text and "canonical" in text
    assert "graph" in text and "authority" in text
    assert "unknown" in text and "healthy" in text
    assert "ui_canonical" in text
    assert "graph_authority" in text


def test_prod_shell_skip_link_intact() -> None:
    text = SHELL.read_text(encoding="utf-8")
    assert "skip-link" in text
    assert "Skip to main" in text
    page = PAGE.read_text(encoding="utf-8")
    assert 'id="main"' in page


def test_sample_mission_stub_flags_only_no_pilot_invent() -> None:
    payload = json.loads(STUB.read_text(encoding="utf-8"))
    assert payload["ui_canonical"] is False
    assert payload["graph_authority"] is False
    assert payload["unknown_equals_healthy"] is False
    assert payload["mission_board_available"] is False
    assert payload["rollup"] == "unknown"
    assert payload["pilot_estate_rows"] == []


def test_web_application_accepted_remains_no() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "WEB APPLICATION ACCEPTED" in text
    assert "NO" in text
    page = PAGE.read_text(encoding="utf-8")
    assert "ACCEPTED" in page and "NO" in page
