"""CLI entrypoints for the durable SDK supervisor."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from pathlib import Path

from project_atlas.orchestration.sdk.auth import discover_auth, record_auth_prerequisite
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
) -> tuple[dict[str, object], int]:
    """Persistent host process. Returns only after stop/max_cycles."""
    from project_atlas.orchestration.autonomy.continuation_broker import (
        BrokerError,
        supersede_legacy_hook_successor,
    )
    from project_atlas.orchestration.sdk.ci_observer import (
        observe_exact_head_ci,
        persist_observation,
    )
    from project_atlas.orchestration.sdk.host import write_host_identity

    with contextlib.suppress(BrokerError):
        supersede_legacy_hook_successor(root, cycle_id="D081-CI-0")

    observed_head = candidate_head

    async def _ready() -> list[object]:
        if observed_head:
            persist_observation(root, observe_exact_head_ci(head_sha=observed_head))
        return []

    supervisor = DurableAtlasSupervisor.create(
        root,
        use_fake=use_fake,
        poll_interval_sec=poll_interval_sec,
        max_cycles=max_cycles if max_cycles is not None else None,
        ready_provider=_ready,  # type: ignore[arg-type]
    )
    write_host_identity(
        root,
        pid=os.getpid(),
        backend=(
            "CLOUD_SDK"
            if supervisor.auth.cloud_sdk_runtime == "ENABLED"
            else "LOCAL_SDK"
            if supervisor.auth.local_sdk_available == "YES"
            else "OBSERVER"
        ),
        package_head=observed_head or "unknown",
        worktree=str(root),
    )
    supervisor.status.next_machine_action = "MONITOR_EXACT_HEAD_CI"
    status = asyncio.run(supervisor.run_forever())
    return status_dict(status), EXIT_OK


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
