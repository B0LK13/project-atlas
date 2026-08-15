"""AS-CODER-ALPHA-ATTENTION-STALE-001 — CLEAR must not hide live disk drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.attention_hygiene import classify_attention
from project_atlas.attention_stale import evaluate_attention_inventory_drift
from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project
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


def test_missing_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    report = evaluate_attention_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "MANIFEST_ABSENT"


def test_missing_source_root_is_unknown_not_fresh(tmp_path: Path) -> None:
    root = tmp_path / "gone-root"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    first = evaluate_attention_inventory_drift(vault, "harbor-api")
    assert first["status"] == "FRESH"
    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["source_root"] = str(tmp_path / "does-not-exist")
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    second = evaluate_attention_inventory_drift(vault, "harbor-api")
    assert second["status"] == "UNKNOWN"
    assert second["honesty"]["unknown_is_fresh"] is False
    assert second["reason_code"] == "SOURCE_ROOT_UNVERIFIED"


def test_sibling_project_rows_do_not_scope_this_project(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    vault = _manifest(root, {"portal/README.md": "portal"}, project_id="harbor-portal")
    report = evaluate_attention_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "NO_ACTIVE_SOURCES"


def test_disk_edit_after_stamp_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "drift"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    first = evaluate_attention_inventory_drift(vault, "harbor-api")
    assert first["status"] == "FRESH"
    (root / "README.md").write_text("v2", encoding="utf-8")
    second = evaluate_attention_inventory_drift(vault, "harbor-api")
    assert second["status"] == "STALE"
    assert "README.md" in second["changed_paths"]


def test_delete_after_export_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "deleted"
    vault = _manifest(
        root,
        {"README.md": "v1", "docs/DECISIONS.md": "keep v1"},
        project_id="harbor-api",
    )
    (root / "docs" / "DECISIONS.md").unlink()
    report = evaluate_attention_inventory_drift(vault, "harbor-api")
    assert report["status"] == "STALE"
    assert "docs/DECISIONS.md" in report["changed_paths"]


def test_rename_after_export_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "renamed"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    (root / "README.md").rename(root / "README-moved.md")
    report = evaluate_attention_inventory_drift(vault, "harbor-api")
    assert report["status"] == "STALE"
    assert "README.md" in report["changed_paths"]


def test_synthetic_clear_without_manifest_stays_clear(tmp_path: Path) -> None:
    """D-041 CLEAR fixtures without hashed inventory must not become STALE."""
    vault = tmp_path / "vault"
    _write(vault / "review" / "conflicts" / "proj.json", {"entries": []})
    _write(vault / "review" / "pending" / "proj.json", {"entries": []})
    _write(vault / "state" / "compilation-outcomes" / "proj.json", {"candidates": []})
    report = classify_attention(vault, "proj")
    assert report["rollup"] == "CLEAR"
    assert report["source_drift"]["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["honesty"]["stale_is_current"] is False


def test_connect_then_disk_edit_attention_is_stale_not_clear(tmp_path: Path) -> None:
    project = tmp_path / "att-stale"
    project.mkdir()
    (project / "README.md").write_text("# Att\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text("# Decisions\n\nKeep v1.\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    first = classify_attention(vault, project_id)
    assert first["rollup"] == "CLEAR"
    assert first["source_drift"]["status"] == "FRESH"
    (project / "README.md").write_text("# Att\n\nv2 changed\n", encoding="utf-8")
    second = classify_attention(vault, project_id)
    assert second["rollup"] == "STALE"
    assert second["rollup"] != "CLEAR"
    assert second["source_drift"]["status"] == "STALE"
    assert second["honesty"]["source_inventory_stale"] is True
    assert second["honesty"]["stale_is_current"] is False
    assert any(item["reason_code"] == "SOURCE_INVENTORY_STALE" for item in second["items"])
    assert any(item["level"] == "STALE" for item in second["care_about"])
    assert "README.md" in second["source_drift"]["changed_paths"]


def test_connect_then_delete_and_rename_are_stale(tmp_path: Path) -> None:
    project = tmp_path / "att-del"
    project.mkdir()
    (project / "README.md").write_text("# Att\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "NOTE.md").write_text("# Note\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "docs" / "NOTE.md").unlink()
    deleted = classify_attention(vault, project_id)
    assert deleted["rollup"] == "STALE"
    assert "docs/NOTE.md" in deleted["source_drift"]["changed_paths"]
    (project / "README.md").rename(project / "README-moved.md")
    renamed = classify_attention(vault, project_id)
    assert renamed["rollup"] == "STALE"
    assert "README.md" in renamed["source_drift"]["changed_paths"]


def test_cli_attention_json_exposes_source_drift(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    project = tmp_path / "cli-att-stale"
    project.mkdir()
    (project / "README.md").write_text("# CLI Att\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "README.md").write_text("# CLI Att\n\nv2\n", encoding="utf-8")
    assert (
        main(["attention", "--vault", str(vault), "--project", project_id, "--json"])
        == EXIT_OK
    )
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert payload["rollup"] == "STALE"
    assert payload["source_drift"]["status"] == "STALE"
    assert payload["honesty"]["unknown_is_fresh"] is False
