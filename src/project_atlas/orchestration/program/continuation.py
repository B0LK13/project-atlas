"""AS-ORCH-DURABLE-CONTINUATION-001: work that outlives the session doing it.

The property this layer exists for: **a conversational session is disposable
and durable task state is authoritative.** A replacement session -- a new
supervisor process, a new terminal, a new worker session, a rebooted host --
must be able to reconstruct the correct task, its authority, its evidence and
its next concrete action from files on disk, without an operator repeating
anything and without reading any prior conversation.

Nothing here grants authority. The same boundaries hold as everywhere else in
this package::

    PROGRAM_APPROVAL          != MERGE_AUTHORIZATION
    CHECKPOINT_PRESENT        != WORK_COMPLETE
    CAPSULE_GENERATED         != AUTHORITY_GRANTED
    DECLARED_REPLAY_CLASS     != OBSERVED_OUTCOME
    RESUMABLE                 != SAFE_TO_REPEAT

Four identities, deliberately separate
--------------------------------------

Conflating any two of these is the defect class this module is built against,
and each conflation has already been observed somewhere in this program:

``task_id``     immutable. Names the unit of work in the approved program. It
                is the one identity that must be stable across every restart,
                because it is what "do not replay completed work" keys on.
``worker_id``   stable. Names the principal that does the work -- a profile's
                registered agent. Survives sessions and restarts. Authority is
                attached here, never to a session.
``session_id``  ephemeral. One process lifetime. A session ending is not a task
                event; a session id in a lease is a lease that expires when a
                terminal window closes, which is how work gets stranded.
``attempt_id``  per execution. One dispatch of one task by one worker. The
                unit a replay decision is made about.

Why a declared replay class is not an observed one
--------------------------------------------------

Three of the six ``ReplayClass`` members describe a property of the *task* and
may be declared in its envelope. Three describe a *finding* about a particular
execution and can only ever be derived by reconciliation -- a task that could
declare itself ``COMPLETED`` would be a task that can skip its own work, and a
task that could declare itself ``HUMAN_DECISION_REQUIRED`` would be a task
that can summon an operator. ``declarable()`` is enforced by the validator,
not documented and hoped for.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from project_atlas.orchestration.program.models import (
    AcceptanceCheck,
    ProgramError,
    ProgramTask,
    WorkProgram,
)
from project_atlas.orchestration.program.store import state_dir, write_json_atomic

PACKAGE_ID: Final[Literal["AS-ORCH-DURABLE-CONTINUATION-001"]] = (
    "AS-ORCH-DURABLE-CONTINUATION-001"
)
DIRECTIVE_ID: Final[Literal["ATLAS-DURABLE-AUTONOMOUS-CONTINUATION-001"]] = (
    "ATLAS-DURABLE-AUTONOMOUS-CONTINUATION-001"
)
TRUTH_BOUNDARY: Final[str] = (
    "PROGRAM_APPROVAL != MERGE_AUTHORIZATION / "
    "CHECKPOINT_PRESENT != WORK_COMPLETE / "
    "CAPSULE_GENERATED != AUTHORITY_GRANTED / "
    "DECLARED_REPLAY_CLASS != OBSERVED_OUTCOME / "
    "RESUMABLE != SAFE_TO_REPEAT"
)

#: Subdirectories of the program state directory this layer owns. Each is a
#: sibling of ``state.json``, never inside the workspace: a worker's own diff
#: must not be able to contain the record of what it is permitted to do.
ENVELOPES_DIR: Final[str] = "envelopes"
CHECKPOINTS_DIR: Final[str] = "checkpoints"
CAPSULE_NAME: Final[str] = "continuation-capsule.json"

#: Hard ceiling on a rendered capsule. A continuation capsule that grows with
#: the history it summarises is a capsule that eventually cannot be handed to
#: anything, which defeats the point. Truncation is always announced in the
#: rendered text; it is never silent.
CAPSULE_MAX_BYTES: Final[int] = 16_384

#: The schema version this code writes into, and requires from, a continuation
#: checkpoint. SKEW-1: it was ``1`` on every version up to and including
#: 643c7ebe, while the field set under the self-digest changed underneath it
#: (``execution_capture``, then ``capture``). A reader therefore had nothing to
#: compare, validated an older record into the newer model, recomputed the
#: digest over the newer field set, and reported an intact record written by an
#: older version as "truncated or edited". Bumped to ``2`` so a version skew is a
#: version skew: it is checked on the raw document BEFORE model validation and
#: BEFORE the digest, and refused as ``CHECKPOINT_VERSION_SKEW`` naming both
#: versions, in both directions. Bump it again whenever the sealed field set
#: changes.
CHECKPOINT_SCHEMA_VERSION: Final[Literal[2]] = 2

_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,190}$")
_REL_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$")
_GIT_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{40}$")
_SHA_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_ACTION_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class ContinuationError(ProgramError):
    """Any refusal raised by the durable continuation layer."""

    code = "CONTINUATION_ERROR"


class EnvelopeError(ContinuationError):
    """An envelope is missing, malformed, or claims authority it was not given."""

    code = "ENVELOPE_INVALID"


class CheckpointError(ContinuationError):
    """A checkpoint is unreadable, unsealed, or contradicts itself."""

    code = "CHECKPOINT_INVALID"


class ReplayClass(StrEnum):
    """How an interrupted execution of this work may be resumed, if at all.

    The first four are properties of the work and may be declared in an
    envelope. The last two are findings and are derived only -- see
    ``declarable()``.
    """

    #: The task reads and reports; it writes nothing outside its own evidence.
    #: Re-running it from the top is always safe.
    READ_ONLY_REPLAYABLE = "READ_ONLY_REPLAYABLE"
    #: The task mutates, but re-applying the same mutation to the same base is
    #: indistinguishable from applying it once. Safe to restart from the top.
    IDEMPOTENT_MUTATION = "IDEMPOTENT_MUTATION"
    #: The task mutates non-idempotently, but its steps are individually
    #: checkpointed, so it may continue from the step after the last one
    #: recorded complete. It may NOT be restarted from the top.
    CHECKPOINT_RESUMABLE = "CHECKPOINT_RESUMABLE"
    #: The task can produce an effect outside this machine's observation -- a
    #: push, a post, a message, a paid call. An interrupted execution is never
    #: automatically repeated, whatever the phase says.
    UNCERTAIN_EXTERNAL_EFFECT = "UNCERTAIN_EXTERNAL_EFFECT"
    #: DERIVED ONLY. The work is finished and sealed. Never replayed.
    COMPLETED = "COMPLETED"
    #: DERIVED ONLY. A person must decide before anything else happens.
    HUMAN_DECISION_REQUIRED = "HUMAN_DECISION_REQUIRED"

    def declarable(self) -> bool:
        """May a task envelope declare this class for itself?"""
        return self in _DECLARABLE


_DECLARABLE: Final[frozenset[ReplayClass]] = frozenset(
    {
        ReplayClass.READ_ONLY_REPLAYABLE,
        ReplayClass.IDEMPOTENT_MUTATION,
        ReplayClass.CHECKPOINT_RESUMABLE,
        ReplayClass.UNCERTAIN_EXTERNAL_EFFECT,
    }
)

#: Classes whose interrupted executions may be restarted from the first step.
#: ``CHECKPOINT_RESUMABLE`` is deliberately absent: resuming at step N and
#: restarting at step 0 are different acts, and this is the set for the second.
RESTARTABLE_FROM_TOP: Final[frozenset[ReplayClass]] = frozenset(
    {ReplayClass.READ_ONLY_REPLAYABLE, ReplayClass.IDEMPOTENT_MUTATION}
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    """Parse one of our own timestamps. Raises on anything else.

    Deliberately strict. A deadline that silently fails to parse is a deadline
    that never expires, and "the clock could not be read" must not become
    "there is still time".
    """
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {value!r} has no timezone")
    return parsed.astimezone(UTC)


#: How many validation errors a refusal quotes. Enough to act on, bounded so a
#: badly wrong document cannot turn one refusal into a wall of output.
_MAX_QUOTED_ERRORS: Final[int] = 3


def summarise_validation_error(exc: ValidationError) -> str:
    """One readable line per schema error: where it was and what was wrong."""
    parts: list[str] = []
    for item in exc.errors()[:_MAX_QUOTED_ERRORS]:
        where = ".".join(str(piece) for piece in item.get("loc", ())) or "<root>"
        parts.append(f"{where}: {item.get('msg', 'invalid')}")
    total = len(exc.errors())
    if total > _MAX_QUOTED_ERRORS:
        parts.append(f"(+{total - _MAX_QUOTED_ERRORS} more)")
    return "; ".join(parts)


def read_durable[DurableT: BaseModel](
    model: type[DurableT],
    raw: Any,
    *,
    path: Path,
    error: type[ContinuationError],
    code: str,
    what: str,
) -> DurableT:
    """Validate one durable document, or refuse it with a stable code.

    Every reader in this layer funnels through here, because the alternative is
    what an independent verifier found: a queue file that was valid JSON but
    schema-invalid escaped as a raw ``pydantic_core.ValidationError`` traceback.
    It failed loudly, which is better than failing silently, but a traceback is
    not a diagnostic -- it names no stable code an operator or a script can act
    on, and it does not say which file is at fault.

    A schema-invalid document is deliberately NOT treated as a missing one.
    "Never written" and "written wrongly" are different facts, and only the
    first is safe to read as an absence.
    """
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise error(
            f"{what} at {path} is schema-invalid: {summarise_validation_error(exc)}",
            code=code,
        ) from exc


def digest_payload(payload: Any) -> str:
    """A stable sha256 over a JSON-serialisable payload."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# --------------------------------------------------------------- identities


