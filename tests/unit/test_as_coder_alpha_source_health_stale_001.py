"""AS-CODER-ALPHA-SOURCE-HEALTH-STALE-001 — CLEAR must not hide disk drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.source_health import explain_source_health
from project_atlas.source_health_stale import evaluate_source_inventory_drift
from project_atlas.source_identity import canonical_source_sha256


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
    (vault / "projects" / project_id).mkdir(parents=True, exist_ok=True)
    return vault


def test_missing_source_root_is_unknown_not_clear(tmp_path: Path) -> None:
    vault = _manifest(tmp_path / "gone", {"README.md": "v1"}, project_id="harbor-api")
    payload = json.loads(
        (vault / "generated" / "ops" / "connect-manifest.json").read_text(encoding="utf-8")
    )
    payload["source_root"] = str(tmp_path / "does-not-exist")
    (vault / "generated" / "ops" / "connect-manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    drift = evaluate_source_inventory_drift(vault, "harbor-api")
    assert drift["status"] == "UNKNOWN"
    assert drift["reason_code"] == "SOURCE_ROOT_UNVERIFIED"
    report = explain_source_health(vault, "harbor-api")
    assert report["health_state"] != "CLEAR"
    assert report["honesty"]["stale_is_healthy"] is False


def test_sibling_project_does_not_scope_this_project(tmp_path: Path) -> None:
    vault = _manifest(tmp_path / "sib", {"portal.md": "x"}, project_id="harbor-portal")
    drift = evaluate_source_inventory_drift(vault, "harbor-api")
    assert drift["status"] == "UNKNOWN"
    assert drift["reason_code"] == "NO_ACTIVE_SOURCES"


def test_connect_then_edit_is_stale_not_clear(tmp_path: Path) -> None:
    project = tmp_path / "live"
    project.mkdir()
    (project / "README.md").write_text("# Health stale\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text("# Decisions\n\nHonest.\n", encoding="utf-8")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    fresh = explain_source_health(vault, project_id)
    assert fresh["honesty"]["inventory_stale"] is False
    assert fresh["health_state"] != "STALE"
    secret = "AKIAIOSFODNN7EXAMPLE"
    (project / "README.md").write_text(f"key={secret}\n", encoding="utf-8")
    stale = explain_source_health(vault, project_id)
    assert stale["health_state"] == "STALE"
    assert stale["honesty"]["inventory_stale"] is True
    assert stale["honesty"]["stale_is_healthy"] is False
    assert "README.md" in stale["inventory_drift"]["changed_paths"]
    assert secret not in json.dumps(stale)
