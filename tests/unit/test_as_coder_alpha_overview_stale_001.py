"""AS-CODER-ALPHA-OVERVIEW-STALE-001 — derived overview must not hide drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project
from project_atlas.overview import build_overview_lens
from project_atlas.overview_stale import evaluate_overview_inventory_drift
from project_atlas.source_identity import canonical_source_sha256


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")


def _manifest(root: Path, files: dict[str, str], *, project_id: str) -> Path:
    sources = []
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        sources.append(
            {
                "path": rel,
                "sha256": canonical_source_sha256(path),
                "likely_project": project_id,
            }
        )
    vault = root / ".atlas-vault"
    dest = vault / "generated" / "ops" / "connect-manifest.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(
            {"source_root": str(root.resolve()), "sources": sources},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return vault


def _derived_project(vault: Path, project_id: str) -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    sources = [
        {
            "path": "README.md",
            "source_id": "source-root",
        }
    ]
    note.write_text(
        "---\ntype: Project\ntitle: "
        + project_id
        + "\n---\n\n# "
        + project_id
        + "\n\n<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps({"project_id": project_id, "sources": sources, "coverage": []})
        + "\n```\n",
        encoding="utf-8",
    )
    imported = vault / "sources" / "imported-documents"
    imported.mkdir(parents=True, exist_ok=True)
    (imported / "source-root.md").write_text(
        "# Harbor Portal\n\nPersistent brain for the harbor estate.\n",
        encoding="utf-8",
    )


def test_missing_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    report = evaluate_overview_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "MANIFEST_ABSENT"


def test_missing_source_root_is_unknown_not_fresh(tmp_path: Path) -> None:
    root = tmp_path / "gone-root"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    first = evaluate_overview_inventory_drift(vault, "harbor-api")
    assert first["status"] == "FRESH"
    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["source_root"] = str(tmp_path / "does-not-exist")
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    second = evaluate_overview_inventory_drift(vault, "harbor-api")
    assert second["status"] == "UNKNOWN"
    assert second["honesty"]["unknown_is_fresh"] is False
    assert second["reason_code"] == "SOURCE_ROOT_UNVERIFIED"


def test_sibling_project_rows_do_not_scope_this_project(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    vault = _manifest(root, {"portal/README.md": "portal"}, project_id="harbor-portal")
    report = evaluate_overview_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "NO_ACTIVE_SOURCES"


def test_disk_edit_after_stamp_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "drift"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    first = evaluate_overview_inventory_drift(vault, "harbor-api")
    assert first["status"] == "FRESH"
    (root / "README.md").write_text("v2", encoding="utf-8")
    second = evaluate_overview_inventory_drift(vault, "harbor-api")
    assert second["status"] == "STALE"
    assert "README.md" in second["changed_paths"]


def test_delete_after_export_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "deleted"
    vault = _manifest(
        root,
        {"README.md": "v1", "docs/NOTE.md": "keep"},
        project_id="harbor-api",
    )
    (root / "docs" / "NOTE.md").unlink()
    report = evaluate_overview_inventory_drift(vault, "harbor-api")
    assert report["status"] == "STALE"
    assert "docs/NOTE.md" in report["changed_paths"]


def test_rename_after_export_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "renamed"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    (root / "README.md").rename(root / "README-moved.md")
    report = evaluate_overview_inventory_drift(vault, "harbor-api")
    assert report["status"] == "STALE"
    assert "README.md" in report["changed_paths"]


def test_synthetic_derived_without_manifest_stays_derived(tmp_path: Path) -> None:
    """Fixtures without hashed inventory must not become STALE or invented FRESH."""
    vault = tmp_path / "vault"
    _derived_project(vault, "proj")
    lens = build_overview_lens(vault, "proj")
    assert lens["status"] == "derived"
    assert "Harbor Portal" in (lens["summary"] or "")
    assert lens["source_drift"]["status"] == "UNKNOWN"
    assert lens["honesty"]["unknown_is_fresh"] is False
    assert lens["honesty"]["stale_is_current"] is False
    assert lens["honesty"]["source_inventory_stale"] is False


def test_derived_overview_cannot_hide_live_drift(tmp_path: Path) -> None:
    root = tmp_path / "derived-drift"
    vault = _manifest(root, {"README.md": "v1"}, project_id="proj")
    _derived_project(vault, "proj")
    first = build_overview_lens(vault, "proj")
    assert first["status"] == "derived"
    assert first["source_drift"]["status"] == "FRESH"
    (root / "README.md").write_text("v2 drifted overview evidence\n", encoding="utf-8")
    second = build_overview_lens(vault, "proj")
    assert second["source_drift"]["status"] == "STALE"
    assert second["honesty"]["source_inventory_stale"] is True
    assert second["honesty"]["stale_is_current"] is False
    assert "source_inventory_stale=" in (second["summary"] or "")
    assert "README.md" in second["source_drift"]["changed_paths"]
    assert any(
        "STALE SOURCE INVENTORY != CURRENT OVERVIEW" in item for item in second["notes"]
    )


def test_connect_then_disk_edit_overview_is_stale(tmp_path: Path) -> None:
    project = tmp_path / "ov-stale"
    project.mkdir()
    (project / "README.md").write_text("# Harbor Portal\n\nv1 purpose\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    first = build_overview_lens(vault, project_id)
    assert first["status"] == "derived"
    assert first["source_drift"]["status"] == "FRESH"
    assert first["honesty"]["source_inventory_stale"] is False
    (project / "README.md").write_text("# Harbor Portal\n\nv2 purpose changed\n", encoding="utf-8")
    second = build_overview_lens(vault, project_id)
    assert second["source_drift"]["status"] == "STALE"
    assert second["honesty"]["source_inventory_stale"] is True
    assert second["honesty"]["stale_is_current"] is False
    assert second["honesty"]["unknown_is_fresh"] is False
    assert "README.md" in second["source_drift"]["changed_paths"]
    assert "source_inventory_stale=" in (second["summary"] or "")


def test_connect_then_delete_and_rename_are_stale(tmp_path: Path) -> None:
    project = tmp_path / "ov-del"
    project.mkdir()
    (project / "README.md").write_text("# Harbor Portal\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "NOTE.md").write_text("# Note\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "docs" / "NOTE.md").unlink()
    deleted = build_overview_lens(vault, project_id)
    assert deleted["source_drift"]["status"] == "STALE"
    assert "docs/NOTE.md" in deleted["source_drift"]["changed_paths"]
    (project / "README.md").rename(project / "README-moved.md")
    renamed = build_overview_lens(vault, project_id)
    assert renamed["source_drift"]["status"] == "STALE"
    assert "README.md" in renamed["source_drift"]["changed_paths"]


def test_overview_stale_does_not_echo_secret(tmp_path: Path) -> None:
    project = tmp_path / "ov-secret"
    project.mkdir()
    (project / "README.md").write_text("# Harbor Portal\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    secret = "AKIAIOSFODNN7EXAMPLE"
    (project / "README.md").write_text(f"# Harbor Portal\n\nkey={secret}\n", encoding="utf-8")
    lens = build_overview_lens(vault, project_id)
    assert lens["honesty"]["source_inventory_stale"] is True
    assert secret not in json.dumps(lens)


def test_cli_overview_json_exposes_source_drift(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    project = tmp_path / "cli-ov-stale"
    project.mkdir()
    (project / "README.md").write_text("# CLI Overview\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "README.md").write_text("# CLI Overview\n\nv2\n", encoding="utf-8")
    assert (
        main(["overview", "--vault", str(vault), "--project", project_id, "--json"])
        == EXIT_OK
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    lenses = payload.get("lenses") or []
    assert lenses
    lens = lenses[0]
    assert lens["source_drift"]["status"] == "STALE"
    assert lens["honesty"]["unknown_is_fresh"] is False
    assert lens["honesty"]["stale_is_current"] is False
