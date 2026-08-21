"""Supervisor restart recovery: high-water first, resume agents, ingest terminals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from project_atlas.orchestration.sdk.backend import ExecutionBackend
from project_atlas.orchestration.sdk.event_log import read_events
from project_atlas.orchestration.sdk.live_dag import load_live_dag
from project_atlas.orchestration.sdk.models import (
    TERMINAL_RUN_STATUSES,
    AgentState,
    RunRecord,
    RunStatus,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.package_registry import load_package_route
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.result_adapter import adapt_run_result
from project_atlas.orchestration.sdk.security_gates import (
    HostHighWater,
    load_high_water,
    reject_host_rollback,
)


@dataclass
class RecoveryReport:
    resumed_agents: list[str]
    ingested_runs: list[str]
    still_active_runs: list[str]
    duplicates_avoided: int
    high_water_validated: bool = False
    safety_stop: bool = False
    merge_authorized: bool = False
    execution_authorized: bool = False


def _validate_loaded_against_high_water(
    *,
    root: Path,
    high_water: HostHighWater,
) -> None:
    """Reject rolled-back live DAG / package route vs trusted high-water."""
    live = load_live_dag(root)
    route = load_package_route(root)
    if live.dag_generation < high_water.dag_generation:
        raise SdkRuntimeError(
            "live dag generation below high-water",
            code="HOST_ROLLBACK_REJECTED",
        )
    if route.dag_generation < high_water.dag_generation:
        raise SdkRuntimeError(
            "package route generation below high-water",
            code="HOST_ROLLBACK_REJECTED",
        )
    if route.registry_revision < high_water.registry_revision:
        raise SdkRuntimeError(
            "package registry revision below high-water",
            code="HOST_ROLLBACK_REJECTED",
        )
    if live.material_transitions < high_water.event_sequence:
        # Cross-check: rolled-back high-water + rolled-back state is caught when
        # event log length (material_transitions) disagrees with high-water.
        proposed = HostHighWater(
            dag_generation=live.dag_generation,
            event_sequence=live.material_transitions,
            registry_revision=route.registry_revision,
            run_attempt=high_water.run_attempt,
            checkpoint_sequence=high_water.checkpoint_sequence,
        )
        reject_host_rollback(current=high_water, proposed=proposed)
    # Dual live-state + high-water rollback: the append-only event log is the
    # witness. Restoring an older consistent pair while leaving newer events
    # must fail closed.
    try:
        events = read_events(root)
    except (OSError, ValueError):
        events = []
    if events:
        max_logged_generation = max(event.dag_generation for event in events)
        if (
            live.dag_generation < max_logged_generation
            or high_water.dag_generation < max_logged_generation
        ):
            raise SdkRuntimeError(
                "event log generation ahead of live/high-water",
                code="HOST_ROLLBACK_REJECTED",
            )


async def recover_runtime(
    *,
    backend: ExecutionBackend,
    agents: CloudAgentRegistry,
    runs: RunRegistry,
    root: Path | None = None,
) -> RecoveryReport:
    """On Atlas supervisor startup: load high-water, then registries, reconcile."""
    high_water_ok = False
    if root is not None:
        high_water = load_high_water(root)
        try:
            _validate_loaded_against_high_water(root=root, high_water=high_water)
            high_water_ok = True
        except SdkRuntimeError:
            return RecoveryReport(
                resumed_agents=[],
                ingested_runs=[],
                still_active_runs=[],
                duplicates_avoided=0,
                high_water_validated=False,
                safety_stop=True,
            )

    resumed: list[str] = []
    ingested: list[str] = []
    active: list[str] = []
    duplicates = 0

    for agent in agents.list_active():
        await backend.resume_agent(agent.agent_id)
        resumed.append(agent.agent_id)

    for run in runs.nonterminal():
        status = await backend.get_run_status(run.run_id, agent_id=run.agent_id)
        if status in TERMINAL_RUN_STATUSES:
            try:
                updated = await backend.wait_run(run.run_id, agent_id=run.agent_id)
            except Exception:
                ingested_result = adapt_run_result(
                    run_id=run.run_id, agent_id=run.agent_id, status=status
                )
                updated = runs.mark_terminal(
                    run.run_id,
                    status=ingested_result.status,
                    result_digest=ingested_result.result_digest,
                )
            ingested.append(updated.run_id)
            stored = agents.get(run.agent_id)
            if stored is not None and stored.state == AgentState.BUSY:
                agents.upsert(stored.model_copy(update={"state": AgentState.IDLE}))
        else:
            active.append(run.run_id)

    state = runs.load()
    if len(state.by_idempotency) < len(state.runs):
        duplicates = len(state.runs) - len(state.by_idempotency)

    return RecoveryReport(
        resumed_agents=resumed,
        ingested_runs=ingested,
        still_active_runs=active,
        duplicates_avoided=duplicates,
        high_water_validated=high_water_ok,
    )


async def ingest_if_terminal(
    *,
    backend: ExecutionBackend,
    runs: RunRegistry,
    run: RunRecord,
) -> RunRecord | None:
    status = await backend.get_run_status(run.run_id, agent_id=run.agent_id)
    if status not in TERMINAL_RUN_STATUSES and status != RunStatus.UNKNOWN:
        return None
    if status == RunStatus.UNKNOWN:
        return None
    return await backend.wait_run(run.run_id, agent_id=run.agent_id)
