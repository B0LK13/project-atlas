"""ATLAS-DURABLE-AUTONOMOUS-CONTINUATION-001 -- the fourteen mandatory proofs.

Every worker here is a labelled FIXTURE and every model call count is zero.
``FIXTURE_RUN != REAL_RUNTIME_COMPATIBILITY``: these tests establish the
*supervisor and dispatcher's* behaviour under restart, and nothing about
compatibility with a real agent runtime.

Two deliberate choices about method:

**Processes are really killed.** Tests 1-4 and 11 spawn a real interpreter,
wait for it to announce that it has sealed a checkpoint, and ``SIGKILL`` it.
Nothing after the announcement runs, so no ``finally`` can tidy up and no
in-memory state survives. A test that simulated the kill would be a test of
its own simulation.

**The replacement session is a different interpreter.** Reconciliation in
tests 1-3 runs through the CLI in a fresh process, so "does not depend on prior
chat history" is established by there being no prior process at all -- not by
the test declining to look at one.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import resource
import signal
import socket
import stat
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.autonomy.lease_projection import (
    active_rows,
    load_projection,
)
from project_atlas.orchestration.program import approved_queue, decisions, resident
from project_atlas.orchestration.program.blocked_work import (
    handle_blocked_task,
    select_fallback,
)
from project_atlas.orchestration.program.capsule import build_capsule, render_capsule
from project_atlas.orchestration.program.continuation import (
    CAPSULE_MAX_BYTES,
    CheckpointError,
    CheckpointPolicy,
    ConsumedBudget,
    ContinuationCheckpoint,
    EnvelopeError,
    ExecutionIdentity,
    LeaseSnapshot,
    ReplayClass,
    TaskBudgets,
    TaskEnvelope,
    checkpoints_dir,
    list_checkpoints,
    list_envelopes,
    load_checkpoint,
    persist_checkpoint,
    persist_envelope,
    utc_now,
    validate_envelope_for_dispatch,
)
from project_atlas.orchestration.program.decisions import DecisionKind, DecisionStatus
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import (
    AcceptanceCheck,
    AcceptanceKind,
    ProgramStopReason,
    ProgramTask,
)
from project_atlas.orchestration.program.reconciliation import (
    Disposition,
    prior_execution_evidence,
    reconcile_one,
    reconcile_root,
    reconcile_task,
)
from project_atlas.orchestration.program.recovery import Liveness, process_liveness
from project_atlas.orchestration.program.resident import (
    DispatcherState,
    DispatcherStopReason,
    ResidentDispatcher,
    dispatcher_status,
    read_heartbeat,
)
from project_atlas.orchestration.program.store import evidence_dir, launches_dir, state_dir

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")
FIXTURE_SESSION = Path(__file__).with_name("_continuation_fixture_session.py")
READY_MARK = "FIXTURE_SESSION_READY"
CLI = "project_atlas.orchestration.program.cli"
#: The CLI's operational-error exit code (project_atlas.cli: 0 ok, 1 error, 2 usage).
EXIT_ERROR_CODE = 1

#: Every pid this module starts, so the cleanup proof can assert on the exact
#: set rather than on a pattern. R-12: never kill by name, pattern or working
#: directory -- only by a pid this test owns, and only after its identity has
#: been checked.
_OWNED_PIDS: list[int] = []


# --------------------------------------------------------------- utilities


def _profile(agent_id: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "agent_id": agent_id,
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["IMPLEMENT"],
        "env_allowlist": [
            "ATLAS_FIXTURE_MODE",
            "ATLAS_PROGRAM_ATTEMPT",
            "ATLAS_PROGRAM_TASK",
        ],
        "adapter_options": {"argv": [sys.executable, str(FIXTURE_WORKER)]},
    }
    body.update(overrides)
    return body


def _task(task_id: str, *, profile_ref: str = "impl", **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "task_id": task_id,
        "title": f"task {task_id}",
        "instruction": "do it",
        "profile_ref": profile_ref,
        "mutation_paths": [f"{task_id}.txt"],
        "surface_id": task_id,
        "surface_semantic": task_id.upper().replace("-", "_"),
        "capabilities_required": ["IMPLEMENT"],
        "acceptance": [
            {
                "check_id": f"{task_id}-out",
                "kind": "FILE_EXISTS",
                "description": f"{task_id}.txt exists",
                "path": f"{task_id}.txt",
            }
        ],
    }
    body.update(overrides)
    return body


def _program_file(
    tmp_path: Path,
    workspace: Path,
    *,
    tasks: list[dict[str, Any]],
    program_id: str = "continuation-program",
    name: str = "program.json",
    profiles: dict[str, dict[str, Any]] | None = None,
    max_attempts_per_task: int = 3,
) -> Path:
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": program_id,
            "objective": "durable continuation coverage",
            "approved_by": "fixture-operator",
            "approval_reference": "docs/orchestration/program/DURABLE-CONTINUATION.md",
            "workspace_root": str(workspace),
            "base_pin": "0" * 40,
            "limits": {
                "max_cycles": 20,
                "idle_sleep_seconds": 0.0,
                "max_concurrent_workers": 1,
                "max_attempts_per_task": max_attempts_per_task,
            },
            "tasks": tasks,
        },
        "profiles": profiles or {"impl": _profile("agent-one")},
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _envelope(
    task_id: str,
    *,
    replay: ReplayClass,
    steps: tuple[str, ...] = (),
    fallbacks: tuple[str, ...] = (),
    budgets: TaskBudgets | None = None,
    program_id: str = "fixture-program",
    worker_id: str = "fixture-worker-01",
    head: str = "a" * 40,
    tree: str = "b" * 40,
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        objective=f"fixture task {task_id}",
        capabilities_required=("IMPLEMENT",),
        candidate_head=head,
        candidate_tree=tree,
        allowed_paths=(f"{task_id}.txt",),
        acceptance=(
            AcceptanceCheck(
                check_id=f"{task_id}-out",
                kind=AcceptanceKind.FILE_EXISTS,
                description=f"{task_id}.txt exists",
                path=f"{task_id}.txt",
            ),
        ),
        budgets=budgets or TaskBudgets(),
        checkpoint_policy=CheckpointPolicy(steps=steps),
        fallback_task_ids=fallbacks,
        replay_class=replay,
        approved_by="fixture-operator",
        approval_reference="tests/unit/test_program_durable_continuation.py",
        profile_ref="impl",
        worker_id=worker_id,
        program_id=program_id,
    )


def _checkpoint(
    envelope: TaskEnvelope,
    *,
    sequence: int = 1,
    last_step: str | None = None,
    terminal: bool = False,
    replay: ReplayClass | None = None,
    pid: int | None = None,
    identity: str | None = None,
    lease: LeaseSnapshot | None = None,
    consumed: ConsumedBudget | None = None,
    root: Path | None = None,
) -> ContinuationCheckpoint:
    return ContinuationCheckpoint(
        identity=ExecutionIdentity(
            task_id=envelope.task_id,
            worker_id=envelope.worker_id,
            session_id=f"session.{sequence}",
            attempt_id=f"{envelope.task_id}.attempt.{sequence}",
        ),
        envelope_digest=envelope.digest(),
        program_id=envelope.program_id,
        sequence=sequence,
        last_completed_step=last_step,
        next_action=f"continue {envelope.task_id}",
        worktree_path=str(root or Path.cwd()),
        git_head=envelope.candidate_head,
        git_tree=envelope.candidate_tree,
        process_pid=pid,
        process_start_identity=identity,
        lease=lease,
        consumed_budget=consumed or ConsumedBudget(),
        replay_class=replay or envelope.replay_class,
        terminal=terminal,
    )


def _spawn_fixture_session(
    root: Path, task_id: str, replay: ReplayClass, mode: str, last_step: str | None = None
) -> subprocess.Popen[str]:
    """Start a real session, wait until it has sealed its checkpoint."""
    root.mkdir(parents=True, exist_ok=True)
    argv = [
        sys.executable,
        str(FIXTURE_SESSION),
        str(root),
        task_id,
        replay.value,
        mode,
    ]
    if last_step:
        argv.append(last_step)
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    _OWNED_PIDS.append(proc.pid)
    assert proc.stdout is not None
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if READY_MARK in line:
            return proc
        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise AssertionError(f"fixture session exited early: {stderr}")
    raise AssertionError("fixture session never announced readiness")


def _kill_owned(proc: subprocess.Popen[str]) -> int:
    """SIGKILL one process this test started, by pid, and wait for it.

    R-12, honoured literally: killed by the pid this test owns, never by name,
    pattern or working directory. SIGKILL rather than SIGTERM because a handler
    that got to run would be a handler that could tidy up, and the whole point
    is state written before the effect, surviving a process that had no chance
    to clean up after itself.
    """
    pid = proc.pid
    os.kill(pid, signal.SIGKILL)
    proc.wait(timeout=30)
    return pid


def _cli(*args: str) -> dict[str, Any]:
    """Run the CLI in a fresh interpreter and return its JSON object."""
    completed = subprocess.run(
        [sys.executable, "-m", CLI, *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.stdout, completed.stderr
    payload: dict[str, Any] = json.loads(completed.stdout)
    return payload


def _lease(holder: str, *, expires: str = "2099-01-01T00:00:00.000Z") -> LeaseSnapshot:
    return LeaseSnapshot(
        lease_id="fixture-lease",
        holder_worker_id=holder,
        holder_session_id="session.legacy",
        granted_at=utc_now(),
        expires_at=expires,
    )


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)


# =========================================================== (1) read-only


def test_a_killed_read_only_task_is_resumed_safely_by_a_replacement_session(
    tmp_path: Path,
) -> None:
    """(1) Process killed mid read-only task -> replacement session resumes."""
    root = tmp_path / "state"
    proc = _spawn_fixture_session(root, "ro-task", ReplayClass.READ_ONLY_REPLAYABLE, "block")
    pid = _kill_owned(proc)
    assert not _pid_alive(pid), "the fixture session must really be dead"

    # A different interpreter, with no memory of the one that died.
    payload = _cli(
        "program",
        "continuation",
        "--state-root",
        str(root),
        "--action",
        "reconcile",
        "--worker-id",
        "fixture-worker-01",
    )
    verdicts = {row["task_id"]: row for row in payload["verdicts"]}
    row = verdicts["ro-task"]
    assert row["disposition"] == Disposition.RESTART_FROM_TOP.value, row
    assert row["launchable"] is True
    assert row["replay_class"] == ReplayClass.READ_ONLY_REPLAYABLE.value
    # The identity check is what established the holder is gone -- not a
    # timeout, and not the absence of a heartbeat.
    assert any("is not running" in item for item in row["evidence"]), row["evidence"]

    # And the capsule a replacement session actually reads says the same thing,
    # generated from files, in a bounded rendering.
    capsule = _cli(
        "program", "capsule", "--state-root", str(root), "--worker-id", "fixture-worker-01"
    )
    assert capsule["rendered_bytes"] <= CAPSULE_MAX_BYTES
    assert "ro-task" in capsule["rendered"]
    assert "[RESTART_FROM_TOP] ro-task" in capsule["rendered"]


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# ================================================ (2) checkpointed mutation


def test_a_killed_checkpointed_mutation_resumes_at_the_next_step(
    tmp_path: Path,
) -> None:
    """(2) Process killed after a checkpointed mutation -> next step, not the top."""
    root = tmp_path / "state"
    proc = _spawn_fixture_session(
        root, "cp-task", ReplayClass.CHECKPOINT_RESUMABLE, "block", "PLAN"
    )
    _kill_owned(proc)

    payload = _cli(
        "program",
        "continuation",
        "--state-root",
        str(root),
        "--action",
        "reconcile",
        "--worker-id",
        "fixture-worker-01",
    )
    row = {r["task_id"]: r for r in payload["verdicts"]}["cp-task"]
    assert row["disposition"] == Disposition.RESUME_AT_NEXT_STEP.value, row
    assert row["resume_step"] == "APPLY", row
    assert row["launchable"] is True

    # The discriminator: it must NOT be the first step. Resuming at the top
    # would redo PLAN, which is exactly what a non-idempotent task must not do.
    assert row["resume_step"] != "PLAN"

    capsule = _cli(
        "program", "capsule", "--state-root", str(root), "--worker-id", "fixture-worker-01"
    )
    rendered = capsule["rendered"]
    assert "Resume task cp-task at step APPLY." in rendered, rendered
    assert "last_completed=PLAN resume_at=APPLY" in rendered


# ================================================= (3) uncertain mutation


def test_a_crash_during_an_uncertain_mutation_is_never_replayed(
    tmp_path: Path,
) -> None:
    """(3) Crash during an uncertain mutation -> no replay, reconcile required."""
    root = tmp_path / "state"
    proc = _spawn_fixture_session(
        root, "unc-task", ReplayClass.UNCERTAIN_EXTERNAL_EFFECT, "uncertain-block"
    )
    _kill_owned(proc)

    payload = _cli(
        "program",
        "continuation",
        "--state-root",
        str(root),
        "--action",
        "reconcile",
        "--worker-id",
        "fixture-worker-01",
    )
    row = {r["task_id"]: r for r in payload["verdicts"]}["unc-task"]
    assert row["disposition"] == Disposition.RECONCILE_REQUIRED.value, row
    assert row["launchable"] is False, "an unknown effect must never be launchable"
    assert row["replay_class"] == ReplayClass.UNCERTAIN_EXTERNAL_EFFECT.value
    assert any("OUTBOUND_WRITE" in item for item in row["evidence"]), row["evidence"]

    # UNCERTAIN_AUTOMATIC_REPLAY_COUNT: reconciling repeatedly must never turn
    # into a launch. Three passes, same answer, zero launchable verdicts.
    for _ in range(3):
        again = _cli(
            "program",
            "continuation",
            "--state-root",
            str(root),
            "--action",
            "reconcile",
            "--worker-id",
            "fixture-worker-01",
        )
        assert all(not r["launchable"] for r in again["verdicts"])

    capsule = build_capsule(root, for_worker_id="fixture-worker-01")
    task = next(t for t in capsule.tasks if t.task_id == "unc-task")
    assert "Do not relaunch it." in task.next_action


def test_MUTATION_dropping_the_unconfirmed_receipt_check_would_permit_a_replay(
    tmp_path: Path,
) -> None:
    """The guard in (3) is load-bearing, shown by removing what it keys on.

    The same durable state, with only the receipt's ``confirmed=None`` changed
    to ``True`` -- an effect somebody established had landed -- produces a
    launchable verdict. So the refusal in the test above came from the
    unconfirmed receipt and not from some other property of the fixture.
    """
    root = tmp_path / "state"
    envelope = _envelope("mut-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    checkpoint = _checkpoint(envelope, pid=None, identity=None, root=root)
    persist_checkpoint(root, checkpoint)

    verdict = reconcile_one(root, "mut-task", our_worker_id=envelope.worker_id)
    assert verdict.disposition is Disposition.RESTART_FROM_TOP
    assert verdict.launchable is True

    # Now add the one thing the guard keys on, and nothing else.
    from project_atlas.orchestration.program.continuation import ExternalEffectReceipt

    with_receipt = checkpoint.model_copy(deep=True)
    with_receipt.sequence = 2
    with_receipt.external_effects = (
        ExternalEffectReceipt(
            receipt_id="mut-effect",
            kind="OUTBOUND_WRITE",
            description="outcome never established",
            recorded_at=utc_now(),
            confirmed=None,
        ),
    )
    persist_checkpoint(root, with_receipt)
    blocked = reconcile_one(root, "mut-task", our_worker_id=envelope.worker_id)
    assert blocked.disposition is Disposition.RECONCILE_REQUIRED
    assert blocked.launchable is False


# ======================================================= (4) completed work


def test_completed_work_survives_two_restarts_with_zero_new_launches(
    tmp_path: Path,
) -> None:
    """(4) A completed task survives two restarts with zero new launches."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("done-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()

    loaded = load_program(program)
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id=loaded.program.program_id,
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="test (4)",
    )

    first = _dispatcher(state_root, queue_root)
    first_result = first.tick()
    assert first_result.report is not None
    assert first_result.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert first_result.launched == 1, "the first run must actually do the work"
    launches_after_first = first_result.report.launches

    entry = approved_queue.load_queue(queue_root).entries["continuation-program"]
    assert entry.status is approved_queue.QueueEntryStatus.COMPLETE

    # Two further restarts, each a brand-new dispatcher object with a new
    # session id -- the "replacement session" case, twice.
    for restart in (1, 2):
        again = _dispatcher(state_root, queue_root)
        result = again.tick()
        assert result.state is DispatcherState.IDLE_EMPTY_QUEUE, (restart, result.notes)
        assert result.launched == 0, restart
        assert result.report is None, restart

    final = approved_queue.load_queue(queue_root).entries["continuation-program"]
    assert final.runs == 1, "COMPLETED_REPLAY_COUNT must be zero"
    state = _load_state(state_root)
    assert state.total_launches == launches_after_first


