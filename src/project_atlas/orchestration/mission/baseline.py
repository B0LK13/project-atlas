"""AS-MISSION-VERTICAL-SLICE-001, MEASUREMENT -- a small, honest,
reproducible baseline over representative missions.

Deliberately small (a handful of trials): this reports counts and
measured values with their sample size in view, not manufactured
precision. Percentages and averages over N<10 are misleading without the
denominator beside them, so every summary keeps it. Treat any improvement
claim derived from this as a target to re-measure against, not a proven
result -- consistent with this package's own founding directive.

Failure classes are kept genuinely separate: an adapter that ran and
returned nonzero is an AGENT_FAILURE; a workspace that could not be
claimed, or an adapter that could not even be spawned, is an
INFRA_FAILURE; nothing in this harness currently exercises a policy
refusal path, so that bucket is always reported as 0/0, not omitted.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from project_atlas.orchestration.mission.adapter import MissionAdapter
from project_atlas.orchestration.mission.context_packet import compile_mission_context
from project_atlas.orchestration.mission.execution import (
    WorkspaceUnavailableError,
    start_mission_run,
)

ErrorClass = Literal["NONE", "AGENT_FAILURE", "INFRA_FAILURE", "POLICY_REFUSAL"]


@dataclass(frozen=True)
class MissionSpec:
    mission_id: str
    objective: str
    keywords: list[str]
    adapter: MissionAdapter


@dataclass(frozen=True)
class TrialResult:
    mission_id: str
    time_to_useful_context_sec: float
    context_sources_count: int
    context_approx_tokens: int
    handoff_success: bool
    error_class: ErrorClass
    detail: str


@dataclass(frozen=True)
class BaselineReport:
    trial_count: int
    trials: list[TrialResult]
    handoff_success_count: int
    by_error_class: dict[ErrorClass, int]
    time_to_useful_context_mean_sec: float | None
    time_to_useful_context_stdev_sec: float | None
    owner_interventions_total: int

    def summary_line(self) -> str:
        n = self.trial_count
        return (
            f"N={n} trials; HANDOFF_SUCCESS_RATE={self.handoff_success_count}/{n}; "
            f"by_error_class={dict(self.by_error_class)}; "
            f"TIME_TO_USEFUL_CONTEXT mean="
            f"{self._fmt(self.time_to_useful_context_mean_sec)}s "
            f"stdev={self._fmt(self.time_to_useful_context_stdev_sec)}s (n={n}); "
            f"owner_interventions_total={self.owner_interventions_total} "
            f"(0 expected -- this harness is fully automated)"
        )

    @staticmethod
    def _fmt(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"


def run_baseline(
    repo_root: Path, missions: list[MissionSpec], *, workspace_parent: Path
) -> BaselineReport:
    """Run each mission spec through the real KNOWLEDGE -> DEVELOPMENT
    path once and record what actually happened. Every trial is real: a
    real context compile against real repository documents, a real
    isolated workspace, a real adapter invocation."""
    trials: list[TrialResult] = []
    for spec in missions:
        workspace = workspace_parent / spec.mission_id
        t0 = time.perf_counter()
        try:
            packet = compile_mission_context(
                repo_root,
                mission_id=spec.mission_id,
                objective=spec.objective,
                keywords=spec.keywords,
            )
        except OSError as exc:
            trials.append(
                TrialResult(
                    mission_id=spec.mission_id,
                    time_to_useful_context_sec=time.perf_counter() - t0,
                    context_sources_count=0,
                    context_approx_tokens=0,
                    handoff_success=False,
                    error_class="INFRA_FAILURE",
                    detail=f"context compile failed: {exc}",
                )
            )
            continue
        t_context = time.perf_counter() - t0
        sources_count = len(packet.decisions) + len(packet.backlog_items) + len(
            packet.prior_related_work
        )

        try:
            result = start_mission_run(
                mission_id=spec.mission_id,
                context=packet,
                adapter=spec.adapter,
                workspace=workspace,
                adapter_timeout_sec=30.0,
            )
        except WorkspaceUnavailableError as exc:
            trials.append(
                TrialResult(
                    mission_id=spec.mission_id,
                    time_to_useful_context_sec=t_context,
                    context_sources_count=sources_count,
                    context_approx_tokens=packet.manifest.approx_tokens,
                    handoff_success=False,
                    error_class="INFRA_FAILURE",
                    detail=str(exc),
                )
            )
            continue

        ok = result.checkpoint.state == "COMPLETE" and (
            result.adapter_result is not None and result.adapter_result.ok
        )
        error_class: ErrorClass = "NONE" if ok else "AGENT_FAILURE"
        detail = "" if ok else f"adapter did not confirm success: {result.checkpoint.state}"
        trials.append(
            TrialResult(
                mission_id=spec.mission_id,
                time_to_useful_context_sec=t_context,
                context_sources_count=sources_count,
                context_approx_tokens=packet.manifest.approx_tokens,
                handoff_success=ok,
                error_class=error_class,
                detail=detail,
            )
        )

    context_times = [t.time_to_useful_context_sec for t in trials]
    by_class: dict[ErrorClass, int] = {
        "NONE": 0,
        "AGENT_FAILURE": 0,
        "INFRA_FAILURE": 0,
        "POLICY_REFUSAL": 0,
    }
    for t in trials:
        by_class[t.error_class] += 1

    return BaselineReport(
        trial_count=len(trials),
        trials=trials,
        handoff_success_count=sum(1 for t in trials if t.handoff_success),
        by_error_class=by_class,
        time_to_useful_context_mean_sec=(
            statistics.fmean(context_times) if context_times else None
        ),
        time_to_useful_context_stdev_sec=(
            statistics.stdev(context_times) if len(context_times) >= 2 else None
        ),
        owner_interventions_total=0,
    )
