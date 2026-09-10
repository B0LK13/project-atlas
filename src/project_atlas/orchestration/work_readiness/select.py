"""Deterministic next-task selection. No model scores; missing estimates ≠ 0."""

from __future__ import annotations

from dataclasses import dataclass

from project_atlas.orchestration.work_readiness.models import (
    SelectionBucket,
    WorkItemProjection,
    WorkQueueReport,
)


@dataclass(frozen=True)
class SelectionResult:
    """Result of select_next. Never invents filler work."""

    selected_task_id: str | None
    bucket: SelectionBucket | None
    rank_key: tuple[object, ...] | None
    explanation: tuple[str, ...]
    offerable: tuple[str, ...]
    awaiting_authorization: tuple[str, ...]
    blocked: tuple[str, ...]
    empty_reasons: tuple[str, ...]


def _rank_key(item: WorkItemProjection, impact_by_task: dict[str, int]) -> tuple[object, ...]:
    """Lower tuple wins.

    Criteria (documented + testable):
    1. Higher backlog priority first (missing priority sorts *after* known, not as 0).
    2. Higher dependency-impact first (how many peers share a cause this task unblocks).
    3. Lexicographic task_id tie-breaker for stability.
    """
    # Missing priority must not silently count as zero → use a large sentinel for "missing".
    priority_rank = -(item.priority) if item.priority is not None else 10_001
    impact = impact_by_task.get(item.task_id, 0)
    return (priority_rank, -impact, item.task_id)


def _impact_map(report: WorkQueueReport) -> dict[str, int]:
    """Dependency impact: max shared-blocker impact touching this task."""
    out: dict[str, int] = {}
    for item in report.items:
        best = 0
        for b in item.blockers:
            if b.dependency_impact is not None:
                best = max(best, b.dependency_impact)
        # For offerable items, estimate how many blocked peers list deps on this task_id.
        dependents = 0
        for other in report.items:
            if other.task_id == item.task_id:
                continue
            for dep in other.dependencies:
                if dep.dependency_id == item.task_id:
                    dependents += 1
        out[item.task_id] = max(best, dependents)
    return out


def select_next(
    report: WorkQueueReport,
    *,
    runtime_profile: str | None = None,
) -> SelectionResult:
    """Pick the next offerable task with an explainable rank key."""
    impact = _impact_map(report)
    candidates = [
        item for item in report.items if item.bucket is SelectionBucket.OFFERABLE_TO_DISPATCHER
    ]
    if runtime_profile:
        filtered = [
            c
            for c in candidates
            if c.required_adapter == runtime_profile or runtime_profile in c.required_capabilities
        ]
        candidates = filtered

    explanations: list[str] = [
        "hard suitability: OFFERABLE_TO_DISPATCHER only",
        "rank: (-priority if present else missing-last, -dependency_impact, task_id)",
        "missing priority does not count as zero",
        "no model score / success prediction used",
    ]
    if runtime_profile:
        explanations.append(f"runtime_profile filter={runtime_profile!r}")

    if not candidates:
        reasons = list(report.empty_queue_reasons) or [
            "no offerable tasks under observed conditions"
        ]
        if runtime_profile and report.offerable:
            reasons.append(
                f"offerable tasks exist but none match runtime_profile={runtime_profile!r}"
            )
        return SelectionResult(
            selected_task_id=None,
            bucket=None,
            rank_key=None,
            explanation=tuple(explanations + [f"empty: {r}" for r in reasons]),
            offerable=report.offerable,
            awaiting_authorization=report.awaiting_authorization,
            blocked=report.blocked,
            empty_reasons=tuple(reasons),
        )

    ordered = sorted(candidates, key=lambda i: _rank_key(i, impact))
    winner = ordered[0]
    key = _rank_key(winner, impact)
    explanations.append(
        f"selected={winner.task_id} rank_key={key!r} "
        f"priority={winner.priority!r} impact={impact.get(winner.task_id, 0)}"
    )
    explanations.extend(winner.selection_explanation)
    return SelectionResult(
        selected_task_id=winner.task_id,
        bucket=winner.bucket,
        rank_key=key,
        explanation=tuple(explanations),
        offerable=report.offerable,
        awaiting_authorization=report.awaiting_authorization,
        blocked=report.blocked,
        empty_reasons=(),
    )


def explain_item(report: WorkQueueReport, task_id: str) -> tuple[str, ...]:
    """Human/machine explanation for one task's suitability."""
    item = next((i for i in report.items if i.task_id == task_id), None)
    if item is None:
        return (f"task_id={task_id} not present in projection",)
    lines = [
        f"task_id={item.task_id}",
        f"bucket={item.bucket.value}",
        (
            f"contract_id={item.contract_id} digest={item.contract_digest} "
            f"valid={item.contract_valid.value}"
        ),
        f"axes={item.axes.model_dump(mode='json')}",
    ]
    lines.extend(item.selection_explanation)
    for b in item.blockers:
        lines.append(
            f"blocker {b.code.value} object={b.object_ref} next={b.next_step} "
            f"role={b.responsible_role} impact={b.dependency_impact}"
        )
    return tuple(lines)
