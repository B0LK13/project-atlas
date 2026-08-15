"""AS-CODER-ALPHA-DECISIONS-STALE-001 — governing evidence must not look current after drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.project_decisions import build_decisions_lens


def test_decisions_md_edit_without_reconnect_is_stale(tmp_path: Path) -> None:
    project = tmp_path / "dec-stale"
    project.mkdir()
    (project / "README.md").write_text("# Decisions stale\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Keep next derived\nNext is not a command.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    fresh = build_decisions_lens(vault, project_id)
    assert fresh["honesty"]["governing_evidence_stale"] is False
    (project / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Supersede next derived\nUse a different rule.\n",
        encoding="utf-8",
    )
    stale = build_decisions_lens(vault, project_id)
    assert stale["honesty"]["governing_evidence_stale"] is True
    assert stale["honesty"]["stale_is_current"] is False
    assert stale["source_drift"]["status"] == "STALE"
    changed = [path.lower() for path in stale["source_drift"]["changed_paths"]]
    assert any(path.endswith("decisions.md") for path in changed)


def test_decisions_stale_does_not_echo_secret(tmp_path: Path) -> None:
    project = tmp_path / "dec-secret"
    project.mkdir()
    (project / "README.md").write_text("# Decisions\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Keep honest\nOk.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    secret = "AKIAIOSFODNN7EXAMPLE"
    (project / "docs" / "DECISIONS.md").write_text(
        f"# Decisions\n\nkey={secret}\n",
        encoding="utf-8",
    )
    lens = build_decisions_lens(vault, project_id)
    assert lens["honesty"]["governing_evidence_stale"] is True
    assert secret not in json.dumps(lens)