class ExecutionIdentity(BaseModel):
    """The four identities, kept apart by construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Immutable. The unit of work in the approved program.
    task_id: str = Field(min_length=1, max_length=128)
    #: Stable across sessions, restarts and hosts. The principal, not a window.
    worker_id: str = Field(min_length=1, max_length=128)
    #: Ephemeral. One process lifetime. Recorded so a stale holder is legible,
    #: never so that authority can be attached to it.
    session_id: str = Field(min_length=1, max_length=190)
    #: One execution of one task by one worker.
    attempt_id: str = Field(min_length=1, max_length=256)

    @field_validator("task_id", "worker_id", "session_id", "attempt_id")
    @classmethod
    def _ident(cls, value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise ValueError("identity must match [A-Za-z0-9][A-Za-z0-9._:-]{0,190}")
        return value

    @model_validator(mode="after")
    def _distinct(self) -> ExecutionIdentity:
        # The conflation this guard exists for is worker_id == session_id: it
        # reads as harmless (both name "who is doing it") and it is how a
        # stable principal quietly acquires a lifetime. Once that happens,
        # every lease the principal holds expires when a terminal closes.
        if self.worker_id == self.session_id:
            raise ValueError(
                "worker_id and session_id must differ: a stable principal must "
                "not inherit a session's lifetime"
            )
        if self.task_id == self.attempt_id:
            raise ValueError(
                "task_id and attempt_id must differ: an immutable unit of work "
                "must not be named after one execution of it"
            )
        return self


# --------------------------------------------------------------- envelopes


class TaskBudgets(BaseModel):
    """What one task may consume. Every field is counted against something.

    ``max_model_calls`` defaults to zero and is enforced by the dispatcher, not
    merely reported: this layer is validated with model-free fixture adapters
    and ``MODEL_BACKED_DISPATCH`` is disabled, so a budget that permitted a
    model call by default would permit exactly the thing that is switched off.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=3, ge=1, le=100)
    max_launches: int = Field(default=3, ge=1, le=1_000)
    max_wall_seconds: int = Field(default=1800, ge=1, le=86_400)
    max_model_calls: int = Field(default=0, ge=0, le=10_000)
    max_estimated_cost_usd: float = Field(default=0.0, ge=0.0, le=10_000.0)


