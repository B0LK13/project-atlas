"""AS-ORCH-001A deterministic transition classification and precedence."""

from __future__ import annotations

from typing import Any

from project_atlas.orchestration import (
    classify_envelope,
    parse_envelope,
    validate_and_classify,
)
from project_atlas.orchestration.models import NextTransition, WorkflowState


def _payload(
    *,
    role: str = "local",
    outcome: str = "PASS",
    state: str = "CERTIFIED",
    target_moved: bool = False,
    unauthorized_mutations: int = 0,
    receipt_status: str | None = "valid",
    include_receipt: bool = True,
    blockers: list[dict[str, str]] | None = None,
    requested_transition: str | None = None,
    extras: dict[str, bool | int | str] | None = None,
) -> dict[str, Any]:
    observations: dict[str, Any] = {
        "target_moved": target_moved,
        "unauthorized_mutations": unauthorized_mutations,
    }
    if extras is not None:
        observations["extras"] = extras
    payload: dict[str, Any] = {
        "schema_version": 1,
        "producer": {"role": role, "agent_id": f"{role}-agent"},
        "task": {"id": "D-137", "attempt": 1},
        "outcome": outcome,
        "state": state,
        "observations": observations,
        "blockers": blockers or [],
        "requested_transition": requested_transition,
    }
    if include_receipt:
        payload["receipt"] = {
            "receipt_id": "ASR-1234567890abcdef",
            "status": receipt_status,
        }
    else:
        payload["receipt"] = None
    return payload


def _classify(**kwargs: Any) -> Any:
    return classify_envelope(parse_envelope(_payload(**kwargs)))


def test_local_pass_valid_receipt_unchanged_target() -> None:
    decision = _classify()
    assert decision.valid is True
    assert decision.next_transition == NextTransition.INTEGRATION_VERIFY
    assert decision.workflow_state == WorkflowState.LOCAL_ACCEPTED
    assert decision.execution_authorized is False
    assert decision.merge_authorized is False
    assert decision.owner_required is False


def test_local_pass_target_moved() -> None:
    decision = _classify(target_moved=True)
    assert decision.next_transition == NextTransition.RECERTIFY_REQUIRED
    assert decision.workflow_state == WorkflowState.RECERTIFY_REQUIRED
    assert decision.execution_authorized is False


def test_local_fail() -> None:
    decision = _classify(outcome="FAIL")
    assert decision.next_transition == NextTransition.BLOCKED
    assert decision.workflow_state == WorkflowState.BLOCKED
    assert decision.execution_authorized is False


def test_local_blocked() -> None:
    decision = _classify(outcome="BLOCKED")
    assert decision.next_transition == NextTransition.BLOCKED
    assert decision.execution_authorized is False


def test_local_pass_missing_receipt() -> None:
    decision = _classify(include_receipt=False)
    assert decision.valid is True
    assert decision.next_transition == NextTransition.REJECTED
    assert "missing_required_receipt" in decision.reasons


def test_local_pass_rejected_receipt() -> None:
    decision = _classify(receipt_status="rejected")
    assert decision.next_transition == NextTransition.REJECTED
    assert "invalid_or_rejected_receipt" in decision.reasons


def test_local_pass_pending_receipt_rejected() -> None:
    decision = _classify(receipt_status="pending")
    assert decision.next_transition == NextTransition.REJECTED


def test_local_pass_unauthorized_mutation() -> None:
    decision = _classify(unauthorized_mutations=1)
    assert decision.next_transition == NextTransition.REJECTED
    assert "unauthorized_mutations" in decision.reasons
    assert decision.execution_authorized is False


def test_pass_plus_certified_plus_mutation_is_not_integration_verify() -> None:
    decision = _classify(outcome="PASS", state="CERTIFIED", unauthorized_mutations=1)
    assert decision.next_transition != NextTransition.INTEGRATION_VERIFY
    assert decision.next_transition == NextTransition.REJECTED


def test_integration_pass() -> None:
    decision = _classify(role="integration")
    assert decision.next_transition == NextTransition.AUTONOMOUS_RECONCILE
    assert decision.workflow_state == WorkflowState.INTEGRATION_ACCEPTED
    assert decision.execution_authorized is False


def test_integration_fail() -> None:
    decision = _classify(role="integration", outcome="FAIL")
    assert decision.next_transition == NextTransition.REMEDIATION_REQUIRED
    assert decision.workflow_state == WorkflowState.REMEDIATION_REQUIRED


def test_integration_blocked() -> None:
    decision = _classify(role="integration", outcome="BLOCKED")
    assert decision.next_transition == NextTransition.BLOCKED


