"""IV routing: implementer != verifier when certification is required."""

from __future__ import annotations

from project_atlas.orchestration.autonomy.adversarial import requires_adversarial_review
from project_atlas.orchestration.autonomy.models import (
    AgentCapability,
    AgentRecord,
    IvState,
    WorkNode,
)


class IvRoutingError(ValueError):
    code = "IV_ROUTING_ERROR"


class IvAssignment:
    __slots__ = ("adversarial", "state", "verifier_id")

    def __init__(self, verifier_id: str, adversarial: bool, state: IvState) -> None:
        self.verifier_id = verifier_id
        self.adversarial = adversarial
        self.state = state


def route_iv(
    node: WorkNode,
    *,
    implementer_id: str,
    agents: tuple[AgentRecord, ...],
) -> IvAssignment:
    if not node.iv_requirements.certification_required:
        return IvAssignment(implementer_id, False, IvState.NOT_REQUIRED)
    adversarial = node.iv_requirements.adversarial_required or requires_adversarial_review(
        node.risk_tags
    )
    required = [AgentCapability.VERIFY]
    if adversarial:
        required.append(AgentCapability.ADVERSARIAL_REVIEW)
    for agent in agents:
        if not agent.available:
            continue
        if agent.agent_id == implementer_id:
            continue
        have = frozenset(agent.capabilities)
        if all(item in have for item in required):
            return IvAssignment(agent.agent_id, adversarial, IvState.ROUTED)
    raise IvRoutingError("no independent verifier with required capabilities")
