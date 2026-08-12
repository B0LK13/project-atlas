"""AS-CODER-ALPHA-DECISIONS/UNKNOWN/BRIEF-001 coverage."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.ask_atlas_live import ask_atlas_live
from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project
from project_atlas.project_brief import materialize_project_briefs
from project_atlas.web_api.knowledge import list_knowledge_answers


def _seed(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "# Brief Fixture\n\nPersistent brain dogfood.\n\n## Stack\n\nPython + Obsidian.\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir()
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## Use OKF\nWe decided to use OKF.\n\n## Local-first\nOffline required.\n",
        encoding="utf-8",
    )
    return root


def test_connect_emits_decisions_unknown_and_brief(tmp_path: Path) -> None:
    project = _seed(tmp_path / "brief-fixture")
    report = connect_project(project)
    vault = Path(report["vault"])

    assert any("ans-decisions-brief-fixture.json" in p for p in report["decisions_answers"])
    assert any("ans-unknown-brief-fixture.json" in p for p in report["unknown_answers"])
    assert any("project-brief-brief-fixture.json" in p for p in report["brief_paths"])

    decisions = json.loads(
        (vault / "generated" / "answers" / "ans-decisions-brief-fixture.json").read_text(
            encoding="utf-8"
        )
    )
    assert decisions["status"] == "derived"
    assert decisions["decision_count"] >= 2
    titles = {item["title"] for item in decisions["decisions"]}
    assert "Use OKF" in titles
    assert "Local-first" in titles

    unknown = json.loads(
        (vault / "generated" / "answers" / "ans-unknown-brief-fixture.json").read_text(
            encoding="utf-8"
        )
    )
    assert unknown["rollup"] in {"unknown", "review", "conflict", "clear"}
    assert "lifecycle=unknown" in " ".join(unknown["signals"]["unknown_items"])

    brief = json.loads(
        (vault / "generated" / "ops" / "project-brief-brief-fixture.json").read_text(
            encoding="utf-8"
        )
    )
    assert brief["project_identity"] == "brief-fixture"
    assert brief["purpose"] != "UNKNOWN"
    assert "Python" in brief["tech_stack"]
    assert brief["important_decisions"] != "UNKNOWN"
    assert brief["unknown_or_conflicting"] != "UNKNOWN"
    assert brief["suggested_next_work"]
    assert brief["honesty"]["fabricated_fields"] is False

    ids = {row["answer_id"] for row in list_knowledge_answers(vault)}
    assert "ans-decisions-brief-fixture" in ids
    assert "ans-unknown-brief-fixture" in ids
    live = ask_atlas_live(vault, query="What decisions matter?")
    assert any(
        row.get("answer_id") == "ans-decisions-brief-fixture"
        for row in live["matches"]["knowledge"]
    )


def test_cli_brief_and_decisions(tmp_path: Path) -> None:
    project = _seed(tmp_path / "cli-brief")
    vault = Path(connect_project(project)["vault"])
    assert main(["decisions", "--vault", str(vault), "--json"]) == EXIT_OK
    assert main(["unknown", "--vault", str(vault), "--json"]) == EXIT_OK
    assert (
        main(["brief", "--vault", str(vault), "--project", "cli-brief", "--no-refresh", "--json"])
        == EXIT_OK
    )
    receipt = materialize_project_briefs(vault, project_ids=["cli-brief"], refresh=False)
    assert receipt["package"] == "AS-CODER-ALPHA-BRIEF-001"
    assert "generated_at" not in receipt


def test_decisions_unknown_without_decision_docs(tmp_path: Path) -> None:
    root = tmp_path / "sparse"
    root.mkdir()
    (root / "README.md").write_text("# Sparse\n\nNo decisions file.\n", encoding="utf-8")
    report = connect_project(root)
    vault = Path(report["vault"])
    decisions = json.loads(
        (vault / "generated" / "answers" / "ans-decisions-sparse.json").read_text(
            encoding="utf-8"
        )
    )
    assert decisions["status"] == "unknown"
    assert decisions["value"] is None
    brief = json.loads(
        (vault / "generated" / "ops" / "project-brief-sparse.json").read_text(encoding="utf-8")
    )
    assert brief["important_decisions"] == "UNKNOWN"
    next_work = brief["suggested_next_work"]
    assert any("DECISIONS" in item or "decision" in item.lower() for item in next_work)
