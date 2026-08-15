"""AS-CODER-ALPHA-UNKNOWN-STALE-001 — CLEAR/current unknown must not hide drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project
from project_atlas.project_unknown import build_unknown_lens
from project_atlas.source_identity import canonical_source_sha256
from project_atlas.unknown_stale import evaluate_unknown_inventory_drift


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


def _clear_project_note(vault: Path, project_id: str) -> None:
    _write(
        vault / "projects" / project_id / "project.md",
        (
            "# Synthetic\n\n"
            "## Semantic record\n"
            "```json\n"
            + json.dumps(
                {
                    "lifecycle": "active",
                    "coverage": [
                        {"category": "overview", "state": "present"},
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n```\n"
        ),
    )


def test_missing_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    report = evaluate_unknown_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "MANIFEST_ABSENT"


def test_missing_source_root_is_unknown_not_fresh(tmp_path: Path) -> None:
    root = tmp_path / "gone-root"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    first = evaluate_unknown_inventory_drift(vault, "harbor-api")
    assert first["status"] == "FRESH"
    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["source_root"] = str(tmp_path / "does-not-exist")
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    second = evaluate_unknown_inventory_drift(vault, "harbor-api")
    assert second["status"] == "UNKNOWN"
    assert second["honesty"]["unknown_is_fresh"] is False
    assert second["reason_code"] == "SOURCE_ROOT_UNVERIFIED"


def test_sibling_project_rows_do_not_scope_this_project(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    vault = _manifest(root, {"portal/README.md": "portal"}, project_id="harbor-portal")
    report = evaluate_unknown_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "NO_ACTIVE_SOURCES"


def test_disk_edit_after_stamp_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "drift"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    first = evaluate_unknown_inventory_drift(vault, "harbor-api")
    assert first["status"] == "FRESH"
    (root / "README.md").write_text("v2", encoding="utf-8")
    second = evaluate_unknown_inventory_drift(vault, "harbor-api")
    assert second["status"] == "STALE"
    assert "README.md" in second["changed_paths"]


def test_delete_after_export_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "deleted"
    vault = _manifest(
        root,
        {"README.md": "v1", "docs/UNKNOWN.md": "open v1"},
        project_id="harbor-api",
    )
    (root / "docs" / "UNKNOWN.md").unlink()
    report = evaluate_unknown_inventory_drift(vault, "harbor-api")
    assert report["status"] == "STALE"
    assert "docs/UNKNOWN.md" in report["changed_paths"]


def test_rename_after_export_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "renamed"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    (root / "README.md").rename(root / "README-moved.md")
    report = evaluate_unknown_inventory_drift(vault, "harbor-api")
    assert report["status"] == "STALE"
    assert "README.md" in report["changed_paths"]


def test_synthetic_clear_without_manifest_stays_clear(tmp_path: Path) -> None:
    """D-041 CLEAR fixtures without hashed inventory must not become STALE."""
    vault = tmp_path / "vault"
    _clear_project_note(vault, "proj")
    _write(vault / "review" / "conflicts" / "proj.json", {"entries": []})
    _write(vault / "review" / "pending" / "proj.json", {"entries": []})
    lens = build_unknown_lens(vault, "proj")
    assert lens["rollup"] == "clear"
    assert lens["source_drift"]["status"] == "UNKNOWN"
    assert lens["honesty"]["unknown_is_fresh"] is False
    assert lens["honesty"]["stale_is_current"] is False
    assert lens["honesty"]["source_inventory_stale"] is False


def test_clear_unknown_cannot_hide_live_drift(tmp_path: Path) -> None:
    root = tmp_path / "clear-drift"
    vault = _manifest(root, {"README.md": "v1"}, project_id="proj")
    _clear_project_note(vault, "proj")
    _write(vault / "review" / "conflicts" / "proj.json", {"entries": []})
    _write(vault / "review" / "pending" / "proj.json", {"entries": []})
    first = build_unknown_lens(vault, "proj")
    assert first["rollup"] == "clear"
    assert first["source_drift"]["status"] == "FRESH"
    (root / "README.md").write_text("v2 drifted unknown evidence\n", encoding="utf-8")
    second = build_unknown_lens(vault, "proj")
    assert second["rollup"] != "clear"
    assert second["source_drift"]["status"] == "STALE"
    assert second["honesty"]["source_inventory_stale"] is True
    assert second["honesty"]["stale_is_current"] is False
    assert any(
        item.startswith("source_inventory_stale=")
        for item in second["signals"]["unknown_items"]
    )
    assert "README.md" in second["source_drift"]["changed_paths"]


def test_connect_then_disk_edit_unknown_is_stale(tmp_path: Path) -> None:
    project = tmp_path / "unk-stale"
    project.mkdir()
    (project / "README.md").write_text("# Unknown\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "UNKNOWN.md").write_text("# Unknowns\n\nNone yet.\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    first = build_unknown_lens(vault, project_id)
    assert first["source_drift"]["status"] == "FRESH"
    assert first["honesty"]["source_inventory_stale"] is False
    (project / "docs" / "UNKNOWN.md").write_text(
        "# Unknowns\n\nNew unresolved datastore conflict.\n",
        encoding="utf-8",
    )
    second = build_unknown_lens(vault, project_id)
    assert second["source_drift"]["status"] == "STALE"
    assert second["honesty"]["source_inventory_stale"] is True
    assert second["honesty"]["stale_is_current"] is False
    assert second["honesty"]["unknown_is_fresh"] is False
    assert any("docs/UNKNOWN.md" in path for path in second["source_drift"]["changed_paths"])
    assert "source_inventory_stale=" in second["summary"]


def test_connect_then_delete_and_rename_are_stale(tmp_path: Path) -> None:
    project = tmp_path / "unk-del"
    project.mkdir()
    (project / "README.md").write_text("# Unknown\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "NOTE.md").write_text("# Note\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "docs" / "NOTE.md").unlink()
    deleted = build_unknown_lens(vault, project_id)
    assert deleted["source_drift"]["status"] == "STALE"
    assert "docs/NOTE.md" in deleted["source_drift"]["changed_paths"]
    (project / "README.md").rename(project / "README-moved.md")
    renamed = build_unknown_lens(vault, project_id)
    assert renamed["source_drift"]["status"] == "STALE"
    assert "README.md" in renamed["source_drift"]["changed_paths"]


def test_unknown_stale_does_not_echo_secret(tmp_path: Path) -> None:
    project = tmp_path / "unk-secret"
    project.mkdir()
    (project / "README.md").write_text("# Unknown\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    secret = "AKIAIOSFODNN7EXAMPLE"
    (project / "README.md").write_text(f"# Unknown\n\nkey={secret}\n", encoding="utf-8")
    lens = build_unknown_lens(vault, project_id)
    assert lens["honesty"]["source_inventory_stale"] is True
    assert secret not in json.dumps(lens)


def test_cli_unknown_json_exposes_source_drift(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    project = tmp_path / "cli-unk-stale"
    project.mkdir()
    (project / "README.md").write_text("# CLI Unknown\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "README.md").write_text("# CLI Unknown\n\nv2\n", encoding="utf-8")
    assert (
        main(["unknown", "--vault", str(vault), "--project", project_id, "--json"])
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
