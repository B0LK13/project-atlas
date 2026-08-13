"""AS-CODER-ALPHA-CONTEXT-001 / HANDOFF-001 coverage."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.agent_handoff import create_handoff, export_agent_context, resume_handoff
from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project


def _seed(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "# Handoff Fixture\n\nAgent continuity seed.\n\n## Stack\n\nPython.\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Prefer handoffs\nUse Atlas handoff packs.\n",
        encoding="utf-8",
    )
    return root


def test_context_export_and_handoff_roundtrip(tmp_path: Path) -> None:
    project = _seed(tmp_path / "handoff-fixture")
    vault = Path(connect_project(project)["vault"])
    ctx = export_agent_context(vault, "handoff-fixture", refresh_brief=False)
    assert ctx["status"] == "ok"
    md = vault / ctx["markdown_path"]
    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    assert "Project identity" in text
    assert "UNKNOWN stays UNKNOWN" in text
    assert "Python" in text
    assert "## Attention (what requires action)" in text
    assert "AS-CODER-ALPHA-ATTENTION-001" in text
    assert "attention_hygiene.py" in text
    assert "## Source health (failures / exclusions)" in text
    assert "AS-CODER-ALPHA-SOURCE-HEALTH-001" in text
    payload = json.loads((vault / ctx["json_path"]).read_text(encoding="utf-8"))
    assert payload["attention"]["package"] == "AS-CODER-ALPHA-ATTENTION-001"
    assert payload["source_health"]["package"] == "AS-CODER-ALPHA-SOURCE-HEALTH-001"

    created = create_handoff(vault, "handoff-fixture", note="overnight", refresh_brief=False)
    assert created["handoff_id"].startswith("handoff-")
    assert (vault / created["path"]).is_file()
    assert (vault / created["latest_path"]).is_file()

    resumed = resume_handoff(vault)
    assert resumed["status"] == "resumed"
    assert resumed["handoff_id"] == created["handoff_id"]
    assert resumed["project_id"] == "handoff-fixture"
    assert resumed.get("operator_note") == "overnight"
    assert "generated_at" not in resumed


def test_cli_context_and_handoff(tmp_path: Path) -> None:
    project = _seed(tmp_path / "cli-handoff")
    vault = Path(connect_project(project)["vault"])
    assert (
        main(
            [
                "context",
                "--vault",
                str(vault),
                "--project",
                "cli-handoff",
                "--no-refresh",
                "--json",
            ]
        )
        == EXIT_OK
    )
    assert (
        main(
            [
                "handoff",
                "create",
                "--vault",
                str(vault),
                "--project",
                "cli-handoff",
                "--no-refresh",
                "--json",
            ]
        )
        == EXIT_OK
    )
    assert main(["handoff", "resume", "--vault", str(vault), "--json"]) == EXIT_OK
    latest = json.loads(
        (vault / "generated" / "ops" / "handoffs" / "latest.json").read_text(encoding="utf-8")
    )
    assert latest["project_id"] == "cli-handoff"
