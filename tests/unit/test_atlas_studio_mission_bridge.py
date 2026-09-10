"""AS-STUDIO-BRIDGE-001 -- Studio task-context -> governed mission run.

The bridge's most important properties are NEGATIVE: a read-only Studio
projection must never become an execution grant, and Studio's own state
must be able to REFUSE a run. Both are tested here with real refusals, not
by asserting that a helper returns a dict.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import mission_bridge as mb  # noqa: E402


def _packet(**overrides):
    base = {
        "schema": mb.SCHEMA_CONST,
        "lane": "pr/791",
        "agent": {"agent_id": "ubuntu-main"},
        "freshness": {"state": "LIVE"},
        "next_step": {
            "status": "SUPPORTED",
            "authorization": "NOT_GRANTED_BY_THIS_PACKET",
            "action": {
                "action_type": "READONLY_ANALYZE",
                "action_class": "READONLY",
            },
        },
        "continuation": {
            "fingerprint": "fp-abc",
            "fingerprints": {"lane_head": "181f2eba"},
        },
        "knowledge": {"lenses": {"state": {"provenance": {"generator": "gen.state"}}}},
    }
    base.update(overrides)
    return base


def test_happy_path_carries_context_but_never_policy():
    got = mb.build_mission_inputs(_packet(), expected_agent_id="ubuntu-main")
    assert got.lane == "pr/791"
    assert got.action_type == "READONLY_ANALYZE"
    assert got.lane_head == "181f2eba"
    assert got.freshness_state == "LIVE"
    # The returned inputs are DATA ONLY -- no policy/authority field exists.
    assert not hasattr(got, "trusted_policy")
    assert "readonly" in got.keywords


def test_packet_that_stops_disclaiming_authorization_is_refused():
    """If Studio ever claimed to grant authorization, the bridge fails closed."""
    p = _packet()
    p["next_step"]["authorization"] = "GRANTED"
    with pytest.raises(mb.StudioAuthorityError, match="disclaims authorization"):
        mb.build_mission_inputs(p, expected_agent_id="ubuntu-main")


@pytest.mark.parametrize("leaked", ["authorization", "next_step", "lane_state", "honesty"])
def test_studio_derived_keys_cannot_become_trusted_policy(leaked):
    with pytest.raises(mb.StudioAuthorityError, match="Studio-derived keys"):
        mb.validate_trusted_policy({leaked: "anything"})


def test_caller_supplied_policy_passes_through_unchanged():
    pol = {"MERGE_AUTHORIZATION": "NO"}
    out = mb.validate_trusted_policy(pol)
    assert out == pol
    assert out is not pol  # defensive copy


def test_no_supported_action_refuses_with_reasons():
    p = _packet()
    p["next_step"] = {
        "status": "NO_SUPPORTED_ACTION",
        "authorization": "NOT_GRANTED_BY_THIS_PACKET",
        "reasons": ["AGENT_INACTIVE", "CANDIDATE_NOT_FROZEN"],
    }
    with pytest.raises(mb.StudioPreconditionError, match="AGENT_INACTIVE"):
        mb.build_mission_inputs(p, expected_agent_id="ubuntu-main")


def test_stale_context_refused_by_default_and_overridable():
    p = _packet(freshness={"state": "STALE"})
    with pytest.raises(mb.StudioPreconditionError, match="not LIVE"):
        mb.build_mission_inputs(p, expected_agent_id="ubuntu-main")
    got = mb.build_mission_inputs(p, expected_agent_id="ubuntu-main", allow_stale=True)
    assert got.freshness_state == "STALE"


def test_actor_mismatch_is_never_silently_substituted():
    with pytest.raises(mb.StudioPreconditionError, match="never substitutes"):
        mb.build_mission_inputs(_packet(), expected_agent_id="someone-else")


def test_write_class_requires_explicit_opt_in():
    p = _packet()
    p["next_step"]["action"] = {
        "action_type": "OWNERSHIP_CLAIM",
        "action_class": "WRITE",
    }
    with pytest.raises(mb.StudioPreconditionError, match="allow_write_class"):
        mb.build_mission_inputs(p, expected_agent_id="ubuntu-main")
    got = mb.build_mission_inputs(
        p, expected_agent_id="ubuntu-main", allow_write_class=True
    )
    assert got.action_class == "WRITE"


def test_human_gate_is_treated_as_write_class():
    p = _packet()
    p["next_step"]["action"] = {
        "action_type": "OWNER_DECISION",
        "action_class": "HUMAN_GATE",
    }
    with pytest.raises(mb.StudioPreconditionError, match="allow_write_class"):
        mb.build_mission_inputs(p, expected_agent_id="ubuntu-main")


def test_non_object_and_wrong_schema_are_refused():
    with pytest.raises(mb.StudioPreconditionError, match="must be a JSON object"):
        mb.build_mission_inputs([], expected_agent_id="ubuntu-main")
    with pytest.raises(mb.StudioPreconditionError, match="unexpected packet schema"):
        mb.build_mission_inputs(
            _packet(schema="SOMETHING_ELSE"), expected_agent_id="ubuntu-main"
        )
