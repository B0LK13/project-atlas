"""AS-2.0-WEB-001 ProdNav project-context for Intelligence."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[2]
NAV = REPO_ROOT / "apps" / "web" / "src" / "components" / "ProdNav.tsx"
PAGE = REPO_ROOT / "apps" / "web" / "src" / "pages" / "production" / "IntelligencePage.tsx"

DARK_FACTORY = "dark-factory-02ee94d0"
HARBOR = "harbor-api"
PROJECT_AWARE = {
    "/knowledge",
    "/intelligence",
    "/context",
    "/ask",
    "/time-machine",
    "/roadmap",
    "/workspace",
}


def _project_aware_href(path: str, project: str | None) -> str:
    if not project or path not in PROJECT_AWARE:
        return path
    return f"{path}?project={quote(project, safe='')}"


def test_intelligence_nav_preserves_project_and_not_from_to() -> None:
    text = NAV.read_text(encoding="utf-8")
    assert '"/intelligence"' in text
    assert "never from=/to=" in text
    assert 'params.get("from")' not in text
    helper = text.split("export function projectAwareHref", 1)[1].split(
        "export function ProdNav",
        1,
    )[0]
    assert "from" not in helper
    assert "to=" not in helper
    href = _project_aware_href("/intelligence", DARK_FACTORY)
    assert href == f"/intelligence?project={DARK_FACTORY}"
    assert HARBOR not in href
    bare = _project_aware_href("/intelligence", None)
    assert bare == "/intelligence"
    page = PAGE.read_text(encoding="utf-8")
    assert f'"{HARBOR}"' not in page
