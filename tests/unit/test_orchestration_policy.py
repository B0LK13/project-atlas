"""AS-ORCH-001B deterministic policy table and typed permission/model gates."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.models import (
    DirectivePermissions,
    NextTransition,
    OrchestrationRoute,
    ProducerRole,
    RouteKind,
    RouteTarget,
    TargetKind,
    TaskDirective,
    TaskType,
)
from project_atlas.orchestration.policy import (
    POLICY,
    POLICY_ID,
    POLICY_VERSION,
    RECERTIFY_TARGET_ROLE,
    REMEDIATION_TARGET_ROLE,
    UnmappedTransitionError,
    resolve_policy,
)
from project_atlas.schema import SchemaValidationError, available_schemas, validate_record


def test_policy_covers_every_001a_transition() -> None:
    assert set(POLICY) == set(NextTransition)


def test_integration_verify_mapping() -> None:
    mapping = resolve_policy(NextTransition.INTEGRATION_VERIFY)
    assert mapping.route_kind == RouteKind.TASK
    assert mapping.target_kind == TargetKind.AGENT
    assert mapping.target_role == ProducerRole.INTEGRATION
    assert mapping.task_type == TaskType.CANDIDATE_VERIFICATION
    assert mapping.owner_gate is False
    assert mapping.dispatchable is True


def test_recertify_uses_integration_role() -> None:
    mapping = resolve_policy(NextTransition.RECERTIFY_REQUIRED)
    assert mapping.target_role == RECERTIFY_TARGET_ROLE == ProducerRole.INTEGRATION
    assert mapping.task_type == TaskType.RECERTIFICATION
    assert mapping.owner_gate is False


def test_autonomous_reconcile_mapping() -> None:
    mapping = resolve_policy(NextTransition.AUTONOMOUS_RECONCILE)
    assert mapping.target_role == ProducerRole.AUTONOMOUS
    assert mapping.task_type == TaskType.PROGRAM_RECONCILIATION
    assert mapping.owner_gate is False


def test_remediation_uses_least_authoritative_existing_role() -> None:
    mapping = resolve_policy(NextTransition.REMEDIATION_REQUIRED)
    assert mapping.target_role == REMEDIATION_TARGET_ROLE == ProducerRole.LOCAL
    assert mapping.task_type == TaskType.REMEDIATION
    assert "implementation" not in {role.value for role in ProducerRole}


def test_owner_required_is_owner_gate_not_merge_task() -> None:
    mapping = resolve_policy(NextTransition.OWNER_REQUIRED)
    assert mapping.route_kind == RouteKind.OWNER_GATE
    assert mapping.target_kind == TargetKind.OWNER_GATE
    assert mapping.target_role is None
    assert mapping.task_type is None
    assert mapping.owner_gate is True
    assert mapping.dispatchable is False


@pytest.mark.parametrize(
    "transition",
    [
        NextTransition.BLOCKED,
        NextTransition.REJECTED,
        NextTransition.BLOCKED_UNKNOWN_STATE,
    ],
)
def test_terminal_transitions_are_non_dispatchable(transition: NextTransition) -> None:
    mapping = resolve_policy(transition)
    assert mapping.route_kind == RouteKind.TERMINAL
    assert mapping.dispatchable is False
    assert mapping.owner_gate is False
    assert mapping.task_type is None
    assert mapping.target_role is None


def test_unknown_transition_fail_closed() -> None:
    with pytest.raises(UnmappedTransitionError, match="unknown_or_unmapped_transition"):
        resolve_policy("NOT_A_REAL_TRANSITION")
    with pytest.raises(UnmappedTransitionError, match="unknown_or_unmapped_transition"):
        resolve_policy("MERGE")


def test_policy_identity_is_stable_and_not_authority() -> None:
    assert POLICY_ID == "atlas-orchestration-routing"
    assert POLICY_VERSION == 1


def test_permissions_reject_privileged_true() -> None:
    with pytest.raises(ValidationError):
        DirectivePermissions.model_validate({"merge": True})
    with pytest.raises(ValidationError):
        DirectivePermissions.model_validate({"production_mutation": True})
    with pytest.raises(ValidationError):
        DirectivePermissions.model_validate({"authority_grant": True})
    with pytest.raises(ValidationError):
        DirectivePermissions.model_validate({"repository_write": True})
    defaults = DirectivePermissions()
    assert defaults.merge is False
    assert defaults.production_mutation is False
    assert defaults.authority_grant is False
    assert defaults.repository_write is False
    assert defaults.branch_write is False
    assert defaults.pull_request_write is False


def test_task_directive_rejects_execution_and_owner_gate() -> None:
    payload = _task_directive_payload()
    payload["execution_authorized"] = True
    with pytest.raises(ValidationError):
        TaskDirective.model_validate(payload)
    payload = _task_directive_payload()
    payload["owner_gate"] = True
    with pytest.raises(ValidationError):
        TaskDirective.model_validate(payload)


def test_task_directive_rejects_executable_fields() -> None:
    payload = _task_directive_payload()
    payload["shell_command"] = "rm -rf /"
    with pytest.raises(ValidationError):
        TaskDirective.model_validate(payload)
    payload = _task_directive_payload()
    payload["cursor_prompt"] = "merge this"
    with pytest.raises(ValidationError):
        TaskDirective.model_validate(payload)
    payload = _task_directive_payload()
    payload["command_line"] = "git merge"
    with pytest.raises(ValidationError):
        TaskDirective.model_validate(payload)


def test_task_directive_rejects_terminal_or_owner_transition() -> None:
    for transition in ("OWNER_REQUIRED", "BLOCKED", "REJECTED", "BLOCKED_UNKNOWN_STATE"):
        payload = _task_directive_payload()
        payload["transition"] = transition
        with pytest.raises(ValidationError):
            TaskDirective.model_validate(payload)


def test_route_rejects_execution_authorized_true() -> None:
    payload = _route_payload()
    payload["execution_authorized"] = True
    with pytest.raises(ValidationError):
        OrchestrationRoute.model_validate(payload)


def test_owner_gate_cannot_carry_a_task() -> None:
    payload = _route_payload()
    payload["route_kind"] = "owner_gate"
    payload["transition"] = "OWNER_REQUIRED"
    payload["target"] = {"kind": "owner_gate", "role": None}
    payload["task_type"] = None
    payload["owner_gate"] = True
    payload["dispatchable"] = False
    payload["task"] = _task_directive_payload()
    with pytest.raises(ValidationError):
        OrchestrationRoute.model_validate(payload)


def test_schema_kinds_registered() -> None:
    kinds = available_schemas()
    assert "task-directive" in kinds
    assert "orchestration-route" in kinds
    assert "handoff-packet" in kinds


def test_task_directive_schema_model_parity() -> None:
    directive = TaskDirective.model_validate(_task_directive_payload())
    validate_record(directive, "task-directive")
    dumped = directive.model_dump(mode="json")
    validate_record(dumped, "task-directive")
    TaskDirective.model_validate(dumped)


def test_task_directive_schema_rejects_privilege_and_executable_fields() -> None:
    payload = _task_directive_payload()
    payload["permissions"] = {**payload["permissions"], "merge": True}
    with pytest.raises((SchemaValidationError, ValidationError)):
        validate_record(payload, "task-directive")
    payload = _task_directive_payload()
    payload["bash"] = "echo hi"
    with pytest.raises(SchemaValidationError):
        validate_record(payload, "task-directive")


def _task_directive_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": {"task_id": "D-137", "attempt": 1, "producer_role": "local"},
        "transition": "INTEGRATION_VERIFY",
        "target": {"kind": "agent", "role": "integration"},
        "task_type": "candidate_verification",
        "permissions": {
            "repository_write": False,
            "branch_write": False,
            "pull_request_write": False,
            "merge": False,
            "production_mutation": False,
            "authority_grant": False,
        },
        "owner_gate": False,
        "execution_authorized": False,
        "source_result_digest": "a" * 64,
        "policy_id": "atlas-orchestration-routing",
        "policy_version": 1,
        "inputs": {
            "outcome": "PASS",
            "state": "CERTIFIED",
            "target_moved": False,
            "unauthorized_mutations": 0,
            "receipt_status": "valid",
            "blocker_codes": [],
        },
    }


def _route_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package_id": "AS-ORCH-001B",
        "policy_id": "atlas-orchestration-routing",
        "policy_version": 1,
        "source": {"task_id": "D-137", "attempt": 1, "producer_role": "local"},
        "source_result_digest": "a" * 64,
        "transition": "INTEGRATION_VERIFY",
        "route_kind": "task",
        "target": {"kind": "agent", "role": "integration"},
        "task_type": "candidate_verification",
        "permissions": {
            "repository_write": False,
            "branch_write": False,
            "pull_request_write": False,
            "merge": False,
            "production_mutation": False,
            "authority_grant": False,
        },
        "owner_gate": False,
        "dispatchable": True,
        "execution_authorized": False,
        "task": _task_directive_payload(),
        "reasons": ["local_pass_certified"],
        "truth_boundary": "RESULT != AUTHORITY",
    }


def test_non_agent_target_cannot_carry_a_role() -> None:
    with pytest.raises(ValidationError):
        RouteTarget.model_validate({"kind": "owner_gate", "role": "integration"})
    with pytest.raises(ValidationError):
        RouteTarget.model_validate({"kind": "agent", "role": None})
