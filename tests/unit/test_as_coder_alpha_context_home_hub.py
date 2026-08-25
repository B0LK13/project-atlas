"""AS-CODER-ALPHA-CONTEXT-MCP-001 — home hub exposes existing Coder Alpha lenses."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOME = REPO_ROOT / "apps" / "web" / "src" / "pages" / "HomePage.tsx"


def test_home_hub_lists_context_time_machine_ask_knowledge() -> None:
    text = HOME.read_text(encoding="utf-8")
    assert 'to: "/context"' in text
    assert 'title: "Agent context"' in text
    assert 'to: "/time-machine"' in text
    assert 'title: "Time Machine"' in text
    assert 'to: "/ask"' in text
    assert 'title: "Ask Atlas"' in text
    assert 'to: "/knowledge"' in text
    assert 'title: "Knowledge"' in text
    assert "LENS≠authority" in text
    assert "kdiff≠authority" in text
    assert "MODEL_OUTPUT≠authority" in text
