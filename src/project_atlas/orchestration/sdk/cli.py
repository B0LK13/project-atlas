"""CLI entrypoints for the durable SDK supervisor."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path

from project_atlas.orchestration.sdk.auth import discover_auth, record_auth_prerequisite
from project_atlas.orchestration.sdk.backend import CursorSDKExecutionBackend
from project_atlas.orchestration.sdk.ci_observer import CANONICAL_PR
from project_atlas.orchestration.sdk.live_dag import LiveDagController
from project_atlas.orchestration.sdk.local_proof import run_local_sdk_proof
from project_atlas.orchestration.sdk.models import PRIMARY_BACKEND, STOP_HOOK_BACKEND
from project_atlas.orchestration.sdk.supervisor import (
    DurableAtlasSupervisor,
    status_dict,
)

EXIT_OK = 0
EXIT_ERROR = 1


def run_auth_status(*, root: Path) -> tuple[dict[str, object], int]:
    discovery = discover_auth()
    newly = record_auth_prerequisite(root, discovery)
    payload = discovery.model_dump(mode="json")
    payload["primary_continuation_backend"] = PRIMARY_BACKEND
    payload["stop_hook_backend"] = STOP_HOOK_BACKEND
    payload["prerequisite_recorded"] = newly
    payload["owner_action_required_now"] = False
    payload["merge_authorized"] = False
    payload["execution_authorized"] = False
    return payload, EXIT_OK


def run_governor_service(
    *,
    root: Path,
    max_cycles: int | None = None,
    poll_interval_sec: float = 2.0,
    use_fake: bool = False,
    candidate_head: str | None = None,
    pr_number: int = CANONICAL_PR,
) -> tuple[dict[str, object], int]:
    """Persistent host process. Returns only after stop/max_cycles."""
    from project_atlas.orchestration.autonomy.continuation_broker import (
        BrokerError,
        supersede_legacy_hook_successor,
    )
    from project_atlas.orchestration.sdk.host import write_host_identity
    from project_atlas.orchestration.sdk.windows_bridge import (
        apply_windows_discovery_patch,
    )

    apply_windows_discovery_patch()

    with contextlib.suppress(BrokerError):
        supersede_legacy_hook_successor(root, cycle_id="D081-CI-0")

    supervisor = DurableAtlasSupervisor.create(
        root,
        use_fake=use_fake,
        poll_interval_sec=poll_interval_sec,
        max_cycles=max_cycles if max_cycles is not None else None,
    )
    real_sdk = isinstance(supervisor.backend, CursorSDKExecutionBackend) and not use_fake
    controller = LiveDagController(
        root,
        pr_number=pr_number,
        supervisor_pid=os.getpid(),
        real_sdk_backend=real_sdk,
    )
    if candidate_head and controller.state.bound_head is None:
        controller.state.bound_head = candidate_head

    async def _ready() -> list[object]:
        _state, items = controller.tick()
        return list(items)

    write_host_identity(
        root,
        pid=os.getpid(),
        backend=(
            "LOCAL_SDK"
            if real_sdk
            else "FAKE_TEST_ONLY"
            if use_fake
            else "OBSERVER"
        ),
        package_head=controller.state.bound_head or candidate_head or "unknown",
        worktree=str(root),
    )
    # Immediate reconcile so a stale launch-time --candidate-head cannot freeze the DAG.
    controller.tick()
    if real_sdk:
        run_local_sdk_proof(root)
    original_cycle = supervisor.schedule_cycle

    async def _cycle_and_mark() -> object:
        result = await original_cycle()
        for run in result.started:
            if run.node_id:
                controller.mark_dispatched(run.node_id)
        return result

    supervisor.schedule_cycle = _cycle_and_mark  # type: ignore[method-assign,assignment]
    supervisor.ready_provider = _ready  # type: ignore[assignment]
    supervisor.status.next_machine_action = "MONITOR_EXACT_HEAD_CI"
    status = asyncio.run(supervisor.run_forever())
    payload = status_dict(status)
    payload["bound_head"] = controller.state.bound_head
    payload["bound_tree"] = controller.state.bound_tree
    payload["ci_run_id"] = controller.state.ci_run_id
    payload["ci_status"] = controller.state.ci_status
    payload["material_transitions"] = controller.state.material_transitions
    payload["target_move_detected"] = controller.state.target_move_detected
    return payload, EXIT_OK


def run_governor_service_once(
    *, root: Path, use_fake: bool = True
) -> tuple[dict[str, object], int]:
    """Single schedule cycle — useful for tests and dry-run."""
    supervisor = DurableAtlasSupervisor.create(root, use_fake=use_fake, max_cycles=1)

    async def _once() -> dict[str, object]:
        await supervisor.startup_recovery()
        await supervisor.schedule_cycle()
        return status_dict(supervisor.status)

    return asyncio.run(_once()), EXIT_OK


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))
