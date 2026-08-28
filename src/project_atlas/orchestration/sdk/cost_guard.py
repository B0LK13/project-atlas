"""Cost / usage tracking. Metrics never become authority."""

from __future__ import annotations

from dataclasses import dataclass, field

from project_atlas.orchestration.sdk.auth import BudgetConfig
from project_atlas.orchestration.sdk.models import AgentRole, SdkRuntimeError
from project_atlas.orchestration.sdk.registries import RunRegistry


@dataclass
class CostGuard:
    """Park optional work when spend thresholds would be exceeded."""

    runs: RunRegistry
    config: BudgetConfig = field(default_factory=BudgetConfig)
    required_roles: set[AgentRole] = field(
        default_factory=lambda: {
            AgentRole.IMPLEMENTER,
            AgentRole.REMEDIATOR,
            AgentRole.INDEPENDENT_VERIFIER,
            AgentRole.SECURITY_REVIEWER,
        }
    )

    def totals(self) -> tuple[int, float]:
        tokens = 0
        cents = 0.0
        for run in self.runs.load().runs.values():
            if run.token_usage_total:
                tokens += run.token_usage_total
            if run.cost_charged_cents:
                cents += float(run.cost_charged_cents)
        return tokens, cents

    def would_exceed(self, *, extra_tokens: int = 0, extra_cents: float = 0.0) -> bool:
        tokens, cents = self.totals()
        if (
            self.config.max_total_tokens is not None
            and tokens + extra_tokens > self.config.max_total_tokens
        ):
            return True
        return (
            self.config.max_charged_cents is not None
            and cents + extra_cents > self.config.max_charged_cents
        )

    def allow_schedule(self, role: AgentRole, *, optional: bool = False) -> bool:
        if not self.would_exceed():
            return True
        if optional and self.config.park_optional_when_exceeded:
            return False
        if role in self.required_roles and not optional:
            # Continue required low/additional-cost work where possible.
            return True
        if optional:
            return False
        raise SdkRuntimeError(
            "budget threshold exceeded for non-required work",
            code="BUDGET_GATE",
        )
