"""AS-ORCH-001A/001B — result contract, classification, and policy routing.

STRUCTURED_RESULT_CONTRACT = IMPLEMENTED
DETERMINISTIC_CLASSIFICATION = IMPLEMENTED
DETERMINISTIC_POLICY_ROUTING = IMPLEMENTED
TYPED_TASK_DIRECTIVE = IMPLEMENTED

ROUTING POLICY IMPLEMENTED
RUNTIME AUTOMATIC ROUTING NOT IMPLEMENTED
CURSOR_HOOK = NOT_IMPLEMENTED
AGENT_DISPATCH = NOT_IMPLEMENTED
AUTONOMOUS_LOOP = NOT_IMPLEMENTED
AUTOMATIC_MERGE = NOT_IMPLEMENTED
OWNER AUTHORITY = STILL REQUIRED

This package classifies and routes what may happen next. It does not execute
the transition, dispatch another agent, create Cursor hooks, merge code, or
grant owner authority. ``execution_authorized`` is always false.
"""

from project_atlas.orchestration.models import (
    PACKAGE_ID,
    SCHEMA_KIND,
    TRUTH_BOUNDARY,
    AgentResultEnvelope,
    NextTransition,
    OrchestrationDecision,
    OrchestrationRoute,
    ProducerRole,
    RequestedTransition,
    ResultOutcome,
    RouteKind,
    TaskDirective,
    TaskType,
    WorkflowState,
)
from project_atlas.orchestration.policy import (
    POLICY_ID,
    POLICY_VERSION,
    ROUTING_PACKAGE_ID,
    resolve_policy,
)
from project_atlas.orchestration.router import (
    RouteConsistencyError,
    route,
    route_payload,
    run_route_result,
    source_result_digest,
)
from project_atlas.orchestration.transitions import classify_envelope
from project_atlas.orchestration.validator import (
    ResultValidationError,
    parse_envelope,
    run_validate_result,
    validate_and_classify,
)

__all__ = [
    "PACKAGE_ID",
    "POLICY_ID",
    "POLICY_VERSION",
    "ROUTING_PACKAGE_ID",
    "SCHEMA_KIND",
    "TRUTH_BOUNDARY",
    "AgentResultEnvelope",
    "NextTransition",
    "OrchestrationDecision",
    "OrchestrationRoute",
    "ProducerRole",
    "RequestedTransition",
    "ResultOutcome",
    "ResultValidationError",
    "RouteConsistencyError",
    "RouteKind",
    "TaskDirective",
    "TaskType",
    "WorkflowState",
    "classify_envelope",
    "parse_envelope",
    "resolve_policy",
    "route",
    "route_payload",
    "run_route_result",
    "run_validate_result",
    "source_result_digest",
    "validate_and_classify",
]
