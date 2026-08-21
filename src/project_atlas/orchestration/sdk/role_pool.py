"""Role pools: never mix incompatible independence lineages."""

from __future__ import annotations

from dataclasses import dataclass, field

from project_atlas.orchestration.sdk.models import (
    INDEPENDENT_ROLES,
    MUTATING_ROLES,
    AgentRecord,
    AgentRole,
    AgentRuntime,
    AgentState,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry


@dataclass
class AgentRolePool:
    """Capacity-aware assignment across isolated role pools."""

    registry: CloudAgentRegistry
    max_per_role: dict[AgentRole, int] = field(default_factory=dict)
    default_max: int = 4

    def capacity_for(self, role: AgentRole) -> int:
        return self.max_per_role.get(role, self.default_max)

    def active_count(self, role: AgentRole) -> int:
        return len(self.registry.list_active(role=role))

    def has_capacity(self, role: AgentRole) -> bool:
        return self.active_count(role) < self.capacity_for(role)

    def select_followup_agent(
        self,
        *,
        role: AgentRole,
        package_id: str,
        preferred_agent_id: str | None = None,
    ) -> AgentRecord | None:
        """Reuse same-role/same-package agent when independence rules permit."""
        if preferred_agent_id:
            existing = self.registry.get(preferred_agent_id)
            if existing is None or existing.archived:
                raise SdkRuntimeError("preferred agent missing", code="UNKNOWN_AGENT")
            if existing.role != role:
                raise SdkRuntimeError("role change requires new agent", code="ROLE_CHANGE")
            if existing.package_id != package_id:
                raise SdkRuntimeError(
                    "package isolation requires new agent",
                    code="PACKAGE_ISOLATION",
                )
            if existing.state == AgentState.BUSY:
                return existing  # caller reconciles AgentBusy
            return existing
        for agent in self.registry.list_active(role=role):
            if agent.package_id == package_id and agent.state == AgentState.IDLE:
                return agent
        return None

    def require_new_agent(self, role: AgentRole, *, reason: str) -> None:
        if role in INDEPENDENT_ROLES and reason == "followup_from_implementer":
            raise SdkRuntimeError(
                "independence roles cannot reuse implementer lineage",
                code="INDEPENDENCE_REQUIRED",
            )
        if role in MUTATING_ROLES and reason == "followup_from_verifier":
            raise SdkRuntimeError(
                "mutating roles cannot reuse verifier lineage",
                code="INDEPENDENCE_REQUIRED",
            )

    def preferred_runtime(self, role: AgentRole) -> AgentRuntime:
        if role == AgentRole.LOCAL_AUTHENTIC_WORKER:
            return AgentRuntime.LOCAL
        return AgentRuntime.CLOUD
