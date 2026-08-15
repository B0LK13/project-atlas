"""AS-CODER-ALPHA-BRIEF-STALE-HONESTY-001 — brief honesty follows next drift."""

from __future__ import annotations

from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.project_brief import build_project_brief


def test_brief_honesty_stale_after_edit_without_reconnect(tmp_path: Path) -> None:
    project = tmp_path / "brief-stale"
    project.mkdir()
    (project / "README.md").write_text("# Brief stale\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\nKeep brief honest.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    fresh = build_project_brief(vault, project_id, refresh=False)
    assert fresh["honesty"]["answer_evidence_stale"] is False
    assert fresh["honesty"]["stale_is_current"] is False
    (project / "README.md").write_text("# Brief stale\n\nv2 changed\n", encoding="utf-8")
    stale = build_project_brief(vault, project_id, refresh=False)
    assert stale["honesty"]["answer_evidence_stale"] is True
    assert stale["honesty"]["stale_is_current"] is False
    suggested = " ".join(stale["suggested_next_work"]).lower()
    assert "stale" in suggested or "connect" in suggested


def test_brief_does_not_echo_secret_after_stale_edit(tmp_path: Path) -> None:
    project = tmp_path / "brief-secret"
    project.mkdir()
    (project / "README.md").write_text("# Brief\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text("# Decisions\n\nHonest.\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    secret = "AKIAIOSFODNN7EXAMPLE"
    (project / "README.md").write_text(f"key={secret}\n", encoding="utf-8")
    brief = build_project_brief(vault, project_id, refresh=False)
    assert brief["honesty"]["answer_evidence_stale"] is True
    assert secret not in str(brief)
