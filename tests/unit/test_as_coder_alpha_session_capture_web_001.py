"""AS-CODER-ALPHA-SESSION-CAPTURE-READ-001 web lens."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveSessionCaptures.ts"
PAGE = WEB / "src" / "pages" / "production" / "SessionCapturesPage.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
APP = WEB / "src" / "App.tsx"
HOME = WEB / "src" / "pages" / "HomePage.tsx"
HARBOR = "harbor-api"


def test_page_follows_project_query() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useSearchParams" in text
    assert 'params.get("project")' in text
    assert "useLiveSessionCaptures(projectId)" in text
    assert "session-project" in text
    assert "UNKNOWN — capture project does not match selected project" in text
    assert "ops-receipt≠truth-core" in text
    assert "record_or_write=false" in text


def test_hook_does_not_label_live_failure_as_demo() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "if (liveApiDemoOnly())" in text
    assert 'setDataSource("live_api")' in text
    catch = text.split(".catch", 1)[1]
    assert "setDataSource(null)" in catch
    assert 'setDataSource("demo_stub")' not in catch
    assert "/v1/session-captures" in text


def test_no_query_does_not_default_to_harbor_api() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "DEFAULT_PROJECT" not in text
    assert f'?? "{HARBOR}"' not in text


def test_nav_and_route_register_session_captures() -> None:
    nav = NAV.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert '{ to: "/session-captures", label: "Sessions" }' in nav
    assert 'path="/session-captures"' in app
    assert 'to: "/session-captures"' in home
