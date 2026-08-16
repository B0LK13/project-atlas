"""AS-ORCH-001A — Agent Result Contract + Deterministic Transition Classification.

STRUCTURED RESULT CONTRACT = IMPLEMENTED
DETERMINISTIC CLASSIFICATION = IMPLEMENTED

AUTOMATIC ROUTING = NOT YET IMPLEMENTED
CURSOR HOOK = NOT YET IMPLEMENTED
AGENT DISPATCH = NOT YET IMPLEMENTED
AUTONOMOUS LOOP = NOT YET IMPLEMENTED
AUTOMATIC MERGE = NOT IMPLEMENTED
OWNER AUTHORITY = STILL REQUIRED

This package classifies what may happen next. It does not execute the
transition, dispatch another agent, merge code, or grant owner authority.
``execution_authorized`` is always false.
"""

from project_atlas.orchestration.models import (
    PACKAGE_ID,
    SCHEMA_KIND,
    TRUTH_BOUNDARY,
    AgentResultEnvelope,
    NextTransition,
    OrchestrationDecision,
    ProducerRole,
    RequestedTransition,
    ResultOutcome,
    WorkflowState,
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
    "SCHEMA_KIND",
    "TRUTH_BOUNDARY",
    "AgentResultEnvelope",
    "NextTransition",
    "OrchestrationDecision",
    "ProducerRole",
    "RequestedTransition",
    "ResultOutcome",
    "ResultValidationError",
    "WorkflowState",
    "classify_envelope",
    "parse_envelope",
    "run_validate_result",
    "validate_and_classify",
]
