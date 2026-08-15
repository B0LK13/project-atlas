"""AS-CODER-ALPHA-OBSIDIAN-002 — living note parity with agent context."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.obsidian_projection import (
    materialize_obsidian_projection,
    project_note_path,
)


def test_obsidian_includes_attention_source_health_roadmap(tmp_path: Path) -> None:
    root = tmp_path / "obs2"
    root.mkdir()
    (root / "README.md").write_text("# Obsidian parity\n\nPython brain.\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Keep derived notes\nObsidian is not authority.\n",
        encoding="utf-8",
    )
    report = connect_project(root)
    vault = Path(report["vault"])
    project_id = str(report["bound_project_id"])
    note = project_note_path(vault, project_id)
    text = note.read_text(encoding="utf-8")
    assert "## Current project position (derived roadmap)" in text
    assert "ROADMAP!=CANONICAL_TRUTH" in text
    assert "## Attention (what requires action)" in text
    assert "ATTENTION LENS != AUTHORITY" in text
    assert "## Source health (failures / exclusions)" in text
    assert "SOURCE HEALTH != AUTHORITY" in text
    assert "attention_is_health_score: false" in text
    assert "roadmap_is_canonical: false" in text
    assert "<!-- BEGIN HUMAN: notes -->" in text


def test_obsidian_002_preserves_human_and_does_not_invent(tmp_path: Path) -> None:
    root = tmp_path / "obs2-human"
    root.mkdir()
    (root / "README.md").write_text("# Sparse\n\nNo decisions.\n", encoding="utf-8")
    connected = connect_project(root)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    note = project_note_path(vault, project_id)
    humanized = note.read_text(encoding="utf-8").replace(
        "<!-- BEGIN HUMAN: notes -->\n<!-- END HUMAN: notes -->",
        "<!-- BEGIN HUMAN: notes -->\nKeep human edit.\n<!-- END HUMAN: notes -->",
    )
    note.write_text(humanized, encoding="utf-8")
    materialize_obsidian_projection(vault, project_id=project_id, refresh_brief=False)
    refreshed = note.read_text(encoding="utf-8")
    assert "Keep human edit." in refreshed
    assert "UNKNOWN" in refreshed
    receipt = json.loads(
        (vault / "generated" / "ops" / "obsidian" / "living-projection-receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["canonical_writes"] is False
    assert receipt["honesty"]["lens_is_authority"] is False
