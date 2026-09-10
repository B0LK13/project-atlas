"""Adversarial tests for FEATURE_16: Final End-to-End Integration Hardening.

E2E != AUTHORITY
NO_SELF_IV / NO_FABRICATED_EVIDENCE
Every denial has a load-bearing positive control. Hermetic fixtures only.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_dag import cli as cli_mod  # noqa: E402
from atlas_dag import e2e_harden as e2e  # noqa: E402
from atlas_dag import handoff as handoff_mod  # noqa: E402


@pytest.fixture
def world(tmp_path):
    return e2e.build_fixture_world(tmp_dir=tmp_path)


@pytest.fixture
def packet(world):
    return e2e.run_e2e_hardening(world=world, live=False)


# --- honesty / schema -------------------------------------------------------


def test_honesty_consts_required(packet):
    assert e2e.validate_packet(packet) == []
    honesty = packet["honesty"]
    assert honesty["e2e_ne_authority"] is True
    assert honesty["no_self_iv"] is True
    assert honesty["no_fabricated_evidence"] is True
    assert packet["provenance"]["e2e_ne_authority"] is True
    assert packet["provenance"]["grants_no_write_claim_dispatch_merge_iv"] is True
    bad = copy.deepcopy(packet)
    bad["honesty"]["e2e_ne_authority"] = False
    assert any("e2e_ne_authority" in err for err in e2e.validate_packet(bad))


def test_no_authority_grant_in_packet(packet):
    assert packet["schema"] == e2e.SCHEMA_CONST
    assert packet["provenance"]["grants_no_write_claim_dispatch_merge_iv"] is True
    # Packet never invents a write/dispatch/merge authorization surface.
    for key in ("dispatch", "merge", "claim", "iv_receipt"):
        assert key not in packet


# --- determinism ------------------------------------------------------------


def test_determinism_same_inputs_same_fingerprint(tmp_path):
    a = e2e.run_e2e_hardening(world=e2e.build_fixture_world(tmp_dir=tmp_path / "a"))
    b = e2e.run_e2e_hardening(world=e2e.build_fixture_world(tmp_dir=tmp_path / "b"))
    assert a["hardening_fingerprint"] == b["hardening_fingerprint"]
    assert a["invariants"] == b["invariants"]
    assert a["overall_status"] == b["overall_status"]
    assert [s["id"] for s in a["scenarios"]] == [s["id"] for s in b["scenarios"]]


# --- scenario coverage ------------------------------------------------------


def test_all_fixture_scenarios_pass(packet):
    fixture = [s for s in packet["scenarios"] if not s["id"].startswith("live_")]
    assert len(fixture) >= 15
    failed = [s["id"] for s in fixture if s["status"] != e2e.PASS]
    assert failed == [], failed
    assert packet["overall_status"] == e2e.PASS


def test_success_owned_runnable_write(world):
    sc = e2e._eval_success(world)
    assert sc["status"] == e2e.PASS
    assert any("implement_state=RUNNABLE" in e for e in sc["evidence"])
    assert any("remediate_state=RUNNABLE" in e for e in sc["evidence"])


def test_stale_head_expect_mismatch_and_handoff_stale(world):
    sc = e2e._eval_stale_head(world)
    assert sc["status"] == e2e.PASS
    joined = " ".join(sc["evidence"])
    assert "EXPECT_HEAD_MISMATCH" in joined
    assert "HANDOFF_STALE" in joined
    assert "PRIORITY_NE_AUTHORITY" in joined


def test_frozen_lane_write_blocked(world):
    sc = e2e._eval_frozen(world)
    assert sc["status"] == e2e.PASS
    assert any("LANE_FROZEN" in e for e in sc["evidence"])


def test_inactive_agent_ineligible_no_safe_steal(world):
    sc = e2e._eval_inactive(world)
    assert sc["status"] == e2e.PASS
    joined = " ".join(sc["evidence"])
    assert "NO_SAFE_STEAL" in joined or "REGISTERED_INACTIVE" in joined


def test_blocked_iv_unbound_verifier(world):
    sc = e2e._eval_blocked_iv(world)
    assert sc["status"] == e2e.PASS
    joined = " ".join(sc["evidence"] + sc["notes"])
    assert "VERIFIER_IDENTITY_UNBOUND" in joined or "external_iv_gated" in joined


def test_main_movement_restack_blocks_write(world):
    sc = e2e._eval_restack(world)
    assert sc["status"] == e2e.PASS
    assert any("STACK_NOT_CURRENT" in e for e in sc["evidence"])
    assert any("restack_action_present=True" in e for e in sc["evidence"])


def test_ownership_ambiguous_fail_closed(world):
    sc = e2e._eval_ambiguous(world)
    assert sc["status"] == e2e.PASS
    assert any("OWNERSHIP_AMBIGUOUS_FAIL_CLOSED" in e for e in sc["evidence"])


def test_residual_durability_and_f12_projection(world):
    sc = e2e._eval_residual(world)
    assert sc["status"] == e2e.PASS
    assert any("durable_ids=" in e for e in sc["evidence"])
    assert any("f12_projected=" in e for e in sc["evidence"])


def test_telemetry_and_control_view_panels(world):
    tel = e2e._eval_telemetry(world)
    cv = e2e._eval_control_view(world)
    assert tel["status"] == e2e.PASS
    assert cv["status"] == e2e.PASS
    assert any("telemetry_ne_authority" in e for e in tel["evidence"])
    assert any("control_view_ne_authority" in e for e in cv["evidence"])


# --- invariants -------------------------------------------------------------


def test_invariant_derivation_fully_integrated(packet):
    inv = packet["invariants"]
    for key in e2e.INVARIANT_KEYS:
        assert key in inv, key
        assert inv[key] is True, key
    assert inv["END_TO_E2E_HARDENING"] is True
    assert inv["ATLAS_AUTONOMOUS_COORDINATION_STACK"] is True


def test_invariant_derivation_fails_when_scenario_fails():
    scenarios = [
        {"id": e2e.SCENARIO_SUCCESS, "status": e2e.FAIL, "evidence": [],
         "notes": ["forced"]},
        {"id": e2e.SCENARIO_AMBIGUOUS, "status": e2e.PASS, "evidence": [],
         "notes": []},
    ]
    inv = e2e.derive_invariants(scenarios)
    assert inv["AGENT_ROUTING"] is False
    assert inv["END_TO_E2E_HARDENING"] is False
    assert inv["ATLAS_AUTONOMOUS_COORDINATION_STACK"] is False


# --- live optional skip -----------------------------------------------------


def test_live_probes_skip_without_snapshot(tmp_path):
    world = e2e.build_fixture_world(tmp_dir=tmp_path)
    packet = e2e.run_e2e_hardening(
        world=world, live=True, snapshot=None, stacks=None, events=[])
    live = [s for s in packet["scenarios"] if s["id"].startswith("live_")]
    assert live
    assert all(s["status"] == e2e.SKIP for s in live)
    # Fixture suite still drives overall PASS when integrated.
    assert packet["invariants"]["END_TO_E2E_HARDENING"] is True
    assert packet["overall_status"] == e2e.PASS


# --- CLI / presentation -----------------------------------------------------


def test_cli_e2e_harden_json_exit_zero(capsys):
    code = cli_mod.main(["e2e-harden", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert e2e.SCHEMA_CONST in out
    assert "END_TO_E2E_HARDENING" in out


def test_e2e_hardening_status_presentation_slice(packet):
    status = e2e.e2e_hardening_status(packet)
    assert status["overall_status"] == e2e.PASS
    assert status["failed_scenario_ids"] == []
    assert status["e2e_ne_authority"] is True
    assert status["invariants"]["ATLAS_AUTONOMOUS_COORDINATION_STACK"] is True


def test_handoff_resume_includes_e2e_status_slice(world, monkeypatch):
    """Presentation-only: resume mode may attach e2e_hardening_status."""
    # Avoid depending on GhClient; exercise the thin helper directly.
    status = e2e.e2e_hardening_status(
        e2e.run_e2e_hardening(world=world, live=False))
    assert "overall_status" in status
    assert "failed_scenario_ids" in status
    # Resume helper fail-closed path.
    unresolved = handoff_mod._resume_e2e_hardening("general")
    assert unresolved is None
    resume = handoff_mod._resume_e2e_hardening("resume")
    assert resume is not None
    assert resume.get("e2e_ne_authority") is True
    assert "overall_status" in resume
