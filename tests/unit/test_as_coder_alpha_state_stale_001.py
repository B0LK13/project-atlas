"""AS-CODER-ALPHA-STATE-STALE-001 — current state must not hide live drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.cli import EXIT_OK, main
from project_atlas.connect import connect_project
from project_atlas.project_state import build_state_lens
from project_atlas.source_identity import canonical_source_sha256
from project_atlas.state_stale import evaluate_state_inventory_drift


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


def _stable_project(vault: Path, project_id: str) -> None:
    _write(
        vault / "projects" / project_id / "project.md",
        (
            "# Synthetic\n\n"
            "## Semantic record\n"
            "```json\n"
            + json.dumps({"lifecycle": "active", "coverage": []}, indent=2, sort_keys=True)
            + "\n```\n"
        ),
    )
    _write(
        vault / "projects" / project_id / "knowledge-status.md",
        (
            "| Signal | Count |\n| --- | --- |\n"
            "| unresolved conflicts | 0 |\n"
            "| claims awaiting review | 0 |\n"
            "| stale claims | 0 |\n"
            "| sources complete | 1 |\n"
            "| sources failed | 0 |\n"
            "| verified claims | 1 |\n"
        ),
    )
    _write(vault / "review" / "conflicts" / f"{project_id}.json", {"entries": []})
    _write(vault / "review" / "pending" / f"{project_id}.json", {"entries": []})


def test_missing_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    report = evaluate_state_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "MANIFEST_ABSENT"


def test_sibling_project_rows_do_not_scope_this_project(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    vault = _manifest(root, {"portal/README.md": "portal"}, project_id="harbor-portal")
    report = evaluate_state_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["reason_code"] == "NO_ACTIVE_SOURCES"


def test_delete_and_rename_after_export_are_stale(tmp_path: Path) -> None:
    root = tmp_path / "moved"
    vault = _manifest(
        root,
        {"README.md": "v1", "docs/NOTE.md": "keep"},
        project_id="harbor-api",
    )
    (root / "docs" / "NOTE.md").unlink()
    deleted = evaluate_state_inventory_drift(vault, "harbor-api")
    assert deleted["status"] == "STALE"
    assert "docs/NOTE.md" in deleted["changed_paths"]
    (root / "README.md").rename(root / "README-moved.md")
    renamed = evaluate_state_inventory_drift(vault, "harbor-api")
    assert renamed["status"] == "STALE"
    assert "README.md" in renamed["changed_paths"]


def test_synthetic_stable_without_manifest_stays_stable(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _stable_project(vault, "proj")
    lens = build_state_lens(vault, "proj")
    assert lens["rollup"] == "stable"
    assert lens["source_drift"]["status"] == "UNKNOWN"
    assert lens["honesty"]["unknown_is_fresh"] is False
    assert lens["honesty"]["source_inventory_stale"] is False


def test_stable_state_cannot_hide_live_drift(tmp_path: Path) -> None:
    root = tmp_path / "stable-drift"
    vault = _manifest(root, {"README.md": "v1"}, project_id="proj")
    _stable_project(vault, "proj")
    first = build_state_lens(vault, "proj")
    assert first["rollup"] == "stable"
    assert first["source_drift"]["status"] == "FRESH"
    (root / "README.md").write_text("v2 drifted state evidence\n", encoding="utf-8")
    second = build_state_lens(vault, "proj")
    assert second["rollup"] != "stable"
    assert second["source_drift"]["status"] == "STALE"
    assert second["honesty"]["source_inventory_stale"] is True
    assert second["honesty"]["stale_is_current"] is False
    assert "source_inventory_stale=" in (second["summary"] or "")
    assert "README.md" in second["source_drift"]["changed_paths"]


def test_connect_then_disk_edit_state_is_stale(tmp_path: Path) -> None:
    project = tmp_path / "state-stale"
    project.mkdir()
    (project / "README.md").write_text("# State\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    first = build_state_lens(vault, project_id)
    assert first["source_drift"]["status"] == "FRESH"
    assert first["honesty"]["source_inventory_stale"] is False
    (project / "README.md").write_text("# State\n\nv2 drifted\n", encoding="utf-8")
    second = build_state_lens(vault, project_id)
    assert second["source_drift"]["status"] == "STALE"
    assert second["honesty"]["source_inventory_stale"] is True
    assert second["honesty"]["stale_is_current"] is False
    assert "README.md" in second["source_drift"]["changed_paths"]
    assert "source_inventory_stale=" in (second["summary"] or "")


def test_state_stale_does_not_echo_secret(tmp_path: Path) -> None:
    project = tmp_path / "state-secret"
    project.mkdir()
    (project / "README.md").write_text("# State\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    secret = "AKIAIOSFODNN7EXAMPLE"
    (project / "README.md").write_text(f"# State\n\nkey={secret}\n", encoding="utf-8")
    lens = build_state_lens(vault, project_id)
    assert lens["honesty"]["source_inventory_stale"] is True
    assert secret not in json.dumps(lens)


def test_cli_state_json_exposes_source_drift(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    project = tmp_path / "cli-state-stale"
    project.mkdir()
    (project / "README.md").write_text("# CLI State\n\nv1\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "README.md").write_text("# CLI State\n\nv2\n", encoding="utf-8")
    assert (
        main(["state", "--vault", str(vault), "--project", project_id, "--json"])
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
