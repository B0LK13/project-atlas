"""AS-WEB-001 web_api read-only adapter tests.

Contract: gen4-next-wave-parallel-001/AS-WEB-001-PACKAGE-CONTRACT.md
Invariants: UI ≠ canonical; Graph ≠ authority; Unknown ≠ healthy; no vault writes.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.web_api import (
    OBS_HEALTH_SNAPSHOT_RELATIVE,
    list_projects,
    read_status,
    read_vault_health,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, (dict, list)):
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        path.write_text(str(payload), encoding="utf-8")


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir()
    _write(
        vault / ".atlas" / "vault.json",
        {"vault_id": "atlas-web", "vault_uuid": "web-fixture-uuid"},
    )
    # Truth-plane probes — must not be mutated by web_api.
    (vault / "state" / "claims").mkdir(parents=True)
    _write(vault / "state" / "claims" / "probe.json", {"ok": True})
    (vault / "projects" / "alpha").mkdir(parents=True)
    _write(vault / "projects" / "alpha" / "project.md", "# Alpha\n")
    (vault / "projects" / "beta").mkdir(parents=True)
    return vault


def _mtimes(vault: Path) -> dict[str, float]:
    paths = [
        vault / "state" / "claims" / "probe.json",
        vault / "projects" / "alpha" / "project.md",
        vault / ".atlas" / "vault.json",
    ]
    return {str(p): p.stat().st_mtime_ns for p in paths if p.exists()}


def test_list_projects_sorted_read_only(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    before = _mtimes(vault)
    rows = list_projects(vault)
    assert [r["project_id"] for r in rows] == ["alpha", "beta"]
    assert rows[0]["has_project_note"] is True
    assert rows[1]["has_project_note"] is False
    assert rows[0]["path"] == "projects/alpha"
    assert _mtimes(vault) == before


def test_list_projects_absent_root_empty(tmp_path: Path) -> None:
    vault = tmp_path / "empty-vault"
    vault.mkdir()
    assert list_projects(vault) == []


def test_missing_ops_snapshot_is_unknown_not_healthy(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    health = read_vault_health(vault)
    assert health["available"] is False
    assert health["rollup"] == "unknown"
    assert health["rollup"] != "healthy"
    assert "UI ≠ canonical" in health["disclaimer"]
    assert health["authority_plane"] == "none"


def test_consume_ops_snapshot_rollup(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write(
        vault / OBS_HEALTH_SNAPSHOT_RELATIVE,
        {
            "schema": "atlas.ops.health_snapshot.v1",
            "truth_plane": "operational",
            "authority_plane": "none",
            "note": "OPERATIONAL HEALTH ≠ PROJECT AUTHORITY",
            "rollup": {"estate": "degraded"},
            "signals": [],
        },
    )
    before = _mtimes(vault)
    health = read_vault_health(vault)
    assert health["available"] is True
    assert health["rollup"] == "degraded"
    assert health["source"].endswith("health-snapshot.json")
    assert _mtimes(vault) == before
    # Snapshot file itself may exist; claims probe must be untouched.
    assert (vault / "state" / "claims" / "probe.json").read_text(encoding="utf-8")


def test_malformed_rollup_not_healthy(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write(
        vault / OBS_HEALTH_SNAPSHOT_RELATIVE,
        {"rollup": {"estate": "totally-fine"}, "truth_plane": "operational"},
    )
    health = read_vault_health(vault)
    assert health["available"] is True
    assert health["rollup"] == "unknown"
    assert health["rollup"] != "healthy"


def test_unreadable_snapshot_unknown(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    path = vault / OBS_HEALTH_SNAPSHOT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    health = read_vault_health(vault)
    assert health["available"] is False
    assert health["rollup"] == "unknown"


def test_read_status_invariants_and_composition(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    before = _mtimes(vault)
    status = read_status(vault)
    assert status["vault_present"] is True
    assert status["vault_id"] == "web-fixture-uuid"
    assert status["read_plane"] == "unread"
    assert status["health"]["rollup"] == "unknown"
    assert status["ui_canonical"] is False
    assert status["graph_authority"] is False
    assert status["unknown_equals_healthy"] is False
    assert len(status["projects"]) == 2
    assert _mtimes(vault) == before


def test_read_status_with_snapshot_sets_ops_plane(tmp_path: Path) -> None:
    vault = _vault(tmp_path)
    _write(
        vault / OBS_HEALTH_SNAPSHOT_RELATIVE,
        {
            "rollup": {"estate": "healthy"},
            "truth_plane": "operational",
            "authority_plane": "none",
            "note": "OPERATIONAL HEALTH ≠ PROJECT AUTHORITY",
        },
    )
    status = read_status(vault)
    assert status["read_plane"] == "ops_snapshot"
    assert status["health"]["rollup"] == "healthy"
    # Even when OBS says healthy, ADR flags remain false for UI/graph authority.
    assert status["ui_canonical"] is False
    assert status["graph_authority"] is False


def test_absent_vault_unknown(tmp_path: Path) -> None:
    missing = tmp_path / "no-vault"
    status = read_status(missing)
    assert status["vault_present"] is False
    assert status["health"]["rollup"] == "unknown"
    assert status["projects"] == []
