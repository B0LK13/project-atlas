"""AS-CODER-ALPHA-HONESTY-TAIL-001 — #384/#382 honesty on current main.

Does not re-wire the six shared drift lenses (#414 conflict set).
Does not duplicate inventory_drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project_atlas.inventory_drift import evaluate_connect_inventory_drift
from project_atlas.project_brief import build_project_brief
from project_atlas.project_changed import build_changed_lens
from project_atlas.source_identity import canonical_source_sha256


def _write_manifest(vault: Path, root: Path, sources: list[dict[str, object]]) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"source_root": str(root), "sources": sources}, indent=2, sort_keys=True),
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


def _pair(tmp_path: Path, *, drift: bool) -> tuple[Path, Path]:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_project(vault, "harbor")
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": canonical_source_sha256(readme),
                "likely_project": "harbor",
            }
        ],
    )
    if drift:
        readme.write_text("# Harbor\n\ndrifted\n", encoding="utf-8")
    return vault, root


def _unchanged_delta() -> dict[str, Any]:
    return {
        "prior_baseline": True,
        "added": [],
        "removed": [],
        "modified": [],
    }


def _unchanged_inventories() -> tuple[dict[str, Any], dict[str, Any]]:
    current = {"projects": {"harbor": {"paths": ["README.md"]}}}
    previous = {"projects": {"harbor": {"paths": ["README.md"]}}}
    return previous, current


def test_unchanged_plus_live_stale(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=True)
    previous, current = _unchanged_inventories()
    changed = build_changed_lens(
        vault, "harbor", previous=previous, current=current, delta=_unchanged_delta()
    )
    assert changed["rollup"] == "unchanged"
    assert changed["honesty"]["unchanged_is_current"] is False
    assert changed["honesty"]["stale_is_current"] is False
    assert changed["honesty"]["lens_is_authority"] is False
    assert changed["source_drift"]["status"] == "STALE"
    assert "reconnect" in (changed["summary"] or "").lower() or any(
        "STALE LIVE" in str(note) for note in changed["notes"]
    )
    engine = evaluate_connect_inventory_drift(vault, "harbor")
    assert engine["package"] == "AS-CODER-ALPHA-INVENTORY-DRIFT-001"
    assert engine["status"] == "STALE"


def test_unchanged_plus_live_fresh(tmp_path: Path) -> None:
    vault, _ = _pair(tmp_path, drift=False)
    previous, current = _unchanged_inventories()
    changed = build_changed_lens(
        vault, "harbor", previous=previous, current=current, delta=_unchanged_delta()
    )
    assert changed["rollup"] == "unchanged"
    assert changed["honesty"]["unchanged_is_current"] is True
    assert changed["honesty"]["stale_is_current"] is False
    assert changed["honesty"]["lens_is_authority"] is False
    assert changed["source_drift"]["status"] == "FRESH"


def test_next_stale_propagates_to_brief(tmp_path: Path, monkeypatch: Any) -> None:
    vault, _ = _pair(tmp_path, drift=True)

    def _stale_next(_vault: Path, _project_id: str) -> dict[str, Any]:
        return {
            "answer_id": "ans-next-harbor",
            "suggested_next_work": ["Ship the demo"],
            "honesty": {
                "answer_evidence_stale": True,
                "live_source_unverified": False,
            },
        }

    monkeypatch.setattr("project_atlas.project_next.build_next_lens", _stale_next)
    brief = build_project_brief(vault, "harbor", refresh=False)
    assert brief["honesty"]["answer_evidence_stale"] is True
    assert brief["honesty"]["stale_is_current"] is False
    assert brief["honesty"]["lens_is_authority"] is False
    assert any("STALE EVIDENCE != CURRENT" in note for note in brief["notes"])
    assert brief["suggested_next_work"][0].startswith("STALE EVIDENCE != CURRENT")
    assert "Ship the demo" in brief["suggested_next_work"]


def test_next_unknown_propagates_to_brief(tmp_path: Path, monkeypatch: Any) -> None:
    vault, _ = _pair(tmp_path, drift=False)

    def _unverified_next(_vault: Path, _project_id: str) -> dict[str, Any]:
        return {
            "answer_id": "ans-next-harbor",
            "suggested_next_work": ["Continue as healthy"],
            "honesty": {
                "answer_evidence_stale": False,
                "live_source_unverified": True,
            },
        }

    monkeypatch.setattr("project_atlas.project_next.build_next_lens", _unverified_next)
    brief = build_project_brief(vault, "harbor", refresh=False)
    assert brief["honesty"]["live_source_unverified"] is True
    assert brief["honesty"]["unknown_is_healthy"] is False
    assert brief["honesty"]["stale_is_current"] is False
    assert any("LIVE SOURCE UNVERIFIED" in note for note in brief["notes"])
    assert "healthy" not in brief["suggested_next_work"][0].lower() or "UNVERIFIED" in brief[
        "suggested_next_work"
    ][0]
    assert brief["suggested_next_work"][0].startswith("LIVE SOURCE UNVERIFIED")


def test_no_duplicate_drift_engine() -> None:
    root = Path(__file__).resolve().parents[2]
    changed = (root / "src/project_atlas/project_changed.py").read_text(encoding="utf-8")
    brief = (root / "src/project_atlas/project_brief.py").read_text(encoding="utf-8")
    assert "evaluate_connect_inventory_drift" in changed
    assert "attach_source_drift" in changed
    assert "def evaluate_connect_inventory_drift" not in changed
    assert "sha256(" not in changed
    assert "evaluate_connect_inventory_drift" not in brief
