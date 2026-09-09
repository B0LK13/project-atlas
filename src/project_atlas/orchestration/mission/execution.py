"""AS-MISSION-VERTICAL-SLICE-001, DEVELOPMENT/RECOVERY -- the smallest
useful path: mission selection -> isolated workspace -> submitted action
-> diff/test evidence -> checkpoint -> handoff.

Durability follows the pattern the research this mission is built from
cites (LangGraph's thread/store distinction; Temporal's crash-window
reasoning): every state transition that matters is written BEFORE the
external effect it precedes, not after, and a checkpoint that says
"the adapter was invoked" without a subsequent CONFIRMED or FAILED is
reported as UNCERTAIN, never silently resumed as if it never started and
never blindly retried as if it definitely finished -- see `recovery.py`.

Ownership of the workspace is `lease.py`'s job, kept independent of this
module's own checkpoint state, matching `resident_driver`'s split between
LOCK_ATOMICITY and RECEIPT_ATOMICITY: a crash releases the lease
immediately (the OS does that), but the checkpoint on disk is what tells a
recovering reader whether the crashed run's own effect landed.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from project_atlas.orchestration.mission.adapter import AdapterResult, MissionAdapter
from project_atlas.orchestration.mission.context_packet import MissionContextPacket
from project_atlas.orchestration.mission.lease import (
    acquire_mission_lease,
    release_mission_lease,
)

CHECKPOINT_NAME = "mission-run-checkpoint.json"

RunState = Literal[
    "STARTED",
    "ADAPTER_INVOKED",
    "ADAPTER_CONFIRMED",
    "ADAPTER_FAILED",
    "COMPLETE",
]


@dataclass(frozen=True)
class MissionRunCheckpoint:
    run_id: str
    mission_id: str
    workspace: str
    adapter_repr: str
    state: RunState
    created_at: float
    updated_at: float
    owner_pid: int
    idempotency_key: str
    result: dict[str, Any] | None = None


def checkpoint_path(workspace: Path) -> Path:
    return workspace / CHECKPOINT_NAME


def load_checkpoint(workspace: Path) -> MissionRunCheckpoint | None:
    path = checkpoint_path(workspace)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return MissionRunCheckpoint(**data)
    except TypeError:
        return None


def _persist_checkpoint(workspace: Path, checkpoint: MissionRunCheckpoint) -> None:
    """Atomic write: temp file in the same directory, then `os.replace` --
    the established convention across this repository's own writers
    (scaffold.py, resident_driver.py's receipt, etc.)."""
    path = checkpoint_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    payload = json.dumps(asdict(checkpoint), indent=2, sort_keys=True) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


class WorkspaceUnavailableError(Exception):
    """Another live process already owns this workspace's lease."""


@dataclass(frozen=True)
class MissionRunResult:
    run_id: str
    checkpoint: MissionRunCheckpoint
    adapter_result: AdapterResult | None


def start_mission_run(
    *,
    mission_id: str,
    context: MissionContextPacket,
    adapter: MissionAdapter,
    workspace: Path,
    adapter_timeout_sec: float = 30.0,
    run_id: str | None = None,
) -> MissionRunResult:
    """Run one mission through the full path: claim the workspace,
    checkpoint BEFORE invoking the adapter (so a crash mid-invocation is
    detectable, not silently lost), invoke it, checkpoint the outcome,
    release the workspace. Raises `WorkspaceUnavailableError` if another
    live run already owns `workspace` -- this function does not queue or
    wait, matching `acquire_primary_lock`'s own never-blocks contract.
    """
    rid = run_id or uuid.uuid4().hex
    if not acquire_mission_lease(workspace, run_id=rid):
        raise WorkspaceUnavailableError(f"workspace already owned: {workspace}")

    now = time.time()
    idempotency_key = f"{mission_id}:{rid}:{context.base_head}"
    checkpoint = MissionRunCheckpoint(
        run_id=rid,
        mission_id=mission_id,
        workspace=str(workspace),
        adapter_repr=repr(adapter),
        state="STARTED",
        created_at=now,
        updated_at=now,
        owner_pid=os.getpid(),
        idempotency_key=idempotency_key,
        result=None,
    )
    _persist_checkpoint(workspace, checkpoint)

    try:
        # Written BEFORE the external effect, deliberately -- this is the
        # line that makes "crashed mid-adapter-call" distinguishable from
        # "never started" during recovery.
        checkpoint = _advance(checkpoint, "ADAPTER_INVOKED")
        _persist_checkpoint(workspace, checkpoint)

        result = adapter.run(workspace=workspace, timeout_sec=adapter_timeout_sec)

        state: RunState = "ADAPTER_CONFIRMED" if result.ok else "ADAPTER_FAILED"
        checkpoint = _advance(checkpoint, state, result=asdict(result))
        _persist_checkpoint(workspace, checkpoint)

        checkpoint = _advance(checkpoint, "COMPLETE")
        _persist_checkpoint(workspace, checkpoint)
        return MissionRunResult(run_id=rid, checkpoint=checkpoint, adapter_result=result)
    finally:
        release_mission_lease(workspace)


def _advance(
    checkpoint: MissionRunCheckpoint, state: RunState, *, result: dict[str, Any] | None = None
) -> MissionRunCheckpoint:
    return MissionRunCheckpoint(
        run_id=checkpoint.run_id,
        mission_id=checkpoint.mission_id,
        workspace=checkpoint.workspace,
        adapter_repr=checkpoint.adapter_repr,
        state=state,
        created_at=checkpoint.created_at,
        updated_at=time.time(),
        owner_pid=checkpoint.owner_pid,
        idempotency_key=checkpoint.idempotency_key,
        result=result if result is not None else checkpoint.result,
    )
