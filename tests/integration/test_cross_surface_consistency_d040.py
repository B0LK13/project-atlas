"""D-040 — cross-surface brief consistency (disk / web / Obsidian / agent)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.agent_handoff import export_agent_context
from project_atlas.connect import connect_project
from project_atlas.obsidian_projection import materialize_obsidian_projection, project_note_path
from project_atlas.web_api.brief import read_project_brief

from tests.integration.d040_cross_surface import (
    FIELD_SET,
    assert_fields_match_authority,
    brief_field_values,
    load_disk_brief,
    parse_obsidian_brief_fields,
)

pytestmark = pytest.mark.integration


def _seed(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "# Cross Surface Fixture\n\n"
        "Purpose: D-040 cross-surface consistency.\n\n"
        "## Stack\n\n"
        "Python 3.12.\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Cross-surface truth\nAll surfaces must agree on brief fields.\n",
        encoding="utf-8",
    )
    return root


def test_cross_surface_brief_fields_match_disk_authority(tmp_path: Path) -> None:
    project = _seed(tmp_path / "cross-surface-fixture")
    project_id = "cross-surface-fixture"
    report = connect_project(project)
    vault = Path(report["vault"])
    assert report["status"] == "connected"

    disk = load_disk_brief(vault, project_id)
    authority = brief_field_values(disk)
    assert disk["honesty"]["atlas_opt_wake_gate"] == "CLOSED"

    web = read_project_brief(vault, project_id)
    assert web["honesty"]["atlas_opt_wake_gate"] == "CLOSED"
    assert_fields_match_authority(
        authority=authority,
        surface="web_api.brief",
        observed=brief_field_values(web),
    )

    materialize_obsidian_projection(vault, project_id=project_id, refresh_brief=False)
    obsidian_text = project_note_path(vault, project_id).read_text(encoding="utf-8")
    assert_fields_match_authority(
        authority=authority,
        surface="obsidian_living_markdown",
        observed=parse_obsidian_brief_fields(obsidian_text),
    )

    ctx = export_agent_context(vault, project_id, refresh_brief=False)
    assert ctx["status"] == "ok"
    agent_payload = json.loads(
        (vault / ctx["json_path"]).read_text(encoding="utf-8")
    )
    brief = agent_payload.get("brief")
    assert isinstance(brief, dict)
    assert agent_payload["honesty"]["atlas_opt_wake_gate"] == "CLOSED"
    assert_fields_match_authority(
        authority=authority,
        surface="export_agent_context.brief",
        observed=brief_field_values(brief),
    )

    # Sanity: all compared fields are present on disk authority.
    assert all(authority[field] for field in FIELD_SET) or any(
        authority[field] == "UNKNOWN" for field in FIELD_SET
    )
