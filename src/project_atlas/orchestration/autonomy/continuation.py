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
    owner_gated_ready = False
    for node in ready:
        if node.owner_gate is not None:
            # ORCHAUT-010 remediation (2026-08-28): READY means
            # dependency-ready, not owner-authorized. A node can reach
            # READY while still carrying an owner_gate (C-F) tag; the
            # loop must never autonomously select owner-gated work,
            # matching the OWNER_HELD/MERGE_ELIGIBLE handling above for
            # gate A. The prior `node.state != NodeState.READY` guard was
            # dead code here -- every node in `ready` already has
            # state == READY, so it never skipped anything.
            owner_gated_ready = True
            continue
        if would_overlap(nodes, node):
            continue
        # D-PHASE2A-1a independent-IV note: the `or dep == node.package_id`
        # self-dependency carve-out that used to live here is gone --
        # WorkNode.dependencies now rejects a self-reference at the model
        # boundary (models.py's `_deps` validator), so `dep` can never
        # equal `node.package_id`. Leaving the old carve-out in would have
        # been permanently dead code, not a bug, but removing it keeps
        # this function's real behavior legible instead of implying a case
        # that can no longer occur.
        deps_ok = all(
            any(
                other.package_id == dep and other.state in {NodeState.CERTIFIED, NodeState.CLOSED}
                for other in nodes
            )
            for dep in node.dependencies
        )
        if node.dependencies and not deps_ok:
            continue
        return ContinuationDecision(node.package_id, None)
    if owner_gated_ready or any(
        node.owner_gate is not None for node in nodes if node.state in _OWNER
    ):
        return ContinuationDecision(None, StopReason.OWNER_GATE)
    return ContinuationDecision(None, StopReason.NO_ELIGIBLE_WORK)
