"""AS-CODER-ALPHA-STALE-LENS-ADAPTERS-001 — thin hooks over inventory_drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.attention_hygiene import classify_attention
from project_atlas.inventory_drift import evaluate_connect_inventory_drift
from project_atlas.project_brief import build_project_brief
from project_atlas.project_changed import build_changed_lens
from project_atlas.project_decisions import build_decisions_lens
from project_atlas.project_next import build_next_lens
from project_atlas.project_state import build_state_lens
from project_atlas.project_unknown import build_unknown_lens
from project_atlas.source_health import explain_source_health
from project_atlas.source_identity import canonical_source_sha256


def _write_manifest(vault: Path, root: Path, sources: list[dict[str, object]]) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"source_root": str(root), "sources": sources}, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _seed_project(vault: Path, project_id: str, *, lifecycle: str = "active") -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    semantic = {
        "project_id": project_id,
        "lifecycle": lifecycle,
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
    status = vault / "projects" / project_id / "knowledge-status.md"
    status.write_text(
        "| metric | count |\n| --- | --- |\n| sources complete | 1 |\n"
        "| sources failed | 0 |\n| verified claims | 1 |\n"
        "| claims awaiting review | 0 |\n| unresolved conflicts | 0 |\n"
        "| stale claims | 0 |\n",
        encoding="utf-8",
    )


def _stale_pair(tmp_path: Path, project_id: str = "harbor") -> tuple[Path, Path]:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    _seed_project(vault, project_id)
    _write_manifest(
        vault,
        root,
        [
            {
                "path": "README.md",
                "sha256": canonical_source_sha256(readme),
                "likely_project": project_id,
            }
        ],
    )
    readme.write_text("# Harbor\n\ndrifted\n", encoding="utf-8")
    return vault, root


def test_state_stable_becomes_unknown_on_stale_inventory(tmp_path: Path) -> None:
    vault, _ = _stale_pair(tmp_path)
    lens = build_state_lens(vault, "harbor")
    assert lens["rollup"] == "unknown"
    assert lens["source_drift"]["status"] == "STALE"
    assert lens["honesty"]["stale_is_current"] is False


def test_unknown_clear_cannot_hide_stale_inventory(tmp_path: Path) -> None:
    vault, _ = _stale_pair(tmp_path)
    lens = build_unknown_lens(vault, "harbor")
    assert lens["rollup"] != "clear"
    assert any(
        str(item).startswith("source_inventory_stale=")
        for item in lens["signals"]["unknown_items"]
    )
    assert lens["source_drift"]["status"] == "STALE"


def test_attention_adds_stale_item_and_does_not_stay_clear(tmp_path: Path) -> None:
    vault, _ = _stale_pair(tmp_path)
    lens = classify_attention(vault, "harbor")
    kinds = [item.get("kind") for item in lens["items"]]
    assert "source_inventory_stale" in kinds
    assert lens["rollup"] != "CLEAR"


def test_decisions_path_filter_and_governing_honesty(tmp_path: Path) -> None:
    vault, root = _stale_pair(tmp_path)
    plan = root / "plan.md"
    plan.write_text("# Plan\n\nchanged\n", encoding="utf-8")
    adr = root / "adr-001.md"
    adr.write_text("# ADR-001\n\nchanged\n", encoding="utf-8")
    manifest = json.loads(
        (vault / "generated" / "ops" / "connect-manifest.json").read_text(encoding="utf-8")
    )
    manifest["sources"].extend(
        [
            {
                "path": "plan.md",
                "sha256": "00",
                "likely_project": "harbor",
            },
            {
                "path": "adr-001.md",
                "sha256": "00",
                "likely_project": "harbor",
            },
        ]
    )
    (vault / "generated" / "ops" / "connect-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lens = build_decisions_lens(vault, "harbor")
    assert lens["source_drift"]["status"] == "STALE"
    assert "plan.md" not in lens["source_drift"]["changed_paths"]
    assert "adr-001.md" in lens["source_drift"]["changed_paths"]
    assert lens["honesty"]["governing_evidence_stale"] is True


def test_source_health_clear_downgrades_to_stale(tmp_path: Path) -> None:
    vault, _ = _stale_pair(tmp_path)
    report = explain_source_health(vault, "harbor")
    assert report["health_state"] == "STALE"
    assert report["honesty"]["inventory_stale"] is True
    assert report["honesty"]["stale_is_current"] is False


def test_next_queue_includes_stale_evidence(tmp_path: Path) -> None:
    vault, _ = _stale_pair(tmp_path)
    lens = build_next_lens(vault, "harbor")
    kinds = [item.get("kind") for item in lens["queue"]]
    assert "stale_evidence" in kinds
    assert lens["honesty"]["answer_evidence_stale"] is True
    assert lens["honesty"]["next_is_authority"] is False
    assert lens["source_drift"]["status"] == "STALE"


def test_changed_unchanged_guard_and_brief_honesty(tmp_path: Path) -> None:
    vault, _ = _stale_pair(tmp_path)
    current = {"projects": {"harbor": {"paths": ["README.md"]}}}
    previous = {"projects": {"harbor": {"paths": ["README.md"]}}}
    delta = {
        "prior_baseline": True,
        "added": [],
        "removed": [],
        "modified": [],
    }
    changed = build_changed_lens(
        vault, "harbor", previous=previous, current=current, delta=delta
    )
    assert changed["rollup"] == "unchanged"
    assert changed["honesty"]["unchanged_is_current"] is False
    assert "reconnect" in (changed["summary"] or "")

    brief = build_project_brief(vault, "harbor", refresh=False)
    assert brief["honesty"]["answer_evidence_stale"] is True
    assert brief["honesty"]["stale_is_current"] is False


def test_shared_engine_not_duplicated(tmp_path: Path) -> None:
    vault, _ = _stale_pair(tmp_path)
    engine = evaluate_connect_inventory_drift(vault, "harbor")
    assert engine["status"] == "STALE"
    assert engine["package"] == "AS-CODER-ALPHA-INVENTORY-DRIFT-001"
