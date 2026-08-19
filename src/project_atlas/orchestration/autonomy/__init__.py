"""AS-ORCH-AUTONOMY-001 autonomous control plane.

Formalizes deterministic, auditable, fail-closed autonomous operation.
Does not implement AS-ORCH-001E, merge, or owner-authority grants.
001D single-hop dispatch lives in project_atlas.orchestration.dispatcher.

AUTONOMOUS_GOVERNOR = IMPLEMENTED
TRUSTED_ANCHOR_ADVANCEMENT = IMPLEMENTED
STATIC_BOOTSTRAP_PIN_AS_RUNTIME_AUTHORITY = NO
WORK_DAG = IMPLEMENTED
AGENT_LEASE_MODEL = IMPLEMENTED
SURFACE_OVERLAP_GATE = IMPLEMENTED
AUTONOMOUS_CONTINUATION_POLICY = IMPLEMENTED
AUTOMATIC_REMEDIATION = IMPLEMENTED
IV_ROUTING = IMPLEMENTED
ADVERSARIAL_REVIEW_TRIGGER = IMPLEMENTED
EVIDENCE_CONTRACT = IMPLEMENTED
OWNER_GATES_A_F = IMPLEMENTED
AGENT_DISPATCH = IMPLEMENTED_BY_AS_ORCH_001D
MULTI_HOP_AUTODISPATCH = NOT_IMPLEMENTED
AUTONOMOUS_LOOP_001E = NOT_IMPLEMENTED
AUTOMATIC_MERGE = NOT_IMPLEMENTED
SUCCESSOR_EXECUTION_UNDER_NEW_MODEL = NOT_YET_ACTIVE
OWNER AUTHORITY = STILL REQUIRED

001D single-hop / owner-authority / dispatch-once semantics are preserved:
this governor never auto-dispatches a next 001D hop and never grants merge.
"""

from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.models import (
    AUTONOMY_PACKAGE_ID,
    DIRECTIVE_ID,
    MAX_AUTONOMOUS_REMEDIATION_CYCLES,
    TRUTH_BOUNDARY,
    AgentCapability,
    AgentLease,
    ExecutionPlan,
    GovernorState,
    NodeState,
    OwnerGateKind,
    StopReason,
    WorkNode,
)

__all__ = [
    "AUTONOMY_PACKAGE_ID",
    "DIRECTIVE_ID",
    "MAX_AUTONOMOUS_REMEDIATION_CYCLES",
    "TRUTH_BOUNDARY",
    "AgentCapability",
    "AgentLease",
    "AutonomousGovernor",
    "ExecutionPlan",
    "GovernorState",
    "NodeState",
    "OwnerGateKind",
    "StopReason",
    "WorkNode",
]
