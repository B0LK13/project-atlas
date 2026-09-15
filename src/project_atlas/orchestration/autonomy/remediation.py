"""Bounded automatic remediation. Max 3 cycles then BLOCKED."""

from __future__ import annotations

from project_atlas.orchestration.autonomy.models import (
    MAX_AUTONOMOUS_REMEDIATION_CYCLES,
    RetryPolicy,
    WorkNode,
)


class RemediationExhausted(ValueError):
    code = "REMEDIATION_EXHAUSTED"


def can_remediate(node: WorkNode) -> bool:
    return node.retry_policy.cycles_used < node.retry_policy.max_autonomous_cycles


def consume_remediation_cycle(node: WorkNode) -> WorkNode:
    used = node.retry_policy.cycles_used + 1
    if used > MAX_AUTONOMOUS_REMEDIATION_CYCLES:
        raise RemediationExhausted("MAX_AUTONOMOUS_REMEDIATION_CYCLES exceeded")
    policy = RetryPolicy(cycles_used=used)
    return node.model_copy(update={"retry_policy": policy})
