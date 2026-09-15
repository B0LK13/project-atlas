"""AS-CODER-ALPHA-HONESTY-TAIL-001 / #384 — unchanged must not hide live drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.connect import connect_project
from project_atlas.inventory_drift import evaluate_connect_inventory_drift
from project_atlas.project_changed import materialize_changed_lenses
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


def _write_inventory_pair(
    vault: Path,
    *,
    project_id: str,
    path: str,
    digest: str,
) -> None:
    payload = {
        "schema_version": 1,
        "schema": "atlas.coder-alpha.connect-inventory.v1",
        "by_path": {path: digest},
        "sources": [{"path": path, "sha256": digest, "project_id": project_id}],
    }
    ops = vault / "generated" / "ops"
    ops.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    (ops / "connect-inventory.json").write_text(text, encoding="utf-8")
    (ops / "connect-inventory.prev.json").write_text(text, encoding="utf-8")


def test_stale_live_and_historical_unchanged_is_not_current(tmp_path: Path) -> None:
    """LIVE_DRIFT=STALE AND HISTORICAL_DIFF=UNCHANGED => UNCHANGED_IS_CURRENT=FALSE."""
    project = tmp_path / "chg-384"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("# Honesty tail 384\n\nv1\n", encoding="utf-8")
    first = connect_project(project)
    project_id = str(first["bound_project_id"])
    vault = Path(first["vault"])
    # Incremental reconnect skips when disk is unchanged, so establish the
    # historical last-connect pair directly (identical current + prev).
    current_inv = vault / "generated" / "ops" / "connect-inventory.json"
    prev_inv = vault / "generated" / "ops" / "connect-inventory.prev.json"
    prev_inv.write_bytes(current_inv.read_bytes())
    unchanged = materialize_changed_lenses(vault, project_ids=[project_id])["lenses"][0]
    assert unchanged["rollup"] == "unchanged"
    assert unchanged["delta"]["added"] == []
    assert unchanged["delta"]["modified"] == []
    assert unchanged["delta"]["removed"] == []
    assert unchanged["honesty"]["unchanged_is_current"] is True
    assert unchanged["honesty"]["stale_is_current"] is False
    assert "reconnect" not in " ".join(unchanged["notes"]).lower()

    readme.write_text("# Honesty tail 384\n\nv2 live edit\n", encoding="utf-8")
    live = evaluate_connect_inventory_drift(vault, project_id)
    assert live["status"] == "STALE"
    lens = materialize_changed_lenses(vault, project_ids=[project_id])["lenses"][0]
    assert lens["source_drift"]["status"] == "STALE"
    assert lens["rollup"] == "unchanged"
    assert lens["delta"]["added"] == []
    assert lens["delta"]["modified"] == []
    assert lens["delta"]["removed"] == []
    assert lens["delta"]["added_count"] == 0
    assert lens["delta"]["modified_count"] == 0
    assert lens["honesty"]["unchanged_is_current"] is False
    assert lens["honesty"]["stale_is_current"] is False
    assert lens["honesty"]["lens_is_authority"] is False
    assert "reconnect" in " ".join(lens["notes"]).lower()


def test_stale_live_does_not_invent_temporal_history(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    readme = root / "README.md"
    readme.write_text("# Harbor\n\nv1\n", encoding="utf-8")
    digest = canonical_source_sha256(readme)
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor").mkdir(parents=True)
    _write_inventory_pair(vault, project_id="harbor", path="README.md", digest=digest)
    _write_manifest(
        vault,
        root,
        [{"path": "README.md", "sha256": digest, "likely_project": "harbor"}],
    )
    readme.write_text("# Harbor\n\nv2\n", encoding="utf-8")
    lens = materialize_changed_lenses(vault, project_ids=["harbor"])["lenses"][0]
    assert lens["rollup"] == "unchanged"
    assert lens["source_drift"]["status"] == "STALE"
    assert lens["delta"]["added"] == []
    assert lens["delta"]["modified"] == []
    assert "README.md" not in lens["delta"]["added"]
    assert "README.md" not in lens["delta"]["modified"]
    assert lens["honesty"]["unchanged_is_current"] is False


def test_changed_stale_does_not_echo_secret_or_sibling(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    harbor = root / "README.md"
    harbor.write_text("# Harbor\n\nv1\n", encoding="utf-8")
    sibling = root / "other.md"
    sibling.write_text("# Sibling\n\nv1\n", encoding="utf-8")
    harbor_digest = canonical_source_sha256(harbor)
    sibling_digest = canonical_source_sha256(sibling)
    vault = tmp_path / "vault"
    (vault / "projects" / "harbor").mkdir(parents=True)
    _write_inventory_pair(vault, project_id="harbor", path="README.md", digest=harbor_digest)
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
    lens = materialize_changed_lenses(vault, project_ids=["harbor"])["lenses"][0]
    payload = json.dumps(lens)
    assert lens["source_drift"]["status"] == "STALE"
    assert "README.md" in lens["source_drift"]["changed_paths"]
    assert "other.md" not in lens["source_drift"]["changed_paths"]
    assert "other.md" not in payload
    assert secret not in payload
