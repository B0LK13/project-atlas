"""AS-CODER-ALPHA-LENS-DRIFT-CONVERGENCE-001 — six remaining lenses."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.attention_hygiene import classify_attention
from project_atlas.project_decisions import build_decisions_lens
from project_atlas.project_next import build_next_lens
from project_atlas.project_state import build_state_lens
from project_atlas.project_unknown import build_unknown_lens
from project_atlas.source_health import explain_source_health
from project_atlas.source_identity import canonical_source_sha256

SECRET = "AKIAIOSFODNN7EXAMPLE"


def _write_manifest(
    vault: Path,
    root: Path,
    sources: list[dict[str, object]],
) -> None:
    path = vault / "generated" / "ops" / "connect-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "source_root": str(root),
                "sources": sources,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_project_note(vault: Path, project_id: str, *, lifecycle: str = "active") -> None:
    note = vault / "projects" / project_id / "project.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    semantic = {
        "project_id": project_id,
        "lifecycle": lifecycle,
        "sources": [],
        "coverage": [],
    }
    note.write_text(
        f"---\ntype: Project\ntitle: {project_id}\n---\n\n# {project_id}\n\n"
        "<!-- atlas:generated:start -->\n## Semantic record\n\n```json\n"
        + json.dumps(semantic)
        + "\n```\n",
        encoding="utf-8",
    )


def _seed_stable_status(vault: Path, project_id: str) -> None:
    status = vault / "projects" / project_id / "knowledge-status.md"
    status.parent.mkdir(parents=True, exist_ok=True)
    status.write_text(
        f"# Knowledge status — {project_id}\n\n"
        "| Signal | Count |\n|---|---:|\n"
        "| unresolved conflicts | 0 |\n"
        "| claims awaiting review | 0 |\n"
        "| stale claims | 0 |\n"
        "| sources complete | 1 |\n"
        "| sources failed | 0 |\n"
        "| verified claims | 1 |\n",
        encoding="utf-8",
    )


def _seed_attention_clear(vault: Path, project_id: str) -> None:
    _write_json(vault / "review" / "conflicts" / f"{project_id}.json", {"entries": []})
    _write_json(vault / "review" / "pending" / f"{project_id}.json", {"entries": []})
    _write_json(
        vault / "state" / "compilation-outcomes" / f"{project_id}.json",
        {"candidates": []},
    )


def _seed_decisions_note(vault: Path, project_id: str) -> None:
    note = vault / "projects" / project_id / "decisions.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        "# Decisions\n\n## Prefer local-first compilation\nOffline required.\n",
        encoding="utf-8",
    )


def _fresh_root(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nstable\n", encoding="utf-8")
    docs = root / "docs"
    docs.mkdir()
    decisions = docs / "DECISIONS.md"
    decisions.write_text("# Decisions\n\n## Prefer local-first compilation\n", encoding="utf-8")
    return root, readme, decisions, tmp_path / "vault"


def _harbor_sources(
    readme: Path,
    decisions: Path,
    extra: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "path": "README.md",
            "sha256": canonical_source_sha256(readme),
            "likely_project": "harbor",
        },
        {
            "path": "docs/DECISIONS.md",
            "sha256": canonical_source_sha256(decisions),
            "likely_project": "harbor",
        },
    ]
    if extra:
        rows.extend(extra)
    return rows


def _seed_all_lenses(vault: Path, project_id: str = "harbor") -> None:
    _seed_project_note(vault, project_id)
    _seed_stable_status(vault, project_id)
    _seed_attention_clear(vault, project_id)
    _seed_decisions_note(vault, project_id)


def test_state_fresh_does_not_rewrite_stable(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    _seed_all_lenses(vault)
    _write_manifest(vault, root, _harbor_sources(readme, decisions))
    lens = build_state_lens(vault, "harbor")
    assert lens["source_drift"]["status"] == "FRESH"
    assert lens["rollup"] == "stable"
    assert "rollup=stable" in str(lens["summary"])


def test_state_stale_rewrites_stable_to_unknown(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    _seed_all_lenses(vault)
    _write_manifest(vault, root, _harbor_sources(readme, decisions))
    readme.write_text(f"# Harbor\n\n{SECRET}\n", encoding="utf-8")
    lens = build_state_lens(vault, "harbor")
    assert lens["source_drift"]["status"] == "STALE"
    assert lens["rollup"] == "unknown"
    assert "rollup=unknown" in str(lens["summary"])
    assert SECRET not in json.dumps(lens)


def test_state_keeps_attention_when_inventory_stale(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    _seed_all_lenses(vault)
    status = vault / "projects" / "harbor" / "knowledge-status.md"
    status.write_text(
        "# Knowledge status — harbor\n\n"
        "| Signal | Count |\n|---|---:|\n"
        "| unresolved conflicts | 1 |\n"
        "| claims awaiting review | 0 |\n"
        "| stale claims | 0 |\n"
        "| sources complete | 1 |\n"
        "| sources failed | 0 |\n"
        "| verified claims | 1 |\n",
        encoding="utf-8",
    )
    _write_json(
        vault / "review" / "conflicts" / "harbor.json",
        {"entries": [{"id": "c1"}]},
    )
    _write_manifest(vault, root, _harbor_sources(readme, decisions))
    readme.write_text("# Harbor\n\nv2\n", encoding="utf-8")
    lens = build_state_lens(vault, "harbor")
    assert lens["source_drift"]["status"] == "STALE"
    assert lens["rollup"] == "attention"


def test_unknown_stale_prevents_clear(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    _seed_all_lenses(vault)
    _write_manifest(vault, root, _harbor_sources(readme, decisions))
    fresh = build_unknown_lens(vault, "harbor")
    assert fresh["source_drift"]["status"] == "FRESH"
    assert fresh["rollup"] == "clear"
    assert "source_inventory_stale" not in fresh["signals"]["unknown_items"]

    readme.write_text("# Harbor\n\nv2\n", encoding="utf-8")
    stale = build_unknown_lens(vault, "harbor")
    assert stale["source_drift"]["status"] == "STALE"
    assert "source_inventory_stale" in stale["signals"]["unknown_items"]
    assert stale["rollup"] != "clear"


def test_unknown_inventory_does_not_invent_signal(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_all_lenses(vault)
    lens = build_unknown_lens(vault, "harbor")
    assert lens["source_drift"]["status"] == "UNKNOWN"
    assert lens["source_drift"]["status"] != "FRESH"
    assert "source_inventory_stale" not in lens["signals"]["unknown_items"]
    assert lens["rollup"] == "clear"


def test_attention_stale_prevents_clear(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    _seed_all_lenses(vault)
    _write_manifest(vault, root, _harbor_sources(readme, decisions))
    fresh = classify_attention(vault, "harbor")
    assert fresh["source_drift"]["status"] == "FRESH"
    assert fresh["rollup"] == "CLEAR"

    decisions.write_text("# Decisions\n\nchanged\n", encoding="utf-8")
    stale = classify_attention(vault, "harbor")
    assert stale["source_drift"]["status"] == "STALE"
    assert stale["rollup"] != "CLEAR"
    assert any(
        item.get("kind") == "source_inventory_stale"
        and item.get("level") == "STALE"
        and item.get("reason_code") == "SOURCE_INVENTORY_STALE"
        for item in stale["items"]
    )


def test_attention_unknown_inventory_may_stay_clear(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_attention_clear(vault, "harbor")
    (vault / "projects" / "harbor").mkdir(parents=True)
    lens = classify_attention(vault, "harbor")
    assert lens["rollup"] == "CLEAR"
    assert lens["source_drift"]["status"] == "UNKNOWN"
    assert lens["source_drift"]["status"] != "FRESH"
    assert not any(item.get("kind") == "source_inventory_stale" for item in lens["items"])


def test_decisions_path_filter_and_governing_honesty(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    _seed_all_lenses(vault)
    _write_manifest(vault, root, _harbor_sources(readme, decisions))
    before = build_decisions_lens(vault, "harbor")
    assert before["source_drift"]["status"] == "FRESH"
    assert before["honesty"]["governing_evidence_stale"] is False
    governing = [item["title"] for item in before["decisions"]]

    readme.write_text("# Harbor\n\nreadme churn\n", encoding="utf-8")
    readme_only = build_decisions_lens(vault, "harbor")
    assert readme_only["source_drift"]["status"] == "FRESH"
    assert readme_only["honesty"]["governing_evidence_stale"] is False
    assert [item["title"] for item in readme_only["decisions"]] == governing

    decisions.write_text("# Decisions\n\n## Adopt a different rule\n", encoding="utf-8")
    stale = build_decisions_lens(vault, "harbor")
    assert stale["source_drift"]["status"] == "STALE"
    assert stale["honesty"]["governing_evidence_stale"] is True
    assert [item["title"] for item in stale["decisions"]] == governing
    assert "Adopt a different rule" not in {item["title"] for item in stale["decisions"]}


def test_source_health_stale_and_unverified_root(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    _seed_all_lenses(vault)
    _write_manifest(vault, root, _harbor_sources(readme, decisions))
    fresh = explain_source_health(vault, "harbor")
    assert fresh["source_drift"]["status"] == "FRESH"
    assert fresh["health_state"] == "CLEAR"
    assert "inventory_drift" not in fresh

    readme.write_text(f"# Harbor\n\n{SECRET}\n", encoding="utf-8")
    stale = explain_source_health(vault, "harbor")
    assert stale["source_drift"]["status"] == "STALE"
    assert stale["health_state"] == "STALE"
    assert stale["summary"]["health_state"] == "STALE"
    assert SECRET not in json.dumps(stale)

    _write_manifest(
        vault,
        tmp_path / "missing-root",
        _harbor_sources(readme, decisions),
    )
    unverified = explain_source_health(vault, "harbor")
    assert unverified["source_drift"]["status"] == "UNKNOWN"
    assert unverified["source_drift"]["reason_code"] == "SOURCE_ROOT_UNVERIFIED"
    assert unverified["health_state"] == "UNKNOWN"


def test_next_stale_inserts_evidence_item(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    _seed_all_lenses(vault)
    _write_manifest(vault, root, _harbor_sources(readme, decisions))
    fresh = build_next_lens(vault, "harbor")
    assert fresh["source_drift"]["status"] == "FRESH"
    assert fresh["honesty"]["answer_evidence_stale"] is False
    assert not any(item.get("kind") == "stale_evidence" for item in fresh["queue"])

    readme.write_text("# Harbor\n\nv2\n", encoding="utf-8")
    stale = build_next_lens(vault, "harbor")
    assert stale["source_drift"]["status"] == "STALE"
    assert stale["honesty"]["answer_evidence_stale"] is True
    stale_item = next(item for item in stale["queue"] if item["kind"] == "stale_evidence")
    assert stale_item["rank"] == 15


def test_next_unknown_does_not_invent_work_item(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_all_lenses(vault)
    lens = build_next_lens(vault, "harbor")
    assert lens["source_drift"]["status"] == "UNKNOWN"
    assert lens["source_drift"]["status"] != "FRESH"
    assert lens["honesty"]["answer_evidence_stale"] is False
    assert not any(item.get("kind") == "stale_evidence" for item in lens["queue"])
    assert lens["primary"]["kind"] == "unknown"


def test_sibling_unowned_and_unknown_project_excluded(tmp_path: Path) -> None:
    root, readme, decisions, vault = _fresh_root(tmp_path)
    sibling = root / "other.md"
    sibling.write_text("# Other\n\nchanged\n", encoding="utf-8")
    unowned = root / "unowned.md"
    unowned.write_text("# Unowned\n\nchanged\n", encoding="utf-8")
    sentinel = root / "sentinel.md"
    sentinel.write_text("# Sentinel\n\nchanged\n", encoding="utf-8")
    _seed_all_lenses(vault)
    _write_manifest(
        vault,
        root,
        _harbor_sources(
            readme,
            decisions,
            extra=[
                {
                    "path": "other.md",
                    "sha256": "deadbeef",
                    "likely_project": "sibling",
                },
                {
                    "path": "unowned.md",
                    "sha256": "00",
                },
                {
                    "path": "sentinel.md",
                    "sha256": "00",
                    "likely_project": "unknown-project",
                },
            ],
        ),
    )
    for path in (sibling, unowned, sentinel):
        path.write_text(path.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")

    state = build_state_lens(vault, "harbor")
    unknown = build_unknown_lens(vault, "harbor")
    attention = classify_attention(vault, "harbor")
    decisions_lens = build_decisions_lens(vault, "harbor")
    health = explain_source_health(vault, "harbor")
    nxt = build_next_lens(vault, "harbor")
    for lens in (state, unknown, attention, decisions_lens, health, nxt):
        assert lens["source_drift"]["status"] == "FRESH"
        leaked = set(lens["source_drift"]["changed_paths"])
        assert "other.md" not in leaked
        assert "unowned.md" not in leaked
        assert "sentinel.md" not in leaked

    sentinel_scope = build_state_lens(vault, "unknown-project")
    assert sentinel_scope["source_drift"]["status"] == "UNKNOWN"


def test_missing_manifest_is_unknown_not_fresh_for_all_lenses(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _seed_all_lenses(vault)
    lenses = (
        build_state_lens(vault, "harbor"),
        build_unknown_lens(vault, "harbor"),
        classify_attention(vault, "harbor"),
        build_decisions_lens(vault, "harbor"),
        explain_source_health(vault, "harbor"),
        build_next_lens(vault, "harbor"),
    )
    for lens in lenses:
        assert lens["source_drift"]["status"] == "UNKNOWN"
        assert lens["source_drift"]["status"] != "FRESH"
        assert lens["honesty"]["unknown_is_fresh"] is False
        assert SECRET not in json.dumps(lens)
