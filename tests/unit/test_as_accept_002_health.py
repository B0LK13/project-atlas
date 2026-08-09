"""AS-ACCEPT-002 Band A — HUN / EMP OBS external oracles.

Wave-A2 P0: AX2-HUN-001, AX2-EMP-001, AX2-EMP-003.
INV-A04 / INV-A05 / INV-A06.
"""

from __future__ import annotations

from pathlib import Path

from tests.unit._as_accept_002_helpers import (
    identity_only_ops_vault,
    signal_map,
    write_json,
)

from project_atlas.ops_health import REQUIRED_SIGNAL_IDS, build_health_snapshot
from project_atlas.schema import validate_record


def test_ax2_hun_001_identity_only_estate_unknown_not_healthy(tmp_path: Path) -> None:
    """AX2-HUN-001: identity-only vault → required signals unknown; estate ≠ healthy.

    INV-A04 / INV-A06 — absent evidence never fabricated ok / healthy.
    """
    vault = identity_only_ops_vault(tmp_path)
    snapshot = build_health_snapshot(vault)
    validate_record(snapshot, "ops-health-snapshot")
    assert snapshot["truth_plane"] == "operational"
    assert snapshot["authority_plane"] == "none"
    assert snapshot["rollup"]["estate"] == "unknown"
    assert snapshot["rollup"]["estate"] != "healthy"
    signals = signal_map(snapshot)
    for signal_id in REQUIRED_SIGNAL_IDS:
        assert signal_id in signals
    for signal_id in (
        "OPS-SIG-002",
        "OPS-SIG-005",
        "OPS-SIG-006",
        "OPS-SIG-010",
        "OPS-SIG-013",
        "OPS-SIG-014",
    ):
        assert signals[signal_id]["status"] == "unknown"
    assert signals["OPS-SIG-005"]["evidence_refs"] == []
    assert signals["OPS-SIG-006"]["evidence_refs"] == []


def test_ax2_emp_001_present_empty_promotion_index_ok_zero(tmp_path: Path) -> None:
    """AX2-EMP-001: present-empty promotion index → OPS-SIG-005 ok / 0 + refs.

    INV-A05 — observed empty is honest zero.
    """
    vault = identity_only_ops_vault(tmp_path)
    write_json(vault / "quarantine" / "promotion-failures" / "index.json", [])
    snapshot = build_health_snapshot(vault)
    sig = signal_map(snapshot)["OPS-SIG-005"]
    assert sig["status"] == "ok"
    assert sig["observed_value"] == 0
    assert sig["evidence_refs"]
    assert len(sig["evidence_refs"]) > 0


def test_ax2_emp_003_absent_vs_present_empty_oracles_do_not_collapse(
    tmp_path: Path,
) -> None:
    """AX2-EMP-003: ABS → unknown+empty refs; EMPTY → ok/0+refs — must not collapse.

    INV-A04 / INV-A05 contrast.
    """
    abs_vault = identity_only_ops_vault(tmp_path / "abs")
    abs_snap = build_health_snapshot(abs_vault)
    abs_sig = signal_map(abs_snap)["OPS-SIG-005"]
    assert abs_sig["status"] == "unknown"
    assert abs_sig["observed_value"] is None
    assert abs_sig["evidence_refs"] == []
    assert abs_snap["rollup"]["estate"] != "healthy"

    empty_vault = identity_only_ops_vault(tmp_path / "empty")
    write_json(empty_vault / "quarantine" / "promotion-failures" / "index.json", [])
    empty_snap = build_health_snapshot(empty_vault)
    empty_sig = signal_map(empty_snap)["OPS-SIG-005"]
    assert empty_sig["status"] == "ok"
    assert empty_sig["observed_value"] == 0
    assert empty_sig["evidence_refs"]
    # Oracles must remain distinct.
    assert (abs_sig["status"], tuple(abs_sig["evidence_refs"])) != (
        empty_sig["status"],
        tuple(empty_sig["evidence_refs"]),
    )
