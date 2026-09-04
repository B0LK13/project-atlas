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
    """The origination policy gate's own verdict. ADVISORY ONLY.

    Nothing in this class grants execution, lease, dispatch, or merge
    authority -- ``run_origination_scan()`` (``cli.py``) already documents
    that origination as a whole "never leases, never dispatches, never
    merges" and always reports fixed ``merge_authorized: False`` /
    ``execution_authorized: False`` sentinels; this docstring exists
    because that guarantee is easy to miss from ``policy.py`` alone,
    which carries no cross-reference to it.

    Verified by direct source inspection, during investigation of a P1
    authority-escalation claim that this repository's own review process
    subsequently found insufficiently qualified and required narrowing
    (see git history for both): ``execution_ready`` has exactly one
    production consumer in the entire codebase -- it is read into the
    scan's own JSON report (``cli.py``) and nowhere else. It is never
    checked as a conditional anywhere. In particular,
    ``materialize.materialize_work_node()`` materializes a proposal
    regardless of this value (its own docstring: "a proposal that has
    already cleared the policy gate, OR is being materialized precisely
    because it did *not* clear it"), and ``governor.lease()`` grants a
    lease based on node state, dependencies, owner_gate, and origination-
    identity freshness -- never on this field, which ``WorkNode`` does
    not even carry.

    ``execution_ready`` therefore answers "does this proposal look
    specification-backed enough, by this pipeline's advisory heuristic"
    -- not "is this work authorized to run." Do not treat a `True` value
    as a security boundary, and do not treat a `False` value as proof a
    node cannot be leased -- but do not over-read that as "any two
    proposals lease identically regardless of this field" either: real
    gates that DO determine leaseability (``proposal.dependencies``,
    ``risk_class``/``owner_gate``, origination-identity freshness) are
    free to differ between two otherwise-similar proposals for reasons
    that happen to correlate with `execution_ready`. What is proven is
    narrower and precise: holding every OTHER policy input fixed and
    varying only the evidence that feeds `execution_ready`
    (`corroborating_signal`) does not by itself change whether the
    resulting node materializes, gets an `owner_gate`, or leases.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    origination_proposal_valid: bool
    authoritative_intent_signal: bool
    #: Advisory only -- see the class docstring. Presently driven solely
    #: by ``adapter.py::extract_corroborating_facts()``, which credits a
    #: module-level skip/xfail-marked evidence file and nothing else; a
    #: known, owner-level, non-emergency design inconsistency (weaker/
    #: disabled-test evidence can outscore a passing test in THIS
    #: advisory signal) that does not affect real execution authority.
    corroborating_signal: bool
    #: Advisory only -- see the class docstring. `True` does not
    #: authorize a lease; `False` does not prevent one. The real
    #: authority boundary is `proposal.blockers` (materialization-time)
    #: and `governor.lease()`'s own checks (state, dependencies,
    #: owner_gate, origination-identity freshness).
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

    if proposal.blockers:
        # A declared blocker is explicit negative authority. Keep the
        # proposal inspectable, but do not convert READY lifecycle metadata
        # into execution authority while its unlock condition is unresolved.
        return PolicyResult(
            origination_proposal_valid=origination_proposal_valid,
            authoritative_intent_signal=authoritative_intent_signal,
            corroborating_signal=corroborating_signal,
            execution_ready=False,
            reason=ExecutionReadyReason.INSUFFICIENT_ACCEPTANCE_CONTRACT,
        )

    if proposal.dependencies:
        # `proposal.dependencies` only ever contains package ids for
        # dependencies the adapter already confirmed are NOT
        # IMPLEMENTED/VERIFIED_COMPLETION (see adapter.eligible_roadmap_items's
        # _DONE_STATUSES filtering) -- so a non-empty tuple here always
        # means a genuinely outstanding prerequisite. This check exists
        # because the existing governed DAG (orchestration.autonomy) does
        # NOT itself enforce dependency-completion gating at lease time:
        # governor.lease()/mark_ready() never consult
        # WorkNode.dependencies -- only plan()'s advisory "what_must_wait"
        # list reflects it descriptively. Preserving the dependency edge
        # on the materialized WorkNode (materialize.py) is necessary for
        # visibility but not sufficient for safety; this policy gate is
        # what actually prevents READY while a real prerequisite remains
        # outstanding, since downstream enforcement does not exist yet.
        return PolicyResult(
            origination_proposal_valid=origination_proposal_valid,
            authoritative_intent_signal=authoritative_intent_signal,
            corroborating_signal=corroborating_signal,
            execution_ready=False,
            reason=ExecutionReadyReason.UNSATISFIED_DEPENDENCIES,
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
