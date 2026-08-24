"""AS-CODER-ALPHA-CONTEXT-STALE-GUARD-001 — stale inventory must not look current."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.agent_handoff import create_handoff, export_agent_context
from project_atlas.connect import connect_project


def _seed(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "# Stale Guard Fixture\n\nPurpose: inventory tooling.\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "overview.md").write_text("Overview of fixture.\n", encoding="utf-8")
    return root


def test_context_and_handoff_mark_stale_inventory(tmp_path: Path) -> None:
    project = _seed(tmp_path / "stale-guard")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])

    fresh = export_agent_context(vault, project_id, refresh_brief=False)
    assert fresh["source_inventory_stale"] is False
    assert (fresh.get("honesty") or {}).get("stale_is_current") is False
    fresh_md = (vault / fresh["markdown_path"]).read_text(encoding="utf-8")
    assert "source_inventory_stale: false" in fresh_md
    assert "STALE SOURCE INVENTORY != CURRENT CONTEXT" not in fresh_md

    (project / "docs" / "overview.md").write_text("Overview CHANGED.\n", encoding="utf-8")

    stale = export_agent_context(vault, project_id, refresh_brief=False)
    assert stale["source_inventory_stale"] is True
    assert (stale.get("honesty") or {}).get("source_inventory_stale") is True
    assert (stale.get("honesty") or {}).get("stale_is_current") is False
    assert (stale.get("source_drift") or {}).get("status") == "STALE"
    payload = json.loads((vault / stale["json_path"]).read_text(encoding="utf-8"))
    assert payload["honesty"]["source_inventory_stale"] is True
    assert payload["honesty"]["stale_is_current"] is False
    text = (vault / stale["markdown_path"]).read_text(encoding="utf-8")
    assert "source_inventory_stale: true" in text
    assert "STALE SOURCE INVENTORY != CURRENT CONTEXT" in text

    handoff = create_handoff(vault, project_id, note="stale-check", refresh_brief=False)
    pack = json.loads((vault / handoff["path"]).read_text(encoding="utf-8"))
    assert pack["honesty"]["source_inventory_stale"] is True
    assert pack["honesty"]["stale_is_current"] is False
