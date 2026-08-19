"""AS-CODER-ALPHA-ARCHITECTURE-STALE-001 — derived architecture must not hide drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.architecture_stale import (
    evaluate_architecture_inventory_drift,
    is_architecture_bearing_path,
)
from project_atlas.connect import connect_project
from project_atlas.project_architecture import _architecture_rank, build_architecture_lens
from project_atlas.source_identity import canonical_source_sha256


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    _write_json(dest, {"source_root": str(root.resolve()), "sources": sources})
    return vault


def test_missing_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    report = evaluate_architecture_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "MANIFEST_ABSENT"


def test_missing_source_root_is_unknown_not_fresh(tmp_path: Path) -> None:
    root = tmp_path / "gone-root"
    vault = _manifest(
        root,
        {"docs/architecture.md": "# Architecture\n\nv1\n"},
        project_id="harbor-api",
    )
    first = evaluate_architecture_inventory_drift(vault, "harbor-api")
    assert first["status"] == "FRESH"
    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["source_root"] = str(tmp_path / "does-not-exist")
    _write_json(manifest_path, payload)
    second = evaluate_architecture_inventory_drift(vault, "harbor-api")
    assert second["status"] == "UNKNOWN"
    assert second["honesty"]["unknown_is_fresh"] is False
    assert second["reason_code"] == "SOURCE_ROOT_UNVERIFIED"


def test_readme_only_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    root = tmp_path / "readme-only"
    vault = _manifest(root, {"README.md": "# Harbor\n\nApp.\n"}, project_id="harbor-api")
    report = evaluate_architecture_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["reason_code"] == "NO_ACTIVE_SOURCES"


def test_sibling_project_rows_do_not_scope_this_project(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    vault = _manifest(
        root,
        {"docs/architecture.md": "# Portal\n"},
        project_id="harbor-portal",
    )
    report = evaluate_architecture_inventory_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["reason_code"] == "NO_ACTIVE_SOURCES"


def test_path_filter_matches_architecture_rank() -> None:
    samples = (
        "docs/architecture.md",
        "docs/plan.md",
        "ARCHITECTURE.md",
        "README.md",
        "docs/demo/architecture.md",
        "docs/atlas-2.2/architecture.md",
        "apps/web/README.md",
    )
    for path in samples:
        ranked = _architecture_rank(path) is not None
        assert is_architecture_bearing_path(path) is ranked


def test_connect_then_architecture_edit_is_stale(tmp_path: Path) -> None:
    project = tmp_path / "arch-stale"
    project.mkdir()
    (project / "README.md").write_text("# Harbor Portal\n\nApp.\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "architecture.md").write_text(
        "# Architecture\n\n## System purpose\nOriginal purpose v1.\n\n"
        "## Major components\nCore compiler v1.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    first = build_architecture_lens(vault, project_id)
    assert first["status"] == "derived"
    assert first["source_drift"]["status"] == "FRESH"
    assert first["honesty"]["source_inventory_stale"] is False
    (project / "docs" / "architecture.md").write_text(
        "# Architecture\n\n## System purpose\nChanged purpose v2 on disk.\n\n"
        "## Major components\nCore compiler v2.\n",
        encoding="utf-8",
    )
    second = build_architecture_lens(vault, project_id)
    assert second["source_drift"]["status"] == "STALE"
    assert second["honesty"]["source_inventory_stale"] is True
    assert second["honesty"]["stale_is_current"] is False
    assert "docs/architecture.md" in second["source_drift"]["changed_paths"]
    assert "source_inventory_stale=" in (second["summary"] or "")


def test_readme_edit_does_not_stale_architecture(tmp_path: Path) -> None:
    project = tmp_path / "arch-readme"
    project.mkdir()
    (project / "README.md").write_text("# Harbor Portal\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "architecture.md").write_text(
        "# Architecture\n\n## System purpose\nStable purpose.\n\n"
        "## Major components\nCore compiler.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "README.md").write_text("# Harbor Portal\n\nv2 readme only\n", encoding="utf-8")
    lens = build_architecture_lens(vault, project_id)
    assert lens["source_drift"]["status"] == "FRESH"
    assert lens["honesty"]["source_inventory_stale"] is False


def test_delete_architecture_source_is_stale(tmp_path: Path) -> None:
    project = tmp_path / "arch-del"
    project.mkdir()
    (project / "README.md").write_text("# Harbor Portal\n\nApp.\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "architecture.md").write_text(
        "# Architecture\n\n## System purpose\nv1.\n\n## Major components\nCore.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    (project / "docs" / "architecture.md").unlink()
    lens = build_architecture_lens(vault, project_id)
    assert lens["source_drift"]["status"] == "STALE"
    assert "docs/architecture.md" in lens["source_drift"]["changed_paths"]


def test_architecture_stale_does_not_echo_secret(tmp_path: Path) -> None:
    project = tmp_path / "arch-secret"
    project.mkdir()
    (project / "README.md").write_text("# Harbor Portal\n\nApp.\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "architecture.md").write_text(
        "# Architecture\n\n## System purpose\nv1.\n\n## Major components\nCore.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    secret = "AKIAIOSFODNN7EXAMPLE"
    (project / "docs" / "architecture.md").write_text(
        f"# Architecture\n\n## System purpose\nkey={secret}\n\n## Major components\nCore.\n",
        encoding="utf-8",
    )
    lens = build_architecture_lens(vault, project_id)
    assert lens["honesty"]["source_inventory_stale"] is True
    assert secret not in json.dumps(lens)
