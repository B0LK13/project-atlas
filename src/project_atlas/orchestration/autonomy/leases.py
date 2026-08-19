"""Agent lease model. No autonomous scope expansion."""

from __future__ import annotations

from project_atlas.orchestration.autonomy.models import (
    AgentCapability,
    AgentLease,
    AgentRecord,
    NodeState,
    WorkNode,
)


class LeaseError(ValueError):
    code = "LEASE_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ScopeExpansionError(LeaseError):
    code = "SCOPE_EXPANSION_FORBIDDEN"


def _has_capabilities(agent: AgentRecord, required: tuple[AgentCapability, ...]) -> bool:
    have = frozenset(agent.capabilities)
    return all(item in have for item in required)


def grant_lease(
    *,
    lease_id: str,
    agent: AgentRecord,
    node: WorkNode,
    branch: str,
    worktree: str,
    sequence: int,
    authorized_paths: tuple[str, ...] | None = None,
    forbidden_paths: tuple[str, ...] | None = None,
) -> AgentLease:
    if not agent.available:
        raise LeaseError("agent is not available", code="AGENT_UNAVAILABLE")
    if not _has_capabilities(agent, node.agent_capabilities_required):
        raise LeaseError("agent lacks required capabilities", code="CAPABILITY_MISMATCH")
    if node.state != NodeState.READY:
        raise LeaseError("only READY nodes may be leased", code="NODE_NOT_READY")
    paths = authorized_paths if authorized_paths is not None else node.mutation_surface.paths
    forbidden = forbidden_paths if forbidden_paths is not None else ("main", "projects")
    return AgentLease(
        lease_id=lease_id,
        agent_id=agent.agent_id,
        package_id=node.package_id,
        branch=branch,
        worktree=worktree,
        base_pin=node.base_pin,
        authorized_paths=paths,
        forbidden_paths=forbidden,
        capabilities=node.agent_capabilities_required,
        start_state=NodeState.READY,
        expected_output="EVIDENCE_BUNDLE",
        expiry_or_terminal_condition="UNTIL_NODE_TERMINAL",
        active=True,
        sequence=sequence,
    )


def expand_lease(_lease: AgentLease) -> None:
    """Autonomous scope expansion is forbidden. Governor reassignment required."""
    raise ScopeExpansionError("lease scope expansion requires governor reassignment")


def release_lease(lease: AgentLease) -> AgentLease:
    return lease.model_copy(update={"active": False})