class ConsumedBudget(BaseModel):
    """What a task has actually consumed so far. Monotonic, never decremented."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    attempts: int = Field(default=0, ge=0, le=1_000_000)
    launches: int = Field(default=0, ge=0, le=1_000_000)
    wall_seconds: float = Field(default=0.0, ge=0.0)
    model_calls: int = Field(default=0, ge=0, le=1_000_000)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)

    def exceeds(self, budgets: TaskBudgets) -> str | None:
        """The first budget this has blown, named, or None."""
        if self.attempts >= budgets.max_attempts:
            return f"attempts {self.attempts} >= max_attempts {budgets.max_attempts}"
        if self.launches >= budgets.max_launches:
            return f"launches {self.launches} >= max_launches {budgets.max_launches}"
        if self.wall_seconds >= budgets.max_wall_seconds:
            return (
                f"wall_seconds {self.wall_seconds:.0f} >= max_wall_seconds "
                f"{budgets.max_wall_seconds}"
            )
        if self.model_calls > budgets.max_model_calls:
            return (
                f"model_calls {self.model_calls} > max_model_calls "
                f"{budgets.max_model_calls}"
            )
        if self.estimated_cost_usd > budgets.max_estimated_cost_usd:
            return (
                f"estimated_cost_usd {self.estimated_cost_usd} > budget "
                f"{budgets.max_estimated_cost_usd}"
            )
        return None


class CheckpointPolicy(BaseModel):
    """The ordered steps of a task, and when a checkpoint must be taken.

    The step list is what makes "resume at the next uncompleted step" a
    mechanical operation rather than a judgement. A ``CHECKPOINT_RESUMABLE``
    task with no steps is rejected: it would have nowhere to resume to.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    steps: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    #: Write a checkpoint after every step. Turning this off is permitted only
    #: for work that is restartable from the top, and the validator enforces
    #: that -- an unresumable task that does not checkpoint cannot be resumed.
    checkpoint_after_each_step: bool = True

    @field_validator("steps")
    @classmethod
    def _steps(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not _ACTION_RE.fullmatch(item):
                raise ValueError("step names must be uppercase identifiers")
        if len(set(value)) != len(value):
            raise ValueError("duplicate step name")
        return value


class TaskEnvelope(BaseModel):
    """Everything one executable task is, may do, and may not do.

    Persisted before dispatch and re-read on every restart. It is the record a
    replacement session reconstructs authority from, which is why it carries
    the approval provenance and the exact candidate it was approved against:
    an envelope found at a different HEAD is an envelope whose authority was
    granted for other code.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-DURABLE-CONTINUATION-001"] = PACKAGE_ID
    task_id: str = Field(min_length=1, max_length=128)
    objective: str = Field(min_length=1, max_length=8192)
    depends_on: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    capabilities_required: tuple[str, ...] = Field(min_length=1, max_length=8)
    #: The exact candidate the authority below was granted against.
    candidate_head: str = Field(min_length=40, max_length=40)
    candidate_tree: str = Field(min_length=40, max_length=40)
    #: Workspace-relative prefixes. Empty ``allowed_paths`` means "mutates
    #: nothing", which is a real and useful envelope, not a mistake.
    allowed_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    forbidden_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    #: Uppercase action names. ``forbidden_actions`` is advisory to a worker and
    #: enforced here only as a refusal to dispatch when it contradicts
    #: ``allowed_actions``; the real enforcement of PUSH, MERGE and the rest
    #: lives in the owner gates, which this layer never grants.
    allowed_actions: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    forbidden_actions: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    acceptance: tuple[AcceptanceCheck, ...] = Field(min_length=1, max_length=32)
    budgets: TaskBudgets = Field(default_factory=TaskBudgets)
    #: Absolute UTC instant after which this envelope may not be dispatched.
    deadline_utc: str | None = None
    checkpoint_policy: CheckpointPolicy = Field(default_factory=CheckpointPolicy)
    #: Tasks that may be selected instead when this one blocks. Order is the
    #: preference order; each must exist in the same approved program.
    fallback_task_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    replay_class: ReplayClass
    #: Provenance of the approval this envelope rests on. Recorded, never
    #: treated as a credential: a name in a file authorises nothing.
    approved_by: str = Field(min_length=1, max_length=256)
    approval_reference: str = Field(min_length=1, max_length=512)
    profile_ref: str = Field(min_length=1, max_length=128)
    worker_id: str = Field(min_length=1, max_length=128)
    program_id: str = Field(min_length=1, max_length=128)
    created_at: str = Field(default_factory=utc_now)
    merge_authorized: Literal[False] = False
    model_backed_dispatch: Literal[False] = False

    @field_validator("task_id", "profile_ref", "worker_id", "program_id")
    @classmethod
    def _ident(cls, value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise ValueError("identifier must match [A-Za-z0-9][A-Za-z0-9._:-]{0,190}")
        return value

    @field_validator("candidate_head", "candidate_tree")
    @classmethod
    def _git(cls, value: str) -> str:
        if not _GIT_RE.fullmatch(value):
            raise ValueError("candidate head/tree must be a 40-char lowercase git SHA")
        return value

    @field_validator("allowed_paths", "forbidden_paths")
    @classmethod
    def _paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not _REL_PATH_RE.fullmatch(item) or ".." in item.split("/"):
                raise ValueError("paths must be safe workspace-relative prefixes")
        return value

    @field_validator("allowed_actions", "forbidden_actions")
    @classmethod
    def _actions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not _ACTION_RE.fullmatch(item):
                raise ValueError("action names must be uppercase identifiers")
        return value

    @field_validator("deadline_utc")
    @classmethod
    def _deadline(cls, value: str | None) -> str | None:
        if value is None:
            return None
        _parse_utc(value)
        return value

    def __init__(self, **data: Any) -> None:
        """Construct, then fail closed with a typed refusal.

        The coherence checks below are deliberately NOT a pydantic
        ``model_validator``. Pydantic wraps whatever a validator raises in a
        ``ValidationError``, which throws away the stable machine code -- and
        the code is the whole interface: a caller keys on
        ``ENVELOPE_CONTRADICTORY_PATHS``, not on a sentence that may be
        reworded. Field-shape errors still raise ``ValidationError``, which is
        correct; these are authority errors and they keep their own type.
        """
        super().__init__(**data)
        _check_envelope_coherence(self)

    def _coherent(self) -> TaskEnvelope:
        if not self.replay_class.declarable():
            raise EnvelopeError(
                f"{self.replay_class.value} is a finding, not a declaration: a "
                "task may not declare it for itself",
                code="REPLAY_CLASS_NOT_DECLARABLE",
            )
        overlap = sorted(set(self.allowed_actions) & set(self.forbidden_actions))
        if overlap:
            raise EnvelopeError(
                "an action cannot be both allowed and forbidden: "
                + ", ".join(overlap),
                code="ENVELOPE_CONTRADICTORY_ACTIONS",
            )
        for forbidden in self.forbidden_paths:
            for allowed in self.allowed_paths:
                if allowed == forbidden or allowed.startswith(forbidden.rstrip("/") + "/"):
                    raise EnvelopeError(
                        f"allowed path {allowed!r} lies inside forbidden path "
                        f"{forbidden!r}",
                        code="ENVELOPE_CONTRADICTORY_PATHS",
                    )
        if self.task_id in self.depends_on:
            raise ValueError("a task cannot depend on itself")
        if self.task_id in self.fallback_task_ids:
            raise ValueError("a task cannot be its own fallback")
        if self.replay_class is ReplayClass.CHECKPOINT_RESUMABLE:
            if not self.checkpoint_policy.steps:
                raise EnvelopeError(
                    "CHECKPOINT_RESUMABLE requires named steps to resume at",
                    code="ENVELOPE_NO_STEPS",
                )
            if not self.checkpoint_policy.checkpoint_after_each_step:
                raise EnvelopeError(
                    "CHECKPOINT_RESUMABLE requires a checkpoint after each step; "
                    "without one there is no recorded step to resume from",
                    code="ENVELOPE_NO_CHECKPOINTS",
                )
        if self.replay_class is ReplayClass.UNCERTAIN_EXTERNAL_EFFECT and (
            self.budgets.max_model_calls > 0
        ):
            # Not a moral objection: a task that may make a paid external call
            # and is also declared non-repeatable is precisely the combination
            # whose interrupted attempts must never be retried, and permitting
            # the call while MODEL_BACKED_DISPATCH is disabled would be a route
            # around the switch rather than a use of it.
            raise EnvelopeError(
                "an UNCERTAIN_EXTERNAL_EFFECT task may not budget model calls "
                "while model-backed dispatch is disabled",
                code="ENVELOPE_MODEL_CALLS_FORBIDDEN",
            )
        return self

    def digest(self) -> str:
        return digest_payload(self.model_dump(mode="json"))

    def next_step_after(self, last_completed: str | None) -> str | None:
        """The first step not yet recorded complete, or None when finished.

        ``None`` for ``last_completed`` means nothing has been completed, so
        the answer is the first step. A step name this envelope does not know
        is an error rather than a silent restart: it means the checkpoint and
        the envelope disagree about what the work is.
        """
        steps = self.checkpoint_policy.steps
        if not steps:
            return None
        if last_completed is None:
            return steps[0]
        if last_completed not in steps:
            raise CheckpointError(
                f"checkpoint names completed step {last_completed!r}, which is "
                f"not a step of task {self.task_id}",
                code="CHECKPOINT_STEP_UNKNOWN",
            )
        index = steps.index(last_completed)
        return steps[index + 1] if index + 1 < len(steps) else None


def _check_envelope_coherence(envelope: TaskEnvelope) -> None:
    envelope._coherent()


def envelope_from_task(
    task: ProgramTask,
    *,
    program: WorkProgram,
    candidate_head: str,
    candidate_tree: str,
    worker_id: str,
    replay_class: ReplayClass,
    budgets: TaskBudgets | None = None,
    checkpoint_policy: CheckpointPolicy | None = None,
    forbidden_paths: tuple[str, ...] = (),
    allowed_actions: tuple[str, ...] = (),
    forbidden_actions: tuple[str, ...] = (),
    deadline_utc: str | None = None,
) -> TaskEnvelope:
    """Derive an envelope from an already-approved program task.

    Derivation, not invention: every field either comes from the approved
    program or is supplied by the operator-facing caller. The approval
    provenance is copied from the program rather than accepted as an argument,
    so an envelope cannot be built claiming an approval the program does not
    carry.
    """
    return TaskEnvelope(
        task_id=task.task_id,
        objective=task.title,
        depends_on=task.depends_on,
        capabilities_required=tuple(cap.value for cap in task.capabilities_required),
        candidate_head=candidate_head,
        candidate_tree=candidate_tree,
        allowed_paths=task.mutation_paths,
        forbidden_paths=forbidden_paths,
        allowed_actions=allowed_actions,
        forbidden_actions=forbidden_actions,
        acceptance=task.acceptance,
        budgets=budgets or TaskBudgets(),
        deadline_utc=deadline_utc,
        checkpoint_policy=checkpoint_policy or CheckpointPolicy(),
        fallback_task_ids=(),
        replay_class=replay_class,
        approved_by=program.approved_by,
        approval_reference=program.approval_reference,
        profile_ref=task.profile_ref,
        worker_id=worker_id,
        program_id=program.program_id,
    )


def validate_envelope_for_dispatch(
    envelope: TaskEnvelope,
    *,
    program: WorkProgram,
    observed_head: str,
    observed_tree: str,
    consumed: ConsumedBudget,
    now: datetime | None = None,
) -> None:
    """Fail closed before dispatch, or return silently.

    Called immediately before every dispatch, never once at start-up. The
    reason is the defect this program has already seen twice: authority read
    at launch and cached is authority that keeps being honoured after it is
    withdrawn. A deadline that passed, a budget that emptied, an envelope for
    a task the program no longer contains and a candidate that moved are all
    conditions that become true *during* a long run.
    """
    moment = now or datetime.now(UTC)

    if envelope.program_id != program.program_id:
        raise EnvelopeError(
            f"envelope names program {envelope.program_id!r} but the approved "
            f"program is {program.program_id!r}",
            code="ENVELOPE_PROGRAM_MISMATCH",
        )
    known = {task.task_id for task in program.tasks}
    if envelope.task_id not in known:
        raise EnvelopeError(
            f"task {envelope.task_id!r} is not in the approved program; its "
            "envelope confers nothing",
            code="ENVELOPE_TASK_NOT_APPROVED",
        )
    unknown_fallbacks = sorted(set(envelope.fallback_task_ids) - known)
    if unknown_fallbacks:
        raise EnvelopeError(
            "fallback task(s) not in the approved program: "
            + ", ".join(unknown_fallbacks),
            code="ENVELOPE_FALLBACK_NOT_APPROVED",
        )
    if envelope.candidate_head != observed_head:
        raise EnvelopeError(
            f"envelope was approved against HEAD {envelope.candidate_head} but "
            f"the worktree is at {observed_head}",
            code="ENVELOPE_HEAD_MOVED",
        )
    if envelope.candidate_tree != observed_tree:
        raise EnvelopeError(
            f"envelope was approved against TREE {envelope.candidate_tree} but "
            f"the worktree is at {observed_tree}",
            code="ENVELOPE_TREE_MOVED",
        )
    if envelope.deadline_utc is not None and _parse_utc(envelope.deadline_utc) <= moment:
        raise EnvelopeError(
            f"envelope deadline {envelope.deadline_utc} has passed",
            code="ENVELOPE_DEADLINE_PASSED",
        )
    blown = consumed.exceeds(envelope.budgets)
    if blown is not None:
        raise EnvelopeError(
            f"budget exhausted for task {envelope.task_id}: {blown}",
            code="ENVELOPE_BUDGET_EXHAUSTED",
        )


def envelopes_dir(root: Path) -> Path:
    return state_dir(root) / ENVELOPES_DIR


def checkpoints_dir(root: Path) -> Path:
    return state_dir(root) / CHECKPOINTS_DIR


def _safe_name(value: str, suffix: str) -> str:
    """A collision-free filename for an identifier from a program file.

    Hashed rather than sanitised: two task ids that sanitise to the same name
    would share a file, and one task overwriting another's envelope is worse
    than an opaque filename. The readable id is inside the file.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest() + suffix


def persist_envelope(root: Path, envelope: TaskEnvelope) -> Path:
    target = envelopes_dir(root) / _safe_name(envelope.task_id, ".envelope.json")
    return write_json_atomic(target, envelope.model_dump(mode="json"))


def load_envelope(root: Path, task_id: str) -> TaskEnvelope | None:
    """Read one envelope. ``None`` means none was ever written.

    A present-but-unreadable envelope raises instead: "no authority was
    recorded" and "the record of authority is corrupt" are different facts and
    only the first of them is safe to treat as an absence.
    """
    path = envelopes_dir(root) / _safe_name(task_id, ".envelope.json")
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EnvelopeError(
            f"envelope for {task_id} at {path} is unreadable: {exc}",
            code="ENVELOPE_UNREADABLE",
        ) from exc
    envelope = read_durable(
        TaskEnvelope,
        raw,
        path=path,
        error=EnvelopeError,
        code="ENVELOPE_SCHEMA_INVALID",
        what=f"envelope for {task_id}",
    )
    if envelope.task_id != task_id:
        raise EnvelopeError(
            f"envelope file for {task_id} names task {envelope.task_id}",
            code="ENVELOPE_TASK_MISMATCH",
        )
    return envelope


def list_envelopes(root: Path) -> tuple[TaskEnvelope, ...]:
    directory = envelopes_dir(root)
    if not directory.is_dir():
        return ()
    found: list[TaskEnvelope] = []
    for path in sorted(directory.glob("*.envelope.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EnvelopeError(
                f"envelope at {path} is unreadable: {exc}", code="ENVELOPE_UNREADABLE"
            ) from exc
        found.append(
            read_durable(
                TaskEnvelope,
                raw,
                path=path,
                error=EnvelopeError,
                code="ENVELOPE_SCHEMA_INVALID",
                what="envelope",
            )
        )
    return tuple(sorted(found, key=lambda item: item.task_id))


# ------------------------------------------------------------- checkpoints


class ExecutionCapture(StrEnum):
    """Was this checkpoint's execution detail observed, or merely absent?

    The distinction G4 is about. A checkpoint whose ``changed_files``,
    ``commands`` and ``artifacts`` are empty is saying one of two completely
    different things, and until this existed a reader could not tell which:

      ``OBSERVED``      a writer captured at least one of the lists from a
                        record of the execution. WHICH lists is stated per
                        field in ``ContinuationCheckpoint.capture``; a list
                        whose field is CAPTURE_AVAILABLE and empty means
                        nothing was observed for it.
      ``NOT_CAPTURED``  nobody captured anything. Empty means nobody looked,
                        and the absence carries no information about what the
                        worker did.

    ``NOT_CAPTURED`` is the honest default for a writer that made no capture
    statement at all.
    """

    OBSERVED = "OBSERVED"
    NOT_CAPTURED = "NOT_CAPTURED"


class CaptureStatus(StrEnum):
    """Whether ONE execution-detail field was actually captured.

    ``ExecutionCapture`` answers for the checkpoint as a whole; this answers per
    field, because the fields have different sources and one can be available
    while another is not. A supervisor that recorded the adapter's command line
    but never watched individual file writes must be able to say exactly that.
    """

    CAPTURE_AVAILABLE = "CAPTURE_AVAILABLE"
    CAPTURE_UNAVAILABLE = "CAPTURE_UNAVAILABLE"


class FieldCapture(BaseModel):
    """The capture statement for one field: available or not, and why.

    ``reason`` is scoped to THIS field and THIS writer -- "the supervisor
    records no per-file write observation" -- never a generic "not captured".
    ``source`` names the durable record the value was read from when it was
    available, so a reader can go and look.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: CaptureStatus = CaptureStatus.CAPTURE_UNAVAILABLE
    reason: str = Field(
        default="no per-field capture statement was recorded by the writer",
        min_length=1,
        max_length=512,
    )
    source: str = Field(default="", max_length=1024)


class ExecutionCaptureReport(BaseModel):
    """Per-field capture statements for ``commands``, ``artifacts``, ``changed_files``.

    The default is UNAVAILABLE for every field with a reason that says the
    writer made no statement -- which is what a checkpoint from a writer that
    predates this report actually tells us. Nothing here is inferred from the
    lists themselves: a non-empty list beside an UNAVAILABLE statement is a
    writer that listed things without saying how it knew, and that is
    rendered as such rather than upgraded.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    commands: FieldCapture = Field(default_factory=FieldCapture)
    artifacts: FieldCapture = Field(default_factory=FieldCapture)
    changed_files: FieldCapture = Field(default_factory=FieldCapture)

    def any_available(self) -> bool:
        return any(
            item.status is CaptureStatus.CAPTURE_AVAILABLE
            for item in (self.commands, self.artifacts, self.changed_files)
        )


class CommandRecord(BaseModel):
    """One command this task ran, and what was observed of it.

    ``exit_status`` of ``None`` means the command's outcome was never observed
    -- it was still running when the process died. That is the record that
    makes an uncertain external effect visible instead of invisible, so it is
    a real value rather than a gap.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    argv: tuple[str, ...] = Field(min_length=1, max_length=64)
    started_at: str
    ended_at: str | None = None
    exit_status: int | None = None
    #: Bounded tail of the observed output. Evidence, never authority.
    output_tail: str = Field(default="", max_length=4096)


class ArtifactRecord(BaseModel):
    """One artifact this task produced, with the hash that identifies it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(min_length=64, max_length=64)
    bytes: int = Field(ge=0)

    @field_validator("sha256")
    @classmethod
    def _sha(cls, value: str) -> str:
        if not _SHA_RE.fullmatch(value):
            raise ValueError("sha256 must be lowercase hex")
        return value


class ExternalEffectReceipt(BaseModel):
    """A record that something may have happened outside this machine.

    ``confirmed`` is three-valued on purpose. ``True`` means the effect was
    observed to have landed, ``False`` that it was observed not to have, and
    ``None`` that nobody knows -- which is the whole reason this record exists.
    A ``None`` receipt is what turns a restart into a reconciliation instead of
    a replay.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_id: str = Field(min_length=1, max_length=190)
    kind: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    recorded_at: str
    confirmed: bool | None = None
    evidence_digest: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator("receipt_id")
    @classmethod
    def _ident(cls, value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise ValueError("receipt_id must be a safe identifier")
        return value

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if not _ACTION_RE.fullmatch(value):
            raise ValueError("receipt kind must be an uppercase identifier")
        return value


class LeaseSnapshot(BaseModel):
    """The lease this execution held, as it stood when the checkpoint was taken.

    Recorded rather than looked up, because the point of a checkpoint is to be
    readable when the thing that held the lease is gone. ``expires_at`` is what
    a successor checks before reacquiring: work is reacquired after expiry and
    an identity check, never because the previous holder stopped answering.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    lease_id: str = Field(min_length=1, max_length=256)
    holder_worker_id: str = Field(min_length=1, max_length=128)
    holder_session_id: str = Field(min_length=1, max_length=190)
    granted_at: str
    expires_at: str

    def expired(self, now: datetime | None = None) -> bool:
        return _parse_utc(self.expires_at) <= (now or datetime.now(UTC))


class ContinuationCheckpoint(BaseModel):
    """One atomic, self-verifying record of where a task actually is.

    Written before the effect it precedes, never after, and sealed with a
    digest over its own content so a truncated or edited record is detectable
    rather than merely suspicious. ``sequence`` is monotonic per task: a
    checkpoint whose sequence went backwards is a contradiction, and this layer
    stops rather than deciding which copy to believe.
    """

    model_config = ConfigDict(extra="forbid")

    #: See ``CHECKPOINT_SCHEMA_VERSION``. Covered by the self-digest like every
    #: other field, and checked on the raw document before anything else.
    schema_version: Literal[2] = CHECKPOINT_SCHEMA_VERSION
    package_id: Literal["AS-ORCH-DURABLE-CONTINUATION-001"] = PACKAGE_ID
    identity: ExecutionIdentity
    envelope_digest: str = Field(min_length=64, max_length=64)
    program_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1, le=1_000_000)
    recorded_at: str = Field(default_factory=utc_now)
    #: The last step recorded complete, and the concrete next action. Both, so
    #: a reader never has to infer one from the other.
    last_completed_step: str | None = None
    next_action: str = Field(min_length=1, max_length=2048)
    #: Worktree and git state, so a replacement session knows what code this
    #: was done against without asking anybody.
    worktree_path: str = Field(min_length=1, max_length=4096)
    git_head: str = Field(min_length=40, max_length=40)
    git_tree: str = Field(min_length=40, max_length=40)
    git_branch: str = Field(default="", max_length=256)
    git_dirty: bool = False
    #: Whether the execution detail below was actually observed. G4: a
    #: BOUNDARY projection writes at program boundaries and never watches a
    #: worker, so it cannot know what the worker changed, ran, or produced.
    #:
    #: Empty lists were therefore ambiguous in the worst way -- "nothing
    #: happened" and "nobody looked" rendered identically, and a replacement
    #: session could not tell a clean task from an unobserved one. This says
    #: which, explicitly. It does NOT invent the missing detail: inferring
    #: commands from a workspace diff would be manufacturing history.
    execution_capture: ExecutionCapture = ExecutionCapture.NOT_CAPTURED
    #: Per-field capture statements. ``execution_capture`` says whether ANY
    #: writer observed anything; this says, for each of the three lists, whether
    #: it was captured and from which record -- so "commands captured from the
    #: adapter transcript, changed files not observed at all" is expressible
    #: instead of being flattened into one OBSERVED.
    capture: ExecutionCaptureReport = Field(default_factory=ExecutionCaptureReport)
    changed_files: tuple[str, ...] = Field(default_factory=tuple, max_length=512)
    commands: tuple[CommandRecord, ...] = Field(default_factory=tuple, max_length=64)
    lease: LeaseSnapshot | None = None
    deadline_utc: str | None = None
    process_pid: int | None = Field(default=None, ge=0, le=2**31 - 1)
    #: Paired with the pid, always. A pid on its own cannot be told apart from
    #: a reused one, which is the defect this program has already fixed twice.
    process_start_identity: str | None = Field(default=None, max_length=256)
    artifacts: tuple[ArtifactRecord, ...] = Field(default_factory=tuple, max_length=256)
    consumed_budget: ConsumedBudget = Field(default_factory=ConsumedBudget)
    blockers: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    uncertainty: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    external_effects: tuple[ExternalEffectReceipt, ...] = Field(
        default_factory=tuple, max_length=64
    )
    #: The class this execution is being treated as. Copied from the envelope
    #: at dispatch and never widened afterwards -- a checkpoint that relaxed
    #: its own replay class would be a task granting itself a replay.
    replay_class: ReplayClass
    terminal: bool = False
    truth_boundary: str = TRUTH_BOUNDARY
    #: sha256 over every other field. Set by ``seal_checkpoint``.
    self_digest: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator("git_head", "git_tree")
    @classmethod
    def _git(cls, value: str) -> str:
        if not _GIT_RE.fullmatch(value):
            raise ValueError("git head/tree must be a 40-char lowercase git SHA")
        return value

    def __init__(self, **data: Any) -> None:
        """Construct, then fail closed with a typed refusal. See TaskEnvelope."""
        super().__init__(**data)
        _check_checkpoint_coherence(self)

    def _paired_identity(self) -> ContinuationCheckpoint:
        if self.process_pid is not None and not self.process_start_identity:
            raise CheckpointError(
                "a recorded pid must travel with the start identity that tells "
                "it apart from a reused pid",
                code="CHECKPOINT_PID_WITHOUT_IDENTITY",
            )
        if self.replay_class in (
            ReplayClass.COMPLETED,
            ReplayClass.HUMAN_DECISION_REQUIRED,
        ) and not self.terminal:
            raise CheckpointError(
                f"{self.replay_class.value} is only reachable on a terminal "
                "checkpoint",
                code="CHECKPOINT_CLASS_NOT_TERMINAL",
            )
        return self

    def unsealed_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload.pop("self_digest", None)
        return payload


def _check_checkpoint_coherence(checkpoint: ContinuationCheckpoint) -> None:
    checkpoint._paired_identity()


def seal_checkpoint(checkpoint: ContinuationCheckpoint) -> ContinuationCheckpoint:
    """Stamp a checkpoint with the digest of its own content."""
    sealed = checkpoint.model_copy(deep=True)
    sealed.self_digest = digest_payload(sealed.unsealed_payload())
    return sealed


def verify_checkpoint(checkpoint: ContinuationCheckpoint) -> ContinuationCheckpoint:
    """Return the checkpoint, or refuse it. Never repairs it.

    A checkpoint that does not verify is not silently rewritten, re-sealed, or
    partially trusted. The directive's requirement is exact: corrupt,
    contradictory or incomplete state fails closed without being silently
    repaired. Repairing it here would be this layer deciding what the previous
    execution had done, which is the one judgement it is not entitled to make.
    """
    if not checkpoint.self_digest:
        raise CheckpointError(
            "checkpoint carries no self digest, so it cannot be told apart "
            "from a truncated or edited one",
            code="CHECKPOINT_UNSEALED",
        )
    expected = digest_payload(checkpoint.unsealed_payload())
    if expected != checkpoint.self_digest:
        raise CheckpointError(
            "checkpoint self digest does not match its content; it was "
            "truncated or edited after it was written",
            code="CHECKPOINT_DIGEST_MISMATCH",
        )
    return checkpoint


def _check_checkpoint_version(raw: Any, *, path: Path, what: str) -> None:
    """Refuse a checkpoint written at another schema version, before anything else.

    SKEW-1. Runs on the raw document, ahead of model validation and ahead of
    the self-digest, because both of those are defined by THIS version's field
    set: an older record validated into the newer model picks up defaults and
    then fails its digest ("truncated or edited"), and a newer record fails
    validation on fields this version does not know ("malformed"). Both
    accusations are false for an intact record from another version, and they
    call for the opposite operator response -- a corrupt root invites a wipe,
    a skew calls for finishing or reverting the upgrade.

    Only an explicit integer ``schema_version`` that differs from
    ``CHECKPOINT_SCHEMA_VERSION`` is a version statement. A document that is
    not an object, that has no ``schema_version``, or whose value is not an
    integer makes no such statement and is left to schema validation, which
    refuses it as before. The skew refusal says what the record CLAIMS; it
    cannot verify the record's integrity, because the digest of another
    version's field set is not computable here. It is never launchable.
    """
    if not isinstance(raw, dict) or "schema_version" not in raw:
        return
    declared = raw["schema_version"]
    if type(declared) is not int or declared == CHECKPOINT_SCHEMA_VERSION:
        return
    reader = CHECKPOINT_SCHEMA_VERSION
    direction = "an OLDER" if declared < reader else "a NEWER"
    raise CheckpointError(
        f"{what} at {path} was written at checkpoint schema_version {declared} "
        f"by {direction} version of this package, and this reader understands "
        f"schema_version {reader} (writer_schema_version={declared}, "
        f"reader_schema_version={reader}). This is version skew, not evidence "
        "of truncation or tampering: the record's integrity cannot be checked "
        "across versions, so nothing proceeds from it. Finish or revert the "
        "upgrade, or reconcile the task explicitly; do not wipe the state root "
        "on the strength of this refusal.",
        code="CHECKPOINT_VERSION_SKEW",
    )


def persist_checkpoint(
    root: Path, checkpoint: ContinuationCheckpoint
) -> ContinuationCheckpoint:
    """Seal, refuse a backwards sequence, then write atomically.

    The sequence check happens here rather than in the caller because this is
    the only funnel every writer passes through. A checkpoint arriving with a
    sequence at or below the one already on disk is two writers disagreeing
    about the same task, and the write is refused rather than applied -- the
    older record is left intact for a human to look at.
    """
    existing = load_checkpoint(root, checkpoint.identity.task_id, verify=False)
    if existing is not None and checkpoint.sequence <= existing.sequence:
        raise CheckpointError(
            f"refusing to write checkpoint sequence {checkpoint.sequence} for "
            f"task {checkpoint.identity.task_id}: sequence {existing.sequence} "
            "is already on disk, so two writers disagree about this task",
            code="CHECKPOINT_SEQUENCE_REGRESSION",
        )
    sealed = seal_checkpoint(checkpoint)
    target = checkpoints_dir(root) / _safe_name(
        checkpoint.identity.task_id, ".checkpoint.json"
    )
    write_json_atomic(target, sealed.model_dump(mode="json"))
    return sealed


def load_checkpoint(
    root: Path, task_id: str, *, verify: bool = True
) -> ContinuationCheckpoint | None:
    """Read the checkpoint for one task.

    ``None`` means none was ever written. Anything present but unusable
    raises: an unreadable checkpoint is not an absent one, and treating it as
    absent is how a restart turns into a replay.

    ``verify=False`` exists for exactly one caller -- ``persist_checkpoint``
    reading the previous sequence -- because a corrupt record must still block
    a write rather than be overwritten by it.
    """
    path = checkpoints_dir(root) / _safe_name(task_id, ".checkpoint.json")
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(
            f"checkpoint for {task_id} at {path} is unreadable: {exc}",
            code="CHECKPOINT_UNREADABLE",
        ) from exc
    # SKEW-1: before validation and before the digest, and regardless of
    # ``verify`` -- a record from another version must block a write exactly as
    # a corrupt one does, rather than be overwritten by it.
    _check_checkpoint_version(raw, path=path, what=f"checkpoint for {task_id}")
    try:
        checkpoint = ContinuationCheckpoint.model_validate(raw)
    except CheckpointError:
        raise
    except Exception as exc:
        raise CheckpointError(
            f"checkpoint for {task_id} at {path} is malformed: {exc}",
            code="CHECKPOINT_MALFORMED",
        ) from exc
    if checkpoint.identity.task_id != task_id:
        raise CheckpointError(
            f"checkpoint file for {task_id} names task "
            f"{checkpoint.identity.task_id}",
            code="CHECKPOINT_TASK_MISMATCH",
        )
    return verify_checkpoint(checkpoint) if verify else checkpoint


def list_checkpoints(
    root: Path, *, verify: bool = True
) -> tuple[ContinuationCheckpoint, ...]:
    directory = checkpoints_dir(root)
    if not directory.is_dir():
        return ()
    found: list[ContinuationCheckpoint] = []
    for path in sorted(directory.glob("*.checkpoint.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(
                f"checkpoint at {path} is unreadable: {exc}",
                code="CHECKPOINT_UNREADABLE",
            ) from exc
        _check_checkpoint_version(raw, path=path, what="checkpoint")
        checkpoint = read_durable(
            ContinuationCheckpoint,
            raw,
            path=path,
            error=CheckpointError,
            code="CHECKPOINT_SCHEMA_INVALID",
            what="checkpoint",
        )
        found.append(verify_checkpoint(checkpoint) if verify else checkpoint)
    return tuple(sorted(found, key=lambda item: item.identity.task_id))


def file_sha256(path: Path) -> tuple[str, int]:
    """Digest and size of one file, streamed."""
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1 << 16)
            if not chunk:
                break
            total += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), total


def artifact_record(path: Path, *, relative_to: Path | None = None) -> ArtifactRecord:
    sha, size = file_sha256(path)
    shown = str(path.relative_to(relative_to)) if relative_to else str(path)
    return ArtifactRecord(path=shown, sha256=sha, bytes=size)


def new_session_id(prefix: str = "session") -> str:
    """An ephemeral session id that carries its own process identity.

    Built from the pid and a monotonic-ish timestamp rather than a bare random
    token so that a stale session id in a lease can be *investigated* -- a
    reader can ask whether that pid is alive -- instead of only being noticed.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}.{os.getpid()}.{stamp}"