def test_merge_eligible_owner_required() -> None:
    decision = _classify(role="integration", state="MERGE_ELIGIBLE")
    assert decision.next_transition == NextTransition.OWNER_REQUIRED
    assert decision.workflow_state == WorkflowState.OWNER_REQUIRED
    assert decision.owner_required is True
    assert decision.merge_authorized is False
    assert decision.execution_authorized is False


def test_merge_eligible_plus_requested_merge_still_owner_required() -> None:
    decision = _classify(
        role="integration",
        state="MERGE_ELIGIBLE",
        requested_transition="MERGE",
    )
    assert decision.next_transition == NextTransition.OWNER_REQUIRED
    assert decision.owner_required is True
    assert decision.merge_authorized is False
    assert decision.execution_authorized is False
    assert decision.requested_transition == "MERGE"
    assert "requested_transition_advisory_only" in decision.reasons
    assert decision.next_transition != "MERGE"


def test_requested_transition_never_overrides_classification() -> None:
    decision = _classify(requested_transition="MERGE")
    assert decision.next_transition == NextTransition.INTEGRATION_VERIFY
    assert decision.owner_required is False
    assert decision.merge_authorized is False
    assert "requested_transition_advisory_only" in decision.reasons


def test_unknown_critical_state_fail_closed() -> None:
    decision = _classify(state="SOME_FUTURE_STATE")
    assert decision.valid is True
    assert decision.next_transition == NextTransition.BLOCKED_UNKNOWN_STATE
    assert decision.workflow_state == WorkflowState.BLOCKED_UNKNOWN_STATE
    assert decision.execution_authorized is False
    assert "unknown_routing_critical_state" in decision.reasons


def test_autonomous_pass_is_unspecified_and_fail_closed() -> None:
    decision = _classify(role="autonomous")
    assert decision.next_transition == NextTransition.BLOCKED_UNKNOWN_STATE
    assert decision.execution_authorized is False


def test_explicit_blockers_override_pass() -> None:
    decision = _classify(blockers=[{"code": "SECRET_SCAN", "detail": "quarantined"}])
    assert decision.next_transition == NextTransition.BLOCKED
    assert "explicit_blockers" in decision.reasons


def test_precedence_mutation_overrides_missing_receipt_and_failure() -> None:
    decision = _classify(
        outcome="FAIL",
        include_receipt=False,
        unauthorized_mutations=1,
        target_moved=True,
        state="MERGE_ELIGIBLE",
    )
    assert decision.next_transition == NextTransition.REJECTED
    assert decision.reasons[0] == "unauthorized_mutations"


def test_precedence_missing_receipt_overrides_failure_and_owner_gate() -> None:
    decision = _classify(
        outcome="FAIL",
        include_receipt=False,
        state="MERGE_ELIGIBLE",
        target_moved=True,
    )
    assert decision.next_transition == NextTransition.REJECTED
    assert "missing_required_receipt" in decision.reasons


def test_precedence_failure_overrides_target_moved_and_owner_gate() -> None:
    decision = _classify(outcome="FAIL", target_moved=True, state="MERGE_ELIGIBLE")
    assert decision.next_transition == NextTransition.BLOCKED
    assert "local_fail" in decision.reasons


def test_precedence_target_moved_overrides_owner_gate() -> None:
    decision = _classify(role="integration", state="MERGE_ELIGIBLE", target_moved=True)
    assert decision.next_transition == NextTransition.RECERTIFY_REQUIRED
    assert decision.owner_required is False


def test_deterministic_replay() -> None:
    first = _classify(role="local", extras={"fixture_name": "harbor-api"})
    second = _classify(role="local", extras={"fixture_name": "harbor-api"})
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    again = validate_and_classify(_payload(role="local", extras={"fixture_name": "harbor-api"}))
    assert again.model_dump(mode="json") == first.model_dump(mode="json")


def test_scenario_a_local_acceptance() -> None:
    decision = _classify(
        role="local",
        outcome="PASS",
        receipt_status="valid",
        target_moved=False,
        unauthorized_mutations=0,
    )
    assert decision.next_transition == NextTransition.INTEGRATION_VERIFY
    assert decision.execution_authorized is False


def test_scenario_b_stale_target() -> None:
    decision = _classify(
        role="local",
        outcome="PASS",
        receipt_status="valid",
        target_moved=True,
        unauthorized_mutations=0,
    )
    assert decision.next_transition == NextTransition.RECERTIFY_REQUIRED
    assert decision.execution_authorized is False


def test_scenario_c_merge_eligible_owner_gate() -> None:
    decision = _classify(
        role="integration",
        outcome="PASS",
        state="MERGE_ELIGIBLE",
        receipt_status="valid",
    )
    assert decision.next_transition == NextTransition.OWNER_REQUIRED
    assert decision.merge_authorized is False
    assert decision.execution_authorized is False
    assert decision.owner_required is True
