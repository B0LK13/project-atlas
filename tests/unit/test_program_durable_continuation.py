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

import json
import os
import resource
import signal
import socket
import subprocess
import sys
import time
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
    reconcile_one,
    reconcile_root,
)
from project_atlas.orchestration.program.recovery import Liveness
from project_atlas.orchestration.program.resident import (
    DispatcherState,
    DispatcherStopReason,
    ResidentDispatcher,
    dispatcher_status,
    read_heartbeat,
)
from project_atlas.orchestration.program.store import state_dir

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")
FIXTURE_SESSION = Path(__file__).with_name("_continuation_fixture_session.py")
READY_MARK = "FIXTURE_SESSION_READY"
CLI = "project_atlas.orchestration.program.cli"

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
    assert any("queue unreadable" in note for note in result.notes), result.notes

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
