"""AS-CODER-ALPHA-CROSS-SURFACE-002 — brief/context agree drift is not current."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.agent_handoff import export_agent_context
from project_atlas.connect import connect_project
from project_atlas.overview import build_overview_lens
from project_atlas.project_brief import build_project_brief
from project_atlas.project_state import build_state_lens

pytestmark = pytest.mark.integration


def _seed(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "README.md").write_text(
        "# Drift fixture\n\nPurpose: cross-surface.\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\nKeep drift honest.\n",
        encoding="utf-8",
    )
    return root


def _assert_not_current(honesty: dict[str, object]) -> None:
    assert honesty.get("stale_is_current") is False
    assert honesty.get("lens_is_authority") is False


def test_cross_surface_stale_inventory_is_not_current(tmp_path: Path) -> None:
    project = _seed(tmp_path / "cross-surface-drift")
    report = connect_project(project)
    project_id = str(report["bound_project_id"])
    vault = Path(report["vault"])
    (project / "README.md").write_text("# Drift fixture\n\nmutated corpus\n", encoding="utf-8")

    brief = build_project_brief(vault, project_id)
    overview = build_overview_lens(vault, project_id)
    state = build_state_lens(vault, project_id)
    exported = export_agent_context(vault, project_id)
    context = json.loads((vault / exported["json_path"]).read_text(encoding="utf-8"))

    assert brief["source_drift"]["status"] == "STALE"
    assert overview["source_drift"]["status"] == "STALE"
    assert state["source_drift"]["status"] == "STALE"
    assert context["brief"]["source_drift"]["status"] == "STALE"

    _assert_not_current(brief["honesty"])
    _assert_not_current(overview["honesty"])
    _assert_not_current(state["honesty"])
    _assert_not_current(context["brief"]["honesty"])
    assert context["honesty"].get("lens_is_authority") is False
