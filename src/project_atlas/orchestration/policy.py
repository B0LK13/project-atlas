"""Deterministic routing policy table for AS-ORCH-001B.

Maps a classifier ``NextTransition`` to a typed route. Does not infer routes
from natural language, requested_transition, or model output.

Policy identity is for audit/replay only. It is not authority.

Remediation role choice (explicit, not invented silently):
  The 001A producer taxonomy is only ``local`` | ``integration`` | ``autonomous``.
  There is no canonical ``implementation`` role in current Atlas contracts.
  REMEDIATION_REQUIRED therefore targets ``local`` — the least-authoritative
  existing role, i.e. the implementation plane that produced the original work.
  Recertification remains an integration-plane task (same plane as verification).

ROUTING POLICY IMPLEMENTED
RUNTIME AUTOMATIC ROUTING NOT IMPLEMENTED
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from project_atlas.orchestration.models import (
    NextTransition,
    ProducerRole,
    RouteKind,
    TargetKind,
    TaskType,
)

ROUTING_PACKAGE_ID: Final[Literal["AS-ORCH-001B"]] = "AS-ORCH-001B"
POLICY_ID: Final[Literal["atlas-orchestration-routing"]] = "atlas-orchestration-routing"
POLICY_VERSION: Final[Literal[1]] = 1

# Recertification stays on the integration plane — same role that verifies
# candidates. Do not invent a separate recertifier role.
RECERTIFY_TARGET_ROLE: Final[ProducerRole] = ProducerRole.INTEGRATION

# Least-authoritative existing role suitable for remediation. Not a new
# ``implementation`` taxonomy member.
REMEDIATION_TARGET_ROLE: Final[ProducerRole] = ProducerRole.LOCAL


@dataclass(frozen=True, slots=True)
class PolicyMapping:
    """Explicit, complete mapping for one classifier transition."""

    route_kind: RouteKind
    target_kind: TargetKind
    target_role: ProducerRole | None
    task_type: TaskType | None
    owner_gate: bool
    dispatchable: bool


POLICY: Final[dict[NextTransition, PolicyMapping]] = {
    NextTransition.INTEGRATION_VERIFY: PolicyMapping(
        route_kind=RouteKind.TASK,
        target_kind=TargetKind.AGENT,
        target_role=ProducerRole.INTEGRATION,
        task_type=TaskType.CANDIDATE_VERIFICATION,
        owner_gate=False,
        dispatchable=True,
    ),
    NextTransition.RECERTIFY_REQUIRED: PolicyMapping(
        route_kind=RouteKind.TASK,
        target_kind=TargetKind.AGENT,
        target_role=RECERTIFY_TARGET_ROLE,
        task_type=TaskType.RECERTIFICATION,
        owner_gate=False,
        dispatchable=True,
    ),
    NextTransition.AUTONOMOUS_RECONCILE: PolicyMapping(
        route_kind=RouteKind.TASK,
        target_kind=TargetKind.AGENT,
        target_role=ProducerRole.AUTONOMOUS,
        task_type=TaskType.PROGRAM_RECONCILIATION,
        owner_gate=False,
        dispatchable=True,
    ),
    NextTransition.REMEDIATION_REQUIRED: PolicyMapping(
        route_kind=RouteKind.TASK,
        target_kind=TargetKind.AGENT,
        target_role=REMEDIATION_TARGET_ROLE,
        task_type=TaskType.REMEDIATION,
        owner_gate=False,
        dispatchable=True,
    ),
    NextTransition.OWNER_REQUIRED: PolicyMapping(
        route_kind=RouteKind.OWNER_GATE,
        target_kind=TargetKind.OWNER_GATE,
        target_role=None,
        task_type=None,
        owner_gate=True,
        dispatchable=False,
    ),
    NextTransition.BLOCKED: PolicyMapping(
        route_kind=RouteKind.TERMINAL,
        target_kind=TargetKind.TERMINAL,
        target_role=None,
        task_type=None,
        owner_gate=False,
        dispatchable=False,
    ),
    NextTransition.REJECTED: PolicyMapping(
        route_kind=RouteKind.TERMINAL,
        target_kind=TargetKind.TERMINAL,
        target_role=None,
        task_type=None,
        owner_gate=False,
        dispatchable=False,
    ),
    NextTransition.BLOCKED_UNKNOWN_STATE: PolicyMapping(
        route_kind=RouteKind.TERMINAL,
        target_kind=TargetKind.TERMINAL,
        target_role=None,
        task_type=None,
        owner_gate=False,
        dispatchable=False,
    ),
}


class UnmappedTransitionError(ValueError):
    """Unknown or unmapped classifier transition. Fail closed."""


def resolve_policy(transition: object) -> PolicyMapping:
    """Look up a deterministic mapping. Unknown transitions fail closed."""
    try:
        key = (
            transition
            if isinstance(transition, NextTransition)
            else NextTransition(str(transition))
        )
    except ValueError as exc:
        raise UnmappedTransitionError("unknown_or_unmapped_transition") from exc
    mapping = POLICY.get(key)
    if mapping is None:
        raise UnmappedTransitionError("unknown_or_unmapped_transition")
    return mapping
