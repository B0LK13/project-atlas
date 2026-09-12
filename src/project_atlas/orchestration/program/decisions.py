"""The durable human decision queue. Asked once, in writing, then moved on.

The behaviour this exists to replace is an agent that hits a blocker and keeps
raising it -- re-asking, re-polling, restating -- which burns the run and
teaches an operator to stop reading. The rule here is the opposite:

    **One blocker, one durable record, then different work.**

A decision request is keyed by what it is actually about, not by when it was
raised. Re-raising the same blocker finds the open record and touches its
``last_seen_at`` -- it does not create a second request, it does not re-notify,
and it does not stop the dispatcher. The task yields its lease and something
else eligible runs.

What must route here rather than being decided automatically, verbatim from the
governing directive: permission, budget, scope expansion, merge, credential,
ACL, service, push, release, and any uncertain external effect. None of these
is a retry and none of them becomes true by being asked again.

Nothing in this module grants anything. Recording that an operator answered is
an *evidence* act: the answer is written down with who gave it and when, and
the gates that actually hold authority -- ``autonomy.owner_gates`` and the
program's own approval -- are unchanged by it. A resolved decision unblocks a
task's selection; it does not widen what that task may do.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.program.continuation import (
    PACKAGE_ID,
    ContinuationError,
    digest_payload,
    read_durable,
    utc_now,
)
from project_atlas.orchestration.program.store import state_dir, write_json_atomic

DECISIONS_DIR: Final[str] = "decisions"
_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,190}$")


class DecisionError(ContinuationError):
    code = "DECISION_QUEUE_ERROR"


class DecisionKind(StrEnum):
    """Categories that are always an operator's, never an agent's.

    Closed on purpose. A blocker that does not fit one of these is not
    automatically an operator decision -- it is usually a bug or a missing
    capability, and giving it a catch-all category would turn "I could not do
    this" into "a human must do this", which is how a decision queue fills up
    with things nobody can act on.
    """

    PERMISSION = "PERMISSION"
    BUDGET_INCREASE = "BUDGET_INCREASE"
    SCOPE_EXPANSION = "SCOPE_EXPANSION"
    MERGE = "MERGE"
    PUSH = "PUSH"
    RELEASE = "RELEASE"
    CREDENTIAL = "CREDENTIAL"
    ACL_OR_ACCOUNT = "ACL_OR_ACCOUNT"
    SERVICE_CHANGE = "SERVICE_CHANGE"
    UNCERTAIN_EXTERNAL_EFFECT = "UNCERTAIN_EXTERNAL_EFFECT"


class DecisionStatus(StrEnum):
    OPEN = "OPEN"
    #: An operator recorded an answer. What that answer permits is decided by
    #: the gates, not by this record.
    ANSWERED = "ANSWERED"
    #: The question stopped being live -- the task was cancelled, the program
    #: superseded. Distinct from ANSWERED: nobody decided anything.
    WITHDRAWN = "WITHDRAWN"


class DecisionRequest(BaseModel):
    """One thing a person must decide, recorded once and never re-asked."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-DURABLE-CONTINUATION-001"] = PACKAGE_ID
    decision_id: str = Field(min_length=1, max_length=190)
    program_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=128)
    kind: DecisionKind
    #: What is being asked, in a sentence an operator can act on without
    #: reading the code. Not a stack trace and not an apology.
    question: str = Field(min_length=1, max_length=4096)
    #: What the agent already established, so the operator is not asked to
    #: re-derive it.
    evidence: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    #: Exactly what would happen if the answer were yes. Written before the
    #: answer, so a granted decision cannot quietly acquire a wider effect.
    requested_action: str = Field(min_length=1, max_length=2048)
    raised_by_worker_id: str = Field(min_length=1, max_length=128)
    raised_by_session_id: str = Field(min_length=1, max_length=190)
    raised_at: str = Field(default_factory=utc_now)
    #: Bumped when the same blocker recurs. The count is the honest measure of
    #: how often the work has hit this, and it costs one file write, not a
    #: second request and not a second notification.
    last_seen_at: str = Field(default_factory=utc_now)
    seen_count: int = Field(default=1, ge=1, le=1_000_000)
    status: DecisionStatus = DecisionStatus.OPEN
    answered_by: str | None = Field(default=None, max_length=256)
    answered_at: str | None = None
    answer: str | None = Field(default=None, max_length=4096)
    merge_authorized: Literal[False] = False

    @field_validator("decision_id", "program_id", "task_id", "raised_by_worker_id")
    @classmethod
    def _ident(cls, value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise ValueError("identifier must be a safe id")
        return value


def decisions_dir(root: Path) -> Path:
    return state_dir(root) / DECISIONS_DIR


def decision_id_for(
    *, program_id: str, task_id: str, kind: DecisionKind, subject: str
) -> str:
    """A stable id for one blocker, so re-raising it finds the same record.

    ``subject`` is what the question is *about* -- a path, a budget name, a
    remote -- not the question text. Keying on the text would make a reworded
    question a new question, which is precisely the re-asking this module
    exists to stop.
    """
    digest = digest_payload(
        {
            "program_id": program_id,
            "task_id": task_id,
            "kind": kind.value,
            "subject": subject,
        }
    )
    return f"{task_id}.{kind.value}.{digest[:16]}"


def _path_for(root: Path, decision_id: str) -> Path:
    name = hashlib.sha256(decision_id.encode("utf-8")).hexdigest() + ".decision.json"
    return decisions_dir(root) / name


def load_decision(root: Path, decision_id: str) -> DecisionRequest | None:
    path = _path_for(root, decision_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecisionError(
            f"decision {decision_id} at {path} is unreadable: {exc}",
            code="DECISION_UNREADABLE",
        ) from exc
    return read_durable(
        DecisionRequest,
        raw,
        path=path,
        error=DecisionError,
        code="DECISION_SCHEMA_INVALID",
        what=f"decision {decision_id}",
    )


def raise_decision(
    root: Path,
    *,
    program_id: str,
    task_id: str,
    kind: DecisionKind,
    subject: str,
    question: str,
    requested_action: str,
    worker_id: str,
    session_id: str,
    evidence: tuple[str, ...] = (),
) -> tuple[DecisionRequest, bool]:
    """Record a blocker once. Returns the record and whether it is new.

    ``newly_raised`` is False for a recurrence, and callers use it to decide
    whether to notify. That single boolean is the whole difference between a
    decision queue an operator reads and one they filter out.

    A recurrence of an *answered* decision is deliberately not reopened here:
    an operator answered the question, and an agent deciding that the answer
    did not take is an agent overriding an operator. It is recorded as seen
    and the caller finds a still-answered record.
    """
    decision_id = decision_id_for(
        program_id=program_id, task_id=task_id, kind=kind, subject=subject
    )
    existing = load_decision(root, decision_id)
    if existing is not None:
        existing.last_seen_at = utc_now()
        existing.seen_count = min(existing.seen_count + 1, 1_000_000)
        write_json_atomic(_path_for(root, decision_id), existing.model_dump(mode="json"))
        return existing, False
    request = DecisionRequest(
        decision_id=decision_id,
        program_id=program_id,
        task_id=task_id,
        kind=kind,
        question=question,
        evidence=evidence,
        requested_action=requested_action,
        raised_by_worker_id=worker_id,
        raised_by_session_id=session_id,
    )
    write_json_atomic(_path_for(root, decision_id), request.model_dump(mode="json"))
    return request, True


def record_answer(
    root: Path, decision_id: str, *, answered_by: str, answer: str
) -> DecisionRequest:
    """Write down that an operator answered. Grants nothing by itself.

    The refusal to re-answer an answered decision is not pedantry: a second
    answer overwriting the first would erase who decided what, and the record
    of an operator's decision is the only evidence this layer has that a human
    was ever involved.
    """
    request = load_decision(root, decision_id)
    if request is None:
        raise DecisionError(
            f"no decision recorded with id {decision_id}", code="DECISION_MISSING"
        )
    if request.status is not DecisionStatus.OPEN:
        raise DecisionError(
            f"decision {decision_id} is already {request.status.value}; it was "
            f"answered by {request.answered_by} at {request.answered_at}",
            code="DECISION_NOT_OPEN",
        )
    request.status = DecisionStatus.ANSWERED
    request.answered_by = answered_by
    request.answered_at = utc_now()
    request.answer = answer
    write_json_atomic(_path_for(root, decision_id), request.model_dump(mode="json"))
    return request


def withdraw_decision(root: Path, decision_id: str, *, reason: str) -> DecisionRequest:
    """Mark a question no longer live. Never conflated with answering it."""
    request = load_decision(root, decision_id)
    if request is None:
        raise DecisionError(
            f"no decision recorded with id {decision_id}", code="DECISION_MISSING"
        )
    if request.status is DecisionStatus.ANSWERED:
        raise DecisionError(
            f"decision {decision_id} was answered by {request.answered_by}; an "
            "answered decision is not withdrawn",
            code="DECISION_ALREADY_ANSWERED",
        )
    request.status = DecisionStatus.WITHDRAWN
    request.answer = reason
    request.answered_at = utc_now()
    write_json_atomic(_path_for(root, decision_id), request.model_dump(mode="json"))
    return request


def list_decisions(
    root: Path, *, status: DecisionStatus | None = None
) -> tuple[DecisionRequest, ...]:
    directory = decisions_dir(root)
    if not directory.is_dir():
        return ()
    found: list[DecisionRequest] = []
    for path in sorted(directory.glob("*.decision.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DecisionError(
                f"decision at {path} is unreadable: {exc}", code="DECISION_UNREADABLE"
            ) from exc
        request = read_durable(
            DecisionRequest,
            raw,
            path=path,
            error=DecisionError,
            code="DECISION_SCHEMA_INVALID",
            what="decision",
        )
        if status is None or request.status is status:
            found.append(request)
    return tuple(sorted(found, key=lambda item: (item.task_id, item.decision_id)))


def blocked_task_ids(root: Path) -> frozenset[str]:
    """Tasks with an open decision against them.

    Used by selection to skip a task rather than re-ask its question. A task
    with an ANSWERED decision is deliberately absent from this set: the
    operator has spoken and the work is eligible again.
    """
    return frozenset(
        request.task_id for request in list_decisions(root, status=DecisionStatus.OPEN)
    )


def parse_utc(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(text).astimezone(UTC)
