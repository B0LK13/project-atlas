"""AS-CODER-ALPHA-CONTEXT-001 web paste-pack honesty gates.

Firewall: web context page + markdown helper. Does not write context files.
WEB_CONTEXT != ATLAS_CONTEXT_FILE. LENS != authority.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HELPER = WEB / "src" / "lib" / "agentContextMarkdown.ts"
PAGE = WEB / "src" / "pages" / "production" / "ContextPage.tsx"
APP = WEB / "src" / "App.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
KNOWLEDGE = WEB / "src" / "pages" / "production" / "KnowledgePage.tsx"
HANDOFF = REPO_ROOT / "src" / "project_atlas" / "agent_handoff.py"


def test_route_and_nav_exist() -> None:
    assert 'path="/context"' in APP.read_text(encoding="utf-8")
    assert '{ to: "/context", label: "Context" }' in NAV.read_text(encoding="utf-8")
    knowledge = KNOWLEDGE.read_text(encoding="utf-8")
    assert "/context?project=" in knowledge
    assert "agent context (≠ authority)" in knowledge


def test_helper_keeps_unknown_and_non_authority() -> None:
    text = HELPER.read_text(encoding="utf-8")
    assert 'return "UNKNOWN"' in text
    assert "WEB_CONTEXT != ATLAS_CONTEXT_FILE" in text
    assert "LENS != AUTHORITY" in text
    assert "UNKNOWN stays UNKNOWN" in text
    assert "conversation≠authority" in text


def test_page_is_read_only_live_brief() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useLiveBrief" in text
    assert "renderAgentContextMarkdown" in text
    assert "web_context≠atlas_context_file" in text
    assert "UNKNOWN — no live brief projection" in text
    assert "Copy for next agent" in text
    assert "method: \"POST\"" not in text


def test_package_does_not_mutate_cli_context_writer() -> None:
    text = HANDOFF.read_text(encoding="utf-8")
    assert "def export_agent_context(" in text
