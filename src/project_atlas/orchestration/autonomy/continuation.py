"""Autonomous continuation policy. Does not auto-dispatch 001D hops."""

from __future__ import annotations

from project_atlas.orchestration.autonomy.models import (
    NodeState,
    StopReason,
    WorkNode,
)
from project_atlas.orchestration.autonomy.overlap import would_overlap

_RUNNABLE = frozenset({NodeState.READY})
_BLOCKING = frozenset({NodeState.BLOCKED})
_OWNER = frozenset({NodeState.OWNER_HELD, NodeState.MERGE_ELIGIBLE})


class ContinuationDecision:
    __slots__ = ("next_package_id", "stop_reason")

    def __init__(self, next_package_id: str | None, stop_reason: StopReason | None) -> None:
        self.next_package_id = next_package_id
        self.stop_reason = stop_reason


def select_next(
    nodes: tuple[WorkNode, ...],
    *,
    hard_blockers: tuple[str, ...] = (),
    resource_exhausted: bool = False,
) -> ContinuationDecision:
    """Select one READY node or stop. Never selects owner-gated merge work."""
    if hard_blockers:
        return ContinuationDecision(None, StopReason.HARD_BLOCKER)
    if resource_exhausted:
        return ContinuationDecision(None, StopReason.RESOURCE_BOUNDARY)
    owner_held = [node for node in nodes if node.state in _OWNER and node.owner_gate is not None]
    if owner_held and not any(node.state in _RUNNABLE for node in nodes):
        return ContinuationDecision(None, StopReason.OWNER_GATE)
    blocked = [node for node in nodes if node.state in _BLOCKING]
    if blocked and not any(node.state in _RUNNABLE for node in nodes):
        return ContinuationDecision(None, StopReason.HARD_BLOCKER)
    ready = [node for node in nodes if node.state in _RUNNABLE]
    if not ready:
        return ContinuationDecision(None, StopReason.NO_ELIGIBLE_WORK)
    for node in ready:
        if node.owner_gate is not None and node.state != NodeState.READY:
            continue
        if would_overlap(nodes, node):
            continue
        deps_ok = all(
            any(other.package_id == dep and other.state in {NodeState.CERTIFIED, NodeState.CLOSED}
                for other in nodes)
            or dep == node.package_id
            for dep in node.dependencies
        )
        if node.dependencies and not deps_ok:
            continue
        return ContinuationDecision(node.package_id, None)
    if any(node.owner_gate is not None for node in nodes if node.state in _OWNER):
        return ContinuationDecision(None, StopReason.OWNER_GATE)
    return ContinuationDecision(None, StopReason.NO_ELIGIBLE_WORK)
