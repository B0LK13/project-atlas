"""AS-CODER-ALPHA-CHANGED-STALE-001 — unchanged must not hide live drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.project_changed import materialize_changed_lenses


def test_edit_without_reconnect_does_not_look_unchanged_current(tmp_path: Path) -> None:
    project = tmp_path / "chg-stale"
    project.mkdir()
    (project / "README.md").write_text("# Changed stale\n\nv1\n", encoding="utf-8")
    first = connect_project(project)
    vault = Path(first["vault"])
    project_id = str(first["bound_project_id"])
    (project / "README.md").write_text("# Changed stale\n\nv2\n", encoding="utf-8")
    report = materialize_changed_lenses(vault, project_ids=[project_id])
    lens = report["lenses"][0]
    assert lens["honesty"]["live_inventory_stale"] is True
    assert lens["honesty"]["unchanged_is_current"] is False
    assert lens["inventory_drift"]["status"] == "STALE"
    assert "README.md" in lens["inventory_drift"]["changed_paths"]
    payload = json.loads(
        (vault / "generated" / "answers" / f"ans-changed-{project_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["honesty"]["live_inventory_stale"] is True


def test_changed_stale_does_not_echo_secret(tmp_path: Path) -> None:
    project = tmp_path / "chg-secret"
    project.mkdir()
    (project / "README.md").write_text("# Changed\n\nv1\n", encoding="utf-8")
    first = connect_project(project)
    vault = Path(first["vault"])
    project_id = str(first["bound_project_id"])
    secret = "AKIAIOSFODNN7EXAMPLE"
    (project / "README.md").write_text(f"key={secret}\n", encoding="utf-8")
    lens = materialize_changed_lenses(vault, project_ids=[project_id])["lenses"][0]
    assert lens["honesty"]["live_inventory_stale"] is True
    assert secret not in json.dumps(lens)
