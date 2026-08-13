"""D-043 PASS-blocker closeout unit coverage."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.project_architecture import (
    _clean_line,
    _component_summary,
    _dedupe_major_components,
    _module_rows,
)
from project_atlas.project_brief import build_project_brief
from project_atlas.project_changed import _semantic_class_for_path, _semantic_narrative
from project_atlas.project_decisions import build_decisions_lens


def test_architecture_modules_preserve_underscores_and_exclude_docs() -> None:
    text = (
        "## Code organization\n\n"
        "| Module | Purpose |\n"
        "|--------|---------|\n"
        "| `cli.py` | entry |\n"
        "| `knowledge_compiler.py` | claims |\n"
        "| `docs/plan.md` | not a module |\n"
        "| atlas-project.yaml | marker |\n"
    )
    rows = _module_rows(text)
    summary = _component_summary(rows)
    assert summary is not None
    assert "knowledge_compiler.py" in summary
    assert "knowledgecompiler.py" not in summary
    assert "docs/plan.md" not in summary
    assert "atlas-project.yaml" not in summary
    assert "MODEL_OUTPUT" in _clean_line("Keep MODEL_OUTPUT != AUTHORITY")


def test_decisions_reject_section_header_noise(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    note = vault / "projects" / "proj" / "decisions.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# Decisions\n\n## Context\n\nnoise\n\n## Consequences\n\nnoise\n\n"
        "## ADR-001 Prefer package data schemas\n\nAccepted.\n",
        encoding="utf-8",
    )
    (vault / "docs" / "adr").mkdir(parents=True)
    adr_src = vault / "sources" / "imported-documents"
    adr_src.mkdir(parents=True)
    (adr_src / "src-adr.md").write_text(
        "# ADR-002 Two-track reconciliation\n\n## Decision\n\nAdopt two tracks.\n"
        "## Context\n\nWhy.\n## Migration and validation\n\nHow.\n",
        encoding="utf-8",
    )
    manifest = {
        "sources": [
            {
                "path": "docs/adr/ADR-002.md",
                "source_id": "src-adr",
                "likely_project": "proj",
            }
        ]
    }
    ops = vault / "generated" / "ops"
    ops.mkdir(parents=True)
    (ops / "connect-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lens = build_decisions_lens(vault, "proj")
    titles = {item["title"]: item["status"] for item in lens.get("decisions") or []}
    assert titles.get("Context") in {None, "NON_DECISION"}
    assert "Consequences" not in titles or titles["Consequences"] == "NON_DECISION"
    assert "Migration and validation" not in titles
    active = [
        item for item in (lens.get("decisions") or []) if item.get("status") == "ACTIVE_GOVERNING"
    ]
    assert active
    assert all(
        "ADR-" in item["title"] or "Prefer" in item["title"] or "Adopt" in item["title"]
        for item in active
    )


def test_semantic_changed_narrative_classes_paths() -> None:
    assert _semantic_class_for_path("docs/adr/ADR-003.md") == "decision_change"
    assert _semantic_class_for_path("docs/DECISIONS.md") == "decision_change"
    assert _semantic_class_for_path("README.md") == "project_state_change"
    assert _semantic_class_for_path("docs/implementation-roadmap.md") == "next_work_change"
    assert _semantic_class_for_path(".atlas-vault/index.md") is None
    # removeprefix("./") must not strip leading ".." (character-set lstrip would).
    assert _semantic_class_for_path("./docs/plan.md") == "project_state_change"
    assert _semantic_class_for_path("../docs/plan.md") is None
    narrative = _semantic_narrative(
        added=["docs/DECISIONS.md"],
        removed=["docs/plan.md"],
        modified=["docs/backlog.md"],
    )
    assert narrative["meaningful"] is True
    assert narrative["decision_change_count"] == 1
    assert narrative["project_state_change_count"] == 1
    assert narrative["next_work_change_count"] == 1
    assert any("decision_change" in signal for signal in narrative["signals"])


def test_major_components_preserves_prose_while_deduping_modules() -> None:
    merged = (
        "ingestion engine; query service; "
        "Core package modules: cli.py, knowledge_compiler.py; "
        "Core package modules: cli.py, validation.py"
    )
    out = _dedupe_major_components(merged)
    assert "ingestion engine" in out
    assert "query service" in out
    assert "knowledge_compiler.py" in out
    assert "validation.py" in out
    assert out.count("cli.py") == 1
    assert out.count("Core package modules:") == 1


def test_human_disposition_only_promotes_decision_claims(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    project = "proj"
    (vault / "state" / "human-decisions").mkdir(parents=True)
    (vault / "state" / "claims").mkdir(parents=True)
    (vault / "state" / "human-decisions" / f"{project}.json").write_text(
        json.dumps(
            {
                "decisions": [
                    {
                        "review_id": "review-tech-stack",
                        "decision": "accept",
                        "category": "pending-claim",
                        "subject_id": "claim-stack",
                        "reason": "looks fine",
                    },
                    {
                        "review_id": "review-decision",
                        "decision": "accept",
                        "category": "pending-claim",
                        "subject_id": "claim-decision",
                        "reason": "owner accepted",
                    },
                    {
                        "review_id": "review-orphan",
                        "decision": "accept",
                        "category": "pending-claim",
                        "subject_id": "claim-missing",
                        "reason": "no claim row",
                    },
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (vault / "state" / "claims" / f"{project}.json").write_text(
        json.dumps(
            {
                "claims": [
                    {
                        "claim_id": "claim-stack",
                        "claim_type": "tech_stack",
                        "value": "Python 3.12",
                        "verification": "accepted",
                    },
                    {
                        "claim_id": "claim-decision",
                        "claim_type": "decision",
                        "value": "Prefer package data schemas",
                        "verification": "accepted",
                    },
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    lens = build_decisions_lens(vault, project)
    active = [
        item for item in (lens.get("decisions") or []) if item.get("status") == "ACTIVE_GOVERNING"
    ]
    titles = {item["title"] for item in active}
    assert "Prefer package data schemas" in titles
    assert "Python 3.12" not in titles
    assert "review-tech-stack" not in titles
    assert "review-orphan" not in titles


def test_second_connect_semantic_summary(tmp_path: Path) -> None:
    root = tmp_path / "sem-proj"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("# Sem Proj\n\nPurpose.\n", encoding="utf-8")
    (root / "docs" / "plan.md").write_text(
        "# Plan\n\n## Architecture\n\nThree-layer vault.\n", encoding="utf-8"
    )
    report = connect_project(root)
    vault = Path(report["vault"])
    project_id = str(report["bound_project_id"])
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\n## ADR-010 Adopt semantic changed narrative\n\nAccepted.\n",
        encoding="utf-8",
    )
    (root / "docs" / "backlog.md").write_text("# Backlog\n\n- next work item\n", encoding="utf-8")
    (root / "README.md").write_text(
        "# Sem Proj\n\nPurpose updated.\n\n## Stack\n\nPython.\n", encoding="utf-8"
    )
    connect_project(root, vault=vault)
    brief = build_project_brief(vault, project_id, refresh=True)
    changed = str(brief.get("recent_meaningful_changes") or "")
    assert "know_about=" in changed
    assert "decision_change" in changed
    assert "project_state_change" in changed or "next_work_change" in changed
