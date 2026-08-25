"""AS-CODER-ALPHA-OBSIDIAN-READ-001 web lens — routing + live-failure honesty."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveObsidian.ts"
PAGE = WEB / "src" / "pages" / "production" / "ObsidianPage.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
APP = WEB / "src" / "App.tsx"
HOME = WEB / "src" / "pages" / "HomePage.tsx"
HARBOR = "harbor-api"


def test_obsidian_page_follows_project_query() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useSearchParams" in text
    assert 'params.get("project")' in text
    assert "useLiveObsidian(projectId)" in text
    assert "obsidian-project" in text
    assert "UNKNOWN — living-note project does not match selected project" in text
    assert "projection≠authority" in text
    assert "materialize_or_write=false" in text


def test_obsidian_hook_does_not_label_live_failure_as_demo() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "if (liveApiDemoOnly())" in text
    assert 'setDataSource("live_api")' in text
    catch = text.split(".catch", 1)[1]
    assert "setDataSource(null)" in catch
    assert 'setDataSource("demo_stub")' not in catch
    assert "obsidian HTTP" in text
    assert "liveApiFetch(path)" in text
    assert "/v1/obsidian" in text
    assert "`/v1/obsidian?project=${encodeURIComponent(projectId)}`" in text


def test_no_query_does_not_default_to_harbor_api() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "DEFAULT_PROJECT" not in text
    assert f'?? "{HARBOR}"' not in text
    assert "projectParam && projectParam.trim()" in text
    assert "useLiveObsidian(projectId)" in text


def test_selector_writes_query_project() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "function onSelectProject(next: string)" in text
    assert 'nextParams.set("project", next)' in text
    assert 'nextParams.delete("project")' in text
    assert "setParams(nextParams, { replace: true })" in text


def test_nav_and_route_register_obsidian() -> None:
    nav = NAV.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert '{ to: "/obsidian", label: "Obsidian" }' in nav
    assert '"/obsidian"' in nav
    assert 'path="/obsidian"' in app
    assert 'to: "/obsidian"' in home
