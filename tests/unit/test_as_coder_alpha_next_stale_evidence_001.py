"""AS-CODER-ALPHA-NEXT-STALE-EVIDENCE-001 — stale What Next must not look current."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.next_stale_evidence import (
    NextStaleEvidenceError,
    evaluate_next_source_drift,
)
from project_atlas.project_next import build_next_lens
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


def test_missing_inventory_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = tmp_path / "empty"
    vault.mkdir()
    report = evaluate_next_source_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"
    assert report["honesty"]["unknown_is_fresh"] is False
    assert report["honesty"]["stale_is_current"] is False


def test_missing_source_root_is_unknown_not_fresh(tmp_path: Path) -> None:
    vault = _manifest(tmp_path / "gone", {"README.md": "v1"}, project_id="harbor-api")
    first = evaluate_next_source_drift(vault, "harbor-api")
    assert first["status"] == "FRESH"
    payload = json.loads(
        (vault / "generated" / "ops" / "connect-manifest.json").read_text(encoding="utf-8")
    )
    payload["source_root"] = str(tmp_path / "does-not-exist")
    (vault / "generated" / "ops" / "connect-manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    second = evaluate_next_source_drift(vault, "harbor-api")
    assert second["status"] == "UNKNOWN"
    assert second["honesty"]["unknown_is_fresh"] is False


def test_sibling_project_rows_do_not_scope_this_project(tmp_path: Path) -> None:
    vault = _manifest(tmp_path / "sib", {"portal.md": "x"}, project_id="harbor-portal")
    report = evaluate_next_source_drift(vault, "harbor-api")
    assert report["status"] == "UNKNOWN"


def test_path_traversal_project_id_fail_closed(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    try:
        evaluate_next_source_drift(vault, "../escape")
    except NextStaleEvidenceError:
        return
    raise AssertionError("path traversal project id must fail closed")


def test_disk_edit_marks_next_stale_and_does_not_echo_secret(tmp_path: Path) -> None:
    root = tmp_path / "drift"
    vault = _manifest(root, {"README.md": "v1"}, project_id="harbor-api")
    secret = "AKIAIOSFODNN7EXAMPLE"
    (root / "README.md").write_text(f"key={secret}\n", encoding="utf-8")
    report = evaluate_next_source_drift(vault, "harbor-api")
    assert report["status"] == "STALE"
    assert "README.md" in report["changed_paths"]
    assert secret not in json.dumps(report)
    lens = build_next_lens(vault, "harbor-api")
    assert lens["honesty"]["answer_evidence_stale"] is True
    assert lens["honesty"]["stale_is_current"] is False
    assert lens["source_drift"]["status"] == "STALE"
    assert any(item["kind"] == "stale_evidence" for item in lens["queue"])
    assert secret not in json.dumps(lens)


def test_connect_then_edit_without_reconnect_surfaces_stale_next(tmp_path: Path) -> None:
    project = tmp_path / "live"
    project.mkdir()
    (project / "README.md").write_text("# Next stale\n\nv1\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\nKeep next honest.\n",
        encoding="utf-8",
    )
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    fresh = build_next_lens(vault, project_id)
    assert fresh["honesty"]["answer_evidence_stale"] is False
    (project / "README.md").write_text("# Next stale\n\nv2 changed\n", encoding="utf-8")
    stale = build_next_lens(vault, project_id)
    assert stale["honesty"]["answer_evidence_stale"] is True
    assert stale["primary"]["kind"] == "stale_evidence"
    assert "connect" in str(stale["primary"]["action"]).lower()