def test_a_terminal_completed_checkpoint_is_never_replayed_by_reconciliation(
    tmp_path: Path,
) -> None:
    """(4) The no-replay guarantee at the layer that actually decides launches.

    Found by mutation: removing the COMPLETED early return in
    ``reconcile_task`` broke nothing, because every existing proof of
    no-replay went through the queue's COMPLETE status instead. Two
    independent mechanisms defend this property and only one of them was
    defended, so a refactor could have deleted the other in silence.

    The observable is the disposition and ``launchable``, never a message.
    """
    root = tmp_path / "state"
    envelope = _envelope("finished-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(
        root,
        _checkpoint(
            envelope,
            last_step=None,
            terminal=True,
            replay=ReplayClass.COMPLETED,
            root=root,
        ),
    )

    # Twice, because "survives two restarts" is the requirement and a guard
    # that fires once is not the same as one that holds.
    for restart in (1, 2):
        verdict = reconcile_one(
            root, "finished-task", our_worker_id=envelope.worker_id
        )
        assert verdict.disposition is Disposition.ALREADY_COMPLETE, restart
        assert verdict.launchable is False, restart
        assert verdict.replay_class is ReplayClass.COMPLETED, restart
        assert "never replayed" in verdict.reason

    # And a different worker arriving fresh gets the same answer -- completion
    # is a property of the work, not of who is asking.
    other = reconcile_one(root, "finished-task", our_worker_id="some-other-worker")
    assert other.disposition is Disposition.ALREADY_COMPLETE
    assert other.launchable is False


def test_MUTATION_a_completed_task_whose_terminal_seal_is_dropped_becomes_replayable(
    tmp_path: Path,
) -> None:
    """The guard above is load-bearing, shown by removing what it keys on.

    Identical durable state except that the checkpoint is not terminal and not
    classed COMPLETED. That one difference turns a refusal into a launchable
    verdict -- so the refusal came from the completion record and not from
    something incidental to the fixture.
    """
    root = tmp_path / "state"
    envelope = _envelope("almost-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(root, _checkpoint(envelope, terminal=False, root=root))
    verdict = reconcile_one(root, "almost-task", our_worker_id=envelope.worker_id)
    assert verdict.disposition is Disposition.RESTART_FROM_TOP
    assert verdict.launchable is True


def test_a_completed_queue_entry_cannot_be_returned_to_a_runnable_status(
    tmp_path: Path,
) -> None:
    """The mechanism behind (4): COMPLETE is terminal in the queue itself."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("t")])
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=tmp_path / "state",
        admitted_by="op",
        reference="ref",
    )
    approved_queue.update_entry(
        queue_root, "continuation-program", status=approved_queue.QueueEntryStatus.COMPLETE
    )
    with pytest.raises(approved_queue.QueueError) as caught:
        approved_queue.update_entry(
            queue_root,
            "continuation-program",
            status=approved_queue.QueueEntryStatus.PENDING,
        )
    assert caught.value.code == "QUEUE_COMPLETE_IS_TERMINAL"


# ====================================================== (5) blocked -> fallback


def test_a_blocked_task_releases_its_lease_and_an_eligible_fallback_is_selected(
    tmp_path: Path,
) -> None:
    """(5) Blocked task: one record, lease released, fallback selected."""
    root = tmp_path / "state"
    blocked_env = _envelope(
        "blocked-task", replay=ReplayClass.IDEMPOTENT_MUTATION, fallbacks=("fallback-task",)
    )
    fallback_env = _envelope("fallback-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, blocked_env)
    persist_envelope(root, fallback_env)

    # A real ACTIVE lease row, through the real projection.
    _grant_projected_lease(root, task_id="blocked-task", agent_id="fixture-worker-01")
    assert [row.package_id for row in active_rows(load_projection(root))] == [
        "blocked-task"
    ]

    outcome = handle_blocked_task(
        root,
        envelope=blocked_env,
        kind=DecisionKind.PERMISSION,
        subject="WRITE_OUTSIDE_ALLOWED_PATHS",
        question="May this task write outside its allowed paths?",
        requested_action="Widen the program's mutation_paths, or decline.",
        worker_id="fixture-worker-01",
        session_id="session.1",
        evidence=("attempted path: outside/allowed",),
    )

    # 1. exactly one durable record
    assert outcome.newly_raised is True
    assert len(decisions.list_decisions(root, status=DecisionStatus.OPEN)) == 1
    # 2. the lease is really gone from the projection
    assert outcome.lease_released is True, outcome.lease_release_detail
    assert active_rows(load_projection(root)) == ()
    # 3. an eligible fallback was selected -- from the approved program only
    assert outcome.fallback_task_id == "fallback-task", outcome.fallback_reason

    # 4. THE REFUSAL: raising the same blocker again does not re-ask.
    again = handle_blocked_task(
        root,
        envelope=blocked_env,
        kind=DecisionKind.PERMISSION,
        subject="WRITE_OUTSIDE_ALLOWED_PATHS",
        question="May this task write outside its allowed paths?",
        requested_action="Widen the program's mutation_paths, or decline.",
        worker_id="fixture-worker-01",
        session_id="session.2",
    )
    assert again.newly_raised is False
    assert again.decision.seen_count == 2
    assert len(decisions.list_decisions(root, status=DecisionStatus.OPEN)) == 1

    # And the blocked task is skipped by selection while the question is open.
    assert decisions.blocked_task_ids(root) == frozenset({"blocked-task"})


def test_a_fallback_that_is_itself_blocked_is_not_selected(tmp_path: Path) -> None:
    """Yielding must not produce a second question. A blocked fallback is skipped."""
    root = tmp_path / "state"
    primary = _envelope(
        "primary", replay=ReplayClass.IDEMPOTENT_MUTATION, fallbacks=("second", "third")
    )
    for task_id in ("primary", "second", "third"):
        persist_envelope(
            root, _envelope(task_id, replay=ReplayClass.IDEMPOTENT_MUTATION)
        )
    persist_envelope(root, primary)
    decisions.raise_decision(
        root,
        program_id="fixture-program",
        task_id="second",
        kind=DecisionKind.BUDGET_INCREASE,
        subject="max_launches",
        question="raise the launch budget?",
        requested_action="raise it or decline",
        worker_id="w",
        session_id="s",
    )
    chosen, reason = select_fallback(root, primary)
    assert chosen == "third", reason


def test_a_fallback_not_in_the_approved_program_is_never_selected(
    tmp_path: Path,
) -> None:
    """Never invent work: an unenveloped fallback has no recorded authority."""
    root = tmp_path / "state"
    primary = _envelope(
        "primary", replay=ReplayClass.IDEMPOTENT_MUTATION, fallbacks=("ghost",)
    )
    persist_envelope(root, primary)
    chosen, reason = select_fallback(root, primary)
    assert chosen is None
    assert "no recorded envelope" in reason


# ==================================================== (6) efficient waiting


def test_an_empty_queue_produces_efficient_waiting_not_a_spin_or_an_exit(
    tmp_path: Path,
) -> None:
    """(6) No eligible work -> waiting. Measured as CPU time, not asserted.

    The oracle is deliberately CPU time rather than a tick count. A tick count
    can be made to look good by lengthening the interval while the loop body
    still burns a core; CPU consumed over a real wall-clock hold cannot. The
    dispatcher must also still be *resident* at the end -- an exit would be the
    behaviour this layer exists to replace, and it would also trivially pass a
    CPU test.
    """
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    dispatcher = ResidentDispatcher(
        root=state_root,
        queue_root=queue_root,
        checkout=tmp_path,
        tick_seconds=0.5,
        wake_quantum_seconds=0.05,
    )

    before = resource.getrusage(resource.RUSAGE_SELF)
    wall_start = time.monotonic()
    reason = dispatcher.run(max_seconds=3.0)
    wall = time.monotonic() - wall_start
    after = resource.getrusage(resource.RUSAGE_SELF)
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)

    assert reason is DispatcherStopReason.DEADLINE_REACHED, reason
    assert wall >= 2.5, f"it must actually have waited, waited {wall:.2f}s"
    # A spin loop consumes CPU at roughly wall-clock rate. Waiting does not.
    assert cpu < wall * 0.25, f"cpu={cpu:.3f}s over wall={wall:.2f}s looks like a spin"
    assert dispatcher._ticks <= 12, dispatcher._ticks
    assert dispatcher._launches == 0
    assert dispatcher._programs_started == 0

    beat = read_heartbeat(state_root)
    assert beat is not None
    assert beat.terminal_reason is DispatcherStopReason.DEADLINE_REACHED
    assert beat.state is DispatcherState.STOPPED
    # No filler work: nothing was created anywhere under the state root except
    # the dispatcher's own published health.
    assert not checkpoints_dir(state_root).exists()
    assert decisions.list_decisions(state_root) == ()


def test_the_dispatcher_refuses_a_zero_wake_quantum(tmp_path: Path) -> None:
    """A zero quantum is a spin loop by construction, so it is refused."""
    with pytest.raises(resident.DispatcherError) as caught:
        ResidentDispatcher(
            root=tmp_path / "s",
            queue_root=tmp_path,
            wake_quantum_seconds=0.0,
        )
    assert caught.value.code == "DISPATCHER_BAD_QUANTUM"


# ======================================================= (7) wake and launch


def test_admitting_approved_work_wakes_the_dispatcher_and_launches_exactly_once(
    tmp_path: Path,
) -> None:
    """(7) New approved work wakes the dispatcher and launches exactly once."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("wake-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()

    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)

    # Idle first: nothing admitted, nothing launched.
    idle = dispatcher.tick()
    assert idle.state is DispatcherState.IDLE_EMPTY_QUEUE
    assert idle.launched == 0

    # The wait must end early on the wake rather than running the full tick.
    resident.request_wake(state_root, reason="test")
    start = time.monotonic()
    slept = dispatcher.wait(5.0)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"a pending wake must shorten the wait, took {elapsed:.2f}s"
    assert slept < 1.0

    # Admission is the operator act; it also requests a wake.
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="test (7)",
    )
    resident.request_wake(state_root, reason="admitted")

    ran = dispatcher.tick()
    assert ran.program_id == "continuation-program"
    assert ran.report is not None
    assert ran.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert ran.launched == 1, "exactly once"

    # EXACTLY once: every later tick launches nothing at all.
    for _ in range(3):
        assert dispatcher.tick().launched == 0
    assert dispatcher._launches == 1
    assert (workspace / "wake-one.txt").read_text(encoding="utf-8").count("\n") == 1


# ============================================================== (8) pause


def test_pause_blocks_new_dispatch_reports_in_flight_work_and_resume_continues(
    tmp_path: Path,
) -> None:
    """(8) Pause withholds dispatch, names what is running, resume continues once."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(
        tmp_path, workspace, tasks=[_task("pause-one"), _task("pause-two")]
    )
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="test (8)",
    )

    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    resident.request_pause(state_root, requested_by="operator:test")

    paused = dispatcher.tick()
    assert paused.state is DispatcherState.PAUSED
    assert paused.launched == 0
    assert paused.report is None, "a paused dispatcher must not run a program"
    assert any("left to finish" in note for note in paused.notes)

    status = dispatcher_status(state_root)
    assert status["paused"] is True
    assert status["heartbeat"]["pause_requested_by"] == "operator:test"
    assert status["heartbeat"]["state"] == DispatcherState.PAUSED.value

    # Pause survives more ticks -- it is not a one-shot that lapses.
    for _ in range(3):
        assert dispatcher.tick().state is DispatcherState.PAUSED
    assert dispatcher._launches == 0
    assert not (workspace / "pause-one.txt").exists()

    # Resume: work continues, and each task runs exactly once.
    assert resident.clear_pause(state_root) is True
    resumed = dispatcher.tick()
    assert resumed.report is not None
    assert resumed.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert resumed.launched == 2
    for name in ("pause-one.txt", "pause-two.txt"):
        assert (workspace / name).read_text(encoding="utf-8").count("\n") == 1

    # And resume does not re-run it.
    assert dispatcher.tick().launched == 0


def test_a_pause_record_survives_a_dispatcher_restart(tmp_path: Path) -> None:
    """An operator's withholding decision must not be cleared by a restart.

    ``clear_signals`` deliberately clears stop, drain and wake but NOT pause,
    because clearing pause would resume work a person had withheld -- and the
    restart is exactly when nobody is watching.
    """
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    resident.request_pause(state_root, requested_by="operator:test")
    resident.request_stop(state_root, requested_by="operator:test")
    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    reason = dispatcher.run(max_ticks=2)
    assert reason is not DispatcherStopReason.OPERATOR_STOP, (
        "a stale stop must not end the next run"
    )
    assert resident.pause_requested(state_root) is not None, "pause must survive"


# ============================================== (9) workers that launch nothing


def test_a_suspended_worker_launches_nothing(tmp_path: Path) -> None:
    """(9) Suspended worker -> zero launches, and the reason is recorded."""
    from project_atlas.orchestration.program.enrollment import (
        AgentStatus,
        assign,
        enroll,
        set_status,
    )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("susp-one")])
    registry = tmp_path / "registry"
    state_root = tmp_path / "state"
    enroll(
        registry,
        agent_id="agent-one",
        role="impl",
        adapter="local-command",
        workspace_root=workspace,
        enrolled_by="op",
    )
    assign(registry, agent_id="agent-one", program_path=program, assigned_by="op")
    set_status(
        registry, agent_id="agent-one", status=AgentStatus.SUSPENDED
    )

    from project_atlas.orchestration.program.supervisor import ProgramSupervisor

    report = ProgramSupervisor(
        load_program(program),
        state_root=state_root,
        registry_root=registry,
        sleeper=lambda _s: None,
    ).start()
    assert report.launches_this_run == 0, "a suspended worker must launch nothing"
    assert report.stop_reason is not ProgramStopReason.PROGRAM_COMPLETE
    assert not (workspace / "susp-one.txt").exists()


def test_a_mismatched_head_refuses_dispatch_before_anything_launches(
    tmp_path: Path,
) -> None:
    """(9)/(12) An envelope approved against other code confers nothing."""
    program_file = _program_file(tmp_path, tmp_path / "ws", tasks=[_task("head-task")])
    (tmp_path / "ws").mkdir(exist_ok=True)
    loaded = load_program(program_file)
    envelope = _envelope(
        "head-task",
        replay=ReplayClass.IDEMPOTENT_MUTATION,
        program_id=loaded.program.program_id,
    )
    with pytest.raises(EnvelopeError) as caught:
        validate_envelope_for_dispatch(
            envelope,
            program=loaded.program,
            observed_head="c" * 40,
            observed_tree=envelope.candidate_tree,
            consumed=ConsumedBudget(),
        )
    assert caught.value.code == "ENVELOPE_HEAD_MOVED"


def test_an_envelope_for_a_task_outside_the_approved_program_confers_nothing(
    tmp_path: Path,
) -> None:
    """(9) A duplicate or invented task id is not approved work."""
    (tmp_path / "ws").mkdir()
    program_file = _program_file(tmp_path, tmp_path / "ws", tasks=[_task("real-task")])
    loaded = load_program(program_file)
    envelope = _envelope(
        "invented-task",
        replay=ReplayClass.IDEMPOTENT_MUTATION,
        program_id=loaded.program.program_id,
    )
    with pytest.raises(EnvelopeError) as caught:
        validate_envelope_for_dispatch(
            envelope,
            program=loaded.program,
            observed_head=envelope.candidate_head,
            observed_tree=envelope.candidate_tree,
            consumed=ConsumedBudget(),
        )
    assert caught.value.code == "ENVELOPE_TASK_NOT_APPROVED"


def test_the_four_identities_cannot_be_conflated(tmp_path: Path) -> None:
    """(9) A stable principal must not inherit a session's lifetime."""
    _ = tmp_path
    with pytest.raises(ValueError, match="must not inherit a session's lifetime"):
        ExecutionIdentity(
            task_id="t",
            worker_id="same",
            session_id="same",
            attempt_id="a",
        )
    with pytest.raises(ValueError, match="named after one execution"):
        ExecutionIdentity(
            task_id="same", worker_id="w", session_id="s", attempt_id="same"
        )


