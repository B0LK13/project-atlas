"""AS-CODER-ALPHA-CONTEXT-STALE-GUARD-001 — stale context must not look current."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.agent_handoff import create_handoff, export_agent_context, resume_handoff
from project_atlas.connect import connect_project
from project_atlas.context_stale_guard import evaluate_context_freshness
from project_atlas.source_identity import canonical_source_sha256


def _manifest(root: Path, files: dict[str, str], *, project_id: str = "harbor-api") -> None:
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


def test_missing_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    report = evaluate_context_freshness(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["live_fingerprint"] is None


def test_missing_source_root_is_unknown_not_fresh(tmp_path: Path) -> None:
    """P1: vanished source_root must not reuse stored hashes as FRESH."""
    root = tmp_path / "gone-root"
    _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    vault = root / ".atlas-vault"
    first = evaluate_context_freshness(vault, "harbor-api")
    assert first["status"] == "FRESH"
    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["source_root"] = str(tmp_path / "does-not-exist")
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    second = evaluate_context_freshness(
        vault,
        "harbor-api",
        frozen_fingerprint=first["live_fingerprint"],
        frozen_rows=first["rows"],
    )
    assert second["status"] == "UNKNOWN"
    assert second["honesty"]["unknown_is_fresh"] is False
    assert second["live_fingerprint"] is None


def test_sibling_project_rows_do_not_scope_this_project(tmp_path: Path) -> None:
    root = tmp_path / "estate"
    _manifest(root, {"portal/README.md": "portal"}, project_id="harbor-portal")
    vault = root / ".atlas-vault"
    report = evaluate_context_freshness(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False


def test_disk_edit_after_stamp_is_stale(tmp_path: Path) -> None:
    root = tmp_path / "drift"
    _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    vault = root / ".atlas-vault"
    first = evaluate_context_freshness(vault, "harbor-api")
    assert first["status"] == "FRESH"
    (root / "README.md").write_text("v2", encoding="utf-8")
    second = evaluate_context_freshness(
        vault,
        "harbor-api",
        frozen_fingerprint=first["live_fingerprint"],
        frozen_rows=first["rows"],
    )
    assert second["status"] == "STALE"
    assert "README.md" in second["changed_paths"]


def test_export_and_resume_detect_source_change(tmp_path: Path) -> None:
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
    ctx = export_agent_context(vault, project_id, refresh_brief=False)
    assert ctx["freshness"]["status"] in {"FRESH", "UNKNOWN"}
    text = (vault / ctx["markdown_path"]).read_text(encoding="utf-8")
    assert "## Context freshness" in text
    created = create_handoff(vault, project_id, note="stale-guard", refresh_brief=False)
    (project / "README.md").write_text("# Stale Guard\n\nv2 changed\n", encoding="utf-8")
    resumed = resume_handoff(vault, handoff_id=created["handoff_id"])
    assert resumed["status"] == "resumed"
    assert resumed["freshness"]["status"] == "STALE"
    assert resumed["freshness"]["honesty"]["fresh_is_authority"] is False
    assert "README.md" in resumed["freshness"]["changed_paths"]
