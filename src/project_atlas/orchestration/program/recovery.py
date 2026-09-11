"""Restart reconciliation. Ambiguity is preserved, never resolved by wishing.

A supervisor that restarts finds attempts in every phase. What it may do with
each one depends entirely on which phase it died in and on evidence it can
still gather -- never on an assumption:

  ``INTENT_RECORDED``      the ambiguity window. The supervisor decided to
                           launch; it may or may not have reached the spawn.
                           Resolved by asking the adapter whether that exact
                           run ever started (``probe_run_started``), which is
                           possible because the session identity was assigned
                           and written down BEFORE the launch.
  ``ADAPTER_INVOKED``      the worker was definitely started and no terminal
                           outcome was recorded. If the process is still
                           alive it is still ours to wait for; if it is gone,
                           the effect is unknown.
  ``ADAPTER_RETURNED``     the run finished, acceptance was never evaluated.
                           Acceptance is read-only and repeatable, so this
                           one is simply finished.
  ``ACCEPTANCE_EVALUATED`` bookkeeping only remains.
  ``TERMINAL``             nothing to do.

The one thing this module never does is relaunch a task because it could not
tell what happened. ``NEEDS_RECONCILIATION`` is a real outcome that stops the
program and asks the operator, and it is preferred over a duplicate effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from project_atlas.orchestration.program.adapters.base import (
    AdapterCapabilities,
    AdapterRequest,
    RuntimeAdapter,
    pid_is_alive,
    process_start_identity,
)
from project_atlas.orchestration.program.models import (
    AttemptPhase,
    ExecutionConfidence,
    ProgramTask,
)
from project_atlas.orchestration.program.store import (
    AttemptRecord,
    load_launch,
    load_launch_intent,
    load_state,
)


class RecoveryAction(StrEnum):
    """What the supervisor may do with an interrupted attempt."""

    #: Nothing was started. The same attempt may be launched.
    SAFE_TO_LAUNCH = "SAFE_TO_LAUNCH"
    #: A worker is still running under a live, verified process identity.
    WORKER_STILL_RUNNING = "WORKER_STILL_RUNNING"
    #: The worker ran; continue that exact session rather than starting again.
    RESUME_SESSION = "RESUME_SESSION"
    #: The run finished; only acceptance remains, and acceptance is repeatable.
    EVALUATE_ACCEPTANCE = "EVALUATE_ACCEPTANCE"
    #: Outcome unknown and not recoverable automatically. Operator decision.
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"
    #: Already finished.
    ALREADY_TERMINAL = "ALREADY_TERMINAL"


@dataclass(frozen=True)
class RecoveryVerdict:
    action: RecoveryAction
    confidence: ExecutionConfidence | None
    reason: str
    #: Session to continue when the action is RESUME_SESSION.
    resume_session_id: str | None = None


class Liveness(StrEnum):
    """Three answers, because there are three.

    The bug this replaces returned a bool, so "we never recorded a pid" and
    "the process is demonstrably gone" produced the same False -- and the
    caller turned that False into the sentence "the worker was launched, is
    gone". It was observed saying that about a worker that was still running.
    Absence has to be shown, not inferred from a gap in our own bookkeeping.
    """

    #: The recorded process is alive and is the one we started.
    ALIVE = "ALIVE"
    #: Demonstrably not our process any more: the pid is dead, or it is alive
    #: under a different start identity, which means ours exited and the number
    #: was reused.
    GONE = "GONE"
    #: Nothing can be shown either way -- no identity was recorded, or the
    #: platform cannot report one. Never treated as absence.
    UNKNOWN = "UNKNOWN"
    #: Launched and recorded, but the start identity probe had not finished
    #: yet -- and the supervisor that launched it is still alive under the
    #: instance token it recorded. Narrower than ALIVE, which requires a
    #: matching identity, and deliberately distinct from UNKNOWN: this is a
    #: process we wrote down ourselves moments ago, whose launcher is still
    #: waiting for it. It cannot be a reused pid, because the launcher has not
    #: stopped waiting. If that launcher is gone, this is UNKNOWN instead and
    #: reconciliation is exactly right.
    IN_FLIGHT = "IN_FLIGHT"


def process_liveness(
    pid: int | None, recorded_identity: str | None
) -> tuple[Liveness, str]:
    """Liveness of one recorded process, with the reason in the same breath."""
    if pid is None or pid <= 0:
        return Liveness.UNKNOWN, "no process identity was recorded for this attempt"
    if not pid_is_alive(pid):
        return Liveness.GONE, f"pid {pid} is not running"
    live = process_start_identity(pid)
    if not recorded_identity or recorded_identity == "unknown":
        return (
            Liveness.UNKNOWN,
            f"pid {pid} is running but no start identity was recorded at launch, "
            "so it cannot be told apart from a reused pid",
        )
    if not live or live == "unknown":
        return (
            Liveness.UNKNOWN,
            f"pid {pid} is running but this platform reports no start identity, "
            "so it cannot be compared with the one recorded at launch",
        )
    if live == recorded_identity:
        return (
            Liveness.ALIVE,
            f"pid {pid} is alive and its start identity matches the one recorded "
            "at launch",
        )
    return (
        Liveness.GONE,
        f"pid {pid} is running but under a different start identity; our worker "
        "exited and the pid was reused",
    )


def attempt_liveness(
    attempt: AttemptRecord, *, root: Path | None = None
) -> tuple[Liveness, str]:
    """Liveness of an attempt's worker, from whichever record exists.

    ``AttemptRecord`` only receives the pid when the adapter returns. While a
    worker is in flight the identity lives in the durable launch record the
    adapter wrote at spawn, which is the record that survives a supervisor
    killed between checkpoints -- so it is consulted whenever the attempt
    itself has none.
    """
    pid = attempt.process_pid
    identity = attempt.process_start_identity
    if pid is None and root is not None:
        recorded = load_launch(root, attempt.attempt_id)
        if recorded is not None:
            pid = int(recorded.get("pid") or 0) or None
            raw_identity = recorded.get("process_start_identity")
            identity = raw_identity if isinstance(raw_identity, str) else None
        else:
            # No identified record yet. There may still be a launch INTENT:
            # the adapter writes one between the spawn and the identity probe,
            # and on Windows that probe is slow enough for a whole worker to
            # run inside it. Before this existed, the gap read as "no process
            # identity was recorded for this attempt" -- about a worker that
            # was running -- and reconciliation was demanded for it.
            intent = load_launch_intent(root, attempt.attempt_id)
            if intent is not None:
                return _intent_liveness(intent, root=root)
    return process_liveness(pid, identity)


def _intent_liveness(intent: dict[str, object], *, root: Path) -> tuple[Liveness, str]:
    """Liveness from a launch intent -- a pid we wrote down, no identity yet.

    A pid on its own is never enough: the operating system is free to reuse it,
    which is the whole reason ``process_liveness`` refuses to call an
    unidentified pid ALIVE. What makes this record different is the pair it
    carries. The supervisor that launched the child recorded its own pid and
    instance token alongside it, and a pid cannot have been reused while the
    process that is still waiting for it is itself still running.

    So the answer is IN_FLIGHT only while that launcher is alive. If it is gone,
    this degrades to UNKNOWN -- the orphan case, where a live pid genuinely
    might belong to a stranger, and where asking an operator is correct.
    """
    raw_pid = intent.get("pid")
    pid = int(raw_pid) if isinstance(raw_pid, int) and raw_pid > 0 else None
    if pid is None:
        return Liveness.UNKNOWN, "a launch intent was recorded without a usable pid"
    if not pid_is_alive(pid):
        return (
            Liveness.GONE,
            f"pid {pid} was recorded at launch and is not running",
        )
    raw_sup = intent.get("supervisor_pid")
    supervisor_pid = int(raw_sup) if isinstance(raw_sup, int) and raw_sup > 0 else None
    if supervisor_pid is None or not pid_is_alive(supervisor_pid):
        return (
            Liveness.UNKNOWN,
            f"pid {pid} was recorded at launch and is running, but its start "
            "identity was never established and the supervisor that launched "
            "it is no longer running, so it cannot be told apart from a reused "
            "pid",
        )
    # A live supervisor pid is not yet the RIGHT supervisor. Pids are reusable
    # on both sides of this record, so a stranger occupying the launcher's old
    # number must not be allowed to vouch for a stranger occupying the
    # worker's. Two independent things are checked, and both are load-bearing.
    #
    # First: is the launcher still the same PROCESS? Re-derived live, from the
    # pid, exactly as B1 does for workers. This is the check that survives the
    # launcher being killed, because it asks the operating system rather than
    # asking a file the launcher wrote.
    recorded_start = intent.get("supervisor_start_identity")
    if not isinstance(recorded_start, str) or not recorded_start or (
        recorded_start == "unknown"
    ):
        return (
            Liveness.UNKNOWN,
            f"pid {pid} was recorded at launch and is running, but no start "
            "identity was recorded for the supervisor that launched it, so a "
            "reused launcher pid could not be ruled out",
        )
    live_start = process_start_identity(supervisor_pid)
    if not live_start or live_start == "unknown" or live_start != recorded_start:
        return (
            Liveness.UNKNOWN,
            f"pid {pid} was recorded at launch and is running, but the process "
            f"now holding the launching supervisor's pid {supervisor_pid} is "
            "not the supervisor that launched it, so this attempt was orphaned "
            "and its worker cannot be told apart from a reused pid",
        )
    # Second: is that supervisor still the one that owns this PROGRAM? The
    # token is minted per run and compared against state.json. This is a
    # weaker check on its own -- state.json is never cleared on exit, so after
    # a kill it still names the dead supervisor -- and it is kept because it
    # catches the case the first one does not: a LIVE supervisor from a later
    # run, whose pid and start identity are genuinely its own, inheriting an
    # intent written by an earlier one.
    recorded_token = intent.get("supervisor_instance_id")
    state = load_state(root)
    live_token = state.supervisor_instance_id if state is not None else None
    if not recorded_token or not live_token or recorded_token != live_token:
        return (
            Liveness.UNKNOWN,
            f"pid {pid} was recorded at launch and is running, but the "
            "supervisor instance that launched it is not the one that owns "
            "this program now, so it cannot be told apart from a reused pid",
        )
    return (
        Liveness.IN_FLIGHT,
        f"pid {pid} was recorded at launch and is running; its start identity "
        f"probe had not completed yet, and the supervisor that launched it "
        f"(pid {supervisor_pid}) is still running and still waiting for it",
    )


def worker_still_alive(attempt: AttemptRecord, *, root: Path | None = None) -> bool:
    """True only when the worker is demonstrably ours and running.

    Kept as the narrow question callers already ask. It answers False for both
    GONE and UNKNOWN, so no caller may use it to decide that a worker is gone;
    ``attempt_liveness`` is what separates those two.
    """
    verdict, _reason = attempt_liveness(attempt, root=root)
    return verdict is Liveness.ALIVE


def classify_attempt(
    attempt: AttemptRecord,
    *,
    task: ProgramTask,
    adapter: RuntimeAdapter,
    capabilities: AdapterCapabilities,
    request: AdapterRequest,
    root: Path | None = None,
) -> RecoveryVerdict:
    """Decide what may be done with one interrupted attempt.

    ``root`` is the supervisor state root. Passing it lets the in-flight launch
    record be consulted; omitting it means an attempt that never reached
    ADAPTER_RETURNED has no identity to read, and the verdict says UNKNOWN
    rather than inventing absence.
    """
    if attempt.phase is AttemptPhase.TERMINAL:
        return RecoveryVerdict(
            action=RecoveryAction.ALREADY_TERMINAL,
            confidence=attempt.confidence,
            reason="attempt already reached a terminal phase",
        )

    if attempt.confidence is ExecutionConfidence.UNCERTAIN:
        # Confidence outranks phase. An attempt can reach ADAPTER_RETURNED --
        # the adapter did return -- and still have brought back no usable
        # answer: a cancelled run, a timeout, a SIGTERM, a result that could
        # not be parsed. Routing that into "just evaluate acceptance" would
        # quietly convert an unknown external effect into a verdict, which is
        # precisely the conversion this package refuses to make anywhere.
        if capabilities.supports_resume and attempt.runtime_session_id:
            return RecoveryVerdict(
                action=RecoveryAction.RESUME_SESSION,
                confidence=ExecutionConfidence.UNCERTAIN,
                reason=(
                    "the previous run's outcome is unknown; its own session "
                    "can be continued rather than a second one started"
                ),
                resume_session_id=attempt.runtime_session_id,
            )
        return RecoveryVerdict(
            action=RecoveryAction.NEEDS_RECONCILIATION,
            confidence=ExecutionConfidence.UNCERTAIN,
            reason=(
                f"the previous run reached phase {attempt.phase.value} with an "
                "uncertain outcome, and this adapter cannot continue its "
                "session; what it changed is unknown"
            ),
        )

    if attempt.phase is AttemptPhase.ACCEPTANCE_EVALUATED:
        return RecoveryVerdict(
            action=RecoveryAction.EVALUATE_ACCEPTANCE,
            confidence=attempt.confidence,
            reason="acceptance was evaluated but the outcome was never sealed",
        )

    if attempt.phase is AttemptPhase.ADAPTER_RETURNED:
        return RecoveryVerdict(
            action=RecoveryAction.EVALUATE_ACCEPTANCE,
            confidence=attempt.confidence,
            reason=(
                "the adapter returned and acceptance was never evaluated; "
                "acceptance is read-only and repeatable"
            ),
        )

    if attempt.phase is AttemptPhase.ADAPTER_INVOKED:
        liveness, why = attempt_liveness(attempt, root=root)
        if liveness in (Liveness.ALIVE, Liveness.IN_FLIGHT):
            # IN_FLIGHT joins ALIVE here and nowhere else. Both mean "a worker
            # of ours is running", which is the only question this branch asks,
            # and neither permits a resume or a relaunch. What separates them --
            # whether the start identity has been established -- matters when
            # deciding if a pid could have been reused, and IN_FLIGHT is only
            # ever returned while the launching supervisor is still alive, which
            # is what rules that out.
            return RecoveryVerdict(
                action=RecoveryAction.WORKER_STILL_RUNNING,
                confidence=None,
                reason=why,
            )
        if liveness is Liveness.UNKNOWN:
            # Absence is not demonstrable, so it is not asserted. Resuming here
            # would be a second worker beside one that may still be running,
            # and reporting "gone" would be a claim about a process nobody
            # looked at. Both are refused: this is an operator decision, which
            # is what NEEDS_RECONCILIATION means.
            return RecoveryVerdict(
                action=RecoveryAction.NEEDS_RECONCILIATION,
                confidence=ExecutionConfidence.UNCERTAIN,
                reason=(
                    f"the worker was launched and its fate is UNKNOWN: {why}. "
                    "Whether it is still running has not been established, so "
                    "neither a resume nor a relaunch is safe; check the process "
                    "before deciding"
                ),
            )
        if capabilities.supports_resume and attempt.runtime_session_id:
            return RecoveryVerdict(
                action=RecoveryAction.RESUME_SESSION,
                confidence=ExecutionConfidence.UNCERTAIN,
                reason=(
                    f"the worker was launched and is gone ({why}); continuing "
                    "its own session rather than starting a second one"
                ),
                resume_session_id=attempt.runtime_session_id,
            )
        return RecoveryVerdict(
            action=RecoveryAction.NEEDS_RECONCILIATION,
            confidence=ExecutionConfidence.UNCERTAIN,
            reason=(
                f"the worker was launched, is gone ({why}), recorded no "
                f"outcome, and the {capabilities.adapter_id} adapter cannot "
                "resume a session; its external effect is unknown"
            ),
        )

    # INTENT_RECORDED -- the ambiguity window.
    started = adapter.probe_run_started(request)
    if started is True:
        if capabilities.supports_resume and attempt.runtime_session_id:
            return RecoveryVerdict(
                action=RecoveryAction.RESUME_SESSION,
                confidence=ExecutionConfidence.UNCERTAIN,
                reason=(
                    "the runtime has evidence this session started even though "
                    "no invocation checkpoint was written; continuing that "
                    "session, not launching a new one"
                ),
                resume_session_id=attempt.runtime_session_id,
            )
        return RecoveryVerdict(
            action=RecoveryAction.NEEDS_RECONCILIATION,
            confidence=ExecutionConfidence.UNCERTAIN,
            reason=(
                "the runtime has evidence this run started, no outcome was "
                "recorded, and this adapter cannot resume it"
            ),
        )

    if started is False:
        if task.retry_safe_when_no_launch_evidence:
            return RecoveryVerdict(
                action=RecoveryAction.SAFE_TO_LAUNCH,
                confidence=None,
                reason=(
                    "the adapter keeps launch evidence and has none for this "
                    "run, and the task declares its effect safe to repeat"
                ),
            )
        return RecoveryVerdict(
            action=RecoveryAction.NEEDS_RECONCILIATION,
            confidence=ExecutionConfidence.UNCERTAIN,
            reason=(
                "no launch evidence exists, but the task does not declare its "
                "effect safe to repeat; relaunching could duplicate work the "
                "evidence merely failed to capture"
            ),
        )

    return RecoveryVerdict(
        action=RecoveryAction.NEEDS_RECONCILIATION,
        confidence=ExecutionConfidence.UNCERTAIN,
        reason=(
            f"the {capabilities.adapter_id} adapter cannot tell whether this "
            "run ever started; the outcome stays uncertain rather than being "
            "guessed in either direction"
        ),
    )
