"""AS-MISSION-VERTICAL-SLICE-001, RECOVERY -- UI closure, worker
interruption, stale ownership and an uncertain external-operation result
must never silently lose progress, duplicate an effect, or resume an
unauthorized write. Ambiguous outcomes are reconciled, never blindly
retried.

Two genuinely different situations, kept genuinely distinct:

  UI RECONNECTION -- the worker (the process that owns the workspace
    lease) is still alive. A reader closing and reopening a view onto
    this run changes nothing about the run itself; it just re-observes
    current state. `reconcile_mission_run()` reports `STILL_RUNNING` and
    touches nothing.

  WORKER RECOVERY -- the worker died (the lease is no longer held). What
    happened depends entirely on which checkpoint state it died in:
    `STARTED` (adapter never invoked -- nothing external happened, safe
    to retry as a NEW run), `ADAPTER_INVOKED` (the adapter call was made
    but no confirmed outcome was ever recorded -- genuinely UNCERTAIN,
    the external effect may or may not have landed, never silently
    retried), or `ADAPTER_CONFIRMED`/`ADAPTER_FAILED` (the outcome WAS
    recorded before death -- known, not ambiguous, even though `COMPLETE`
    and the lease release never happened).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from project_atlas.orchestration.mission.execution import MissionRunCheckpoint, load_checkpoint
from project_atlas.orchestration.mission.lease import read_mission_lease_state

ReconciliationOutcome = Literal[
    "NO_RUN_FOUND",
    "STILL_RUNNING",
    "ALREADY_COMPLETE",
    "SAFE_TO_RETRY_NEVER_STARTED_EXTERNAL_EFFECT",
    "KNOWN_OUTCOME_CLEANUP_ONLY",
    "UNCERTAIN_REQUIRES_RECONCILIATION",
]


@dataclass(frozen=True)
class ReconciliationResult:
    run_id: str | None
    outcome: ReconciliationOutcome
    detail: str
    safe_to_retry: bool
    checkpoint: MissionRunCheckpoint | None


def reconcile_mission_run(workspace: Path) -> ReconciliationResult:
    """Determine what actually happened to the mission run that last
    touched `workspace`, without disturbing anything -- this function
    never writes."""
    checkpoint = load_checkpoint(workspace)
    if checkpoint is None:
        return ReconciliationResult(
            run_id=None,
            outcome="NO_RUN_FOUND",
            detail="no checkpoint found in this workspace",
            safe_to_retry=True,
            checkpoint=None,
        )

    lease = read_mission_lease_state(workspace)
    if lease.held:
        # The owning process is alive. This is a UI-reconnect situation,
        # not a recovery situation -- do not touch the run.
        return ReconciliationResult(
            run_id=checkpoint.run_id,
            outcome="STILL_RUNNING",
            detail=f"workspace lease held by pid {lease.holder_pid}; run is live",
            safe_to_retry=False,
            checkpoint=checkpoint,
        )

    # The lease is free. Either the run finished cleanly (released its own
    # lease at COMPLETE) or the owning process died before reaching that
    # point. The checkpoint's last recorded state is the only evidence.
    if checkpoint.state == "COMPLETE":
        return ReconciliationResult(
            run_id=checkpoint.run_id,
            outcome="ALREADY_COMPLETE",
            detail="run finished and released its own lease normally",
            safe_to_retry=False,
            checkpoint=checkpoint,
        )
    if checkpoint.state == "STARTED":
        return ReconciliationResult(
            run_id=checkpoint.run_id,
            outcome="SAFE_TO_RETRY_NEVER_STARTED_EXTERNAL_EFFECT",
            detail="worker died before the adapter was invoked -- no external effect to reconcile",
            safe_to_retry=True,
            checkpoint=checkpoint,
        )
    if checkpoint.state in ("ADAPTER_CONFIRMED", "ADAPTER_FAILED"):
        return ReconciliationResult(
            run_id=checkpoint.run_id,
            outcome="KNOWN_OUTCOME_CLEANUP_ONLY",
            detail=(
                f"the adapter's outcome WAS recorded ({checkpoint.state}) before the worker "
                "died reaching COMPLETE -- the outcome is known, not ambiguous; only the final "
                "cleanup step (releasing the lease, which the OS already did on crash) was skipped"
            ),
            safe_to_retry=False,
            checkpoint=checkpoint,
        )
    # checkpoint.state == "ADAPTER_INVOKED": the adapter call was made, but
    # this process died before any confirmed/failed outcome was recorded.
    # Whether the external effect landed is genuinely unknown from this
    # checkpoint alone -- reconciliation (inspecting the workspace/target
    # system for evidence the effect actually happened) must happen before
    # any retry, never an automatic blind retry.
    return ReconciliationResult(
        run_id=checkpoint.run_id,
        outcome="UNCERTAIN_REQUIRES_RECONCILIATION",
        detail=(
            "worker died mid-adapter-invocation with no recorded outcome -- the external effect "
            "may or may not have landed; inspect the workspace for evidence before retrying, "
            "never retry blindly"
        ),
        safe_to_retry=False,
        checkpoint=checkpoint,
    )
