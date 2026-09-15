"""AS-OBS-SIG005-001 — live promotion-failure schema is not healthy.

OPS-SIG-005 must consume the receipt ingestion writes
(``projects[].candidates[].outcome=PROMOTION_FAILED``). Reading only
``failures`` / ``items`` fabricated ``ok`` / 0 while source_health on the
same file is ACTION_REQUIRED.

Does not touch ingestion.py. OPERATIONAL HEALTH ≠ PROJECT AUTHORITY.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_atlas.ops_health import build_health_snapshot, emit_health_snapshot
from project_atlas.source_health import explain_source_health
from project_atlas.web_api.health import read_vault_health

PACKAGE_ID = "AS-OBS-SIG005-001"

_LIVE_PROMOTION_INDEX = {
    "schema_version": 1,
    "receipt_type": "promotion-failure",
    "projects": [
        {
            "project_id": "harbor-api",
            "candidates": [
                {
                    "source_path": "docs/adr/ADR-001.md",
                    "outcome": "PROMOTION_FAILED",
                    "claims_extracted": 3,
                    "claims_withheld": 0,
                    "diagnostics": ["canonical-promotion-cas-conflict"],
                }
            ],
        }
    ],
    "diagnostics": [{"code": "PROMOTION_FAILURE", "severity": "ERROR"}],
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _identity_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir(parents=True)
    (vault / "projects" / "harbor-api").mkdir(parents=True)
    _write(
        vault / ".atlas" / "vault.json",
        {
            "schema_version": 1,
            "vault_id": "v-test",
            "vault_uuid": "11111111-1111-4111-8111-111111111111",
        },
    )
    return vault


def _signal_map(snapshot: dict[str, object]) -> dict[str, dict[str, object]]:
    signals = snapshot["signals"]
    assert isinstance(signals, list)
    return {str(item["signal_id"]): item for item in signals if isinstance(item, dict)}


def test_live_promotion_schema_is_fail_not_ok(tmp_path: Path) -> None:
    vault = _identity_vault(tmp_path)
    _write(vault / "quarantine" / "promotion-failures" / "index.json", _LIVE_PROMOTION_INDEX)
    snapshot = build_health_snapshot(vault)
    sig = _signal_map(snapshot)["OPS-SIG-005"]
    assert sig["status"] == "fail"
    assert sig["severity"] == "HIGH"
    assert sig["observed_value"] == 1
    assert "quarantine/promotion-failures/index.json" in str(sig["evidence_refs"])
    health = explain_source_health(vault, "harbor-api")
    assert health["health_state"] == "ACTION_REQUIRED"
    assert health["reason_counts"]["PROMOTION_FAILED"] == 1


def test_live_promotion_schema_cannot_rollup_healthy(tmp_path: Path) -> None:
    """Once recommended evidence exists, estate must not become healthy."""
    vault = _identity_vault(tmp_path)
    _write(vault / "quarantine" / "promotion-failures" / "index.json", _LIVE_PROMOTION_INDEX)
    _write(vault / "generated" / "ops" / "evidence" / "sync-failures.json", [])
    _write(vault / "generated" / "ops" / "evidence" / "last-sync.json", {"status": "ok"})
    _write(
        vault / "generated" / "ops" / "evidence" / "freshness.json",
        {"stale": False, "sync_needed": False},
    )
    _write(
        vault / "generated" / "reports" / "injection-findings.json",
        {"schema_version": 1, "findings": []},
    )
    _write(vault / "generated" / "reports" / "secret-findings.json", [])
    _write(
        vault / "generated" / "graph" / "acceptance" / "harbor-api.json",
        {"project_id": "harbor-api", "rejected_count": 0},
    )
    _write(
        vault / ".atlas" / "agent-readiness.json",
        {
            "adapters": {
                "generic": {
                    "rehearsal_status": "passed",
                    "governed_work_ready": True,
                    "revoked": False,
                    "skill_sha256": "a" * 64,
                    "observed_skill_sha256": "a" * 64,
                }
            }
        },
    )
    _write(vault / "generated" / "ops" / "evidence" / "backup-receipt.json", {"status": "ok"})
    _write(
        vault / "generated" / "ops" / "evidence" / "migration-status.json",
        {"status": "ok"},
    )
    _write(vault / "generated" / "ops" / "evidence" / "ci-status.json", {"status": "green"})
    _write(
        vault / "generated" / "reports" / "ingestion-report.json",
        {"classifications": {"unknown": 0}},
    )
    _write(
        vault / "generated" / "ops" / "evidence" / "query-diagnostics.json",
        {"query_corruption_count": 0, "query_nonanswer_count": 1},
    )
    snapshot = build_health_snapshot(vault)
    sig = _signal_map(snapshot)["OPS-SIG-005"]
    assert sig["status"] == "fail"
    assert snapshot["rollup"]["estate"] != "healthy"
    emit_health_snapshot(vault, persist=True)
    served = read_vault_health(vault)
    assert served["rollup"] != "healthy"


def test_legacy_failures_list_and_empty_index_still_hold(tmp_path: Path) -> None:
    vault = _identity_vault(tmp_path / "legacy")
    _write(
        vault / "quarantine" / "promotion-failures" / "index.json",
        {"failures": [{"resolved": False}]},
    )
    sig = _signal_map(build_health_snapshot(vault))["OPS-SIG-005"]
    assert sig["status"] == "fail"
    assert sig["observed_value"] == 1

    empty = _identity_vault(tmp_path / "empty")
    _write(empty / "quarantine" / "promotion-failures" / "index.json", [])
    empty_sig = _signal_map(build_health_snapshot(empty))["OPS-SIG-005"]
    assert empty_sig["status"] == "ok"
    assert empty_sig["observed_value"] == 0

    absent = _identity_vault(tmp_path / "absent")
    absent_sig = _signal_map(build_health_snapshot(absent))["OPS-SIG-005"]
    assert absent_sig["status"] == "unknown"
    assert absent_sig["observed_value"] is None
    assert absent_sig["evidence_refs"] == []


def test_resolved_live_candidate_is_not_open(tmp_path: Path) -> None:
    vault = _identity_vault(tmp_path)
    payload = json.loads(json.dumps(_LIVE_PROMOTION_INDEX))
    payload["projects"][0]["candidates"][0]["resolved"] = True
    _write(vault / "quarantine" / "promotion-failures" / "index.json", payload)
    sig = _signal_map(build_health_snapshot(vault))["OPS-SIG-005"]
    assert sig["status"] == "ok"
    assert sig["observed_value"] == 0
