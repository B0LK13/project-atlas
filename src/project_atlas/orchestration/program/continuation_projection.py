"""Turning a program run into durable envelopes and checkpoints.

Without this, the continuation layer is a set of correct mechanisms that
nothing feeds: a program executed through the dispatcher produces `state.json`
and `events.jsonl`, and a replacement session asking for a capsule is told
"no task envelopes recorded" -- which is true, and useless.

So the dispatcher materialises an **envelope per approved task before the
program runs**, and **projects a checkpoint per task after it stops**. Both are
derivations from records that already exist; neither invents anything.

What this DOES give: a replacement session, on a different process and after a
reboot, reconstructs every task's authority, its disposition, its artifacts and
its next concrete action from files.

What it does NOT give, stated plainly because the difference matters: these
checkpoints are written at **program boundaries**, not after every step inside a
worker. A task that wants step-level resume declares steps in its envelope's
checkpoint policy and writes its own checkpoints as it goes -- the mechanism is
the same `persist_checkpoint`, and `reconciliation` treats both identically.
Boundary checkpoints are enough to answer "may this run again?"; they are not
enough to answer "which of its five steps already landed?", and this module
does not pretend otherwise.

The replay class for a task that does not declare one is deliberately the
**most cautious** available: `UNCERTAIN_EXTERNAL_EFFECT`. An unannotated
mutating task interrupted mid-flight then demands reconciliation rather than
being replayed. Defaulting the other way would make silence mean "safe to
repeat", and silence is exactly what an unannotated task is.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final

from project_atlas.orchestration.autonomy.lease_projection import (
    ProjectionError,
    active_rows,
    load_projection,
)
from project_atlas.orchestration.autonomy.models import NodeState
from project_atlas.orchestration.program.continuation import (
    ArtifactRecord,
    CaptureStatus,
    CheckpointError,
    CheckpointPolicy,
    CommandRecord,
    ContinuationCheckpoint,
    ExecutionCapture,
    ExecutionCaptureReport,
    ExecutionIdentity,
    FieldCapture,
    LeaseSnapshot,
    ReplayClass,
    TaskBudgets,
    TaskEnvelope,
    envelope_from_task,
    load_checkpoint,
    load_envelope,
    persist_checkpoint,
    persist_envelope,
    utc_now,
)
from project_atlas.orchestration.program.loader import LoadedProgram
from project_atlas.orchestration.program.models import (
    AcceptanceKind,
    AttemptPhase,
    ExecutionConfidence,
    ProgramTask,
)
from project_atlas.orchestration.program.path_safety import checked_path, child_path, trusted_root
from project_atlas.orchestration.program.profiles import AdapterKind
from project_atlas.orchestration.program.store import (
    AttemptRecord,
    ProgramStateRecord,
    evidence_dir,
)

#: Task states that mean the work is finished and sealed.
_DONE: frozenset[NodeState] = frozenset({NodeState.CERTIFIED, NodeState.CLOSED})
#: Task states that mean a person has to decide before anything else happens.
_STUCK: frozenset[NodeState] = frozenset({NodeState.BLOCKED, NodeState.OWNER_HELD})
#: The adapter transcript an attempt names in its evidence paths. Written by
#: the adapter from what it observed of the child: argv, exit status, output.
_TRANSCRIPT_SUFFIX: Final[str] = ".transcript.json"
#: Acceptance kinds that name a workspace path the supervisor itself observed.
_ARTIFACT_CHECK_KINDS: Final[frozenset[AcceptanceKind]] = frozenset(
    {AcceptanceKind.FILE_EXISTS, AcceptanceKind.FILE_MATCHES}
)
_OUTPUT_TAIL_BYTES: Final[int] = 4096
_HASH_CHUNK: Final[int] = 1 << 16


def _unavailable(reason: str) -> FieldCapture:
    return FieldCapture(status=CaptureStatus.CAPTURE_UNAVAILABLE, reason=reason[:512])


def _capture_commands(
    root: Path, attempt: AttemptRecord | None
) -> tuple[tuple[CommandRecord, ...], FieldCapture]:
    """The command the supervisor actually observed for this task's attempt.

    G4b. The source is the adapter transcript the attempt names in its own
    evidence paths -- a record the adapter wrote from the child it launched,
    with the argv it launched, the exit status it collected and the output it
    read. Nothing here is reconstructed: an attempt without a transcript, an
    unreadable transcript or a transcript without an argv all yield
    CAPTURE_UNAVAILABLE with the reason scoped to that attempt.
    """
    if attempt is None:
        return (), _unavailable(
            "no attempt is recorded for this task, so nothing was dispatched and "
            "there is no command to report"
        )
    names = [
        name
        for name in attempt.evidence_paths
        if name.endswith(_TRANSCRIPT_SUFFIX) and "/" not in name and "\\" not in name
    ]
    if not names:
        return (), _unavailable(
            f"adapter {attempt.adapter} recorded no transcript for attempt "
            f"{attempt.attempt_id}; the supervisor did not observe its command line"
        )
    name = names[0]
    # ContainmentError is a ValueError: do not demote it to an unavailable
    # optional capture. A planted transcript link requires fail-closed recovery.
    target = child_path(evidence_dir(root), name)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return (), _unavailable(
            f"transcript {name} for attempt {attempt.attempt_id} is unreadable "
            f"({type(exc).__name__}); the observed command line cannot be reported"
        )
    argv = payload.get("argv") if isinstance(payload, dict) else None
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > 64
        or not all(isinstance(item, str) and item for item in argv)
    ):
        return (), _unavailable(
            f"transcript {name} records no usable argv; the observed command line "
            "cannot be reported"
        )
    exit_status = payload.get("exit_status")
    if isinstance(exit_status, bool) or not isinstance(exit_status, int):
        exit_status = None
    stdout = payload.get("stdout")
    stderr = payload.get("stderr")
    tail = (stdout if isinstance(stdout, str) else "") + (
        stderr if isinstance(stderr, str) else ""
    )
    record = CommandRecord(
        argv=tuple(argv),
        started_at=attempt.started_at,
        ended_at=attempt.ended_at,
        exit_status=exit_status,
        output_tail=tail[-_OUTPUT_TAIL_BYTES:],
    )
    return (record,), FieldCapture(
        status=CaptureStatus.CAPTURE_AVAILABLE,
        reason=(
            "argv, exit status and output tail read from the adapter transcript "
            f"written for attempt {attempt.attempt_id}; start and end times from "
            "the attempt record"
        ),
        source=f"evidence/{name}",
    )


def _sha256_of(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with checked_path(path).open("rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _capture_artifacts(
    task: ProgramTask, attempt: AttemptRecord | None, workspace: Path
) -> tuple[tuple[ArtifactRecord, ...], FieldCapture]:
    """Artifacts the supervisor observed through its own acceptance checks.

    G4b. A FILE_EXISTS or FILE_MATCHES check that PASSED is the supervisor
    having looked at that path itself; those paths, and only those, are
    reported. Each is hashed inside the workspace at projection time, which is
    after acceptance and is said so in the reason. A path the acceptance saw
    that is gone or is not a regular file by now is named as missing rather
    than dropped.
    """
    if attempt is None:
        return (), _unavailable(
            "no attempt is recorded for this task, so no acceptance check ran and "
            "no artifact path was observed"
        )
    if not attempt.acceptance_detail:
        return (), _unavailable(
            f"attempt {attempt.attempt_id} reached phase {attempt.phase.value} "
            "without an acceptance evaluation; no artifact path was observed"
        )
    passed = {
        detail.get("check_id")
        for detail in attempt.acceptance_detail
        if detail.get("passed") is True
    }
    candidates = [
        check
        for check in task.acceptance
        if check.kind in _ARTIFACT_CHECK_KINDS and check.path and check.check_id in passed
    ]
    if not candidates:
        return (), _unavailable(
            "no passed FILE_EXISTS or FILE_MATCHES acceptance check names a path; "
            "the supervisor observed no artifact path for this task"
        )
    base = trusted_root(workspace)
    records: list[ArtifactRecord] = []
    missing: list[str] = []
    for check in candidates:
        relative = check.path or ""
        target = child_path(base, relative)
        if not target.is_file():
            missing.append(relative)
            continue
        try:
            sha, size = _sha256_of(target)
        except OSError:
            missing.append(relative)
            continue
        records.append(ArtifactRecord(path=relative, sha256=sha, bytes=size))
    if not records:
        return (), _unavailable(
            "acceptance observed "
            + ", ".join(missing)
            + " but none is a regular file inside the workspace at projection time"
        )
    reason = (
        "paths taken from acceptance checks the supervisor observed to pass; each "
        "hashed inside the workspace at projection time, which is after acceptance, "
        "not at it"
    )
    if missing:
        reason += "; not found at projection: " + ", ".join(missing)
    return tuple(records), FieldCapture(
        status=CaptureStatus.CAPTURE_AVAILABLE,
        reason=reason[:512],
        source=f"attempt {attempt.attempt_id} acceptance_detail",
    )


#: changed_files has no observing writer in this projection, and the reason is
#: fixed rather than computed: the supervisor watches no individual file write
#: for any adapter, and the one thing that COULD fill the list -- a workspace
#: diff -- would be reconstructing history, not observing it.
_CHANGED_FILES_UNAVAILABLE: Final[FieldCapture] = FieldCapture(
    status=CaptureStatus.CAPTURE_UNAVAILABLE,
    reason=(
        "the supervisor records no per-file write observation for any adapter; a "
        "workspace diff would reconstruct history rather than observe it and is "
        "deliberately not used"
    ),
)


def replay_class_for(task: ProgramTask) -> ReplayClass:
    """The replay class a task gets when it does not declare one.

    Three cases, and the ordering is the argument:

    1. A task that declares its effect safe to repeat after a crash with no
       launch evidence has already told us it is idempotent. Believe it -- that
       flag is the existing, reviewed way for a program to say so.
    2. A task with no mutation paths writes nothing but its own evidence.
    3. Everything else is treated as capable of an effect we cannot see. That
       is the cautious answer, and it is the right default because the
       alternative reading of silence is "safe to repeat".
    """
    if task.execution_steps:
        return ReplayClass.CHECKPOINT_RESUMABLE
    if task.retry_safe_when_no_launch_evidence:
        return ReplayClass.IDEMPOTENT_MUTATION
    if not task.mutation_paths:
        return ReplayClass.READ_ONLY_REPLAYABLE
    return ReplayClass.UNCERTAIN_EXTERNAL_EFFECT


def materialise_envelopes(
    loaded: LoadedProgram,
    root: Path,
    *,
    candidate_head: str,
    candidate_tree: str,
) -> tuple[TaskEnvelope, ...]:
    """Write one envelope per approved task, idempotently.

    An existing envelope is left alone rather than rewritten. Rewriting it
    would move the authority a running attempt was started under, and
    ``reconcile_task`` would then -- correctly -- declare that authority had
    changed mid-flight and refuse to continue. The one thing that must not
    happen on every tick is the layer invalidating its own checkpoints.
    """
    written: list[TaskEnvelope] = []
    for task in loaded.program.tasks:
        existing = load_envelope(root, task.task_id)
        if existing is not None:
            written.append(existing)
            continue
        profile = loaded.effective_profile(task.task_id)
        limits = profile.limits
        envelope = envelope_from_task(
            task,
            program=loaded.program,
            candidate_head=candidate_head,
            candidate_tree=candidate_tree,
            worker_id=profile.agent_id,
            replay_class=replay_class_for(task),
            budgets=TaskBudgets(
                max_attempts=loaded.program.limits.max_attempts_per_task,
                max_launches=max(1, loaded.program.limits.max_task_launches),
                max_wall_seconds=loaded.program.limits.max_task_seconds,
                # Zero, always, while model-backed dispatch is disabled. Taken
                # from the switch and not from the profile's own cost ceiling:
                # a profile that permits spend is not a grant to spend here.
                max_model_calls=0,
                max_estimated_cost_usd=float(limits.max_estimated_cost_usd or 0.0),
            ),
            checkpoint_policy=CheckpointPolicy(
                steps=tuple(s.step_id for s in task.execution_steps)
            ),
            forbidden_paths=(),
            allowed_actions=(),
            # Recorded on every envelope, for a reader rather than for a gate:
            # these are the acts this package never performs, and an envelope
            # that listed none would leave that to be inferred.
            forbidden_actions=("MERGE", "PUSH", "RELEASE", "CREDENTIAL_CHANGE"),
            model_backed_dispatch=profile.adapter is not AdapterKind.LOCAL_COMMAND,
        )
        persist_envelope(root, envelope)
        written.append(envelope)
    return tuple(written)


def _lease_snapshot(root: Path, task_id: str, *, session_id: str) -> LeaseSnapshot | None:
    """The ACTIVE projected lease for a task, as a checkpoint snapshot.

    ``expires_at`` is the honest problem here: the projection row carries a
    terminal condition, not a wall-clock expiry. Rather than invent one, the
    snapshot records a far-future expiry, which makes the checkpoint say "this
    lease has not expired" -- and reconciliation then falls through to the
    process identity check, which is the evidence that actually decides whether
    the holder is gone. An invented near expiry would let a successor take work
    from a live holder on the strength of a number nobody measured.
    """
    try:
        from project_atlas.orchestration.program.store import state_dir

        projection = load_projection(state_dir(root))
    except ProjectionError:
        return None
    for row in active_rows(projection):
        if row.package_id != task_id:
            continue
        return LeaseSnapshot(
            lease_id=row.lease_id,
            holder_worker_id=row.agent_id,
            holder_session_id=session_id,
            granted_at=utc_now(),
            expires_at="2099-01-01T00:00:00.000Z",
        )
    return None


def _attempt_for(state: ProgramStateRecord, task_id: str) -> AttemptRecord | None:
    record = state.tasks.get(task_id)
    if record is None or record.last_attempt_id is None:
        return None
    return state.attempts.get(record.last_attempt_id)


def project_checkpoints(
    loaded: LoadedProgram,
    root: Path,
    *,
    state: ProgramStateRecord,
    session_id: str,
    worktree: Path,
    git_head: str,
    git_tree: str,
    revision_observed: bool = True,
) -> tuple[ContinuationCheckpoint, ...]:
    """Project one checkpoint per task from durable supervisor state.

    Every value comes from a record the supervisor already wrote. Nothing here
    observes a process, evaluates acceptance, or decides an outcome -- it
    projects, and a projection that disagreed with its source would be a second
    opinion nobody asked for.
    """
    worktree = checked_path(
        worktree, root=loaded.governed_root or loaded.source_path.parent
    )
    written: list[ContinuationCheckpoint] = []
    for task in loaded.program.tasks:
        envelope = load_envelope(root, task.task_id)
        if envelope is None:
            continue
        record = state.tasks.get(task.task_id)
        if record is None:
            continue
        attempt = _attempt_for(state, task.task_id)

        previous = None
        try:
            previous = load_checkpoint(root, task.task_id)
        except CheckpointError:
            # A checkpoint we cannot read must not be overwritten by a fresh
            # projection: the unreadable record is evidence of something, and
            # replacing it would destroy the only trace of it. Reconciliation
            # already fails closed on it.
            #
            # This is the SECOND of two mechanisms, and measured as such rather
            # than assumed: removing it alone changes nothing, because
            # `persist_checkpoint` refuses a sequence at or below the one on
            # disk and an unreadable record still yields sequence 1. Removing
            # BOTH lets the projection clobber the tampered file. Kept because
            # it refuses earlier and for the right reason -- the sequence check
            # is defending a different property and would stop defending this
            # one the moment a projection legitimately carried a higher
            # sequence.
            continue
        # TAKEOVER-001: a boundary snapshot is not an execution. Keep never
        # dispatched work as an envelope; otherwise an uncertain replay class
        # turns an ordinary pause into a fictitious interrupted execution.
        if attempt is None and previous is None and record.state not in _DONE | _STUCK:
            continue
        # Preserve first-hand uncertainty instead of laundering it through a
        # weaker boundary projection after dispatch was refused.
        if previous is not None and (
            previous.envelope_digest != envelope.digest()
            or previous.uncertainty
            or any(effect.confirmed is not True for effect in previous.external_effects)
        ):
            continue
        # An interrupted read-only dispatch has a first-hand intent, too.
        # Recovery may have refused conflicting process records. Do not erase
        # that checkpoint's identity with the weaker pre-return state fields.
        if (
            previous is not None
            and attempt is not None
            and previous.identity.attempt_id == attempt.attempt_id
            and attempt.phase is AttemptPhase.ADAPTER_INVOKED
        ):
            continue
        # Step checkpoints are first-hand execution records. A boundary lens
        # may add a final task seal, but must never erase their history.
        if task.execution_steps and previous is not None:
            if record.state in _DONE:
                from project_atlas.orchestration.program.consumption import consumed_for_task

                written.append(persist_checkpoint(root, previous.model_copy(update={
                    "sequence": previous.sequence + 1,
                    "recorded_at": utc_now(),
                    "consumed_budget": consumed_for_task(state, task.task_id, previous),
                    "terminal": True, "replay_class": ReplayClass.COMPLETED,
                    "next_action": "nothing; task acceptance confirmed; never replay",
                })))
            continue
        sequence = (previous.sequence + 1) if previous is not None else 1

        terminal = record.state in _DONE or record.state in _STUCK
        if record.state in _DONE:
            replay = ReplayClass.COMPLETED
            next_action = f"nothing; {task.task_id} is complete and is never replayed"
        elif record.state in _STUCK:
            replay = ReplayClass.HUMAN_DECISION_REQUIRED
            next_action = (
                f"a person decides what happens to {task.task_id}; "
                f"it is {record.state.value}"
            )
        else:
            replay = envelope.replay_class
            next_action = (
                f"reconcile {task.task_id} (state {record.state.value}) before "
                "any dispatch"
            )

        # ``record.reason`` is the supervisor's note for whatever state the
        # task is in -- including "every acceptance condition observed to
        # hold". Carrying that into ``blockers`` unconditionally would label a
        # success as a blocker in the capsule, which is worse than saying
        # nothing: a reader scanning for blockers would find one on every
        # completed task. It is a blocker only when the task is actually stuck.
        blockers: tuple[str, ...] = ()
        if record.state in _STUCK and record.reason:
            blockers = (record.reason[:512],)
        uncertainty: tuple[str, ...] = ()
        if attempt is not None and attempt.confidence is ExecutionConfidence.UNCERTAIN:
            uncertainty = (
                f"attempt {attempt.attempt_id} reached phase "
                f"{attempt.phase.value} with an uncertain outcome",
            )

        # G4b. What the supervisor genuinely observed, per field, from records
        # it or its adapter wrote: the command from the attempt's transcript,
        # the artifacts from acceptance checks that passed. changed_files has
        # no observer and says so. Each field carries its own statement, so a
        # reader sees "commands captured, changed files not" rather than one
        # flag flattened over three lists. Nothing is inferred from a diff.
        commands, commands_capture = _capture_commands(root, attempt)
        artifacts, artifacts_capture = _capture_artifacts(task, attempt, worktree)
        capture = ExecutionCaptureReport(
            commands=commands_capture,
            artifacts=artifacts_capture,
            changed_files=_CHANGED_FILES_UNAVAILABLE,
        )

        from project_atlas.orchestration.program.consumption import (
            consumed_for_task,
            unobserved_wall_attempts,
        )

        checkpoint = ContinuationCheckpoint(
            identity=ExecutionIdentity(
                task_id=task.task_id,
                worker_id=envelope.worker_id,
                session_id=session_id,
                attempt_id=(
                    attempt.attempt_id
                    if attempt is not None
                    else f"{task.task_id}.no-attempt.{sequence}"
                ),
            ),
            envelope_digest=envelope.digest(),
            program_id=loaded.program.program_id,
            sequence=sequence,
            last_completed_step=None,
            next_action=next_action,
            worktree_path=str(worktree),
            git_head=git_head,
            git_tree=git_tree,
            process_pid=attempt.process_pid if attempt is not None else None,
            process_start_identity=(
                attempt.process_start_identity if attempt is not None else None
            ),
            lease=_lease_snapshot(root, task.task_id, session_id=session_id),
            consumed_budget=consumed_for_task(state, task.task_id, previous),
            # G4a: OBSERVED means at least one field below was captured from a
            # record; NOT_CAPTURED means none was. The per-field report says
            # which. Neither value is ever set from the emptiness of a list.
            execution_capture=(
                ExecutionCapture.OBSERVED
                if capture.any_available()
                else ExecutionCapture.NOT_CAPTURED
            ),
            capture=capture,
            commands=commands,
            artifacts=artifacts,
            blockers=blockers,
            uncertainty=uncertainty,
            replay_class=replay,
            terminal=terminal,
        )
        if not revision_observed:
            from project_atlas.orchestration.program.candidate import UNVERSIONED_FIXTURE_BOUNDARY

            checkpoint.truth_boundary += " / " + UNVERSIONED_FIXTURE_BOUNDARY
        if unobserved_wall_attempts(state, task.task_id):
            checkpoint.truth_boundary += (
                " / WALL_BUDGET_UNOBSERVED: recorded wall time is a known lower bound; "
                "missing attempt measurements block further dispatch"
            )
        try:
            written.append(persist_checkpoint(root, checkpoint))
        except CheckpointError:
            # A sequence regression here means somebody else wrote a checkpoint
            # for this task while the program ran. Theirs stands; a projection
            # is the weaker record and must not overwrite a first-hand one.
            continue
    return tuple(written)
