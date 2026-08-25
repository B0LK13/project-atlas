"""AS-CODER-ALPHA-HANDOFF-MCP-001 web lens — routing + live-failure honesty."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveHandoffs.ts"
PAGE = WEB / "src" / "pages" / "production" / "HandoffsPage.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
APP = WEB / "src" / "App.tsx"
HOME = WEB / "src" / "pages" / "HomePage.tsx"

HARBOR = "harbor-api"


def test_handoffs_page_follows_project_query() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useSearchParams" in text
    assert 'params.get("project")' in text
    assert "useLiveHandoffs(projectId)" in text
    assert "handoff-project" in text
    assert "UNKNOWN — handoff project does not match selected project" in text
    assert "handoff≠authority" in text
    assert "create_or_resume=false" in text


def test_handoffs_hook_does_not_label_live_failure_as_demo() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "if (liveApiDemoOnly())" in text
    assert 'setDataSource("live_api")' in text
    catch = text.split(".catch", 1)[1]
    assert "setDataSource(null)" in catch
    assert 'setDataSource("demo_stub")' not in catch
    assert "handoffs HTTP" in text
    assert "liveApiFetch(path)" in text
    assert "/v1/handoffs" in text
    assert "`/v1/handoffs?project=${encodeURIComponent(projectId)}`" in text


def test_no_query_does_not_default_to_harbor_api() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "DEFAULT_PROJECT" not in text
    assert f'?? "{HARBOR}"' not in text
    assert "projectParam && projectParam.trim()" in text
    assert "useLiveHandoffs(projectId)" in text


def test_selector_writes_query_project() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "function onSelectProject(next: string)" in text
    assert 'nextParams.set("project", next)' in text
    assert 'nextParams.delete("project")' in text
    assert "setParams(nextParams, { replace: true })" in text


def test_nav_and_route_register_handoffs() -> None:
    nav = NAV.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert '{ to: "/handoffs", label: "Handoffs" }' in nav
    assert '"/handoffs"' in nav
    assert 'path="/handoffs"' in app
    assert 'to: "/handoffs"' in home
