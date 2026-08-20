"""AS-CODER-ALPHA-HONESTY-TAIL-001 / #382 — brief must not treat stale next as current."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from project_atlas.connect import connect_project
from project_atlas.project_brief import build_project_brief
from project_atlas.source_identity import canonical_source_sha256


def _write_manifest(
    vault: Path,
    root: Path,
    sources: list[dict[str, object]],
) -> None:
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


def _seed_brief_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# Brief honesty\n\nv1\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "DECISIONS.md").write_text(
        "# Decisions\n\nKeep brief honest.\n",
        encoding="utf-8",
    )
    return root


def test_brief_does_not_present_stale_next_as_current(tmp_path: Path) -> None:
    project = _seed_brief_project(tmp_path / "brief-382")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    fresh = build_project_brief(vault, project_id, refresh=False)
    assert fresh["source_drift"]["status"] == "FRESH"
    assert fresh["honesty"]["answer_evidence_stale"] is False
    assert fresh["honesty"]["live_source_unverified"] is False
    assert fresh["honesty"]["stale_is_current"] is False
    assert fresh["honesty"]["brief_is_authority"] is False
    assert fresh["honesty"]["lens_is_authority"] is False
    assert fresh["honesty"]["unknown_is_healthy"] is False
    fresh_notes = " ".join(fresh["notes"]).lower()
    fresh_suggested = " ".join(fresh["suggested_next_work"]).lower()
    assert "stale" not in fresh_notes
    assert "reconnect" not in fresh_notes
    assert "stale" not in fresh_suggested
    assert "reconnect" not in fresh_suggested
    assert "not current" not in fresh_suggested

    (project / "README.md").write_text("# Brief honesty\n\nv2 changed\n", encoding="utf-8")
    stale = build_project_brief(vault, project_id, refresh=False)
    assert stale["source_drift"]["status"] == "STALE"
    assert stale["honesty"]["answer_evidence_stale"] is True
    assert stale["honesty"]["stale_is_current"] is False
    assert stale["honesty"]["brief_is_authority"] is False
    assert stale["honesty"]["lens_is_authority"] is False
    assert stale["honesty"]["unknown_is_healthy"] is False
    suggested = " ".join(stale["suggested_next_work"]).lower()
    assert "not current" in suggested
    assert "stale" in suggested or "reconnect" in suggested
    assert "stale" in " ".join(stale["notes"]).lower()


def test_brief_preserves_live_source_unverified(tmp_path: Path) -> None:
    project = _seed_brief_project(tmp_path / "brief-unverified")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])
    manifest_path = vault / "generated" / "ops" / "connect-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_root"] = str(tmp_path / "missing-root")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    brief = build_project_brief(vault, project_id, refresh=False)
    assert brief["source_drift"]["status"] == "UNKNOWN"
    assert brief["honesty"]["live_source_unverified"] is True
    assert brief["honesty"]["answer_evidence_stale"] is False
    assert brief["honesty"]["stale_is_current"] is False
    assert brief["honesty"]["unknown_is_healthy"] is False
    assert brief["honesty"]["brief_is_authority"] is False
    suggested = " ".join(brief["suggested_next_work"]).lower()
    assert "unverified" in suggested
    notes = " ".join(brief["notes"]).lower()
    assert "uncertainty" in notes
    assert "stale next evidence" not in notes


def test_brief_does_not_echo_secret_or_sibling_after_stale_edit(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    harbor = root / "README.md"
    harbor.write_text("# Harbor\n\nv1\n", encoding="utf-8")
    sibling = root / "other.md"
    sibling.write_text("# Sibling\n\nv1\n", encoding="utf-8")
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor").mkdir(parents=True)
    (vault / "projects" / "harbor" / "project.md").write_text(
        "---\ntype: Project\ntitle: harbor\n---\n\n# harbor\n",
        encoding="utf-8",
    )
    harbor_digest = canonical_source_sha256(harbor)
    sibling_digest = canonical_source_sha256(sibling)
    _write_manifest(
        vault,
        root,
        [
            {"path": "README.md", "sha256": harbor_digest, "likely_project": "harbor"},
            {"path": "other.md", "sha256": sibling_digest, "likely_project": "portal"},
        ],
    )
    secret = "AKIAIOSFODNN7EXAMPLE"
    harbor.write_text(f"key={secret}\n", encoding="utf-8")
    sibling.write_text("# Sibling\n\ndrifted\n", encoding="utf-8")
    brief = build_project_brief(vault, project_id="harbor", refresh=False)
    payload = json.dumps(brief)
    assert brief["honesty"]["answer_evidence_stale"] is True
    assert "README.md" in brief["source_drift"]["changed_paths"]
    assert "other.md" not in brief["source_drift"]["changed_paths"]
    assert "other.md" not in payload
    assert secret not in payload
    assert brief["honesty"]["brief_is_authority"] is False


def test_next_stale_honesty_propagates_to_fresh_brief(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _seed_brief_project(tmp_path / "brief-next-stale")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])

    def _stale_next(_vault: Path, _project_id: str) -> dict[str, object]:
        return {
            "answer_id": f"ans-next-{_project_id}",
            "suggested_next_work": ["Ship the release"],
            "honesty": {
                "answer_evidence_stale": True,
                "live_source_unverified": False,
            },
        }

    monkeypatch.setattr("project_atlas.project_next.build_next_lens", _stale_next)
    brief = build_project_brief(vault, project_id, refresh=False)
    assert brief["source_drift"]["status"] == "FRESH"
    assert brief["honesty"]["answer_evidence_stale"] is True
    assert brief["honesty"]["stale_is_current"] is False
    assert "not current" in " ".join(brief["suggested_next_work"]).lower()


def test_next_unverified_honesty_propagates_to_fresh_brief(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _seed_brief_project(tmp_path / "brief-next-unknown")
    connected = connect_project(project)
    vault = Path(connected["vault"])
    project_id = str(connected["bound_project_id"])

    def _unverified_next(_vault: Path, _project_id: str) -> dict[str, object]:
        return {
            "answer_id": f"ans-next-{_project_id}",
            "suggested_next_work": ["Ship the release"],
            "honesty": {
                "answer_evidence_stale": False,
                "live_source_unverified": True,
            },
        }

    monkeypatch.setattr("project_atlas.project_next.build_next_lens", _unverified_next)
    brief = build_project_brief(vault, project_id, refresh=False)
    assert brief["source_drift"]["status"] == "FRESH"
    assert brief["honesty"]["live_source_unverified"] is True
    assert brief["honesty"]["answer_evidence_stale"] is False
    assert brief["honesty"]["stale_is_current"] is False
    assert "unverified" in " ".join(brief["suggested_next_work"]).lower()
    assert "stale next evidence" not in " ".join(brief["notes"]).lower()
