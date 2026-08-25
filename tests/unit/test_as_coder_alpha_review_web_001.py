"""AS-CODER-ALPHA-REVIEW-MCP-001 web lens — routing + live-failure honesty."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveReviews.ts"
PAGE = WEB / "src" / "pages" / "production" / "ReviewsPage.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
APP = WEB / "src" / "App.tsx"
HOME = WEB / "src" / "pages" / "HomePage.tsx"
HARBOR = "harbor-api"


def test_reviews_page_follows_project_query() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useSearchParams" in text
    assert 'params.get("project")' in text
    assert "useLiveReviews(projectId)" in text
    assert "review-project" in text
    assert "UNKNOWN — review project does not match selected project" in text
    assert "review≠authority" in text
    assert "decide_or_promote=false" in text


def test_reviews_hook_does_not_label_live_failure_as_demo() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "if (liveApiDemoOnly())" in text
    assert 'setDataSource("live_api")' in text
    catch = text.split(".catch", 1)[1]
    assert "setDataSource(null)" in catch
    assert 'setDataSource("demo_stub")' not in catch
    assert "reviews HTTP" in text
    assert "/v1/reviews" in text


def test_no_query_does_not_default_to_harbor_api() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "DEFAULT_PROJECT" not in text
    assert f'?? "{HARBOR}"' not in text
    assert "projectParam && projectParam.trim()" in text


def test_nav_and_route_register_reviews() -> None:
    nav = NAV.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert '{ to: "/reviews", label: "Reviews" }' in nav
    assert 'path="/reviews"' in app
    assert 'to: "/reviews"' in home
