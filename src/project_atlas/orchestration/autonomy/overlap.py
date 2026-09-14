"""SURFACE_OVERLAP_GATE — refuse unsafe parallel mutation."""

from __future__ import annotations

from project_atlas.orchestration.autonomy.models import (
    NodeState,
    OverlapState,
    WorkNode,
)

_ACTIVE_PARALLEL_STATES: frozenset[NodeState] = frozenset(
    {
        NodeState.LEASED,
        NodeState.ACTIVE,
        NodeState.VERIFYING,
        NodeState.REMEDIATING,
    }
)


def normalize_rel_path(path: str) -> str:
    """Collapse empty and ``.`` segments. Does not resolve ``..`` or follow links."""
    parts = [part for part in path.replace("\\", "/").split("/") if part not in ("", ".")]
    return "/".join(parts)


def _paths_overlap(left: set[str], right: set[str]) -> bool:
    """Exact intersection or prefix containment.

    ``src`` overlaps ``src/child.txt``. Sibling names such as ``src/exp`` and
    ``src/exporter`` do not: containment requires a path-separator boundary.
    ``src/.`` / ``src/./child.txt`` normalize to the same identity as ``src``
    / ``src/child.txt`` so a dotted cwd cannot bypass the gate.
    Aligned with ``work_readiness.project._paths_overlap``.
    """
    left_n = {normalize_rel_path(item) or item for item in left}
    right_n = {normalize_rel_path(item) or item for item in right}
    if left_n & right_n:
        return True
    for lp in left_n:
        for rp in right_n:
            if lp.startswith(rp.rstrip("/") + "/") or rp.startswith(lp.rstrip("/") + "/"):
                return True
    return False


def surfaces_overlap(left: WorkNode, right: WorkNode) -> bool:
    if left.mutation_surface.surface_id == right.mutation_surface.surface_id:
        return True
    if left.mutation_surface.semantic == right.mutation_surface.semantic:
        return True
    return _paths_overlap(set(left.mutation_surface.paths), set(right.mutation_surface.paths))


def overlap_gate(nodes: tuple[WorkNode, ...]) -> OverlapState:
    """PARALLEL_EXECUTION = NO unless surfaces are proven disjoint."""
    active = [node for node in nodes if node.state in _ACTIVE_PARALLEL_STATES]
    conflicts: list[str] = []
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if surfaces_overlap(left, right):
                conflicts.append(left.mutation_surface.surface_id)
                conflicts.append(right.mutation_surface.surface_id)
    unique = tuple(sorted(set(conflicts)))
    if unique:
        return OverlapState(
            parallel_execution=False,
            conflict_surfaces=unique,
            reason="SURFACE_OVERLAP_UNSAFE",
        )
    return OverlapState(
        parallel_execution=len(active) > 1,
        conflict_surfaces=(),
        reason="SURFACES_DISJOINT" if len(active) > 1 else "SINGLE_OR_NO_ACTIVE_LANE",
    )


def would_overlap(existing: tuple[WorkNode, ...], candidate: WorkNode) -> bool:
    active = [node for node in existing if node.state in _ACTIVE_PARALLEL_STATES]
    return any(surfaces_overlap(node, candidate) for node in active)
