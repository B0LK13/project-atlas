"""Compact capacity view. Does not raise concurrency/budget/launch limits."""

from __future__ import annotations

from dataclasses import dataclass

from project_atlas.orchestration.work_readiness.adapters import EnrollmentPort
from project_atlas.orchestration.work_readiness.models import SelectionBucket, WorkQueueReport
from project_atlas.orchestration.work_readiness.project import _paths_overlap


@dataclass(frozen=True)
class CapacityView:
    """Read-only assignment picture for operators."""

    profile_matches: dict[str, tuple[str, ...]]
    conflict_pairs: tuple[tuple[str, str], ...]
    independent_pairs: tuple[tuple[str, str], ...]
    flow_limits: tuple[str, ...]
    conflict_check: str
    raises_limits: bool = False


def capacity_view(report: WorkQueueReport, enrollment: EnrollmentPort) -> CapacityView:
    prepared = [
        i
        for i in report.items
        if i.bucket
        in (
            SelectionBucket.OFFERABLE_TO_DISPATCHER,
            SelectionBucket.CONTENT_READY_AWAITING_AUTHORIZATION,
        )
    ]
    agents = enrollment.agents()
    profiles: dict[str, list[str]] = {}
    for agent in agents:
        if agent.status != "ACTIVE":
            continue
        key = f"{agent.adapter}:{agent.agent_id}"
        matches = [
            i.task_id
            for i in prepared
            if (i.required_adapter is None or i.required_adapter == agent.adapter)
            and (
                not i.required_capabilities
                or set(i.required_capabilities).issubset(set(agent.capabilities))
            )
        ]
        profiles[key] = matches

    conflicts: list[tuple[str, str]] = []
    independent: list[tuple[str, str]] = []
    for i, left in enumerate(prepared):
        for right in prepared[i + 1 :]:
            pair = tuple(sorted((left.task_id, right.task_id)))
            if _paths_overlap(left.mutation_paths, right.mutation_paths):
                conflicts.append(pair)  # type: ignore[arg-type]
            else:
                independent.append(pair)  # type: ignore[arg-type]

    flow: list[str] = []
    if report.awaiting_authorization:
        flow.append(
            f"owner/launch auth gates {len(report.awaiting_authorization)} prepared task(s)"
        )
    review_wait = [
        i.task_id
        for i in report.items
        if any(b.code.value == "AWAITING_INDEPENDENT_REVIEW" for b in i.blockers)
    ]
    if review_wait:
        flow.append(f"independent review capacity gates {len(review_wait)} task(s)")
    suspended = [a.agent_id for a in agents if a.status == "SUSPENDED"]
    if suspended:
        flow.append(f"suspended runtimes (not free capacity): {', '.join(suspended)}")

    return CapacityView(
        profile_matches={k: tuple(v) for k, v in sorted(profiles.items())},
        conflict_pairs=tuple(sorted(conflicts)),
        independent_pairs=tuple(sorted(independent)),
        flow_limits=tuple(flow),
        conflict_check="path-set + prefix (autonomy SURFACE_OVERLAP_GATE aligned)",
        raises_limits=False,
    )
