"""FIXTURE session for the durable-continuation acceptance tests.

LABEL: FIXTURE. Not a model and not an agent runtime. It exists so a real
process can write a real envelope and a real sealed checkpoint, publish its own
pid and start identity, and then be killed for real -- which is the only way to
establish "a replacement session resumes from durable state" rather than
simulating it in the test's own interpreter.

Argv: <state-root> <task-id> <replay-class> <mode> [last-completed-step]

Modes:
  block            write the checkpoint, announce readiness, then sleep until
                   killed. The parent sends SIGKILL, so nothing after the
                   announcement ever runs and no cleanup can tidy up after it.
  uncertain-block  same, plus an external-effect receipt with confirmed=None
                   written BEFORE the announcement -- the record that makes an
                   interrupted effect visible instead of invisible.
  complete         write a terminal COMPLETED checkpoint and exit 0.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from project_atlas.orchestration.program.adapters.base import process_start_identity
from project_atlas.orchestration.program.continuation import (
    CheckpointPolicy,
    ContinuationCheckpoint,
    ExecutionIdentity,
    ExternalEffectReceipt,
    LeaseSnapshot,
    ReplayClass,
    TaskBudgets,
    TaskEnvelope,
    load_envelope,
    persist_checkpoint,
    persist_envelope,
    utc_now,
)
from project_atlas.orchestration.program.models import AcceptanceCheck, AcceptanceKind

READY_MARK = "FIXTURE_SESSION_READY"


def _envelope(root: Path, task_id: str, replay: ReplayClass) -> TaskEnvelope:
    existing = load_envelope(root, task_id)
    if existing is not None:
        return existing
    steps = ("PLAN", "APPLY", "VERIFY") if replay is ReplayClass.CHECKPOINT_RESUMABLE else ()
    envelope = TaskEnvelope(
        task_id=task_id,
        objective=f"fixture task {task_id}",
        capabilities_required=("IMPLEMENT",),
        candidate_head="a" * 40,
        candidate_tree="b" * 40,
        allowed_paths=(f"{task_id}.txt",),
        acceptance=(
            AcceptanceCheck(
                check_id=f"{task_id}-out",
                kind=AcceptanceKind.FILE_EXISTS,
                description=f"{task_id}.txt exists",
                path=f"{task_id}.txt",
            ),
        ),
        budgets=TaskBudgets(max_attempts=3, max_launches=3, max_wall_seconds=600),
        checkpoint_policy=CheckpointPolicy(steps=steps),
        replay_class=replay,
        approved_by="fixture-operator",
        approval_reference="tests/unit/_continuation_fixture_session.py",
        profile_ref="impl",
        worker_id="fixture-worker-01",
        program_id="fixture-program",
    )
    persist_envelope(root, envelope)
    return envelope


def main() -> int:
    root = Path(sys.argv[1])
    task_id = sys.argv[2]
    replay = ReplayClass(sys.argv[3])
    mode = sys.argv[4]
    last_step = sys.argv[5] if len(sys.argv) > 5 else None

    envelope = _envelope(root, task_id, replay)
    pid = os.getpid()
    identity = process_start_identity(pid) or "unknown"
    terminal = mode == "complete"
    effects: tuple[ExternalEffectReceipt, ...] = ()
    if mode == "uncertain-block":
        effects = (
            ExternalEffectReceipt(
                receipt_id=f"{task_id}-effect-1",
                kind="OUTBOUND_WRITE",
                description=(
                    "a mutation was begun outside this machine's observation "
                    "and its outcome was never established"
                ),
                recorded_at=utc_now(),
                confirmed=None,
            ),
        )

    checkpoint = ContinuationCheckpoint(
        identity=ExecutionIdentity(
            task_id=task_id,
            worker_id=envelope.worker_id,
            session_id=f"fixture.{pid}",
            attempt_id=f"{task_id}.attempt.1",
        ),
        envelope_digest=envelope.digest(),
        program_id=envelope.program_id,
        sequence=1,
        last_completed_step=last_step,
        next_action=(
            f"task {task_id} recorded complete"
            if terminal
            else f"continue task {task_id}"
        ),
        worktree_path=str(root),
        git_head="a" * 40,
        git_tree="b" * 40,
        process_pid=pid,
        process_start_identity=identity,
        lease=LeaseSnapshot(
            lease_id=f"{task_id}-lease",
            holder_worker_id=envelope.worker_id,
            holder_session_id=f"fixture.{pid}",
            granted_at=utc_now(),
            # Deliberately far in the future: a successor must be blocked by an
            # unexpired lease even when its holder is dead, until the identity
            # check establishes the holder is gone.
            expires_at="2099-01-01T00:00:00.000Z",
        ),
        external_effects=effects,
        replay_class=ReplayClass.COMPLETED if terminal else replay,
        terminal=terminal,
    )
    persist_checkpoint(root, checkpoint)

    if terminal:
        (root / f"{task_id}.done").write_text("done\n", encoding="utf-8")
        return 0

    print(f"{READY_MARK} pid={pid}", flush=True)
    while True:
        time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