# ================================================= (10) fail-closed on state


def test_a_corrupt_checkpoint_fails_closed_and_is_never_repaired(
    tmp_path: Path,
) -> None:
    """(10) A corrupt checkpoint fails closed, and nothing rewrites it."""
    root = tmp_path / "state"
    envelope = _envelope("corrupt-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    sealed = persist_checkpoint(root, _checkpoint(envelope, root=root))

    path = next(checkpoints_dir(root).glob("*.checkpoint.json"))
    original = path.read_bytes()
    payload = json.loads(original)
    payload["next_action"] = "do something else entirely"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(CheckpointError) as caught:
        load_checkpoint(root, "corrupt-task")
    assert caught.value.code == "CHECKPOINT_DIGEST_MISMATCH"

    verdict = reconcile_one(root, "corrupt-task", our_worker_id=envelope.worker_id)
    assert verdict.disposition is Disposition.FAIL_CLOSED
    assert verdict.launchable is False

    # NOT SILENTLY REPAIRED: the bytes on disk are exactly what the tamper
    # left, and the original digest is not restored behind anyone's back.
    assert json.loads(path.read_text(encoding="utf-8"))["self_digest"] == (
        sealed.self_digest
    )
    assert json.loads(path.read_text(encoding="utf-8"))["next_action"] == (
        "do something else entirely"
    )

    # And the capsule still lists the task -- omitting it would assert it does
    # not exist.
    capsule = build_capsule(root, for_worker_id=envelope.worker_id)
    assert [t.task_id for t in capsule.tasks] == ["corrupt-task"]
    assert capsule.tasks[0].disposition is Disposition.FAIL_CLOSED
    assert "must not be repaired automatically" in capsule.tasks[0].next_action


def test_an_unexpired_lease_held_by_another_worker_fails_closed(
    tmp_path: Path,
) -> None:
    """(10) Reacquisition needs expiry AND an identity check -- not one of them."""
    root = tmp_path / "state"
    envelope = _envelope("leased-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(
        root,
        _checkpoint(envelope, lease=_lease("other-worker-99"), root=root),
    )
    verdict = reconcile_one(root, "leased-task", our_worker_id="fixture-worker-01")
    assert verdict.disposition is Disposition.LEASE_HELD_ELSEWHERE
    assert verdict.launchable is False


def test_a_stale_lease_is_reacquirable_only_after_expiry_and_an_identity_check(
    tmp_path: Path,
) -> None:
    """(10) The same lease, expired, with its holder demonstrably gone."""
    root = tmp_path / "state"
    envelope = _envelope("stale-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(
        root,
        _checkpoint(
            envelope,
            lease=_lease("other-worker-99", expires="2000-01-01T00:00:00.000Z"),
            root=root,
        ),
    )
    verdict = reconcile_one(root, "stale-task", our_worker_id="fixture-worker-01")
    assert verdict.disposition is Disposition.RESTART_FROM_TOP
    assert any("expired at" in item for item in verdict.evidence), verdict.evidence


def test_a_checkpoint_whose_sequence_goes_backwards_is_refused(
    tmp_path: Path,
) -> None:
    """(10) Two writers disagreeing about one task is contradictory state."""
    root = tmp_path / "state"
    envelope = _envelope("seq-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(root, _checkpoint(envelope, sequence=5, root=root))
    with pytest.raises(CheckpointError) as caught:
        persist_checkpoint(root, _checkpoint(envelope, sequence=4, root=root))
    assert caught.value.code == "CHECKPOINT_SEQUENCE_REGRESSION"
    # The older record survives untouched.
    assert load_checkpoint(root, "seq-task").sequence == 5


def test_a_checkpoint_written_under_a_different_envelope_fails_closed(
    tmp_path: Path,
) -> None:
    """(10) Authority that changed mid-flight is a contradiction, not a resume."""
    root = tmp_path / "state"
    envelope = _envelope("drift-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(root, _checkpoint(envelope, root=root))
    widened = envelope.model_copy(update={"allowed_paths": ("drift-task.txt", "extra/")})
    persist_envelope(root, widened)
    verdict = reconcile_one(root, "drift-task", our_worker_id=envelope.worker_id)
    assert verdict.disposition is Disposition.FAIL_CLOSED
    assert "authority for this work changed mid-flight" in verdict.reason


def test_an_unsealed_checkpoint_is_refused(tmp_path: Path) -> None:
    """(10) Incomplete state -- a checkpoint with no digest -- fails closed."""
    root = tmp_path / "state"
    envelope = _envelope("unsealed-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(root, _checkpoint(envelope, root=root))
    path = next(checkpoints_dir(root).glob("*.checkpoint.json"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("self_digest")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(CheckpointError) as caught:
        load_checkpoint(root, "unsealed-task")
    assert caught.value.code == "CHECKPOINT_UNSEALED"


def test_a_pid_without_a_start_identity_is_refused_at_construction(
    tmp_path: Path,
) -> None:
    """(10)/(11) A pid alone cannot be told apart from a reused one."""
    envelope = _envelope("pid-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    with pytest.raises(CheckpointError) as caught:
        _checkpoint(envelope, pid=1234, identity=None, root=tmp_path)
    assert caught.value.code == "CHECKPOINT_PID_WITHOUT_IDENTITY"


# ================================================== (11) cleanup and identity


def test_cleanup_uses_pid_plus_start_identity_and_leaks_no_test_processes(
    tmp_path: Path,
) -> None:
    """(11) Every process this module started is dead, and identity decided it."""
    from project_atlas.orchestration.program.reconciliation import holder_liveness

    root = tmp_path / "state"
    proc = _spawn_fixture_session(root, "live-task", ReplayClass.READ_ONLY_REPLAYABLE, "block")

    # ALIVE requires a MATCHING identity, not merely a live pid.
    checkpoint = load_checkpoint(root, "live-task")
    assert checkpoint is not None
    liveness, why = holder_liveness(checkpoint)
    assert liveness is Liveness.ALIVE, why
    assert "start identity matches" in why

    # A wrong recorded identity reads as GONE -- the pid was reused.
    reused = checkpoint.model_copy(deep=True)
    reused.process_start_identity = "0"
    assert holder_liveness(reused)[0] is Liveness.GONE

    # No recorded identity is UNKNOWN, never absence.
    unknown = checkpoint.model_copy(deep=True)
    unknown.process_pid = None
    unknown.process_start_identity = None
    assert holder_liveness(unknown)[0] is Liveness.UNKNOWN

    pid = _kill_owned(proc)
    assert not _pid_alive(pid)
    assert holder_liveness(checkpoint)[0] is Liveness.GONE

    # TEST_PROCESS_LEAKS=0, over every pid this module ever started.
    survivors = [owned for owned in _OWNED_PIDS if _pid_alive(owned)]
    assert survivors == [], survivors


def test_this_module_never_kills_by_pattern_or_working_directory() -> None:
    """(11) R-12 as a property of the test code, not a promise about it.

    Read from the source of this file, so it cannot drift away from the claim.
    A broad kill in a shared session has already killed a peer's process once
    in this program; the guard is cheap and the failure was not.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("pkill", "killall", "-f ", "os.system"):
        assert forbidden not in source.replace(
            'for forbidden in ("pkill", "killall", "-f ", "os.system")', ""
        ), forbidden


# ================================= (12) authority and budget before dispatch


def test_budget_and_authority_are_rechecked_immediately_before_dispatch(
    tmp_path: Path,
) -> None:
    """(12) Each condition that can become true mid-run is checked at dispatch."""
    (tmp_path / "ws").mkdir()
    program_file = _program_file(tmp_path, tmp_path / "ws", tasks=[_task("budget-task")])
    loaded = load_program(program_file)
    envelope = _envelope(
        "budget-task",
        replay=ReplayClass.IDEMPOTENT_MUTATION,
        budgets=TaskBudgets(max_attempts=2, max_launches=2, max_wall_seconds=60),
        program_id=loaded.program.program_id,
    )

    # Inside budget: no refusal.
    validate_envelope_for_dispatch(
        envelope,
        program=loaded.program,
        observed_head=envelope.candidate_head,
        observed_tree=envelope.candidate_tree,
        consumed=ConsumedBudget(attempts=1, launches=1),
    )

    for consumed, code in (
        (ConsumedBudget(attempts=2), "ENVELOPE_BUDGET_EXHAUSTED"),
        (ConsumedBudget(launches=2), "ENVELOPE_BUDGET_EXHAUSTED"),
        (ConsumedBudget(wall_seconds=60.0), "ENVELOPE_BUDGET_EXHAUSTED"),
        (ConsumedBudget(model_calls=1), "ENVELOPE_BUDGET_EXHAUSTED"),
    ):
        with pytest.raises(EnvelopeError) as caught:
            validate_envelope_for_dispatch(
                envelope,
                program=loaded.program,
                observed_head=envelope.candidate_head,
                observed_tree=envelope.candidate_tree,
                consumed=consumed,
            )
        assert caught.value.code == code, consumed

    # A deadline that passed is refused too -- it is the condition that becomes
    # true purely with time, which is what makes a start-up check insufficient.
    expired = envelope.model_copy(update={"deadline_utc": "2000-01-01T00:00:00.000Z"})
    with pytest.raises(EnvelopeError) as caught:
        validate_envelope_for_dispatch(
            expired,
            program=loaded.program,
            observed_head=envelope.candidate_head,
            observed_tree=envelope.candidate_tree,
            consumed=ConsumedBudget(),
        )
    assert caught.value.code == "ENVELOPE_DEADLINE_PASSED"


def test_a_task_cannot_declare_itself_complete_or_in_need_of_a_human(
    tmp_path: Path,
) -> None:
    """(12) Three of the six replay classes are findings, not declarations."""
    _ = tmp_path
    for klass in (ReplayClass.COMPLETED, ReplayClass.HUMAN_DECISION_REQUIRED):
        with pytest.raises(EnvelopeError) as caught:
            _envelope("declare-task", replay=klass)
        assert caught.value.code == "REPLAY_CLASS_NOT_DECLARABLE", klass


def test_an_envelope_with_contradictory_authority_is_refused(tmp_path: Path) -> None:
    """(12) Malformed authority fails closed, at construction."""
    _ = tmp_path
    base = _envelope("contradiction", replay=ReplayClass.IDEMPOTENT_MUTATION)
    payload = base.model_dump()
    payload["allowed_actions"] = ("WRITE", "PUSH")
    payload["forbidden_actions"] = ("PUSH",)
    with pytest.raises(EnvelopeError) as caught:
        TaskEnvelope(**payload)
    assert caught.value.code == "ENVELOPE_CONTRADICTORY_ACTIONS"

    payload = base.model_dump()
    payload["allowed_paths"] = ("secrets/key.txt",)
    payload["forbidden_paths"] = ("secrets",)
    with pytest.raises(EnvelopeError) as caught:
        TaskEnvelope(**payload)
    assert caught.value.code == "ENVELOPE_CONTRADICTORY_PATHS"


def test_an_admitted_program_whose_bytes_changed_is_refused(tmp_path: Path) -> None:
    """(12) Approval was for the bytes, never for whatever is at the path now."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("pin-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="test (12)",
    )
    # Swap the approved work for different work, under the same name.
    _program_file(
        tmp_path, workspace, tasks=[_task("pin-one"), _task("smuggled-two")]
    )
    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    result = dispatcher.tick()
    assert result.state is DispatcherState.IDLE_EMPTY_QUEUE
    assert result.launched == 0
    assert any("QUEUE_PROGRAM_CHANGED" in n or "re-admitted" in n for n in result.notes), (
        result.notes
    )
    assert not (workspace / "smuggled-two.txt").exists()


def test_a_corrupt_queue_is_reported_and_never_looks_like_an_empty_one(
    tmp_path: Path,
) -> None:
    """(10) "I could not read the queue" and "there is no work" are different.

    Collapsing them is the failure that hides itself: an unreadable queue would
    present exactly as a quiet, healthy, idle dispatcher, and an operator would
    have nothing to look at. The two states are kept distinct and the reason is
    carried in the tick's notes.
    """
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.queue_path(queue_root).write_text("{not json", encoding="utf-8")

    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    result = dispatcher.tick()

    assert result.state is DispatcherState.WAITING_ON_WORK
    assert result.state is not DispatcherState.IDLE_EMPTY_QUEUE
    assert result.launched == 0
    # Keyed on the CODE, not on the sentence. This assertion used to match the
    # note's prose and broke the moment the note was reworded to lead with the
    # code -- which is the whole argument for having a code: a caller keys on
    # QUEUE_UNREADABLE, never on a message that may be improved.
    assert result.queue_status == "UNREADABLE"
    assert result.queue_error_code == "QUEUE_UNREADABLE"
    assert any("QUEUE_UNREADABLE" in note for note in result.notes), result.notes

    beat = read_heartbeat(state_root)
    assert beat is not None
    assert beat.state is DispatcherState.WAITING_ON_WORK


# ============================================= (13) finite-program compatibility


def test_the_existing_finite_program_behaviour_is_unchanged(tmp_path: Path) -> None:
    """(13) A plain `start()` still runs to PROGRAM_COMPLETE, with no new state.

    The compatibility claim is narrow and checked as such: a program run
    WITHOUT any continuation surface behaves as before, and specifically does
    not acquire envelopes, checkpoints, decisions or a dispatcher directory.
    This layer is additive; if it were not, a previous revision could not read
    the state a new one wrote, and rollback would stop being safe.
    """
    from project_atlas.orchestration.program.supervisor import ProgramSupervisor

    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(
        tmp_path,
        workspace,
        tasks=[_task("compat-one"), _task("compat-two", depends_on=["compat-one"])],
    )
    state_root = tmp_path / "state"
    report = ProgramSupervisor(
        load_program(program), state_root=state_root, sleeper=lambda _s: None
    ).start()
    assert report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert report.complete is True
    dispatched = [r["task_id"] for r in report.to_public_dict()["tasks_dispatched"]]
    assert dispatched == ["compat-one", "compat-two"]
    assert [n["kind"] for n in report.notifications] == ["PROGRAM_COMPLETE"]

    base = state_dir(state_root)
    for added in ("envelopes", "checkpoints", "decisions", "dispatcher"):
        assert not (base / added).exists(), added
    assert (base / "state.json").is_file()
    assert (base / "events.jsonl").is_file()


def test_the_new_state_directories_are_additive_siblings(tmp_path: Path) -> None:
    """(13) Every new artifact is a NEW file under the program state dir.

    Rollback safety rests on this: a previous revision ignores directories it
    does not know about, so there is nothing to migrate and nothing to delete.
    """
    root = tmp_path / "state"
    envelope = _envelope("add-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(root, _checkpoint(envelope, root=root))
    decisions.raise_decision(
        root,
        program_id=envelope.program_id,
        task_id=envelope.task_id,
        kind=DecisionKind.PERMISSION,
        subject="s",
        question="q",
        requested_action="a",
        worker_id="w",
        session_id="s1",
    )
    base = state_dir(root)
    written = sorted(p.relative_to(base).parts[0] for p in base.rglob("*") if p.is_file())
    assert set(written) <= {"envelopes", "checkpoints", "decisions", "dispatcher"}, written
    # Nothing was written into the pre-existing files.
    assert not (base / "state.json").exists()
    assert not (base / "events.jsonl").exists()


# ============================================== (14) zero model and network


def test_the_whole_layer_makes_zero_model_calls_and_opens_no_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(14) MODEL_CALLS=0 and no outbound socket, enforced not asserted.

    The socket ban covers this interpreter, which is where the dispatcher, the
    reconciler and the capsule all run. It does NOT cover a fixture child
    process; that is stated rather than implied, and the fixture adapter's argv
    is asserted to be the local fixture worker, which opens nothing.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("zero-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="test (14)",
    )

    opened: list[Any] = []

    class _BannedSocket:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            opened.append((args, kwargs))
            raise AssertionError("this layer must open no network socket")

    monkeypatch.setattr(socket, "socket", _BannedSocket)
    monkeypatch.setattr(socket, "create_connection", _BannedSocket)

    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    result = dispatcher.tick()
    assert result.report is not None
    assert result.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    build_capsule(state_root, for_worker_id="fixture-worker-01", queue_root=queue_root)
    reconcile_root(state_root, our_worker_id="fixture-worker-01")
    assert opened == []

    beat = read_heartbeat(state_root)
    assert beat is not None
    assert beat.model_calls == 0
    assert beat.model_backed_dispatch == "DISABLED"

    # The adapter that actually ran is the labelled local fixture, not a runtime.
    loaded = load_program(program)
    profile = loaded.effective_profile("zero-one")
    assert profile.adapter.value == "local-command"
    assert profile.adapter_options["argv"][1] == str(FIXTURE_WORKER)


def test_a_model_call_budget_is_forbidden_for_an_uncertain_effect_task() -> None:
    """(14) The switch cannot be routed around by an envelope that budgets a call."""
    with pytest.raises(EnvelopeError) as caught:
        _envelope(
            "paid-task",
            replay=ReplayClass.UNCERTAIN_EXTERNAL_EFFECT,
            budgets=TaskBudgets(max_model_calls=1),
        )
    assert caught.value.code == "ENVELOPE_MODEL_CALLS_FORBIDDEN"


# ============================================ capsule boundedness and honesty


def test_the_capsule_is_bounded_and_announces_every_truncation(
    tmp_path: Path,
) -> None:
    """A short list and a truncated list must not look the same to a reader."""
    root = tmp_path / "state"
    for index in range(40):
        envelope = _envelope(
            f"many-{index:03d}", replay=ReplayClass.IDEMPOTENT_MUTATION
        )
        persist_envelope(root, envelope)
    capsule = build_capsule(root, for_worker_id="fixture-worker-01")
    assert capsule.truncated is True
    assert capsule.truncation_note
    rendered = render_capsule(capsule)
    assert len(rendered.encode("utf-8")) <= CAPSULE_MAX_BYTES
    assert "TRUNCATED" in rendered
    assert "durable state under state_root is complete" in rendered


def test_the_capsule_never_reads_a_transcript_and_grants_nothing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    envelope = _envelope("grant-task", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    capsule = build_capsule(root, for_worker_id="fixture-worker-01")
    assert capsule.merge_authorized is False
    assert capsule.model_backed_dispatch == "DISABLED"
    rendered = render_capsule(capsule)
    assert "It contains no conversation history" in rendered
    assert "grants nothing" in rendered
    assert "MERGE_AUTHORIZED=False" in rendered


# ======================================================= operator commands


def test_the_operator_commands_all_answer(tmp_path: Path) -> None:
    """status / events / decisions / pause / resume / reconcile / drain / stop.

    Plus the two that deliberately do NOT act: restart and rollback print the
    exact operator procedure instead of claiming a privilege this process does
    not hold.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("cmd-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()

    admitted = _cli(
        "program",
        "queue",
        "--queue-root",
        str(queue_root),
        "--state-root",
        str(state_root),
        "--action",
        "admit",
        "--program",
        str(program),
        "--admitted-by",
        "fixture-operator",
        "--reference",
        "test operator commands",
    )
    assert admitted["admitted"]["program_id"] == "continuation-program"

    listed = _cli("program", "queue", "--queue-root", str(queue_root), "--action", "list")
    assert listed["entries"][0]["pin_check"] == "MATCHES_ADMITTED_BYTES"

    run = _cli(
        "program",
        "dispatcher",
        "--state-root",
        str(state_root),
        "--queue-root",
        str(queue_root),
        "--action",
        "run",
        "--max-ticks",
        "1",
        "--tick-seconds",
        "0.5",
    )
    assert run["model_calls"] == 0
    assert run["launches"] == 1

    status = _cli(
        "program", "dispatcher", "--state-root", str(state_root), "--action", "status"
    )
    assert status["model_backed_dispatch"] == "DISABLED"
    # The dispatcher process ended, so its own liveness answer must be False --
    # not None, because the identity WAS recorded and can be compared.
    assert status["alive"] is False

    for action in ("pause", "resume", "wake", "drain", "stop"):
        payload = _cli(
            "program",
            "dispatcher",
            "--state-root",
            str(state_root),
            "--action",
            action,
            "--requested-by",
            "operator:test",
        )
        assert "error" not in payload, (action, payload)

    restart = _cli(
        "program", "dispatcher", "--state-root", str(state_root), "--action", "restart"
    )
    assert restart["performed"] is False
    assert restart["reason"] == "NOT_AUTHORIZED_FROM_HERE"
    assert restart["operator_commands"]

    rollback = _cli(
        "program", "continuation", "--state-root", str(state_root), "--action", "rollback"
    )
    assert rollback["performed"] is False
    assert rollback["state_compatibility"] == "ADDITIVE_ONLY_NO_IN_PLACE_MIGRATION"

    events = _cli("program", "events", "--program", str(program), "--state-root", str(state_root))
    names = {row.get("event") for row in events["events"]}
    assert "DISPATCHER_PROGRAM_STARTED" in names
    assert "DISPATCHER_PROGRAM_STOPPED" in names

    dec = _cli("program", "decisions", "--state-root", str(state_root), "--action", "list")
    assert dec["open_count"] == 0


def test_answering_a_decision_is_recorded_once_and_never_overwritten(
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    request, newly = decisions.raise_decision(
        root,
        program_id="p",
        task_id="t",
        kind=DecisionKind.BUDGET_INCREASE,
        subject="max_launches",
        question="raise it?",
        requested_action="raise or decline",
        worker_id="w",
        session_id="s",
    )
    assert newly is True
    answered = decisions.record_answer(
        root, request.decision_id, answered_by="operator", answer="declined"
    )
    assert answered.status is DecisionStatus.ANSWERED
    with pytest.raises(decisions.DecisionError) as caught:
        decisions.record_answer(
            root, request.decision_id, answered_by="someone-else", answer="approved"
        )
    assert caught.value.code == "DECISION_NOT_OPEN"
    # The operator's own answer survives the attempt to overwrite it.
    assert decisions.load_decision(root, request.decision_id).answered_by == "operator"
    # An answered decision no longer blocks selection.
    assert decisions.blocked_task_ids(root) == frozenset()


# ================================================== schemas stay in sync


def test_the_published_schemas_match_the_models_they_describe() -> None:
    """A shipped schema that drifts from its model is worse than none.

    Readers outside this package validate against the schema file, so a model
    field added without regenerating the schema produces a validator that
    accepts documents the code rejects -- and the first symptom is a refusal
    nobody can explain from the published contract.
    """
    import jsonschema

    from project_atlas.orchestration.program.approved_queue import ApprovedWorkQueue
    from project_atlas.orchestration.program.capsule import (
        ContinuationCapsule as CapsuleModel,
    )
    from project_atlas.orchestration.program.decisions import DecisionRequest
    from project_atlas.orchestration.program.resident import Heartbeat

    schemas = Path(
        __import__("project_atlas").__file__
    ).parent / "schemas"
    pairs = {
        "continuation-task-envelope": TaskEnvelope,
        "continuation-checkpoint": ContinuationCheckpoint,
        "continuation-capsule": CapsuleModel,
        "continuation-decision-request": DecisionRequest,
        "continuation-approved-queue": ApprovedWorkQueue,
        "continuation-dispatcher-heartbeat": Heartbeat,
    }
    for name, model in pairs.items():
        path = schemas / f"{name}.schema.json"
        assert path.is_file(), name
        published = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(published)
        current = model.model_json_schema(mode="serialization")
        for key, value in current.items():
            if key in {"title", "description"}:
                continue
            assert published.get(key) == value, f"{name}: {key} has drifted"


def test_a_real_envelope_and_checkpoint_validate_against_their_schemas(
    tmp_path: Path,
) -> None:
    """The schema accepts what the code actually writes, not only what it says."""
    import jsonschema

    root = tmp_path / "state"
    envelope = _envelope(
        "schema-task", replay=ReplayClass.CHECKPOINT_RESUMABLE, steps=("PLAN", "APPLY")
    )
    persist_envelope(root, envelope)
    sealed = persist_checkpoint(
        root, _checkpoint(envelope, last_step="PLAN", root=root)
    )
    schemas = Path(__import__("project_atlas").__file__).parent / "schemas"
    jsonschema.validate(
        envelope.model_dump(mode="json"),
        json.loads(
            (schemas / "continuation-task-envelope.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    jsonschema.validate(
        sealed.model_dump(mode="json"),
        json.loads(
            (schemas / "continuation-checkpoint.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )


# ====================================== projection into the durable layer


def test_a_dispatcher_run_leaves_a_capsule_a_replacement_session_can_use(
    tmp_path: Path,
) -> None:
    """The integration the mechanisms exist for, end to end.

    Found by running the operator journey rather than by reasoning: every piece
    of this layer passed its own test while a real dispatcher run produced a
    capsule that said "no task envelopes recorded under this state root". The
    mechanisms were correct and nothing fed them. This is the test that would
    have caught it.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(
        tmp_path,
        workspace,
        tasks=[_task("proj-a"), _task("proj-b", depends_on=["proj-a"])],
    )
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="projection",
    )

    first = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    ran = first.tick()
    assert ran.report is not None
    assert ran.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert ran.launched == 2
    assert any("continuation checkpoint" in note for note in ran.notes), ran.notes

    # Envelopes exist for every approved task, with the authority recorded.
    envelopes = {e.task_id: e for e in list_envelopes(state_root)}
    assert sorted(envelopes) == ["proj-a", "proj-b"]
    assert envelopes["proj-a"].allowed_paths == ("proj-a.txt",)
    assert "MERGE" in envelopes["proj-a"].forbidden_actions
    assert envelopes["proj-a"].budgets.max_model_calls == 0

    # And the capsule a replacement session reads is not empty.
    capsule = build_capsule(
        state_root, for_worker_id="agent-one", queue_root=queue_root
    )
    assert [t.task_id for t in capsule.tasks] == ["proj-a", "proj-b"]
    for task in capsule.tasks:
        assert task.disposition is Disposition.ALREADY_COMPLETE
        assert task.launchable is False
        assert "do not replay it" in task.next_action
        # A completed task must not be labelled as carrying a blocker.
        assert task.blockers == (), task.blockers

    rendered = render_capsule(capsule)
    assert "[ALREADY_COMPLETE] proj-a" in rendered
    assert len(rendered.encode("utf-8")) <= CAPSULE_MAX_BYTES

    # A replacement dispatcher, new session id, launches nothing.
    second = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    assert second.session_id != first.session_id
    assert second.tick().launched == 0
    assert reconcile_root(state_root, our_worker_id="agent-one")[0].launchable is False


def test_the_default_replay_class_is_the_cautious_one() -> None:
    """Silence must not mean "safe to repeat"."""
    from project_atlas.orchestration.program.continuation_projection import (
        replay_class_for,
    )

    mutating = ProgramTask.model_validate(_task("m"))
    assert replay_class_for(mutating) is ReplayClass.UNCERTAIN_EXTERNAL_EFFECT

    read_only = ProgramTask.model_validate({**_task("r"), "mutation_paths": []})
    assert replay_class_for(read_only) is ReplayClass.READ_ONLY_REPLAYABLE

    declared = ProgramTask.model_validate(
        {**_task("i"), "retry_safe_when_no_launch_evidence": True}
    )
    assert replay_class_for(declared) is ReplayClass.IDEMPOTENT_MUTATION


def test_materialising_envelopes_twice_does_not_move_the_authority(
    tmp_path: Path,
) -> None:
    """Rewriting an envelope would invalidate every checkpoint under it.

    ``reconcile_task`` fails closed when a checkpoint's envelope digest does
    not match the envelope on disk -- correctly, because the authority would
    have changed mid-flight. A projection that rewrote the envelope on every
    tick would trigger that against itself, so the second write must be a
    no-op.
    """
    from project_atlas.orchestration.program.continuation_projection import (
        materialise_envelopes,
    )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("idem-a")])
    loaded = load_program(program)
    state_root = tmp_path / "state"

    first = materialise_envelopes(
        loaded, state_root, candidate_head="a" * 40, candidate_tree="b" * 40
    )
    # A second pass with a DIFFERENT candidate must not move the recorded one.
    second = materialise_envelopes(
        loaded, state_root, candidate_head="c" * 40, candidate_tree="d" * 40
    )
    assert first[0].digest() == second[0].digest()
    assert second[0].candidate_head == "a" * 40


def test_a_projection_never_overwrites_an_unreadable_checkpoint(
    tmp_path: Path,
) -> None:
    """An unreadable record is evidence. Replacing it destroys the only trace.

    Two mechanisms defend this, and mutation says which one is load-bearing
    today: removing the projection's own refusal changes nothing, because
    ``persist_checkpoint`` rejects a sequence at or below the one on disk and a
    record it cannot read still yields sequence 1. Removing both lets the
    projection clobber the tampered file. So this test currently passes because
    of the sequence check -- recorded here rather than left to be assumed,
    since a projection that legitimately carried a higher sequence would slip
    straight past it.
    """
    from project_atlas.orchestration.program.continuation_projection import (
        project_checkpoints,
    )
    from project_atlas.orchestration.program.store import load_state

    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("tamper-a")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="op",
        reference="ref",
    )
    _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05).tick()

    path = next(checkpoints_dir(state_root).glob("*.checkpoint.json"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["next_action"] = "tampered"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    before = path.read_bytes()

    loaded = load_program(program)
    state = load_state(state_root)
    assert state is not None
    written = project_checkpoints(
        loaded,
        state_root,
        state=state,
        session_id="session.later",
        worktree=workspace,
        git_head="a" * 40,
        git_tree="b" * 40,
    )
    assert written == (), "a projection must not overwrite an unusable record"
    assert path.read_bytes() == before


# ============================ ATLAS-CONTINUITY-RELEASE-HANDOFF-001 gap closure
#
# Three properties the release handoff directive names explicitly, each of which
# the first round tested only in HALVES. Written after mapping the fourteen
# proofs onto the plan, which is what made the halves visible.


def test_pause_survives_a_restart_and_still_withholds_an_ELIGIBLE_task(
    tmp_path: Path,
) -> None:
    """Pause survives a restart AND withholds work that would otherwise run.

    The first round tested both halves and neither together:
    ``test_a_pause_record_survives_a_dispatcher_restart`` ran with an EMPTY
    queue, so it could show the record survived but not that it withheld
    anything, and the withholding test never restarted. A pause that survived
    as a file while quietly ceasing to block would have passed both.

    The eligibility is PROVEN rather than assumed, and that is the part that
    matters: `0 launches` is the same observation whether pause caused it or
    whether the work was never dispatchable. So the same dispatcher instance
    that reported PAUSED is made to launch the moment pause is cleared, with
    nothing else changed. ROLE_CONTENTION and RECONCILE_REQUIRED cannot be
    hiding here, because either would still be present after the clear.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(
        tmp_path, workspace, tasks=[_task("pr-one"), _task("pr-two")]
    )
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="pause across restart",
    )

    resident.request_pause(state_root, requested_by="operator:test")

    first = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    paused = first.tick()
    assert paused.state is DispatcherState.PAUSED
    assert paused.launched == 0

    # RESTART: a brand-new dispatcher object with its own session id, which is
    # what `clear_signals` runs against.
    second = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    assert second.session_id != first.session_id
    reason = second.run(max_ticks=2)
    assert reason is not DispatcherStopReason.OPERATOR_STOP
    assert second._launches == 0, "a restarted dispatcher must still honour pause"
    assert resident.pause_requested(state_root) is not None

    # The work was eligible the whole time: the entry never left a runnable
    # status, so nothing but pause was withholding it.
    entry = approved_queue.load_queue(queue_root).entries["continuation-program"]
    assert entry.status in approved_queue.RUNNABLE_STATUSES, entry.status
    assert entry.runs == 0, "pause must withhold before the program is ever run"
    assert not (workspace / "pr-one.txt").exists()

    # THE DISCRIMINATOR: clear pause, change nothing else, and the SAME
    # restarted dispatcher launches. That is what makes the zero above
    # attributable to pause rather than to contention or ineligibility.
    assert resident.clear_pause(state_root) is True
    ran = second.tick()
    assert ran.report is not None
    assert ran.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert ran.launched == 2, ran.notes
    for name in ("pr-one.txt", "pr-two.txt"):
        assert (workspace / name).read_text(encoding="utf-8").count("\n") == 1


def test_process_ownership_and_cleanup_on_the_REAL_dispatch_route(
    tmp_path: Path,
) -> None:
    """Ownership and cleanup on dispatcher -> supervisor -> adapter -> worker.

    The first round proved the identity rules against a helper this test file
    spawned itself. That establishes the rules and not the route: the pids that
    matter in production are the ones the ADAPTER records at spawn, through a
    code path the earlier test never entered.

    Everything below is read from durable records the real route wrote.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(
        tmp_path, workspace, tasks=[_task("own-a"), _task("own-b", depends_on=["own-a"])]
    )
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="real route cleanup",
    )
    before = _child_pids()

    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    ran = dispatcher.tick()
    assert ran.report is not None
    assert ran.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert ran.launched == 2

    state = _load_state(state_root)
    attempts = [a for a in state.attempts.values() if a.task_id in {"own-a", "own-b"}]
    assert len(attempts) == 2, sorted(state.attempts)

    for attempt in attempts:
        # The pid and its start identity travel together, on the real route.
        assert attempt.process_pid is not None, attempt.attempt_id
        assert attempt.process_start_identity, attempt.attempt_id
        assert attempt.process_start_identity != "unknown"
        # And each recorded worker is demonstrably finished -- established by
        # the identity pair, not by a timeout and not by a name match.
        liveness, why = process_liveness(
            attempt.process_pid, attempt.process_start_identity
        )
        assert liveness is Liveness.GONE, (attempt.attempt_id, liveness, why)

    # The adapter's in-flight records are cleared, so no later reader can be
    # handed a pid the operating system is free to reuse.
    leftover = sorted(p.name for p in launches_dir(state_root).glob("*.json"))
    assert leftover == [], leftover

    # No process this test caused is still running. Compared as a SET of pids
    # this process owns, never by pattern, name or working directory (R-12).
    after = _child_pids()
    assert after - before == set(), sorted(after - before)


def test_a_real_dispatcher_run_records_a_LIVE_task_not_only_completed_ones(
    tmp_path: Path,
) -> None:
    """The layer is fed with tasks that did NOT finish, which is the hard case.

    The first round showed a dispatcher run producing envelopes and checkpoints
    for tasks that all reached CERTIFIED. Every disposition was
    ALREADY_COMPLETE, so the capsule proved the plumbing and nothing about the
    state a replacement session actually needs to act on.

    Here task ``live-a`` runs a worker that CLAIMS success and changes nothing,
    so acceptance fails against what the supervisor observes locally, and
    ``live-b`` depends on it and therefore never becomes eligible. The capsule
    must show both, must not call either complete, and must give a next action
    for each.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(
        tmp_path,
        workspace,
        tasks=[_task("live-a"), _task("live-b", depends_on=["live-a"])],
        max_attempts_per_task=1,
    )
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=state_root,
        admitted_by="fixture-operator",
        reference="live task",
    )

    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05)
    with _fixture_mode("claim-only"):
        ran = dispatcher.tick()
    assert ran.report is not None
    assert ran.report.stop_reason is not ProgramStopReason.PROGRAM_COMPLETE
    assert ran.launched >= 1, "the worker must really have run"

    # A worker's confident claim is not acceptance: nothing was written.
    assert not (workspace / "live-a.txt").exists()

    capsule = build_capsule(
        state_root, for_worker_id="agent-one", queue_root=queue_root
    )
    by_id = {t.task_id: t for t in capsule.tasks}
    assert sorted(by_id) == ["live-a", "live-b"], sorted(by_id)

    for task in capsule.tasks:
        assert task.disposition is not Disposition.ALREADY_COMPLETE, task.task_id
        assert task.replay_class != ReplayClass.COMPLETED.value, task.task_id
        assert task.next_action, task.task_id

    # live-b never ran and must not be presented as if it had.
    assert by_id["live-b"].last_completed_step is None
    checkpoint_b = load_checkpoint(state_root, "live-b")
    assert checkpoint_b is not None
    assert checkpoint_b.terminal is False
    assert checkpoint_b.consumed_budget.launches == 0

    rendered = render_capsule(capsule)
    assert "live-a" in rendered and "live-b" in rendered
    assert "do not replay it" not in rendered


# ---------------------------------------------------------- new helpers


def _child_pids() -> set[int]:
    """Pids whose parent is THIS process, read from /proc.

    A set of pids we own, never a name or a command-line pattern. R-12 in this
    program exists because a pattern kill once took out a peer session's
    process, and a pattern *check* has the matching failure: it reports
    strangers as ours.
    """
    me = os.getpid()
    found: set[int] = set()
    proc = Path("/proc")
    if not proc.is_dir():  # pragma: no cover - POSIX-only, as is this test file
        return found
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            status = (entry / "status").read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in status.splitlines():
            if line.startswith("PPid:"):
                if int(line.split()[1]) == me:
                    found.add(int(entry.name))
                break
    return found


@contextlib.contextmanager
def _fixture_mode(mode: str) -> Iterator[None]:
    """Run the fixture worker in one of its declared modes."""
    previous = os.environ.get("ATLAS_FIXTURE_MODE")
    os.environ["ATLAS_FIXTURE_MODE"] = mode
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ATLAS_FIXTURE_MODE", None)
        else:
            os.environ["ATLAS_FIXTURE_MODE"] = previous


# ================== findings from independent verification (Agent 9)


def test_a_capsule_spans_every_admitted_programs_state_root(tmp_path: Path) -> None:
    """IV finding F1: the capsule must not report emptiness that is a wrong lookup.

    The dispatcher publishes its heartbeat under its OWN root -- the one on the
    command line -- while each admitted program keeps its task records under the
    state root in its queue entry. Those are allowed to differ and by design do
    whenever one dispatcher serves several programs.

    Reading only the dispatcher's root meant a healthy, completed program
    produced a capsule saying "no task envelopes recorded under this state
    root". An independent verifier hit it on a real run and nearly filed a FAIL
    against their own configuration twice before reading the source. The capsule
    is the ONLY surface a replacement session has; an absence it reports must be
    a real absence.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("split-one")])
    dispatcher_root = tmp_path / "dispatcher-root"
    program_state = tmp_path / "program-state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()

    # The split: admitted against one root, dispatcher run against another.
    approved_queue.admit(
        queue_root,
        program_path=program,
        program_id="continuation-program",
        state_root=program_state,
        admitted_by="fixture-operator",
        reference="F1",
    )
    dispatcher = _dispatcher(dispatcher_root, queue_root, tick_seconds=0.5, quantum=0.05)
    ran = dispatcher.tick()
    assert ran.report is not None
    assert ran.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert ran.launched == 1

    # The records really are in the other root -- this is the split, not a fiction.
    assert list_envelopes(program_state), "the program keeps its own records"
    assert list_envelopes(dispatcher_root) == ()

    capsule = build_capsule(
        dispatcher_root, for_worker_id="agent-one", queue_root=queue_root
    )
    # ONE capsule carries both halves: the dispatcher's health AND the tasks.
    assert capsule.dispatcher, "the heartbeat lives under the dispatcher root"
    assert [t.task_id for t in capsule.tasks] == ["split-one"]
    assert capsule.tasks[0].state_root == str(program_state.resolve())
    assert str(program_state.resolve()) in capsule.state_roots_scanned
    assert capsule.root_split_note, "a split must be stated, not inferred"

    rendered = render_capsule(capsule)
    assert "no task envelopes recorded" not in rendered
    assert "split-one" in rendered
    assert "records in:" in rendered
    assert str(program_state.resolve()) in rendered


def test_an_empty_capsule_says_which_roots_it_actually_looked_in(
    tmp_path: Path,
) -> None:
    """The other half of F1: a genuine emptiness must still name its scope.

    "Nothing to resume" and "you pointed me at the wrong root" read identically
    unless the capsule says where it looked. Without a --queue-root it has only
    one root to offer, and it must say so rather than implying it searched.
    """
    root = tmp_path / "state"
    capsule = build_capsule(root, for_worker_id="nobody")
    assert capsule.tasks == ()
    assert capsule.state_roots_scanned == (str(root.resolve()),)
    assert "re-run with --queue-root" in capsule.root_split_note
    rendered = render_capsule(capsule)
    assert "no task records found in 1 scanned root(s)" in rendered
    assert str(root.resolve()) in rendered


def test_every_durable_reader_refuses_a_schema_invalid_document_with_a_code(
    tmp_path: Path,
) -> None:
    """IV finding F3: valid JSON that is not our schema must not be a traceback.

    Found by an independent verifier while building a control: a queue file that
    parsed as JSON but had ``entries`` as a list escaped as a raw
    ``pydantic_core.ValidationError``. It failed loudly, which beats failing
    silently, but a traceback names no stable code a script can branch on and
    does not say which file is at fault.

    It was never one call site. EIGHT readers in this layer called
    ``model_validate`` and only the checkpoint one wrapped it, so the same hole
    existed for envelopes, decisions and the heartbeat. All of them now funnel
    through ``read_durable``, and this test walks every one — a fix applied to
    the reported file alone would pass a test that only checked the queue.

    Schema-invalid is deliberately NOT treated as missing: "never written" and
    "written wrongly" are different facts and only the first is safe to read as
    an absence.
    """
    from project_atlas.orchestration.program.continuation import (
        CheckpointError,
        checkpoints_dir,
        envelopes_dir,
    )
    from project_atlas.orchestration.program.decisions import decisions_dir
    from project_atlas.orchestration.program.resident import (
        DispatcherError,
        dispatcher_dir,
        heartbeat_path,
    )

    root = tmp_path / "state"
    valid_json_wrong_shape = '{"schema_version": 1, "entries": []}'

    # queue
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.queue_path(queue_root).write_text(
        '{"schema_version":1,"package_id":"AS-ORCH-DURABLE-CONTINUATION-001",'
        '"entries":[]}',
        encoding="utf-8",
    )
    with pytest.raises(approved_queue.QueueError) as q:
        approved_queue.load_queue(queue_root)
    assert q.value.code == "QUEUE_SCHEMA_INVALID"
    assert "entries" in str(q.value)

    # envelope
    envelopes_dir(root).mkdir(parents=True, exist_ok=True)
    (envelopes_dir(root) / "deadbeef.envelope.json").write_text(
        valid_json_wrong_shape, encoding="utf-8"
    )
    with pytest.raises(EnvelopeError) as e:
        list_envelopes(root)
    assert e.value.code == "ENVELOPE_SCHEMA_INVALID"

    # checkpoint
    checkpoints_dir(root).mkdir(parents=True, exist_ok=True)
    (checkpoints_dir(root) / "deadbeef.checkpoint.json").write_text(
        valid_json_wrong_shape, encoding="utf-8"
    )
    with pytest.raises(CheckpointError) as c:
        list_checkpoints(root)
    assert c.value.code in {"CHECKPOINT_SCHEMA_INVALID", "CHECKPOINT_MALFORMED"}

    # decision
    decisions_dir(root).mkdir(parents=True, exist_ok=True)
    (decisions_dir(root) / "deadbeef.decision.json").write_text(
        valid_json_wrong_shape, encoding="utf-8"
    )
    with pytest.raises(decisions.DecisionError) as d:
        decisions.list_decisions(root)
    assert d.value.code == "DECISION_SCHEMA_INVALID"

    # heartbeat
    dispatcher_dir(root).mkdir(parents=True, exist_ok=True)
    heartbeat_path(root).write_text(valid_json_wrong_shape, encoding="utf-8")
    with pytest.raises(DispatcherError) as h:
        read_heartbeat(root)
    assert h.value.code == "HEARTBEAT_SCHEMA_INVALID"


def test_an_unreadable_queue_stops_the_run_instead_of_burning_its_tick_budget(
    tmp_path: Path,
) -> None:
    """IV finding F2, narrowed by the verifier: it must not look like a timeout.

    Their correction to their own wording is the precise version and it is the
    one worth defending: the run DID differ from an empty queue, by reporting
    ``TICK_BUDGET_REACHED`` instead of ``QUEUE_DRAINED``. But "ran out of ticks"
    is equally what a slow or busy queue produces, it names no file, and with
    five ticks it burned all five in silence.

    A dispatcher whose only source of work is unreadable has nothing it could
    discover by waiting, so it now stops on the first tick with a reason of its
    own. The two failure shapes are kept apart as well: damaged bytes and a
    valid document of the wrong schema are different operator problems.
    """
    cases = {
        "corrupt": ("{not json", "QUEUE_UNREADABLE"),
        "schema_invalid": (
            '{"schema_version":1,"package_id":"AS-ORCH-DURABLE-CONTINUATION-001"'
            ',"entries":[]}',
            "QUEUE_SCHEMA_INVALID",
        ),
    }
    for name, (content, expected_code) in cases.items():
        state_root = tmp_path / f"{name}-state"
        queue_root = tmp_path / f"{name}-queue"
        queue_root.mkdir()
        queue_file = approved_queue.queue_path(queue_root)
        queue_file.write_text(content, encoding="utf-8")
        before = queue_file.read_bytes()

        dispatcher = _dispatcher(
            state_root, queue_root, tick_seconds=0.5, quantum=0.05
        )
        reason = dispatcher.run(max_ticks=5)

        # 1. a reason of its own, not a timeout
        assert reason is DispatcherStopReason.QUEUE_UNREADABLE, (name, reason)
        assert reason is not DispatcherStopReason.TICK_BUDGET_REACHED
        # it stopped at once rather than burning the budget in silence
        assert dispatcher._ticks == 1, (name, dispatcher._ticks)
        # 2. still fails closed
        assert dispatcher._launches == 0
        assert dispatcher._programs_started == 0
        # 3. THE AUTHORITATIVE INPUT IS UNTOUCHED. A run that "repaired" the
        #    queue would destroy the evidence of what was wrong with it.
        assert queue_file.read_bytes() == before, name
        # 4. the code, which is the assertion that fails on the predecessor;
        #    launches == 0 already passed there and would prove nothing.
        beat = read_heartbeat(state_root)
        assert beat is not None
        assert beat.queue_status == "UNREADABLE", name
        assert beat.queue_error_code == expected_code, (name, beat.queue_error_code)
        assert str(queue_file) in (beat.queue_error or ""), name
        assert beat.terminal_reason is DispatcherStopReason.QUEUE_UNREADABLE


def test_an_unreadable_queue_is_distinguishable_from_an_empty_one_AT_THE_CLI(
    tmp_path: Path,
) -> None:
    """IV finding F2: fail closed is not enough; it must fail DISTINGUISHABLY.

    The in-process test above already asserted the tick reports
    WAITING_ON_WORK with a note. That was true and invisible: the CLI `run`
    payload carried neither, so from the operator's surface a corrupt manifest
    and an empty queue both showed exit 0, zero launches and no error. The
    verifier compared the two outputs and could not tell them apart.

    Three independent signals now separate them, and all three are asserted
    because any one of them could be dropped by a refactor.
    """
    corrupt_state = tmp_path / "corrupt-state"
    corrupt_queue = tmp_path / "corrupt-queue"
    corrupt_queue.mkdir()
    approved_queue.queue_path(corrupt_queue).write_text("{not json", encoding="utf-8")

    empty_state = tmp_path / "empty-state"
    empty_queue = tmp_path / "empty-queue"
    empty_queue.mkdir()

    def _run(state: Path, queue: Path) -> tuple[dict[str, Any], int]:
        completed = subprocess.run(
            [
                sys.executable, "-m", CLI, "program", "dispatcher",
                "--state-root", str(state), "--queue-root", str(queue),
                "--action", "run", "--max-ticks", "1", "--tick-seconds", "1",
            ],
            capture_output=True, text=True, timeout=120, check=False,
        )
        return json.loads(completed.stdout), completed.returncode

    corrupt, corrupt_rc = _run(corrupt_state, corrupt_queue)
    empty, empty_rc = _run(empty_state, empty_queue)

    # Both fail closed: nothing dispatched either way.
    assert corrupt["launches"] == 0 and empty["launches"] == 0
    assert corrupt["programs_started"] == 0 and empty["programs_started"] == 0

    # 1. queue_status
    assert corrupt["queue_status"] == "UNREADABLE"
    assert empty["queue_status"] == "READABLE"
    # 2. a machine-readable code and an error naming the path and the parse fault
    assert corrupt["code"] == "QUEUE_UNREADABLE"
    assert "unreadable" in corrupt["error"]
    assert str(approved_queue.queue_path(corrupt_queue)) in corrupt["error"]
    assert "code" not in empty and "error" not in empty
    # 3. process exit status
    assert corrupt_rc == EXIT_ERROR_CODE, corrupt_rc
    assert empty_rc == 0, empty_rc

    # And the heartbeat carries it too, for a reader who arrives later.
    beat = read_heartbeat(corrupt_state)
    assert beat is not None
    assert beat.queue_status == "UNREADABLE"
    assert beat.queue_error


# ============ ATLAS-RESIDENT-INTEGRATION-CLOSURE-001: the resident path
#
# Everything below exercises the RESIDENT dispatcher path specifically. The
# finite `program start` path was covered all along, and that is exactly why
# these defects survived: D3, D4 and D5 are all reachable only through
# `program dispatcher`, and every one of them was found by running the
# candidate as a service rather than by a test.


def _enrol(registry: Path, program: Path, *, agent_id: str, role: str = "impl",
           workspace: Path | None = None) -> None:
    """Enrol and assign through the intended enrollment interface."""
    from project_atlas.orchestration.program.enrollment import assign, enroll

    enroll(
        registry,
        agent_id=agent_id,
        role=role,
        adapter="local-command",
        workspace_root=workspace or program.parent,
        enrolled_by="test-operator",
    )
    assign(registry, agent_id=agent_id, program_path=program, assigned_by="test-operator")


def test_D5_an_active_assigned_enrolment_dispatches_on_the_RESIDENT_path(
    tmp_path: Path,
) -> None:
    """D5: the resident path never bound enrolments, so registry use froze it.

    `ResidentDispatcher` threaded `registry_root` into `ProgramSupervisor` but
    never passed `enrolled_agents`, so `_apply_enrollments` could not run. The
    program's profiles kept their placeholder agent ids and every task was held
    with "no active enrolled agent is bound" -- with an ACTIVE, correctly
    assigned agent sitting in the registry.

    It failed CLOSED, which is why nothing caught fire, but a
    registry-configured deployment could never dispatch at all. The finite
    `program start` path bound enrolments the whole time; only this one did not.

    Repaired through the enrollment interface, not around it: the same ACTIVE
    filter the finite path applies.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("d5-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    registry = tmp_path / "registry"
    _enrol(registry, program, agent_id="agent-one", workspace=workspace)

    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="D5",
    )
    dispatcher = ResidentDispatcher(
        root=state_root, queue_root=queue_root,
        checkout=Path(__file__).resolve().parents[2],
        registry_root=registry, tick_seconds=0.5, wake_quantum_seconds=0.05,
    )
    ran = dispatcher.tick()

    assert ran.report is not None
    assert ran.launched == 1, ran.notes
    assert ran.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert (workspace / "d5-one.txt").read_text(encoding="utf-8").count("\n") == 1


@pytest.mark.parametrize(
    ("scenario", "detail"),
    [
        ("missing", "no agent enrolled at all"),
        ("suspended", "enrolled and assigned, then SUSPENDED"),
        ("mismatched_role", "ACTIVE but enrolled for a role this program has not"),
        ("unassigned", "ACTIVE and enrolled but assigned to another program"),
    ],
)
def test_D5_negatives_no_usable_enrolment_dispatches_NOTHING(
    tmp_path: Path, scenario: str, detail: str
) -> None:
    """Binding must not become a way to dispatch without authority.

    The repair for D5 adds a path from the registry to a live dispatch, so each
    way that path can be *wrong* is asserted separately. A fix that bound
    whatever it found would turn a frozen dispatcher into an unbound one, which
    is worse than the defect.
    """
    from project_atlas.orchestration.program.enrollment import AgentStatus, set_status

    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("neg-one")])
    other = _program_file(
        tmp_path, workspace, tasks=[_task("other-one")],
        program_id="other-program", name="other.json",
    )
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    registry = tmp_path / "registry"

    if scenario == "suspended":
        _enrol(registry, program, agent_id="agent-one", workspace=workspace)
        set_status(registry, agent_id="agent-one", status=AgentStatus.SUSPENDED)
    elif scenario == "mismatched_role":
        # Stronger than expected, and worth asserting where it actually
        # happens: the enrollment interface refuses the ASSIGNMENT outright
        # when the program declares no such role, so a mismatched agent can
        # never reach the dispatcher at all. Asserting a zero-launch dispatch
        # here would have tested a path the guard makes unreachable.
        from project_atlas.orchestration.program.enrollment import EnrollmentError

        with pytest.raises(EnrollmentError, match="declares no role"):
            _enrol(registry, program, agent_id="agent-one", role="verifier",
                   workspace=workspace)
    elif scenario == "unassigned":
        _enrol(registry, other, agent_id="agent-one", workspace=workspace)
    # "missing": nothing enrolled

    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference=scenario,
    )
    dispatcher = ResidentDispatcher(
        root=state_root, queue_root=queue_root,
        checkout=Path(__file__).resolve().parents[2],
        registry_root=registry, tick_seconds=0.5, wake_quantum_seconds=0.05,
    )
    ran = dispatcher.tick()

    assert ran.launched == 0, (scenario, detail, ran.notes)
    assert not (workspace / "neg-one.txt").exists(), (scenario, detail)
    if ran.report is not None:
        assert ran.report.stop_reason is not ProgramStopReason.PROGRAM_COMPLETE


def test_D5_authority_withdrawn_between_dispatches_stops_the_next_one(
    tmp_path: Path,
) -> None:
    """Authority is re-read before EVERY dispatch, not cached at bind time.

    Two tasks, one agent. The agent is suspended after the first task succeeds,
    so the second must not run -- and the discriminator is that the first one
    DID, against the same dispatcher and the same registry.
    """
    from project_atlas.orchestration.program.enrollment import AgentStatus, set_status

    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(
        tmp_path, workspace,
        tasks=[_task("auth-a"), _task("auth-b", depends_on=["auth-a"])],
    )
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    registry = tmp_path / "registry"
    _enrol(registry, program, agent_id="agent-one", workspace=workspace)
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="authority",
    )

    dispatcher = ResidentDispatcher(
        root=state_root, queue_root=queue_root,
        checkout=Path(__file__).resolve().parents[2],
        registry_root=registry, tick_seconds=0.5, wake_quantum_seconds=0.05,
        # one worker, so the tasks are strictly sequential and the withdrawal
        # lands between them rather than during a race
    )
    # Let the first task run, then withdraw authority mid-program.
    import threading

    def _suspend_after_first() -> None:
        for _ in range(200):
            if (workspace / "auth-a.txt").exists():
                set_status(registry, agent_id="agent-one",
                           status=AgentStatus.SUSPENDED)
                return
            time.sleep(0.05)

    watcher = threading.Thread(target=_suspend_after_first, daemon=True)
    watcher.start()
    ran = dispatcher.tick()
    watcher.join(timeout=15)

    assert (workspace / "auth-a.txt").exists(), "the first task must have run"
    assert not (workspace / "auth-b.txt").exists(), (
        "authority was withdrawn before the second dispatch and it ran anyway"
    )
    assert ran.report is not None
    assert ran.report.stop_reason is not ProgramStopReason.PROGRAM_COMPLETE


def test_D3_a_program_the_supervisor_REFUSES_quarantines_instead_of_killing(
    tmp_path: Path,
) -> None:
    """D3: reproduced first, then repaired. It took the resident service down.

    Two admitted programs sharing one state root makes `supervisor.start()`
    raise PROGRAM_MISMATCH. `_run_entry` caught only `ProgramLoadError`, so it
    escaped `tick()` and `run()`, the CLI exited non-zero, and systemd restarted
    straight back into the identical error until the start limit tripped. One
    misconfigured entry stopped the whole dispatcher.

    Observed live on the authorized user-service pilot before the repair:
    Result=exit-code, "restart counter is at 3", start-limit-hit.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    first = _program_file(tmp_path, workspace, tasks=[_task("q-one")])
    second = _program_file(
        tmp_path, workspace, tasks=[_task("q-two")],
        program_id="second-program", name="second.json",
    )
    shared_state = tmp_path / "shared-state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    for path, pid in ((first, "continuation-program"), (second, "second-program")):
        approved_queue.admit(
            queue_root, program_path=path, program_id=pid,
            state_root=shared_state, admitted_by="op", reference="D3",
        )

    dispatcher = _dispatcher(shared_state, queue_root, tick_seconds=0.5, quantum=0.05)
    # THE ASSERTION: run() completes. Before the repair this raised out of the
    # loop and the process exited non-zero.
    reason = dispatcher.run(max_ticks=4)
    assert reason is not DispatcherStopReason.FATAL_ERROR

    entries = approved_queue.load_queue(queue_root).entries
    quarantined = [
        e for e in entries.values()
        if e.status is approved_queue.QueueEntryStatus.QUARANTINED
    ]
    assert quarantined, {k: v.status.value for k, v in entries.items()}
    assert any("PROGRAM_MISMATCH" in (e.last_stop_reason or "") for e in quarantined), (
        [e.last_stop_reason for e in entries.values()]
    )
    # And the dispatcher is still usable afterwards.
    assert dispatcher.tick() is not None


def test_D4_a_runnable_entry_that_cannot_progress_does_not_spin(
    tmp_path: Path,
) -> None:
    """D4: reproduced by measurement, then repaired.

    A queue entry that stays runnable while its program returns immediately --
    NO_ELIGIBLE_WORK from an owner-gated task -- reported RUNNING_PROGRAM, and
    the loop slept only for IDLE/PAUSED/WAITING. So it never slept: measured on
    the pilot at 186 program runs in 5s against an expected 3, 24% of one core,
    the entry's run counter reaching 5162.

    The oracle is WALL TIME, not a counter: a loop that honours its tick
    interval cannot finish N ticks faster than (N-1) intervals. A run counter
    could be satisfied by a slower spin; elapsed time cannot.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    # The stop reason has to leave the entry RUNNABLE, which is what made the
    # pilot spin. An owner gate does not: it routes to the decision queue and
    # quarantines after one run. An unresolvable external precondition does --
    # the task never becomes eligible, the program stops NO_ELIGIBLE_WORK, and
    # the entry goes back to PENDING for the dispatcher to pick up again.
    gated = _task("gated-one")
    gated["external_precondition"] = {
        "precondition_id": "never-resolves",
        "external_id": "fixture-never",
        "probe_argv": [sys.executable, "-c", "raise SystemExit(3)"],
        "pass_exit_code": 0,
        "poll_interval_seconds": 0.0,
        "probe_timeout_seconds": 10,
        "max_wait_seconds": 3600.0,
    }
    program = _program_file(tmp_path, workspace, tasks=[gated])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="D4",
    )

    tick = 0.4
    dispatcher = _dispatcher(state_root, queue_root, tick_seconds=tick, quantum=0.05)
    started = time.monotonic()
    dispatcher.run(max_ticks=4)
    elapsed = time.monotonic() - started

    # The entry stayed runnable and nothing was ever launched -- i.e. this is
    # genuinely the spin condition and not an idle queue.
    entry = approved_queue.load_queue(queue_root).entries["continuation-program"]
    assert entry.status in approved_queue.RUNNABLE_STATUSES, entry.status
    assert dispatcher._launches == 0
    assert not (workspace / "gated-one.txt").exists()

    assert elapsed >= tick * 3 * 0.8, (
        f"4 ticks finished in {elapsed:.2f}s with a {tick}s interval: the loop "
        "is not waiting between ticks"
    )
    assert entry.runs <= 6, f"program run {entry.runs} times in 4 ticks"


def test_the_resident_path_leaves_no_test_owned_processes(tmp_path: Path) -> None:
    """Cleanup on the resident path, over every scenario this module drives."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("leak-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    registry = tmp_path / "registry"
    _enrol(registry, program, agent_id="agent-one", workspace=workspace)
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="leak",
    )
    before = _child_pids()
    dispatcher = ResidentDispatcher(
        root=state_root, queue_root=queue_root,
        checkout=Path(__file__).resolve().parents[2],
        registry_root=registry, tick_seconds=0.5, wake_quantum_seconds=0.05,
    )
    assert dispatcher.tick().launched == 1
    assert _child_pids() - before == set(), sorted(_child_pids() - before)
    assert launches_dir(state_root).exists() is False or not list(
        launches_dir(state_root).glob("*.json")
    )


def test_the_resident_path_gives_the_capsule_ACTUAL_task_records(
    tmp_path: Path,
) -> None:
    """A capsule from a registry-bound resident run is not empty."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("cap-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    registry = tmp_path / "registry"
    _enrol(registry, program, agent_id="agent-one", workspace=workspace)
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="capsule",
    )
    ResidentDispatcher(
        root=state_root, queue_root=queue_root,
        checkout=Path(__file__).resolve().parents[2],
        registry_root=registry, tick_seconds=0.5, wake_quantum_seconds=0.05,
    ).tick()

    capsule = build_capsule(
        state_root, for_worker_id="agent-one", queue_root=queue_root
    )
    assert [t.task_id for t in capsule.tasks] == ["cap-one"]
    assert capsule.tasks[0].disposition is Disposition.ALREADY_COMPLETE
    assert capsule.tasks[0].launchable is False
    assert "do not replay it" in render_capsule(capsule)


def test_D2_admit_refuses_to_default_the_state_root(tmp_path: Path) -> None:
    """D-2: a default cannot be right for a path whose writability is unknown.

    Admitting with no --state-root used to resolve it to the program file's own
    directory, which a hardened deployment mounts read-only. The dispatcher
    accepted the work and could not write the durable records -- the exact ones
    a replacement session needs. It survives install and systemd-analyze and
    fails only on first dispatch.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("d2-one")])
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    completed = subprocess.run(
        [sys.executable, "-m", CLI, "program", "queue",
         "--queue-root", str(queue_root), "--action", "admit",
         "--program", str(program), "--admitted-by", "op",
         "--reference", "D2 no state root"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    payload = json.loads(completed.stdout)
    assert payload["code"] == "ADMIT_STATE_ROOT_REQUIRED", payload
    assert completed.returncode == 2, completed.returncode
    assert approved_queue.load_queue(queue_root).entries == {}


def test_D6_a_stale_envelope_must_not_shadow_a_COMPLETED_record(
    tmp_path: Path,
) -> None:
    """D-6: which record wins is decided by evidence, not by scan order.

    `_scan_roots` puts the dispatcher's own root first, and that root is where
    debris lands: `materialise_envelopes` writes envelopes BEFORE a program
    runs, so a run that aborts before any checkpoint leaves an envelope with no
    checkpoint. Under first-root-wins that stale envelope shadowed the
    authoritative terminal record in the program's own root, and the capsule
    reported START_FRESH / launchable=True for completed work.

    Not a replay -- the queue entry is terminal so nothing re-dispatches. The
    damage is to the capsule, which is the only surface a replacement session
    has: it pointed that session at finished work.

    Found by the state-compatibility check on a real deployment, where the
    debris had been left by an earlier defect (D-3) in the same lane. One
    defect manufactured the precondition for another.

    The precondition is asserted, not assumed: the dispatcher root really must
    hold an envelope with no checkpoint, or this test proves nothing.
    """
    dispatcher_root = tmp_path / "dispatcher-root"
    program_root = tmp_path / "program-state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    workspace = tmp_path / "ws"
    workspace.mkdir()

    envelope = _envelope("shadowed", replay=ReplayClass.IDEMPOTENT_MUTATION)
    # debris in the root that is scanned FIRST
    persist_envelope(dispatcher_root, envelope)
    # the authoritative, completed record in the program's own root
    persist_envelope(program_root, envelope)
    persist_checkpoint(
        program_root,
        _checkpoint(
            envelope, terminal=True, replay=ReplayClass.COMPLETED, root=program_root
        ),
    )
    program = _program_file(tmp_path, workspace, tasks=[_task("shadowed")])
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=program_root, admitted_by="op", reference="D6",
    )

    # THE PRECONDITION, asserted.
    assert [e.task_id for e in list_envelopes(dispatcher_root)] == ["shadowed"]
    assert load_checkpoint(dispatcher_root, "shadowed") is None, (
        "the debris must be an envelope WITHOUT a checkpoint"
    )
    assert load_checkpoint(program_root, "shadowed") is not None

    capsule = build_capsule(
        dispatcher_root, for_worker_id=envelope.worker_id, queue_root=queue_root
    )
    task = next(t for t in capsule.tasks if t.task_id == "shadowed")

    assert task.disposition is Disposition.ALREADY_COMPLETE, task.disposition
    assert task.launchable is False
    assert task.state_root == str(program_root.resolve()), (
        "the capsule must read the root holding the stronger evidence"
    )
    assert "do not replay it" in task.next_action
    # and both roots are still reported, so the situation stays visible
    assert len(capsule.state_roots_scanned) == 2


def test_D6_evidence_precedence_orders_terminal_over_checkpoint_over_envelope(
    tmp_path: Path,
) -> None:
    """The ordering IS the fix, so it is asserted directly rather than inferred."""
    from project_atlas.orchestration.program.capsule import _evidence_rank

    envelope = _envelope("ranked", replay=ReplayClass.IDEMPOTENT_MUTATION)

    bare = tmp_path / "bare"
    persist_envelope(bare, envelope)

    running = tmp_path / "running"
    persist_envelope(running, envelope)
    persist_checkpoint(running, _checkpoint(envelope, terminal=False, root=running))

    done = tmp_path / "done"
    persist_envelope(done, envelope)
    persist_checkpoint(
        done,
        _checkpoint(envelope, terminal=True, replay=ReplayClass.COMPLETED, root=done),
    )

    assert _evidence_rank(done, "ranked") > _evidence_rank(running, "ranked")
    assert _evidence_rank(running, "ranked") > _evidence_rank(bare, "ranked")
    # a root that has never heard of the task ranks as envelope-only, which is
    # the floor for "present"; it is never allowed to outrank a real record.
    assert _evidence_rank(tmp_path / "empty", "ranked") <= _evidence_rank(bare, "ranked")


def _next_action_for_start(task_id: str) -> str:
    """What the capsule says when it believes a task has never run."""
    return f"Start task {task_id}."


def test_a_LOST_record_whose_program_is_COMPLETE_fails_closed(
    tmp_path: Path,
) -> None:
    """REQ-1's consequence: a lost record must not read as work never started.

    The D-6 fix chooses the strongest SURVIVING record. It cannot help when the
    strongest survivor is a bare envelope because the terminal checkpoint was
    lost -- an interrupted write whose rename never became durable, say. An
    independent verifier measured exactly that on the D-6 candidate and found
    START_FRESH, launchable=True, "Start task t1." The fix had closed
    "which record wins", not "the record is gone".

    The signal was already in the capsule and unused: it printed
    by_status={'COMPLETE': [...]} a few lines above the instruction to start
    that program's task. A task with no durable record whose owning program is
    recorded COMPLETE is contradictory state, and contradictory state fails
    closed rather than resolving toward redoing finished work.

    Both arms are asserted, because the override must not fire for a task that
    genuinely never ran.
    """
    from project_atlas.orchestration.program.continuation import checkpoints_dir

    workspace = tmp_path / "ws"
    workspace.mkdir()
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()

    program = _program_file(tmp_path, workspace, tasks=[_task("lost-one")])
    envelope = _envelope(
        "lost-one",
        replay=ReplayClass.IDEMPOTENT_MUTATION,
        program_id="continuation-program",
    )
    persist_envelope(state_root, envelope)
    persist_checkpoint(
        state_root,
        _checkpoint(
            envelope, terminal=True, replay=ReplayClass.COMPLETED, root=state_root
        ),
    )
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="REQ-1",
    )
    approved_queue.update_entry(
        queue_root, "continuation-program",
        status=approved_queue.QueueEntryStatus.COMPLETE,
    )

    intact = build_capsule(
        state_root, for_worker_id=envelope.worker_id, queue_root=queue_root
    ).tasks[0]
    assert intact.disposition is Disposition.ALREADY_COMPLETE
    assert intact.launchable is False

    # Lose the terminal checkpoint, keeping everything else.
    for path in checkpoints_dir(state_root).glob("*.checkpoint.json"):
        path.unlink()

    lost = build_capsule(
        state_root, for_worker_id=envelope.worker_id, queue_root=queue_root
    ).tasks[0]
    assert lost.disposition is Disposition.RECONCILE_REQUIRED, lost.disposition
    assert lost.launchable is False, "a lost record must never read as launchable"
    # Keyed on the status NAME, which is structural, not on the sentence around
    # it. An earlier assertion in this module matched prose and broke the
    # moment the prose improved; that is a test discouraging better messages.
    assert "COMPLETE" in lost.reason
    assert lost.next_action != _next_action_for_start(lost.task_id)


