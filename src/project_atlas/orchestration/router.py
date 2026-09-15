"""AS-ORCH-001B deterministic policy router.

Composition:
  AgentResultEnvelope → 001A validate/classify → OrchestrationDecision
  → 001B route(decision, envelope) → OrchestrationRoute / TaskDirective

The router consumes ``OrchestrationDecision.next_transition`` (and re-checks
it against a fresh 001A classify). ``requested_transition`` is advisory only.

This module does not dispatch, spawn agents, write queues, call GitHub,
merge, mutate production, or grant authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TextIO

from project_atlas.orchestration.models import (
    AgentResultEnvelope,
    DirectiveInputs,
    DirectivePermissions,
    DirectiveSource,
    NextTransition,
    OrchestrationDecision,
    OrchestrationRoute,
    RouteKind,
    RouteTarget,
    TargetKind,
    TaskDirective,
    TaskDirectiveSource,
)
from project_atlas.orchestration.policy import (
    POLICY_ID,
    POLICY_VERSION,
    PolicyMapping,
    UnmappedTransitionError,
    resolve_policy,
)
from project_atlas.orchestration.transitions import classify_envelope
from project_atlas.orchestration.validator import (
    ResultValidationError,
    load_result_bytes,
    malformed_decision,
    parse_envelope,
    read_result_source,
)


class RouteConsistencyError(ValueError):
    """Decision and envelope do not describe the same classified result."""


def canonical_payload_digest(payload: object) -> str:
    """Deterministic SHA-256 over canonical JSON. Identity, not authority."""
    if isinstance(payload, dict):
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    else:
        canonical = json.dumps(
            {"invalid_payload_type": type(payload).__name__},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def source_result_digest(envelope: AgentResultEnvelope) -> str:
    """Bind a route to the canonical validated envelope."""
    return canonical_payload_digest(envelope.model_dump(mode="json"))


def route(decision: OrchestrationDecision, envelope: AgentResultEnvelope) -> OrchestrationRoute:
    """Route a classifier decision bound to one envelope. Pure / fail-closed."""
    expected = classify_envelope(envelope)
    _assert_consistent(decision, envelope, expected)
    try:
        mapping = resolve_policy(expected.next_transition)
    except UnmappedTransitionError:
        return _terminal_route(
            envelope=envelope,
            transition=NextTransition.BLOCKED_UNKNOWN_STATE,
            digest=source_result_digest(envelope),
            reasons=["unknown_or_unmapped_transition"],
        )
    return _build_route(expected, envelope, mapping)


def route_payload(payload: object) -> OrchestrationRoute:
    """001A validate/classify then 001B route. Malformed input is terminal."""
    try:
        envelope = parse_envelope(payload)
    except ResultValidationError as exc:
        return _malformed_terminal(payload, str(exc))
    decision = classify_envelope(envelope)
    return route(decision, envelope)


def run_route_result(
    *,
    path: Path | None,
    from_stdin: bool,
    stdin: TextIO,
) -> tuple[OrchestrationRoute, int]:
    """Read-only CLI entry. Exit 0 iff the envelope is schema-valid."""
    try:
        raw = read_result_source(path=path, from_stdin=from_stdin, stdin=stdin)
        payload = load_result_bytes(raw)
    except ResultValidationError as exc:
        return _malformed_terminal(None, str(exc)), 1
    except OSError as exc:
        return _malformed_terminal(None, f"cannot read result file: {exc}"), 1
    try:
        envelope = parse_envelope(payload)
    except ResultValidationError as exc:
        return _malformed_terminal(payload, str(exc)), 1
    route_out = route(classify_envelope(envelope), envelope)
    return route_out, 0


def _assert_consistent(
    decision: OrchestrationDecision,
    envelope: AgentResultEnvelope,
    expected: OrchestrationDecision,
) -> None:
    if decision.task != envelope.task.id:
        raise RouteConsistencyError("decision/envelope task mismatch")
    if decision.producer != envelope.producer.role:
        raise RouteConsistencyError("decision/envelope producer role mismatch")
    if decision.outcome != envelope.outcome:
        raise RouteConsistencyError("decision/envelope outcome mismatch")
    if decision.next_transition != expected.next_transition:
        raise RouteConsistencyError("decision/envelope transition mismatch")
    if expected.task != envelope.task.id or expected.producer != envelope.producer.role:
        raise RouteConsistencyError("classifier/envelope identity mismatch")
    if expected.outcome != envelope.outcome:
        raise RouteConsistencyError("classifier/envelope outcome mismatch")


def _build_route(
    decision: OrchestrationDecision,
    envelope: AgentResultEnvelope,
    mapping: PolicyMapping,
) -> OrchestrationRoute:
    digest = source_result_digest(envelope)
    permissions = DirectivePermissions()
    source = DirectiveSource(
        task_id=envelope.task.id,
        attempt=envelope.task.attempt,
        producer_role=envelope.producer.role,
    )
    target = RouteTarget(kind=mapping.target_kind, role=mapping.target_role)
    task: TaskDirective | None = None
    if mapping.route_kind == RouteKind.TASK:
        assert mapping.task_type is not None
        assert mapping.target_role is not None
        task = TaskDirective(
            source=TaskDirectiveSource(
                task_id=envelope.task.id,
                attempt=envelope.task.attempt,
                producer_role=envelope.producer.role,
            ),
            transition=decision.next_transition,
            target=RouteTarget(kind=TargetKind.AGENT, role=mapping.target_role),
            task_type=mapping.task_type,
            permissions=DirectivePermissions(),
            owner_gate=False,
            execution_authorized=False,
            source_result_digest=digest,
            policy_id=POLICY_ID,
            policy_version=POLICY_VERSION,
            inputs=_bounded_inputs(envelope),
        )
    return OrchestrationRoute(
        policy_id=POLICY_ID,
        policy_version=POLICY_VERSION,
        source=source,
        source_result_digest=digest,
        transition=decision.next_transition,
        route_kind=mapping.route_kind,
        target=target,
        task_type=mapping.task_type,
        permissions=permissions,
        owner_gate=mapping.owner_gate,
        dispatchable=mapping.dispatchable,
        execution_authorized=False,
        task=task,
        reasons=list(decision.reasons),
    )


def _bounded_inputs(envelope: AgentResultEnvelope) -> DirectiveInputs:
    receipt_status = envelope.receipt.status if envelope.receipt is not None else None
    return DirectiveInputs(
        outcome=envelope.outcome,
        state=envelope.state,
        target_moved=envelope.observations.target_moved,
        unauthorized_mutations=envelope.observations.unauthorized_mutations,
        receipt_status=receipt_status,
        blocker_codes=[blocker.code for blocker in envelope.blockers],
    )


def _terminal_route(
    *,
    envelope: AgentResultEnvelope | None,
    transition: NextTransition,
    digest: str,
    reasons: list[str],
) -> OrchestrationRoute:
    source = DirectiveSource()
    if envelope is not None:
        source = DirectiveSource(
            task_id=envelope.task.id,
            attempt=envelope.task.attempt,
            producer_role=envelope.producer.role,
        )
    return OrchestrationRoute(
        policy_id=POLICY_ID,
        policy_version=POLICY_VERSION,
        source=source,
        source_result_digest=digest,
        transition=transition,
        route_kind=RouteKind.TERMINAL,
        target=RouteTarget(kind=TargetKind.TERMINAL, role=None),
        task_type=None,
        permissions=DirectivePermissions(),
        owner_gate=False,
        dispatchable=False,
        execution_authorized=False,
        task=None,
        reasons=reasons,
    )


def _malformed_terminal(payload: object, reason: str) -> OrchestrationRoute:
    decision = malformed_decision(reason)
    digest = canonical_payload_digest(payload)
    return _terminal_route(
        envelope=None,
        transition=NextTransition.REJECTED,
        digest=digest,
        reasons=list(decision.reasons),
    )
