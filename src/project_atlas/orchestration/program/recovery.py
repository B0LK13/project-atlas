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
from project_atlas.orchestration.program.store import AttemptRecord, load_launch


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


def _same_process_older_format(live: str, recorded: str) -> bool:
    """Does a legacy 'linux:<ticks>' identity match a current 'linux:<ticks>:<boot>'?

    Only the pre-boot-id Linux shape is accepted here. Anything else -- a
    different platform prefix, a current-format identity, a malformed value --
    is not this case and must fall through to the normal verdict.
    """
    recorded_parts = recorded.split(":")
    live_parts = live.split(":")
    if len(recorded_parts) != 2 or len(live_parts) != 3:
        return False
    if recorded_parts[0] != "linux" or live_parts[0] != "linux":
        return False
    return recorded_parts[1] == live_parts[1]


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
    # HARDENING-005 G4b: an identity recorded before the boot id was added has
    # one field fewer. Its start time may still match exactly, and calling that
    # GONE would declare a genuinely running worker dead across an upgrade --
    # the one direction B1 exists to prevent. It is not ALIVE either, because
    # without the boot id a reboot cannot be ruled out. So: UNKNOWN, which
    # routes to an operator rather than to a relaunch.
    if _same_process_older_format(live, recorded_identity):
        return (
            Liveness.UNKNOWN,
            f"pid {pid} is running and matches the start time recorded at "
            "launch, but that identity predates the boot id, so a reboot "
            "cannot be ruled out",
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
    return process_liveness(pid, identity)


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
        if liveness is Liveness.ALIVE:
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
