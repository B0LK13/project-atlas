"""AS-PROJECT-ROADMAP-001 — Living Project Roadmap V1."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.app_service import open_app_service
from project_atlas.cli import EXIT_OK, main
from project_atlas.project_roadmap import build_roadmap_lens, materialize_roadmap_lenses
from project_atlas.schema import validate_record
from project_atlas.web_api.roadmap import read_project_roadmap


def _write_roadmap(vault: Path, project_id: str, record: dict) -> None:
    note = vault / "projects" / project_id / "roadmap.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        "---\ntype: Roadmap\n---\n\n# Roadmap\n\n## Roadmap record\n\n```json\n"
        + json.dumps(record)
        + "\n```\n",
        encoding="utf-8",
    )
    (vault / "projects" / project_id / "project.md").write_text(
        f"---\ntype: Project\ntitle: {project_id}\n---\n\n# {project_id}\n",
        encoding="utf-8",
    )


def _realistic_record() -> dict:
    return {
        "milestones": [
            {"id": "m-core", "title": "Core compile", "status": "VERIFIED_COMPLETION"},
            {"id": "m-next", "title": "Next unlock", "status": "IN_PROGRESS"},
        ],
        "items": [
            {
                "id": "pkg-identity",
                "title": "Governed identity",
                "status": "VERIFIED_COMPLETION",
                "milestone": "m-core",
                "depends_on": [],
                "evidence": ["generated/ops/receipts/identity.json"],
            },
            {
                "id": "pkg-connect",
                "title": "Connect compile",
                "status": "IMPLEMENTED",
                "milestone": "m-core",
                "depends_on": ["pkg-identity"],
                "evidence": ["generated/ops/receipts/connect.json"],
            },
            {
                "id": "pkg-roadmap",
                "title": "Living roadmap",
                "status": "IN_PROGRESS",
                "milestone": "m-next",
                "depends_on": ["pkg-connect"],
                "evidence": [],
            },
            {
                "id": "pkg-gated",
                "title": "Gated surface",
                "status": "BLOCKED",
                "milestone": "m-next",
                "depends_on": ["pkg-roadmap"],
                "blockers": [
                    {
                        "reason": "owner merge gate",
                        "waiting_on": "D042",
                        "unlock_condition": "D042 merged to main",
                    }
                ],
            },
        ],
    }


def _seed_realistic(vault: Path, project_id: str = "harbor-slice") -> str:
    _write_roadmap(vault, project_id, _realistic_record())
    receipts = vault / "generated" / "ops" / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)
    (receipts / "identity.json").write_text("{}\n", encoding="utf-8")
    (receipts / "connect.json").write_text("{}\n", encoding="utf-8")
    (vault / "generated" / "answers").mkdir(parents=True, exist_ok=True)
    (vault / "generated" / "answers" / f"ans-state-{project_id}.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "derived",
                "rollup": "IN_PROGRESS",
                "summary": "compile live; gated work blocked",
            }
        ),
        encoding="utf-8",
    )
    return project_id


def test_realistic_fixture_you_are_here_and_critical_path(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    project_id = _seed_realistic(vault)
    lens = build_roadmap_lens(vault, project_id)
    validate_record(lens, "project-roadmap")
    assert lens["honesty"]["roadmap_is_canonical"] is False
    assert lens["honesty"]["percent_complete_is_canonical"] is False
    assert lens["critical_path"] == [
        "pkg-identity",
        "pkg-connect",
        "pkg-roadmap",
        "pkg-gated",
    ]
    assert lens["you_are_here"]["item_id"] == "pkg-roadmap"
    assert lens["you_are_here"]["status"] == "IN_PROGRESS"
    assert lens["next_unlock"]["item_id"] == "pkg-roadmap"
    gated = next(item for item in lens["items"] if item["id"] == "pkg-gated")
    assert gated["status"] == "BLOCKED"
    assert gated["blockers"][0]["waiting_on"] == "D042"
    assert "74%" not in json.dumps(lens)


def test_missing_evidence_is_not_verified(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_roadmap(
        vault,
        "missing-ev",
        {
            "items": [
                {
                    "id": "pkg-a",
                    "title": "Claimed done",
                    "status": "VERIFIED_COMPLETION",
                    "evidence": ["generated/ops/receipts/absent.json"],
                }
            ]
        },
    )
    lens = build_roadmap_lens(vault, "missing-ev")
    item = lens["items"][0]
    assert item["status"] != "VERIFIED_COMPLETION"
    assert item["missing_acceptance_evidence"] is True
    assert "MISSING_ACCEPTANCE_EVIDENCE" in item["flags"]


def test_percent_theatre_rejected(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_roadmap(
        vault,
        "theatre",
        {"items": [{"id": "pkg-a", "title": "Counted", "status": "37 packages done / 50"}]},
    )
    lens = build_roadmap_lens(vault, "theatre")
    assert lens["items"][0]["status"] == "UNKNOWN"
    assert "rejected_package_count_theatre" in lens["items"][0]["flags"]


def test_cyclic_dependencies_unknown_honesty(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_roadmap(
        vault,
        "cycle",
        {
            "items": [
                {"id": "a", "title": "A", "status": "IN_PROGRESS", "depends_on": ["b"]},
                {"id": "b", "title": "B", "status": "IN_PROGRESS", "depends_on": ["a"]},
            ]
        },
    )
    lens = build_roadmap_lens(vault, "cycle")
    assert lens["honesty"]["cyclic_dependencies"] is True
    assert lens["critical_path"] == []
    assert lens["you_are_here"]["status"] == "UNKNOWN"
    assert lens["next_unlock"]["reason"] == "cyclic_dependencies"
    assert "cyclic dependencies" in lens["unknowns"]


def test_contradictory_verified_without_evidence_list(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_roadmap(
        vault,
        "contradict",
        {"items": [{"id": "a", "title": "Bare complete", "status": "VERIFIED_COMPLETION"}]},
    )
    lens = build_roadmap_lens(vault, "contradict")
    assert lens["items"][0]["status"] == "UNKNOWN"
    assert "no_evidence_neq_complete" in lens["items"][0]["flags"]


def test_unknown_without_roadmap_record(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    project = vault / "projects" / "empty"
    project.mkdir(parents=True)
    (project / "project.md").write_text("# empty\n", encoding="utf-8")
    lens = build_roadmap_lens(vault, "empty")
    assert lens["status"] == "unknown"
    assert lens["you_are_here"]["status"] == "UNKNOWN"
    assert "no structured roadmap record" in lens["unknowns"]
    validate_record(lens, "project-roadmap")


def test_cli_and_api_and_materialize(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    project_id = _seed_realistic(vault)
    report = materialize_roadmap_lenses(vault, project_ids=[project_id])
    written = vault / "generated" / "answers" / f"ans-roadmap-{project_id}.json"
    assert written.is_file()
    assert report["honesty"]["roadmap_is_canonical"] is False

    code = main(["roadmap", "--vault", str(vault), "--project", project_id])
    assert code == EXIT_OK
    out = capsys.readouterr().out
    assert "ROADMAP!=CANONICAL_TRUTH" in out
    assert "pkg-roadmap" in out

    service = open_app_service(vault)
    api = service.roadmap(project_id)
    assert api["you_are_here"]["item_id"] == "pkg-roadmap"
    assert api["honesty"]["ui_is_canonical"] is False
    read = read_project_roadmap(vault, project_id)
    assert read["critical_path"] == api["critical_path"]