def test_the_lost_record_override_does_NOT_fire_for_work_that_never_ran(
    tmp_path: Path,
) -> None:
    """The other arm. A genuinely new task must still be startable.

    An override that made everything unlaunchable would pass the test above and
    break the layer, so the discriminator is a task whose program is NOT
    complete: it must stay START_FRESH and launchable.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("fresh-one")])
    envelope = _envelope(
        "fresh-one",
        replay=ReplayClass.IDEMPOTENT_MUTATION,
        program_id="continuation-program",
    )
    persist_envelope(state_root, envelope)
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="control",
    )
    # entry stays PENDING -- the program has not completed

    task = build_capsule(
        state_root, for_worker_id=envelope.worker_id, queue_root=queue_root
    ).tasks[0]
    assert task.disposition is Disposition.START_FRESH, task.disposition
    assert task.launchable is True, "never-run work must stay startable"


def test_G4_empty_execution_capture_says_nobody_looked_not_nothing_happened(
    tmp_path: Path,
) -> None:
    """G4: distinguish an unobserved task from a task that did nothing.

    A verifier measured a real completed run whose task demonstrably mutated
    its workspace and found artifacts=[], changed_files=[], commands=[] --
    a replacement session could learn THAT a task completed and nothing about
    what it did. Worse, those empty lists were indistinguishable from a task
    that genuinely touched nothing.

    The first fix was a marker (G4a): the projection declared NOT_CAPTURED
    and the capsule rendered it. The verifier then split the case: the
    declaration closed G4a, and G4b stayed open because no production writer
    ever produced an observed capture -- while the supervisor DID observe the
    command (adapter transcript) and the artifact (its own acceptance check).
    This test now asserts G4b: those observations are carried, per field,
    from their named records; changed_files, which nobody observes, stays
    UNAVAILABLE with a scoped reason. Nothing is inferred from a diff.

    THE PRECONDITION IS ASSERTED: the workspace must actually have changed, or
    capture proves nothing.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task("g4-one")])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="G4",
    )
    ran = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05).tick()
    assert ran.report is not None
    assert ran.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE

    # PRECONDITION: the worker really did mutate the workspace.
    produced = workspace / "g4-one.txt"
    assert produced.is_file(), "the fixture must actually have written something"
    assert produced.read_text(encoding="utf-8").strip(), "and it must be non-empty"

    checkpoint = load_checkpoint(state_root, "g4-one")
    assert checkpoint is not None
    from project_atlas.orchestration.program.continuation import (
        CaptureStatus,
        ExecutionCapture,
    )

    # G4b. The marker alone (G4a, the earlier fix) said "nobody looked" over a
    # run the supervisor HAD looked at: its adapter wrote the child's argv and
    # exit status, and its own acceptance check read the produced file. Those
    # two observations are now carried, each from its named record.
    assert checkpoint.execution_capture is ExecutionCapture.OBSERVED
    (command,) = checkpoint.commands
    assert command.argv == (sys.executable, str(FIXTURE_WORKER))
    assert command.exit_status == 0
    assert "g4-one" in command.output_tail
    assert command.started_at and command.ended_at
    assert checkpoint.capture.commands.status is CaptureStatus.CAPTURE_AVAILABLE
    source = checkpoint.capture.commands.source
    assert source.startswith("evidence/") and source.endswith(".transcript.json")
    assert (evidence_dir(state_root) / Path(source).name).is_file()

    (artifact,) = checkpoint.artifacts
    assert artifact.path == "g4-one.txt"
    assert artifact.sha256 == hashlib.sha256(produced.read_bytes()).hexdigest()
    assert artifact.bytes == produced.stat().st_size
    assert checkpoint.capture.artifacts.status is CaptureStatus.CAPTURE_AVAILABLE
    assert "at projection time" in checkpoint.capture.artifacts.reason

    # changed_files has NO observer, and the checkpoint says exactly that --
    # scoped to the field, with the reason a diff is not used.
    assert checkpoint.changed_files == ()
    assert checkpoint.capture.changed_files.status is CaptureStatus.CAPTURE_UNAVAILABLE
    assert "workspace diff" in checkpoint.capture.changed_files.reason

    capsule = build_capsule(
        state_root, for_worker_id="agent-one", queue_root=queue_root
    )
    task = next(t for t in capsule.tasks if t.task_id == "g4-one")
    assert task.execution_capture == "OBSERVED"
    assert task.capture["commands"]["status"] == "CAPTURE_AVAILABLE"
    assert task.capture["artifacts"]["status"] == "CAPTURE_AVAILABLE"
    assert task.capture["changed_files"]["status"] == "CAPTURE_UNAVAILABLE"
    rendered = render_capsule(capsule)
    assert "NOT CAPTURED" not in rendered
    assert "capture commands:      CAPTURE_AVAILABLE" in rendered
    assert "capture artifacts:     CAPTURE_AVAILABLE" in rendered
    assert "capture changed_files: CAPTURE_UNAVAILABLE" in rendered
    assert "artifact:    g4-one.txt@" in rendered
    assert f"command:     {sys.executable}" in rendered


