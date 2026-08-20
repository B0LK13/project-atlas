"""AS-CODER-ALPHA-CONTEXT-STALE-GUARD-001 — stale context must not look current.

Reuses inventory_drift already on main. Does not retarget #380.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.agent_handoff import (
    PACKAGE_STALE_GUARD,
    STALE_CONTEXT_BANNER,
    UNKNOWN_CONTEXT_BANNER,
    create_handoff,
    evaluate_context_freshness,
    export_agent_context,
    resume_handoff,
)
from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project
from project_atlas.inventory_drift import PACKAGE_ID as DRIFT_PACKAGE
from project_atlas.source_identity import canonical_source_sha256


def _write_manifest(vault: Path, root: Path, sources: list[dict[str, object]]) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"source_root": str(root), "sources": sources},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _seed_project(vault: Path, project_id: str) -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    semantic = {
        "project_id": project_id,
        "lifecycle": "active",
        "sources": [],
        "coverage": [],
    }
    note.write_text(
        "---\ntype: Project\ntitle: "
        + project_id
        + "\n---\n\n# "
        + project_id
        + "\n\n<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps(semantic)
        + "\n```\n",
        encoding="utf-8",
    )


def _pair(tmp_path: Path, *, drift: bool, project_id: str = "harbor") -> tuple[Path, Path]:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_project(vault, project_id)
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": canonical_source_sha256(readme),
                "likely_project": project_id,
            }
        ],
    )
    if drift:
        readme.write_text("# Harbor\n\ndrifted\n", encoding="utf-8")
    return vault, root


def _layer_b_snapshot(vault: Path) -> dict[str, str]:
    root = vault / "projects"
    if not root.is_dir():
        return {}
    return {
        path.relative_to(vault).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_missing_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    report = evaluate_context_freshness(vault, "harbor")
    assert report["status"] == "UNKNOWN"
    assert report["package"] == PACKAGE_STALE_GUARD
    assert report["engine"] == DRIFT_PACKAGE
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["honesty"]["stale_is_current"] is False
    assert report["honesty"]["fresh_is_authority"] is False


def test_missing_source_root_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=False)
    manifest = json.loads(
        (vault / "generated" / "ops" / "connect-manifest.json").read_text(encoding="utf-8")
    )
    manifest["source_root"] = str(tmp_path / "does-not-exist")
    (vault / "generated" / "ops" / "connect-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report = evaluate_context_freshness(vault, "harbor")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["honesty"]["stale_is_current"] is False


def test_sibling_project_rows_do_not_scope_this_project(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=False, project_id="harbor-portal")
    report = evaluate_context_freshness(vault, "harbor")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["changed_paths"] == []


def test_disk_edit_is_stale_not_current(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=True)
    report = evaluate_context_freshness(vault, "harbor")
    assert report["status"] == "STALE"
    assert "README.md" in report["changed_paths"]
    assert report["honesty"]["stale_is_current"] is False
    assert report["honesty"]["source_inventory_stale"] is True
    assert report["honesty"]["lens_is_authority"] is False
    assert STALE_CONTEXT_BANNER in report["notes"]


def test_fresh_inventory_still_not_authority(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=False)
    report = evaluate_context_freshness(vault, "harbor")
    assert report["status"] == "FRESH"
    assert report["honesty"]["stale_is_current"] is False
    assert report["honesty"]["fresh_is_authority"] is False
    assert report["honesty"]["source_inventory_stale"] is False


def test_export_stale_markdown_and_json(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=True)
    before = _layer_b_snapshot(vault)
    ctx = export_agent_context(vault, "harbor", refresh_brief=False)
    assert ctx["freshness"]["status"] == "STALE"
    assert ctx["honesty"]["stale_is_current"] is False
    assert ctx["honesty"]["source_inventory_stale"] is True
    text = (vault / ctx["markdown_path"]).read_text(encoding="utf-8")
    assert "## Context freshness" in text
    assert STALE_CONTEXT_BANNER in text
    assert "stale_is_current: false" in text
    payload = json.loads((vault / ctx["json_path"]).read_text(encoding="utf-8"))
    assert payload["freshness"]["status"] == "STALE"
    assert payload["honesty"]["stale_is_current"] is False
    secret = "# Harbor\n\ndrifted\n"
    assert secret not in text
    assert secret not in json.dumps(payload)
    assert _layer_b_snapshot(vault) == before


def test_export_unknown_does_not_look_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_project(vault, "harbor")
    ctx = export_agent_context(vault, "harbor", refresh_brief=False)
    assert ctx["freshness"]["status"] == "UNKNOWN"
    assert ctx["honesty"]["unknown_is_fresh"] is False
    text = (vault / ctx["markdown_path"]).read_text(encoding="utf-8")
    assert UNKNOWN_CONTEXT_BANNER in text


def test_handoff_resume_detects_source_change(tmp_path: Path) -> None:
    project = tmp_path / "handoff-stale"
    project.mkdir()
    (project / "README.md").write_text("# Stale Guard\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\nKeep freshness honest.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    created = create_handoff(vault, project_id, note="stale-guard", refresh_brief=False)
    assert (created.get("freshness") or {}).get("status") in {"FRESH", "UNKNOWN"}
    (project / "README.md").write_text("# Stale Guard\n\nv2 changed\n", encoding="utf-8")
    resumed = resume_handoff(vault, handoff_id=created["handoff_id"])
    assert resumed["status"] == "resumed"
    assert resumed["freshness"]["status"] == "STALE"
    assert resumed["honesty"]["stale_is_current"] is False
    assert resumed["honesty"]["fresh_is_authority"] is False
    assert "README.md" in resumed["freshness"]["changed_paths"]


def test_cli_context_json_includes_freshness(tmp_path: Path, capsys: Any) -> None:
    vault, _ = _pair(tmp_path, drift=True)
    assert (
        main(
            [
                "context",
                "--vault",
                str(vault),
                "--project",
                "harbor",
                "--no-refresh",
                "--json",
            ]
        )
        == EXIT_OK
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert payload["freshness"]["status"] == "STALE"
    assert payload["honesty"]["stale_is_current"] is False


def test_no_second_drift_engine() -> None:
    root = Path(__file__).resolve().parents[2]
    handoff = (root / "src/project_atlas/agent_handoff.py").read_text(encoding="utf-8")
    assert "from project_atlas.inventory_drift import" in handoff
    assert "attach_source_drift" in handoff
    assert "def evaluate_connect_inventory_drift" not in handoff
    assert "canonical_source_sha256" not in handoff
    assert "context_stale_guard" not in handoff
