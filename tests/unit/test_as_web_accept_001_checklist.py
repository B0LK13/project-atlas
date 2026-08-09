"""AS-WEB-ACCEPT-001 checklist gates — criteria draft only.

Does NOT claim WEB APPLICATION ACCEPTED. Asserts ADR presence, checklist
artifact, and web_api read-only import boundary for acceptance prep.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr"
CHECKLIST = REPO_ROOT / "docs" / "AS-WEB-ACCEPT-001-checklist.md"
WEB_API_INIT = REPO_ROOT / "src" / "project_atlas" / "web_api" / "__init__.py"


def test_checklist_exists_and_accepted_is_no() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "AS-WEB-ACCEPT-001" in text
    assert "WEB APPLICATION ACCEPTED" in text
    assert "NO" in text
    assert "ACCEPTED" in text


def test_adr_008_009_010_present() -> None:
    expected = [
        "ADR-008-atlas-web-application.md",
        "ADR-009-web-design-tokens.md",
        "ADR-010-atlas-web-ux.md",
    ]
    for name in expected:
        path = ADR_DIR / name
        assert path.is_file(), f"missing ADR: {name}"


def test_adr_008_states_ui_graph_unknown_invariants() -> None:
    text = (ADR_DIR / "ADR-008-atlas-web-application.md").read_text(encoding="utf-8")
    assert "UI" in text and "canonical" in text.lower()
    assert "graph" in text.lower() and "authority" in text.lower()
    assert "unknown" in text.lower() or "healthy" in text.lower()


def test_web_api_init_is_read_only_boundary() -> None:
    text = WEB_API_INIT.read_text(encoding="utf-8")
    assert "Read-only" in text or "read-only" in text
    import_lines = [
        line
        for line in text.splitlines()
        if line.lstrip().startswith("from ") or line.lstrip().startswith("import ")
    ]
    import_lines = [line for line in import_lines if "__future__" not in line]
    forbidden = (
        "knowledge_compiler",
        "ingestion",
        "semantic_compiler",
        "write_plan",
        "_promote",
    )
    for line in import_lines:
        for token in forbidden:
            assert token not in line, f"web_api must not import writer: {token}"
        assert "project_atlas.web_api" in line, "web_api must only import web_api submodules"
