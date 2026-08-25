"""AS-CODER-ALPHA-DOCTOR-MCP-001 web lens — routing + live-failure honesty."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"
HOOK = WEB / "src" / "hooks" / "useLiveDoctor.ts"
PAGE = WEB / "src" / "pages" / "production" / "DoctorPage.tsx"
NAV = WEB / "src" / "components" / "ProdNav.tsx"
APP = WEB / "src" / "App.tsx"
HOME = WEB / "src" / "pages" / "HomePage.tsx"


def test_doctor_page_does_not_grant_gates() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "useLiveDoctor()" in text
    assert "doctor≠authority" in text
    assert "owner_gate_grant=false" in text
    assert "unknown≠healthy" in text
    assert "DEFAULT_PROJECT" not in text


def test_doctor_hook_does_not_label_live_failure_as_demo() -> None:
    text = HOOK.read_text(encoding="utf-8")
    assert "if (liveApiDemoOnly())" in text
    assert 'setDataSource("live_api")' in text
    catch = text.split(".catch", 1)[1]
    assert "setDataSource(null)" in catch
    assert 'setDataSource("demo_stub")' not in catch
    assert "doctor HTTP" in text
    assert 'liveApiFetch("/v1/doctor")' in text


def test_nav_and_route_register_doctor() -> None:
    nav = NAV.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    home = HOME.read_text(encoding="utf-8")
    assert '{ to: "/doctor", label: "Doctor" }' in nav
    assert 'path="/doctor"' in app
    assert 'to: "/doctor"' in home
