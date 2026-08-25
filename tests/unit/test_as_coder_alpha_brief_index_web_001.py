"""AS-CODER-ALPHA-BRIEF-INDEX-WEB-001 — vault-scoped brief index honesty.

Firewall: web index page + hook only. Does not add /v1/briefs, does not
write Layer B, does not grant owner capability, does not touch D-149.
BRIEF != AUTHORITY. UI != CANONICAL. MCP != AUTHORITY.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveBriefIndex.ts"
PAGE = WEB / "src" / "pages" / "production" / "BriefIndexPage.tsx"
APP = WEB / "src" / "App.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
HOME = WEB / "src" / "pages" / "HomePage.tsx"
PROJECTS = WEB / "src" / "pages" / "production" / "ProjectsPage.tsx"
API_SERVER = REPO_ROOT / "src" / "project_atlas" / "api_server.py"
MCP_SERVER = REPO_ROOT / "src" / "project_atlas" / "mcp_server.py"
AUTHENTIC = (
    REPO_ROOT / "src" / "project_atlas" / "orchestration" / "autonomy" / "authentic_estate.py"
)


def test_route_and_nav_exist() -> None:
    assert 'path="/briefs"' in APP.read_text(encoding="utf-8")
    assert "BriefIndexPage" in APP.read_text(encoding="utf-8")
    assert '{ to: "/briefs", label: "Briefs" }' in NAV.read_text(encoding="utf-8")
    assert 'to: "/briefs"' in HOME.read_text(encoding="utf-8")
    assert 'to="/briefs"' in PROJECTS.read_text(encoding="utf-8")


def test_page_is_read_only_vault_scoped() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useLiveBriefIndex" in text
    assert "AS-CODER-ALPHA-BRIEF-INDEX-WEB-001" in text
    assert "brief≠authority" in text
    assert "mcp≠authority" in text
    assert "unknown≠healthy" in text
    assert "owner_capability_granted=false" in text
    assert "zero_arg_vault_scope=true" in text
    assert "UNKNOWN — no project rows in read-status" in text
    assert 'method: "POST"' not in text
    assert "atlas connect" not in text
    for forbidden in (
        "useLiveAsk",
        "useLiveTimeMachine",
        "useEstateDiscovery",
        "AUTHENTIC_ESTATE_ROOT",
    ):
        assert forbidden not in text


def test_hook_composes_existing_brief_api_only() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "AS-CODER-ALPHA-BRIEF-INDEX-WEB-001" in text
    assert "/v1/brief?project=" in text
    assert "/v1/briefs" not in text
    assert "owner_capability_granted: false" in text
    assert "brief_is_authority: false" in text
    assert "zero_arg_vault_scope: true" in text
    assert "portfolio_implicit_all: false" in text
    assert "authentic_pilot: false" in text
    assert "useReadStatus" in text
    assert "liveApiDemoOnly" in text
    assert "demo_stub" in text
    assert 'method: "POST"' not in text
    assert "write_estate_credential" not in text


def test_does_not_invent_briefs_http_protocol() -> None:
    api = API_SERVER.read_text(encoding="utf-8")
    assert '"/v1/briefs"' not in api
    assert "brief-requires-project" in api
    mcp = MCP_SERVER.read_text(encoding="utf-8")
    assert "atlas.brief.read" in mcp
    assert "atlas.briefs.index" not in mcp


def test_package_does_not_touch_d149_or_owner_gates() -> None:
    hook = HOOK.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    authentic = AUTHENTIC.read_text(encoding="utf-8")
    for blob in (hook, page):
        assert "refresh_authentic_o2_node_states" not in blob
        assert "OWNER_GATE" not in blob
        assert "OWNER_CAPABILITY_GRANTED" not in blob
    # Live D-149/D-148 module remains on main; this package must not rewrite it.
    assert "def refresh_authentic_o2_node_states" in authentic
    assert 'OWNER_CAPABILITY_GRANTED": False' in authentic
