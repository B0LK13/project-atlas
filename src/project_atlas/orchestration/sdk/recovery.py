"""Supervisor restart recovery: resume agents, ingest terminals, never duplicate."""

from __future__ import annotations

from dataclasses import dataclass

from project_atlas.orchestration.sdk.backend import ExecutionBackend
from project_atlas.orchestration.sdk.models import (
    TERMINAL_RUN_STATUSES,
    AgentState,
    RunRecord,
    RunStatus,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.result_adapter import adapt_run_result


@dataclass
class RecoveryReport:
    resumed_agents: list[str]
    ingested_runs: list[str]
    still_active_runs: list[str]
    duplicates_avoided: int
    merge_authorized: bool = False
    execution_authorized: bool = False


async def recover_runtime(
    *,
    backend: ExecutionBackend,
    agents: CloudAgentRegistry,
    runs: RunRegistry,
) -> RecoveryReport:
    """On Atlas supervisor startup: load registries and reconcile nonterminal runs."""
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
            # Prefer waiting to capture result digest when possible.
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

    # Idempotency map integrity: count collisions already prevented by registry.
    state = runs.load()
    if len(state.by_idempotency) < len(state.runs):
        duplicates = len(state.runs) - len(state.by_idempotency)

    return RecoveryReport(
        resumed_agents=resumed,
        ingested_runs=ingested,
        still_active_runs=active,
        duplicates_avoided=duplicates,
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
