"""AS-PROJECT-ROADMAP-001 web lens — project routing + live-failure honesty."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveRoadmap.ts"
PAGE = WEB / "src" / "pages" / "production" / "RoadmapPage.tsx"


def test_roadmap_page_follows_project_query() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useSearchParams" in text
    assert 'params.get("project")' in text
    assert "useLiveRoadmap(projectId)" in text
    assert "roadmap-project" in text
    assert "UNKNOWN — roadmap project does not match selected project" in text
    assert "roadmap≠authority" in text


def test_roadmap_hook_does_not_label_live_failure_as_demo() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "if (liveApiDemoOnly())" in text
    assert 'setDataSource("live_api")' in text
    catch = text.split(".catch", 1)[1]
    assert "setDataSource(null)" in catch
    assert 'setDataSource("demo_stub")' not in catch
    assert "roadmap HTTP" in text
