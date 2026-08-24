"""AS-CODER-ALPHA-CHANGED-WEB-001 — #/changed project routing + live-failure honesty."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveChanged.ts"
PAGE = WEB / "src" / "pages" / "production" / "ChangedPage.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
APP = WEB / "src" / "App.tsx"

HARBOR = "harbor-api"


def test_changed_route_and_nav() -> None:
    app = APP.read_text(encoding="utf-8")
    nav = NAV.read_text(encoding="utf-8")
    assert 'path="/changed"' in app
    assert '{ to: "/changed", label: "What Changed" }' in nav
    assert '"/changed"' in nav


def test_changed_page_follows_project_query() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useSearchParams" in text
    assert 'params.get("project")' in text
    assert "useLiveChanged(projectId)" in text
    assert "changed-project" in text
    assert "UNKNOWN — changed project does not match selected project" in text
    assert "changed≠kdiff" in text
    assert "changed≠authority" in text


def test_changed_hook_does_not_label_live_failure_as_demo() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "if (liveApiDemoOnly())" in text
    assert 'setDataSource("live_api")' in text
    catch = text.split(".catch", 1)[1]
    assert "setDataSource(null)" in catch
    assert 'setDataSource("demo_stub")' not in catch
    assert "changed HTTP" in text


def test_no_query_does_not_default_to_harbor_api() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "DEFAULT_PROJECT" not in text
    assert '?? "harbor-api"' not in text
    assert "projectParam && projectParam.trim()" in text
    assert "useLiveChanged(projectId)" in text
    assert 'projectId ?? "UNKNOWN"' in text
    assert "unknown — select a project" in text


def test_explicit_query_uses_live_hook() -> None:
    hook = HOOK.read_text(encoding="utf-8")
    assert "liveApiFetch(`/v1/changed?project=${encodeURIComponent(projectId)}`)" in hook
    assert "if (!projectId)" in hook


def test_selector_writes_query_project() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "function onSelectProject(nextProject: string)" in text
    assert 'nextParams.set("project", nextProject)' in text
    assert 'nextParams.delete("project")' in text
    assert "setParams(nextParams, { replace: true })" in text


def test_harbor_api_valid_only_when_explicitly_selected() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "DEFAULT_PROJECT" not in text
    assert f'"{HARBOR}"' not in text
    assert f"'{HARBOR}'" not in text


def test_changed_is_not_kdiff_or_invented_unchanged() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "This is not" in text
    assert "/v1/kdiff" in text
    assert "UNKNOWN history" in text
    assert "STALE LIVE != UNCHANGED" in text
