"""AS-ORCH-001A/001B/001C — result contract, routing, and Cursor bridge.

STRUCTURED_RESULT_CONTRACT = IMPLEMENTED
DETERMINISTIC_CLASSIFICATION = IMPLEMENTED
DETERMINISTIC_POLICY_ROUTING = IMPLEMENTED
TYPED_TASK_DIRECTIVE = IMPLEMENTED
CURSOR_INTEGRATION_BRIDGE = IMPLEMENTED
CURSOR_STOP_HOOK = IMPLEMENTED

CURSOR TRIGGER INTEGRATION IMPLEMENTED
CROSS-AGENT DISPATCH NOT IMPLEMENTED
AUTHENTIC_WINDOWS_CURSOR_RUNTIME = NOT_YET_CERTIFIED
AGENT_DISPATCH = NOT_IMPLEMENTED
AUTONOMOUS_LOOP = NOT_IMPLEMENTED
AUTOMATIC_MERGE = NOT_IMPLEMENTED
OWNER AUTHORITY = STILL REQUIRED

The Cursor hook is a lifecycle trigger only. Atlas remains the source of
workflow truth. ``execution_authorized`` is always false.
"""

from project_atlas.orchestration.cursor_bridge import (
    CursorBridgeResponse,
    CursorBridgeState,
    CursorStopEvent,
    handle_stop_event,
    stage_result,
)
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
    "CursorBridgeResponse",
    "CursorBridgeState",
    "CursorStopEvent",
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
    "handle_stop_event",
    "parse_envelope",
    "resolve_policy",
    "route",
    "route_payload",
    "run_route_result",
    "run_validate_result",
    "source_result_digest",
    "stage_result",
    "validate_and_classify",
]
