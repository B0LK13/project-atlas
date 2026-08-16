"""AS-ORCH-001A/001B/001C/001D — result, routing, bridge, single-hop dispatch.

STRUCTURED_RESULT_CONTRACT = IMPLEMENTED
DETERMINISTIC_CLASSIFICATION = IMPLEMENTED
DETERMINISTIC_POLICY_ROUTING = IMPLEMENTED
TYPED_TASK_DIRECTIVE = IMPLEMENTED
CURSOR_BRIDGE_CORE = IMPLEMENTED
CURSOR_STOP_HOOK_ADAPTER = IMPLEMENTED
EXPLICIT_COMPLETION_TRANSPORT = IMPLEMENTED
SINGLE_HOP_AGENT_DISPATCHER = IMPLEMENTED
CURSOR_CLI_PROCESS_TRANSPORT = IMPLEMENTED
AUTHENTIC_CURSOR_STOP_EVENT_DELIVERY = NOT_RELIABLE_IN_CURRENT_WINDOWS_CLI_RUNTIME
AUTHENTIC_CURSOR_STOP_EVENT_DELIVERY = ENVIRONMENT_DEPENDENT
AUTHENTIC_WINDOWS_CURSOR_AGENT_DISPATCH = NOT_YET_CERTIFIED
HOOK_RUNTIME_REQUIRED_FOR_CORE_FLOW = NO
CURSOR_STOP_EVENT_REQUIRED_FOR_DISPATCH = NO
CROSS_AGENT_DISPATCH = SINGLE_HOP_ONLY
AGENT_DISPATCH = IMPLEMENTED
AUTONOMOUS_LOOP = NOT_IMPLEMENTED
MULTI_HOP_AUTODISPATCH = NOT_IMPLEMENTED
PARALLEL_AGENT_FANOUT = NOT_IMPLEMENTED
AUTOMATIC_MERGE = NOT_IMPLEMENTED
OWNER AUTHORITY = STILL REQUIRED

The Cursor stop hook is an optional transport adapter. Atlas remains the
source of workflow truth. Explicit completion does not require a Cursor
stop event. ``execution_authorized`` is always false. One spawned target
process is not an autonomous loop.
"""

from project_atlas.orchestration.cursor_bridge import (
    CompletionTransport,
    CursorBridgeResponse,
    CursorBridgeState,
    CursorStopEvent,
    HandoffPacket,
    complete_staged_handoff,
    handle_stop_event,
    stage_result,
    surface_pending_handoff,
)
from project_atlas.orchestration.dispatcher import (
    DispatchReceipt,
    DispatchRecord,
    DispatchStatus,
    recover_dispatch,
    run_dispatch_once,
    submit_target_result,
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
    "CompletionTransport",
    "CursorBridgeResponse",
    "CursorBridgeState",
    "CursorStopEvent",
    "DispatchReceipt",
    "DispatchRecord",
    "DispatchStatus",
    "HandoffPacket",
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
    "complete_staged_handoff",
    "handle_stop_event",
    "parse_envelope",
    "recover_dispatch",
    "resolve_policy",
    "route",
    "route_payload",
    "run_dispatch_once",
    "run_route_result",
    "run_validate_result",
    "source_result_digest",
    "stage_result",
    "submit_target_result",
    "surface_pending_handoff",
    "validate_and_classify",
]