def test_G4_a_writer_that_DID_observe_is_not_mislabelled(tmp_path: Path) -> None:
    """The other arm: OBSERVED must stay distinguishable from NOT_CAPTURED.

    A marker that was always NOT_CAPTURED would pass the test above and carry
    no information at all. A task writing its own checkpoints can record what
    it observed, and that must render differently.
    """
    root = tmp_path / "state"
    envelope = _envelope("observed-one", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    from project_atlas.orchestration.program.continuation import (
        ArtifactRecord,
        ExecutionCapture,
    )

    checkpoint = _checkpoint(envelope, root=root)
    checkpoint.execution_capture = ExecutionCapture.OBSERVED
    checkpoint.changed_files = ("observed-one.txt",)
    checkpoint.artifacts = (
        ArtifactRecord(path="observed-one.txt", sha256="a" * 64, bytes=3),
    )
    persist_checkpoint(root, checkpoint)

    capsule = build_capsule(root, for_worker_id=envelope.worker_id)
    task = next(t for t in capsule.tasks if t.task_id == "observed-one")
    assert task.execution_capture == "OBSERVED"
    rendered = render_capsule(capsule)
    assert "NOT CAPTURED" not in rendered
    assert "observed-one.txt" in rendered


# ---------------------------------------------------------------- helpers


def _dispatcher(
    state_root: Path,
    queue_root: Path,
    *,
    tick_seconds: float = 1.0,
    quantum: float = 0.1,
) -> ResidentDispatcher:
    return ResidentDispatcher(
        root=state_root,
        queue_root=queue_root,
        checkout=Path(__file__).resolve().parents[2],
        tick_seconds=tick_seconds,
        wake_quantum_seconds=quantum,
    )


def _load_state(state_root: Path) -> Any:
    from project_atlas.orchestration.program.store import load_state

    state = load_state(state_root)
    assert state is not None
    return state


def _grant_projected_lease(root: Path, *, task_id: str, agent_id: str) -> None:
    from project_atlas.orchestration.autonomy.lease_projection import project_grant
    from project_atlas.orchestration.autonomy.models import (
        AgentCapability,
        AgentLease,
        NodeState,
    )

    lease = AgentLease(
        lease_id=f"{task_id}-lease",
        agent_id=agent_id,
        package_id=task_id,
        branch="fixture-branch",
        worktree=str(root),
        base_pin="0" * 40,
        authorized_paths=(f"{task_id}.txt",),
        capabilities=(AgentCapability.IMPLEMENT,),
        start_state=NodeState.READY,
        expected_output="fixture output",
        expiry_or_terminal_condition="TERMINAL",
        active=True,
        sequence=1,
    )
    project_grant(root, lease, live_main="0" * 40)


# ------------------------------------------------- R1 / R2 / G4b / REQ-1 repairs
# ATLAS-R1-R2-G4-IMPLEMENTATION-CLOSURE-001. Every case below has two arms: the
# defect arm and the positive control that proves the repair is not a blanket
# refusal. The harness that defined R1/R2/G4 lives with the verifier; these are
# the implementer's own, and they measure the same properties from inside.


def _run_one_program(tmp_path: Path, task_id: str) -> tuple[Path, Path, Path, Path]:
    """Admit and run one fixture task to completion on the real resident path.

    Returns (workspace, state_root, queue_root, program_path). Asserts the
    preconditions every R1/R2/G4 case rests on: the program completed, the
    worker really wrote its file, and the queue records the program COMPLETE.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program = _program_file(tmp_path, workspace, tasks=[_task(task_id)])
    state_root = tmp_path / "state"
    queue_root = tmp_path / "queue"
    queue_root.mkdir()
    approved_queue.admit(
        queue_root, program_path=program, program_id="continuation-program",
        state_root=state_root, admitted_by="op", reference="closure-001",
    )
    ran = _dispatcher(state_root, queue_root, tick_seconds=0.5, quantum=0.05).tick()
    assert ran.report is not None
    assert ran.report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE
    assert (workspace / f"{task_id}.txt").is_file(), "fixture must have written"
    entry = approved_queue.load_queue(queue_root).entries["continuation-program"]
    assert entry.status is approved_queue.QueueEntryStatus.COMPLETE
    return workspace, state_root, queue_root, program


def test_R1_a_lost_checkpoint_with_a_recorded_attempt_is_quarantined_even_without_the_queue(
    tmp_path: Path,
) -> None:
    """R1, the arm the queue witness cannot cover.

    The earlier repair consulted the queue: no checkpoint + program COMPLETE
    => reconcile. The verifier's residual was exact: lose the queue witness as
    well and an envelope-only task read launchable again. But the supervisor's
    own state.json still records the attempt, and an attempt is evidence of
    prior execution whether or not the queue survived. So the decision is now
    made from every durable record that remembers the task, not from one.
    """
    _, state_root, _queue_root, _ = _run_one_program(tmp_path, "r1-lost")
    intact = build_capsule(state_root, for_worker_id="agent-one").tasks[0]
    assert intact.disposition is Disposition.ALREADY_COMPLETE

    for path in checkpoints_dir(state_root).glob("*.checkpoint.json"):
        path.unlink()

    # No --queue-root at all: the only witness left is state.json.
    capsule = build_capsule(state_root, for_worker_id="agent-one")
    task = capsule.tasks[0]
    assert task.disposition is Disposition.RECONCILE_REQUIRED, task.disposition
    assert task.launchable is False, "a lost record must never read as launchable"
    assert "attempt" in task.reason and "state.json" in task.reason
    assert "reconcile" in task.next_action.lower()
    assert "Do not relaunch" in task.next_action
    rendered = render_capsule(capsule)
    assert "launchable=True" not in rendered
    assert "START_FRESH" not in rendered
    assert "Start task" not in rendered

    # ONE decision: the reconcile command reaches the same disposition from
    # the same records, so a replacement session cannot be told two things.
    verdict = reconcile_one(state_root, "r1-lost", our_worker_id="agent-one")
    assert verdict.disposition is task.disposition
    assert verdict.launchable is False
    assert verdict.reason == task.reason

    # And the evidence function itself is silent about a task nobody ran.
    assert prior_execution_evidence((state_root,), "never-dispatched") == ()


def test_R1_positive_controls_new_work_starts_and_valid_checkpoints_continue() -> None:
    """The other arm, pure. A blanket refusal would pass R1 and break the layer.

    Three shapes, three answers: no record at all starts fresh; a valid
    checkpoint decides on its own terms and ignores prior-execution evidence
    entirely (it IS the prior execution); only the envelope-with-evidence
    shape is quarantined.
    """
    fresh = _envelope("fresh", replay=ReplayClass.IDEMPOTENT_MUTATION)
    verdict = reconcile_task(envelope=fresh, checkpoint=None, our_worker_id=fresh.worker_id)
    assert verdict.disposition is Disposition.START_FRESH
    assert verdict.launchable is True
    assert "no other record" in verdict.reason

    stepped = _envelope(
        "stepped", replay=ReplayClass.CHECKPOINT_RESUMABLE, steps=("ONE", "TWO", "THREE")
    )
    checkpoint = _checkpoint(stepped, last_step="ONE")
    with_evidence = reconcile_task(
        envelope=stepped,
        checkpoint=checkpoint,
        our_worker_id=stepped.worker_id,
        prior_execution=("attempt stepped.a1 recorded in state.json",),
    )
    without = reconcile_task(
        envelope=stepped, checkpoint=checkpoint, our_worker_id=stepped.worker_id
    )
    assert with_evidence.disposition is Disposition.RESUME_AT_NEXT_STEP
    assert without.disposition is Disposition.RESUME_AT_NEXT_STEP
    assert with_evidence.resume_step == without.resume_step == "TWO"

    lost = reconcile_task(
        envelope=fresh,
        checkpoint=None,
        our_worker_id=fresh.worker_id,
        prior_execution=("attempt fresh.a1 recorded in state.json under /x",),
    )
    assert lost.disposition is Disposition.RECONCILE_REQUIRED
    assert lost.launchable is False
    assert lost.replay_class is ReplayClass.UNCERTAIN_EXTERNAL_EFFECT
    assert "attempt fresh.a1" in lost.reason
    assert lost.evidence[0] == "no checkpoint file"


def test_R2_the_complete_rendered_capsule_is_consistent_when_the_queue_says_COMPLETE(
    tmp_path: Path,
) -> None:
    """R2: one document, one decision. Tested on the COMPLETE rendered text.

    The defect was a capsule holding by_status={'COMPLETE': [...]} a few lines
    above "[START_FRESH] ... launchable=True ... Start task". The whole
    rendering is searched, not one task line, because the contradiction lived
    across lines. The reconcile command and its CLI surface must say the same.
    """
    _, state_root, queue_root, _ = _run_one_program(tmp_path, "r2-lost")
    for path in checkpoints_dir(state_root).glob("*.checkpoint.json"):
        path.unlink()

    capsule = build_capsule(state_root, for_worker_id="agent-one", queue_root=queue_root)
    rendered = render_capsule(capsule)
    assert "by_status" in rendered and "'COMPLETE'" in rendered
    assert "START_FRESH" not in rendered
    assert "Start task" not in rendered
    assert "launchable=True" not in rendered
    assert "[RECONCILE_REQUIRED] r2-lost" in rendered
    assert "queue records the program owning r2-lost as COMPLETE" in rendered

    (verdict,) = reconcile_root(state_root, our_worker_id="agent-one", queue_root=queue_root)
    assert verdict.disposition is Disposition.RECONCILE_REQUIRED
    assert verdict.reason == capsule.tasks[0].reason

    payload = _cli(
        "program", "continuation", "--action", "reconcile",
        "--state-root", str(state_root), "--queue-root", str(queue_root),
        "--worker-id", "agent-one",
    )
    (row,) = payload["verdicts"]
    assert row["disposition"] == "RECONCILE_REQUIRED"
    assert row["launchable"] is False
    assert payload["queue_root"] == str(queue_root.resolve())


def test_G4a_a_checkpoint_with_no_capture_statement_still_renders_NOT_CAPTURED(
    tmp_path: Path,
) -> None:
    """G4a survives G4b: a writer that made no capture statement is still
    rendered as "nobody looked", per field and as a whole. Nothing is upgraded
    from the emptiness of its lists."""
    root = tmp_path / "state"
    envelope = _envelope("silent-one", replay=ReplayClass.IDEMPOTENT_MUTATION)
    persist_envelope(root, envelope)
    persist_checkpoint(root, _checkpoint(envelope, root=root))

    capsule = build_capsule(root, for_worker_id=envelope.worker_id)
    task = capsule.tasks[0]
    assert task.execution_capture == "NOT_CAPTURED"
    assert set(task.capture) == {"commands", "artifacts", "changed_files"}
    assert all(item["status"] == "CAPTURE_UNAVAILABLE" for item in task.capture.values())
    assert all("no per-field capture statement" in item["reason"] for item in task.capture.values())
    rendered = render_capsule(capsule)
    assert "NOT CAPTURED" in rendered and "nobody looked" in rendered
    assert "capture changed_files: CAPTURE_UNAVAILABLE" in rendered


def test_G4b_capture_is_UNAVAILABLE_with_a_scoped_reason_and_nothing_is_reconstructed(
    tmp_path: Path,
) -> None:
    """The negative arm of G4b, per source. When the record a field comes from
    is missing or unusable, the field is UNAVAILABLE and the reason names that
    record -- and the value is NOT reconstructed from the workspace, the
    profile, or anything else that would be inventing history."""
    from project_atlas.orchestration.program.continuation import CaptureStatus
    from project_atlas.orchestration.program.continuation_projection import (
        _capture_artifacts,
        _capture_commands,
    )

    workspace, state_root, _queue_root, program = _run_one_program(tmp_path, "g4-gone")
    state = _load_state(state_root)
    attempt = state.attempts[state.tasks["g4-gone"].last_attempt_id]
    task = load_program(program).program.tasks[0]

    # Control first: with the records intact both fields are available.
    commands, statement = _capture_commands(state_root, attempt)
    assert commands and statement.status is CaptureStatus.CAPTURE_AVAILABLE
    artifacts, statement = _capture_artifacts(task, attempt, workspace)
    assert artifacts and statement.status is CaptureStatus.CAPTURE_AVAILABLE

    # A transcript without an argv: the profile still knows the argv, and it
    # is deliberately NOT used -- the profile says what was configured, the
    # transcript says what ran.
    name = next(n for n in attempt.evidence_paths if n.endswith(".transcript.json"))
    transcript = evidence_dir(state_root) / name
    transcript.write_text('{"exit_status": 0}\n', encoding="utf-8")
    commands, statement = _capture_commands(state_root, attempt)
    assert commands == ()
    assert statement.status is CaptureStatus.CAPTURE_UNAVAILABLE
    assert "no usable argv" in statement.reason and name in statement.reason

    transcript.unlink()
    commands, statement = _capture_commands(state_root, attempt)
    assert commands == () and "unreadable" in statement.reason

    # The artifact vanished between acceptance and projection: named as
    # missing, not re-derived from whatever else is in the workspace.
    (workspace / "g4-gone.txt").unlink()
    artifacts, statement = _capture_artifacts(task, attempt, workspace)
    assert artifacts == ()
    assert statement.status is CaptureStatus.CAPTURE_UNAVAILABLE
    assert "g4-gone.txt" in statement.reason

    # No attempt at all: both fields say so, scoped.
    commands, statement = _capture_commands(state_root, None)
    assert commands == () and "no attempt is recorded" in statement.reason
    artifacts, statement = _capture_artifacts(task, None, workspace)
    assert artifacts == () and "no attempt is recorded" in statement.reason


def test_write_atomic_fsyncs_the_file_then_renames_then_fsyncs_the_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-1, the sequence. The order is the property: file fsync before the
    rename, directory fsync after it. This test establishes that the calls are
    MADE in that order; it does not and cannot establish power-loss durability,
    which no process-level test can."""
    from project_atlas.orchestration.program import store as program_store

    if not program_store.DIRECTORY_SYNC_SUPPORTED:
        pytest.skip("directory fsync is not claimed on this platform")
    calls: list[str] = []
    real_fsync, real_replace = os.fsync, os.replace

    def spy_fsync(fd: int) -> None:
        kind = "dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"
        calls.append(f"fsync:{kind}")
        real_fsync(fd)

    def spy_replace(src: Any, dst: Any) -> None:
        calls.append("replace")
        real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "replace", spy_replace)
    target = tmp_path / "state.json"
    program_store.write_json_atomic(target, {"n": 1})
    assert calls == ["fsync:file", "replace", "fsync:dir"], calls
    assert json.loads(target.read_text(encoding="utf-8")) == {"n": 1}
    assert not target.with_name("state.json.tmp").exists()


