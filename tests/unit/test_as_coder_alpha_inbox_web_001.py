"""AS-CODER-ALPHA-INBOX-WEB-001 — #/inbox project routing + live-failure honesty."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveInbox.ts"
PAGE = WEB / "src" / "pages" / "production" / "InboxPage.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
APP = WEB / "src" / "App.tsx"

HARBOR = "harbor-api"


def test_inbox_route_and_nav() -> None:
    app = APP.read_text(encoding="utf-8")
    nav = NAV.read_text(encoding="utf-8")
    assert 'path="/inbox"' in app
    assert '{ to: "/inbox", label: "Inbox" }' in nav
    assert '"/inbox"' in nav


def test_inbox_page_follows_project_query() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useSearchParams" in text
    assert 'params.get("project")' in text
    assert "useLiveInbox(projectId)" in text
    assert "inbox-project" in text
    assert "UNKNOWN — inbox project does not match selected project" in text
    assert "inbox≠authority" in text
    assert "listing≠command" in text


def test_inbox_hook_does_not_label_live_failure_as_demo() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "if (liveApiDemoOnly())" in text
    assert 'setDataSource("live_api")' in text
    catch = text.split(".catch", 1)[1]
    assert "setDataSource(null)" in catch
    assert 'setDataSource("demo_stub")' not in catch
    assert "inbox HTTP" in text


def test_no_query_does_not_default_to_harbor_api() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "DEFAULT_PROJECT" not in text
    assert '?? "harbor-api"' not in text
    assert "projectParam && projectParam.trim()" in text
    assert "useLiveInbox(projectId)" in text
    assert 'projectId ?? "UNKNOWN"' in text
    assert "unknown — select a project" in text


def test_explicit_query_uses_live_hook() -> None:
    hook = HOOK.read_text(encoding="utf-8")
    assert "liveApiFetch(`/v1/inbox?project=${encodeURIComponent(projectId)}`)" in hook
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


def test_inbox_is_not_a_command() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "These rows are observations, not commands." in text
    assert "Listing is not a command" in text
