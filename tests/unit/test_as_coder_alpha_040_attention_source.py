"""D-040 attention hygiene + source-health explainability tests."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.attention_hygiene import classify_attention
from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project
from project_atlas.source_health import explain_source_health


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")


def test_attention_classifies_conflict_and_pending(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(
        vault / "review" / "conflicts" / "proj.json",
        {
            "entries": [
                {
                    "conflict_id": "c1",
                    "field": "architecture",
                    "conflict_type": "materially-incompatible",
                }
            ]
        },
    )
    _write(
        vault / "review" / "pending" / "proj.json",
        {
            "entries": [
                {
                    "review_id": "r1",
                    "status": "pending",
                    "category": "pending-claim",
                    "reason": "claim requires human verification",
                }
            ]
        },
    )
    report = classify_attention(vault, "proj")
    assert report["rollup"] == "BLOCKING"
    levels = {item["level"] for item in report["items"]}
    assert "BLOCKING" in levels
    assert "NEEDS_HUMAN_REVIEW" in levels
    assert report["honesty"]["confidence_theatre"] is False
    assert all("why_seeing_this" in item for item in report["items"])


def test_source_health_explains_exclusions(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write(
        vault / "generated" / "ops" / "connect-manifest.json",
        {
            "sources": [
                {
                    "path": "fixtures/demo/README.md",
                    "source_id": "source-x",
                    "likely_project": "proj",
                    "exclusion_reason": "default-excluded-directory",
                },
                {
                    "path": "README.md",
                    "source_id": "source-y",
                    "likely_project": "proj",
                    "exclusion_reason": None,
                },
            ]
        },
    )
    report = explain_source_health(vault, "proj")
    assert report["source_count"] == 1
    row = report["sources"][0]
    assert row["reason_code"] == "default-excluded-directory"
    assert row["pipeline_stage"] == "discover"
    assert "excluded directory" in row["human_explanation"].lower()
    assert report["honesty"]["secrets_echoed"] is False


def test_cli_attention_and_source_health(tmp_path: Path) -> None:
    project = tmp_path / "cli-att"
    project.mkdir()
    (project / "README.md").write_text("# CLI Att\n\nbody\n", encoding="utf-8")
    vault = Path(connect_project(project)["vault"])
    assert (
        main(["attention", "--vault", str(vault), "--project", "cli-att", "--json"])
        == EXIT_OK
    )
    assert (
        main(
            [
                "source-health",
                "--vault",
                str(vault),
                "--project",
                "cli-att",
                "--json",
            ]
        )
        == EXIT_OK
    )
