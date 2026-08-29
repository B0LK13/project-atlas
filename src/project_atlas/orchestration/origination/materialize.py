"""Proposal -> WorkNode. A pure mapping, not a new execution path.

From here on an origination-derived node moves through the existing,
unmodified ``orchestration.autonomy`` DAG/lease/dispatch machinery exactly
like any other ``WorkNode``.
"""

from __future__ import annotations

import re

from project_atlas.orchestration.autonomy.models import (
    AgentCapability,
    ExecutionHostClass,
    IvRequirements,
    MutationSurface,
    OwnerGateKind,
    RiskTag,
    WorkNode,
)
from project_atlas.orchestration.origination.proposal import OriginationProposal, RiskClass
from project_atlas.orchestration.origination.risk import DisqualifyingAttribute, RiskClassification

_DISQUALIFIER_TO_GATE: dict[DisqualifyingAttribute, OwnerGateKind] = {
    DisqualifyingAttribute.DEPENDENCY_CHANGE: OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
    DisqualifyingAttribute.WORKFLOW_CHANGE: OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
    DisqualifyingAttribute.SECURITY_SURFACE: OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
    DisqualifyingAttribute.CREDENTIAL_REQUIREMENT: OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
    DisqualifyingAttribute.DEPLOYMENT_EFFECT: OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
    DisqualifyingAttribute.DATA_MUTATION: OwnerGateKind.E_DESTRUCTIVE_OPS,
    DisqualifyingAttribute.EXTERNAL_SIDE_EFFECT: OwnerGateKind.F_MATERIAL_EXTERNAL_SPEND,
    DisqualifyingAttribute.OUT_OF_SPECIFICATION_COVERAGE: (
        OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY
    ),
}

_DISQUALIFIER_TO_RISK_TAG: dict[DisqualifyingAttribute, RiskTag] = {
    DisqualifyingAttribute.DEPENDENCY_CHANGE: RiskTag.HIGH_BLAST_RADIUS,
    DisqualifyingAttribute.WORKFLOW_CHANGE: RiskTag.CONTROL_PLANE,
    DisqualifyingAttribute.SECURITY_SURFACE: RiskTag.SECURITY_RELEVANT,
    DisqualifyingAttribute.CREDENTIAL_REQUIREMENT: RiskTag.SECURITY_RELEVANT,
    DisqualifyingAttribute.DEPLOYMENT_EFFECT: RiskTag.HIGH_BLAST_RADIUS,
    DisqualifyingAttribute.DATA_MUTATION: RiskTag.DATA_INTEGRITY,
    DisqualifyingAttribute.EXTERNAL_SIDE_EFFECT: RiskTag.HIGH_BLAST_RADIUS,
    DisqualifyingAttribute.OUT_OF_SPECIFICATION_COVERAGE: RiskTag.AUTHORIZATION,
}

_MAX_ACCEPTANCE_CRITERIA = 16
_MAX_MUTATION_PATHS = 64
#: Mirrors ``orchestration.autonomy.models._REL_PATH_RE`` exactly (that
#: name is module-private there too; duplicated here as a one-line
#: constant rather than imported, since re-deriving MutationSurface's own
#: validation contract this way keeps this module independently readable
#: without depending on another module's private regex staying stable).
_SAFE_MUTATION_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")


def owner_gate_for(classification: RiskClassification) -> OwnerGateKind | None:
    if classification.risk_class != RiskClass.OWNER_HELD:
        return None
    for attribute in classification.disqualifying_attributes:
        gate = _DISQUALIFIER_TO_GATE.get(attribute)
        if gate is not None:
            return gate
    return OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY  # pragma: no cover - defensive fallback


def risk_tags_for(classification: RiskClassification) -> tuple[RiskTag, ...]:
    tags = tuple(
        dict.fromkeys(
            _DISQUALIFIER_TO_RISK_TAG[attribute]
            for attribute in classification.disqualifying_attributes
            if attribute in _DISQUALIFIER_TO_RISK_TAG
        )
    )
    return tags[:8]  # WorkNode.risk_tags max_length=8


def materialize_work_node(
    proposal: OriginationProposal,
    classification: RiskClassification,
    *,
    base_pin: str,
    surface_id: str,
) -> WorkNode:
    """Pure mapping from an ``OriginationProposal`` (that has already
    cleared the policy gate, or is being materialized precisely because
    it did *not* clear it -- OWNER_HELD nodes are still materialized, just
    routed straight to ``owner_gate``) into a real ``WorkNode``.
    """
    owner_gate = owner_gate_for(classification)
    acceptance_criteria = proposal.success_criteria[:_MAX_ACCEPTANCE_CRITERIA]
    # WorkNode.mutation_surface.paths must satisfy the same safe-relative-
    # identifier pattern as every other orchestration.autonomy path field
    # (alphanumeric-first -- a bare dotfile like ".env" does not qualify).
    # risk.classify() (UNSAFE_MUTATION_PATH, D-PHASE2A independent-IV
    # finding) already checks this same pattern and forces OWNER_HELD if
    # any proposed_scope entry fails it -- so by the time an O1
    # `classification` reaches this function, every path here is
    # guaranteed to match. This filter is now purely defensive: it only
    # ever has anything to drop for an OWNER_HELD classification (which
    # never executes autonomously regardless of what its registered
    # surface says), never for O1, so it can no longer silently narrow
    # what an autonomously-executing node is authorized to touch.
    mutation_paths = tuple(
        path for path in proposal.proposed_scope if _SAFE_MUTATION_PATH_RE.fullmatch(path)
    )[:_MAX_MUTATION_PATHS]

    return WorkNode(
        package_id=proposal.work_id,
        objective=proposal.intent,
        base_pin=base_pin,
        dependencies=(),
        mutation_surface=MutationSurface(
            surface_id=surface_id,
            paths=mutation_paths,
            semantic="ORIGINATION_SPECIFICATION_BOUND",
        ),
        execution_host_class=ExecutionHostClass.IN_PROCESS,
        # IMPLEMENT only: VERIFY is a separate routing step
        # (governor.route_and_verify(), IvRequirements.
        # implementer_cannot_verify=True below) that assigns its OWN
        # agent, deliberately never the same one holding the lease --
        # requiring both here would mean no DEFAULT_AGENTS entry could
        # ever qualify to hold this lease at all, since capability
        # separation is by design (see governor.py's DEFAULT_AGENTS).
        agent_capabilities_required=(AgentCapability.IMPLEMENT,),
        acceptance_criteria=acceptance_criteria,
        test_requirements=("SPEC_TEST_SUITE_PASSES",),
        iv_requirements=IvRequirements(
            certification_required=True,
            implementer_cannot_verify=True,
            adversarial_required=classification.risk_class == RiskClass.OWNER_HELD,
        ),
        owner_gate=owner_gate,
        risk_tags=risk_tags_for(classification),
    )