def test_a_failed_directory_sync_is_a_typed_error_and_never_a_silent_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from project_atlas.orchestration.program import store as program_store

    if not program_store.DIRECTORY_SYNC_SUPPORTED:
        pytest.skip("directory fsync is not claimed on this platform")
    real_fsync = os.fsync

    def failing_dir_fsync(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(5, "injected EIO")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", failing_dir_fsync)
    target = tmp_path / "state.json"
    with pytest.raises(program_store.StoreError) as caught:
        program_store.write_json_atomic(target, {"n": 1})
    assert caught.value.code == "DIRECTORY_SYNC_FAILED"
    assert "after the rename" in str(caught.value)
    # The rename itself completed; what could not be established is its
    # durability, and that is exactly what was reported instead of assumed.
    assert json.loads(target.read_text(encoding="utf-8")) == {"n": 1}


def test_a_failed_write_leaves_the_previous_state_file_intact_and_no_temp_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ATOMIC VISIBILITY, established by injected failure. A write that fails
    before the rename leaves the old document whole and removes its own temp
    file; a temp path that cannot be created is refused the same way."""
    from project_atlas.orchestration.program import store as program_store

    target = tmp_path / "state.json"
    program_store.write_json_atomic(target, {"n": 0})
    before = target.read_bytes()
    real_fsync = os.fsync

    def failing_file_fsync(fd: int) -> None:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(28, "injected ENOSPC")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", failing_file_fsync)
    with pytest.raises(program_store.StoreError) as caught:
        program_store.write_json_atomic(target, {"n": 1, "pad": "x" * 1000})
    assert caught.value.code == "STATE_WRITE_FAILED"
    assert target.read_bytes() == before
    assert list(tmp_path.glob("*.tmp")) == []
    monkeypatch.undo()

    # The temp path is occupied by a directory: creation fails, typed.
    target.with_name("state.json.tmp").mkdir()
    with pytest.raises(program_store.StoreError) as caught:
        program_store.write_json_atomic(target, {"n": 2})
    assert caught.value.code == "STATE_WRITE_FAILED"
    assert target.read_bytes() == before


def test_a_writer_killed_mid_loop_leaves_a_whole_state_file_never_a_torn_one(
    tmp_path: Path,
) -> None:
    """PROCESS-INTERRUPTION RECOVERY, and only that.

    A real writer process is killed while writing a 200 KB document in a tight
    loop. Whatever survives must be a complete document or nothing; a ``.tmp``
    sibling may remain and every loader ignores it. This is NOT a power-loss
    test: the kernel's page cache survives a killed process, so this proves the
    rename discipline, not the fsync discipline. That claim is not made here.
    """
    target = tmp_path / "state.json"
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from project_atlas.orchestration.program.store import write_json_atomic\n"
        "target = Path(sys.argv[1]); n = 0\n"
        "print('ready', flush=True)\n"
        "while True:\n"
        "    n += 1\n"
        "    write_json_atomic(target, {'n': n, 'pad': 'x' * 200_000})\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(target)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "ready"
        deadline = time.monotonic() + 5.0
        while not target.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.2)
    finally:
        proc.kill()
        proc.wait(timeout=30)
    assert target.exists(), "the writer never produced a state file in time"
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["pad"] == "x" * 200_000
    assert payload["n"] >= 1
    assert {p.suffix for p in tmp_path.iterdir()} <= {".json", ".tmp"}
