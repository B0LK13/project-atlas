"""Deterministic policy gate. No LLM call, no free-form judgment.

``evaluate()`` is pure: same ``OriginationProposal`` in, same
``PolicyResult`` out, forever. Free-form model reasoning is never
consulted here -- evidence and this function are the only authority.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from project_atlas.orchestration.origination.proposal import (
    AuthorityClass,
    ExecutionReadyReason,
    OriginationProposal,
    RiskClass,
)


class PolicyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    origination_proposal_valid: bool
    authoritative_intent_signal: bool
    corroborating_signal: bool
    execution_ready: bool
    reason: ExecutionReadyReason


def evaluate(proposal: OriginationProposal) -> PolicyResult:
    authoritative_intent_signal = (
        proposal.authority_class != AuthorityClass.INSUFFICIENT
        and bool(proposal.authoritative_source.location)
    )
    corroborating_signal = len(proposal.acceptance_evidence) > 0

    # ORIGINATION_PROPOSAL = VALID requires at least the authoritative
    # intent signal; a proposal with no authoritative source should never
    # have been constructible in the first place (proposal.py's own
    # validator would already have rejected a missing authoritative_source
    # at the type level), so this is a defensive re-check, not the primary
    # gate.
    origination_proposal_valid = authoritative_intent_signal

    if proposal.contradictions:
        return PolicyResult(
            origination_proposal_valid=origination_proposal_valid,
            authoritative_intent_signal=authoritative_intent_signal,
            corroborating_signal=corroborating_signal,
            execution_ready=False,
            reason=ExecutionReadyReason.CONFLICTING_PROJECT_EVIDENCE,
        )

    if not origination_proposal_valid:
        return PolicyResult(
            origination_proposal_valid=False,
            authoritative_intent_signal=authoritative_intent_signal,
            corroborating_signal=corroborating_signal,
            execution_ready=False,
            reason=ExecutionReadyReason.INSUFFICIENT_ACCEPTANCE_CONTRACT,
        )

    if not corroborating_signal:
        return PolicyResult(
            origination_proposal_valid=True,
            authoritative_intent_signal=True,
            corroborating_signal=False,
            execution_ready=False,
            reason=ExecutionReadyReason.INSUFFICIENT_ACCEPTANCE_CONTRACT,
        )

    if proposal.risk_class == RiskClass.OWNER_HELD:
        return PolicyResult(
            origination_proposal_valid=True,
            authoritative_intent_signal=True,
            corroborating_signal=True,
            execution_ready=False,
            reason=ExecutionReadyReason.OWNER_HELD_RISK,
        )

    return PolicyResult(
        origination_proposal_valid=True,
        authoritative_intent_signal=True,
        corroborating_signal=True,
        execution_ready=True,
        reason=ExecutionReadyReason.READY,
    )
