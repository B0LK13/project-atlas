"""AS-STUDIO-A2 governance substrate — reusable loop, claim as first instance.

STUDIO_UI != AUTHORITY
REQUESTED != EXECUTED
PREVIEW != EXECUTION
UNSUPPORTED_ACTION = FAIL_CLOSED
NOT_STARTED != IMPLEMENTED
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from atlas_studio import action_intent as gc  # noqa: E402
from atlas_studio import governance as gov  # noqa: E402
from atlas_studio import mission_control as mc  # noqa: E402
from test_atlas_dag_router import make_profile, write_registry  # noqa: E402

FIXED = "2026-09-09T12:00:00Z"
AGENT = "ubuntu-main"
HEAD = "a" * 40
TREE = "b" * 40


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _claim_action(*, pr: int = 900) -> dict:
    lane = f"pr/{pr}"
    return {
        "action_id": f"{lane}:OWNERSHIP_CLAIM",
        "pr": pr,
        "lane": lane,
        "head": HEAD,
        "tree": TREE,
        "action_type": "OWNERSHIP_CLAIM",
        "action_class": "WRITE",
        "runnable_state": "RUNNABLE",
        "blocking_reasons": [],
        "agent_eligible": True,
        "ownership": "UNOWNED",
        "owner": None,
        "frozen": False,
        "score_total": 99.0,
        "truth_fingerprint": _fp(f"claim-{pr}"),
    }


def _matrix(actions: list[dict]) -> dict:
    return {
        "schema": "ATLAS_MULTIDIMENSIONAL_FRONTIER_V1",
        "generated_at_utc": FIXED,
        "agent": AGENT,
        "agent_status": "REGISTERED_ACTIVE",
        "frontier_fingerprint": _fp("frontier-" + AGENT),
        "actions": actions,
        "by_action_class": {},
        "typed_rankings": {},
    }


def _mc() -> dict:
    return {
        "schema": "ATLAS_STUDIO_MISSION_CONTROL_V1",
        "snapshot_fingerprint": _fp("mc-live"),
        "provenance": {"frontier_fingerprint": _fp("frontier-" + AGENT)},
    }


def _intent(*, action_type: str = "OWNERSHIP_CLAIM", **extra) -> dict:
    base = {
        "schema": "ATLAS_STUDIO_ACTION_INTENT_V1",
        "intent_id": "intent-substrate-1",
        "action_type": action_type,
        "requested_at_utc": FIXED,
        "max_age_seconds": 120,
        "actor_agent_id": AGENT,
        "target_agent_id": AGENT,
        "target_lane": "pr/900",
        "target_pr": 900,
        "target_head": HEAD,
        "source_mc_fingerprint": _fp("mc-live"),
        "source_frontier_fingerprint": _fp("frontier-" + AGENT),
        "candidate_action_id": "pr/900:OWNERSHIP_CLAIM",
        "capability_claims": ["CLAIM_OWNERSHIP", "POST_EVENTS"],
        "notes": None,
        "honesty": gov.honesty_intent(),
    }
    base.update(extra)
    return base


def test_supported_actions_lists_claim_implemented_and_futures_not_started():
    by_type = {row["action_type"]: row for row in gov.supported_actions()}
    assert by_type["OWNERSHIP_CLAIM"]["status"] == "IMPLEMENTED"
    for future in (
        "CI_DISPATCH",
        "IV_REQUEST",
        "HANDOFF_DELIVER",
        "STEAL_EXECUTE",
        "MERGE",
        "WORKTREE_OPEN",
    ):
        assert by_type[future]["status"] == "NOT_STARTED"


def test_unknown_action_type_refuses_unsupported():
    decision = gov.evaluate_governed_intent(_intent(action_type="TELEPORT_MERGE"))
    assert decision["decision"] == gov.REFUSED_UNSUPPORTED_ACTION
    assert decision["mutated"] is False
    assert any("UNSUPPORTED_ACTION_TYPE" in r for r in decision["reasons"])


def test_not_started_action_refuses_without_mutation():
    decision = gov.execute_governed_intent(
        _intent(action_type="CI_DISPATCH"),
        dry_run=False,
        client=object(),
        registry={},
    )
    assert decision["decision"] == gov.REFUSED_UNSUPPORTED_ACTION
    assert decision["mutated"] is False
    assert any("ACTION_NOT_STARTED:CI_DISPATCH" in r for r in decision["reasons"])


def test_forbidden_authz_fields_rejected_at_substrate():
    intent = _intent()
    intent["authorized"] = True
    decision = gov.evaluate_governed_intent(intent)
    assert decision["decision"] == gov.REFUSED_SCHEMA
    assert any("FORBIDDEN_AUTHZ_FIELD:authorized" in r for r in decision["reasons"])


def test_claim_allowed_via_substrate_evaluate(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    matrix = _matrix([_claim_action()])
    decision = gov.evaluate_governed_intent(
        _intent(),
        frontier_matrix=matrix,
        mission_control=_mc(),
        registry=registry,
        clock=lambda: FIXED,
        now_clock=lambda: FIXED,
    )
    assert decision["decision"] == gov.EXECUTE_ALLOWED
    assert decision["action_type"] == "OWNERSHIP_CLAIM"
    assert decision["mutated"] is False


def test_claim_dry_run_execute_via_substrate_no_mutate(tmp_path):
    registry = write_registry(tmp_path, [make_profile()])
    matrix = _matrix([_claim_action()])
    decision = gov.execute_governed_intent(
        _intent(),
        dry_run=True,
        frontier_matrix=matrix,
        mission_control=_mc(),
        registry=registry,
        clock=lambda: FIXED,
        now_clock=lambda: FIXED,
        client=object(),
    )
    assert decision["decision"] == gov.EXECUTED
    assert decision["dry_run"] is True
    assert decision["mutated"] is False
    assert "DRY_RUN_NO_EMIT" in decision["reasons"]
    assert decision["evidence"].get("substrate") == "atlas_studio.governance"


def test_execute_ownership_claim_routes_through_substrate():
    """Public claim API must remain a thin substrate instance."""
    src = Path(gc.__file__).read_text(encoding="utf-8")
    assert "gov.execute_governed_intent" in src
    assert "_OwnershipClaimHandler" in src
    assert "gov.register_action" in src
    assert "def apply_authorized(" in src
    assert "def mutate(" not in Path(gov.__file__).read_text(encoding="utf-8")


def test_mission_control_does_not_import_governance_or_claim():
    mc_src = Path(mc.__file__).read_text(encoding="utf-8")
    assert "action_intent" not in mc_src
    assert "governance" not in mc_src


def test_a1_build_mission_control_still_ro():
    """A1 remains usable without mutation context (governance loaded)."""
    assert gov.supported_actions()  # substrate present
    assert not hasattr(mc, "execute_ownership_claim")
    assert not hasattr(mc, "execute_governed_intent")
