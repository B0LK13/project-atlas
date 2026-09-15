"""AS-WEB-WORKSPACE-001 Workspace lens gates.

Does NOT claim WEB APPLICATION ACCEPTED. Firewall: apps/web + this test only.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
PAGE = WEB / "src" / "pages" / "production" / "WorkspacePage.tsx"
APP = WEB / "src" / "App.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
SHELL = WEB / "src" / "components" / "ProdShell.tsx"
STUB = WEB / "public" / "sample-workspace.json"
CHECKLIST = REPO_ROOT / "docs" / "AS-WEB-ACCEPT-001-checklist.md"


def test_workspace_page_exists() -> None:
    assert PAGE.is_file()


def test_app_registers_workspace_route() -> None:
    text = APP.read_text(encoding="utf-8")
    assert "/workspace" in text
    assert "WorkspacePage" in text


def test_prod_nav_links_workspace() -> None:
    text = NAV.read_text(encoding="utf-8")
    assert "/workspace" in text
    assert "Workspace" in text


def test_workspace_enforces_invariant_banners() -> None:
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


def test_sample_workspace_stub_flags_only_no_pilot_invent() -> None:
    payload = json.loads(STUB.read_text(encoding="utf-8"))
    assert payload["ui_canonical"] is False
    assert payload["graph_authority"] is False
    assert payload["unknown_equals_healthy"] is False
    assert payload["workspace_board_available"] is False
    assert payload["rollup"] == "unknown"
    assert payload["pilot_estate_rows"] == []


def test_web_application_accepted_is_yes_ui_not_canonical() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "**WEB APPLICATION ACCEPTED** | **YES**" in text
    page = PAGE.read_text(encoding="utf-8")
    assert "APPLICATION ACCEPTED = YES" in page
    assert "UI ≠ canonical" in page
