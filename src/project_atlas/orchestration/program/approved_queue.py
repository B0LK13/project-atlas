"""The approved-work queue: the only place the dispatcher may get work from.

The dispatcher never discovers work. It never scans the repository for
something that looks useful, never reads a backlog file and decides an
unchecked box is a task, and never manufactures a placeholder to look busy
while it waits. It executes programs an operator **admitted** to this queue,
and nothing else.

Admission is a deliberate human act with a receipt:

    atlas program queue admit --queue-root <Q> --program ./p.json \\
        --admitted-by "$USER" --reference "<where the approval is written>"

What admission records is a *pin*, not a path: the program file's sha256 at the
moment it was admitted. A queued entry whose file no longer hashes to that
digest is refused at read time rather than executed, because "the operator
approved this program" and "the operator approved whatever is at this path
now" are different statements and only the first one is true.

Removal is equally explicit. A completed program stays in the queue as a
completed entry -- it is not deleted, because deleting it would make "has this
already run?" unanswerable and the next restart would be free to run it again.
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.program.continuation import (
    PACKAGE_ID,
    ContinuationError,
    file_sha256,
    read_durable,
    utc_now,
)
from project_atlas.orchestration.program.store import write_json_atomic

QUEUE_NAME: Final[str] = "approved-work-queue.json"
_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,190}$")


class QueueError(ContinuationError):
    code = "APPROVED_QUEUE_ERROR"


class QueueEntryStatus(StrEnum):
    """Where one admitted program stands.

    ``COMPLETE`` is terminal and is what stops a finished program from being
    restarted. ``QUARANTINED`` is its opposite in the same way ``UNCERTAIN`` is
    the opposite of ``CONFIRMED``: something happened that nobody has resolved,
    and the dispatcher must not touch it until a person does.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    QUARANTINED = "QUARANTINED"
    #: Admitted, then explicitly withdrawn by an operator. Kept, not deleted.
    WITHDRAWN = "WITHDRAWN"


#: Statuses the dispatcher may pick up. Explicit, so a new status cannot become
#: runnable merely by existing.
RUNNABLE_STATUSES: Final[frozenset[QueueEntryStatus]] = frozenset(
    {QueueEntryStatus.PENDING, QueueEntryStatus.RUNNING}
)


class QueueEntry(BaseModel):
    """One admitted program, pinned to the bytes that were admitted."""

    model_config = ConfigDict(extra="forbid")

    program_id: str = Field(min_length=1, max_length=128)
    program_path: str = Field(min_length=1, max_length=4096)
    program_sha256: str = Field(min_length=64, max_length=64)
    state_root: str = Field(min_length=1, max_length=4096)
    admitted_by: str = Field(min_length=1, max_length=256)
    admitted_at: str = Field(default_factory=utc_now)
    #: Where the approval is written down. Provenance; never a credential.
    reference: str = Field(min_length=1, max_length=512)
    status: QueueEntryStatus = QueueEntryStatus.PENDING
    last_stop_reason: str | None = Field(default=None, max_length=128)
    last_run_at: str | None = None
    runs: int = Field(default=0, ge=0, le=1_000_000)
    note: str = Field(default="", max_length=1024)

    @field_validator("program_id")
    @classmethod
    def _ident(cls, value: str) -> str:
        if not _ID_RE.fullmatch(value):
            raise ValueError("program_id must be a safe identifier")
        return value


class ApprovedWorkQueue(BaseModel):
    """The whole queue. Small, atomic, and read fresh on every tick."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-DURABLE-CONTINUATION-001"] = PACKAGE_ID
    updated_at: str = Field(default_factory=utc_now)
    entries: dict[str, QueueEntry] = Field(default_factory=dict)
    merge_authorized: Literal[False] = False

    def runnable(self) -> tuple[QueueEntry, ...]:
        """Entries the dispatcher may pick up, in a stable order.

        Ordered by admission time, then program id: first admitted, first run.
        A stable order matters because an unstable one makes "launched exactly
        once" hard to assert and easy to violate under a restart.
        """
        return tuple(
            sorted(
                (e for e in self.entries.values() if e.status in RUNNABLE_STATUSES),
                key=lambda e: (e.admitted_at, e.program_id),
            )
        )


def queue_path(queue_root: Path) -> Path:
    return queue_root / QUEUE_NAME


def load_queue(queue_root: Path) -> ApprovedWorkQueue:
    """Read the queue. A missing queue is empty; an unreadable one is an error."""
    path = queue_path(queue_root)
    if not path.is_file():
        return ApprovedWorkQueue()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QueueError(
            f"approved work queue at {path} is unreadable: {exc}",
            code="QUEUE_UNREADABLE",
        ) from exc
    return read_durable(
        ApprovedWorkQueue,
        raw,
        path=path,
        error=QueueError,
        code="QUEUE_SCHEMA_INVALID",
        what="approved work queue",
    )


def persist_queue(queue_root: Path, queue: ApprovedWorkQueue) -> Path:
    queue.updated_at = utc_now()
    return write_json_atomic(queue_path(queue_root), queue.model_dump(mode="json"))


def admit(
    queue_root: Path,
    *,
    program_path: Path,
    program_id: str,
    state_root: Path,
    admitted_by: str,
    reference: str,
    note: str = "",
) -> QueueEntry:
    """Admit one approved program, pinned to its current bytes.

    Re-admitting a program id that is already present is refused rather than
    silently replacing it. Replacement would let an admitted program be swapped
    for different work under the same name, which is the exact substitution the
    digest pin exists to prevent -- doing it through this function instead of
    through the filesystem would not make it a different act.
    """
    resolved = program_path.resolve()
    if not resolved.is_file():
        raise QueueError(
            f"program file {resolved} does not exist", code="QUEUE_PROGRAM_MISSING"
        )
    sha, _size = file_sha256(resolved)
    queue = load_queue(queue_root)
    existing = queue.entries.get(program_id)
    if existing is not None and existing.status is not QueueEntryStatus.WITHDRAWN:
        raise QueueError(
            f"program {program_id} is already admitted (status "
            f"{existing.status.value}); withdraw it before admitting again",
            code="QUEUE_ALREADY_ADMITTED",
        )
    entry = QueueEntry(
        program_id=program_id,
        program_path=str(resolved),
        program_sha256=sha,
        state_root=str(state_root.resolve()),
        admitted_by=admitted_by,
        reference=reference,
        note=note,
    )
    queue.entries[program_id] = entry
    persist_queue(queue_root, queue)
    return entry


def verify_entry(entry: QueueEntry) -> None:
    """Refuse an entry whose file is gone or no longer the admitted bytes."""
    path = Path(entry.program_path)
    if not path.is_file():
        raise QueueError(
            f"admitted program {entry.program_id} is missing from {path}",
            code="QUEUE_PROGRAM_MISSING",
        )
    sha, _size = file_sha256(path)
    if sha != entry.program_sha256:
        raise QueueError(
            f"admitted program {entry.program_id} at {path} no longer matches "
            f"the bytes that were admitted ({sha[:16]}... != "
            f"{entry.program_sha256[:16]}...); it must be re-admitted",
            code="QUEUE_PROGRAM_CHANGED",
        )


def update_entry(
    queue_root: Path,
    program_id: str,
    *,
    status: QueueEntryStatus | None = None,
    last_stop_reason: str | None = None,
    increment_runs: bool = False,
    note: str | None = None,
) -> QueueEntry:
    """Apply one bookkeeping change to an entry, atomically.

    ``COMPLETE`` is refused a transition back to a runnable status. A completed
    program becoming runnable again is exactly the "restart completed programs"
    behaviour the dispatcher is required not to have, and the queue is where it
    would have to be permitted for that to happen.
    """
    queue = load_queue(queue_root)
    entry = queue.entries.get(program_id)
    if entry is None:
        raise QueueError(
            f"program {program_id} is not in the approved work queue",
            code="QUEUE_ENTRY_MISSING",
        )
    if (
        status is not None
        and entry.status is QueueEntryStatus.COMPLETE
        and status in RUNNABLE_STATUSES
    ):
        raise QueueError(
            f"program {program_id} is COMPLETE; a completed program is never "
            "returned to a runnable status",
            code="QUEUE_COMPLETE_IS_TERMINAL",
        )
    if status is not None:
        entry.status = status
    if last_stop_reason is not None:
        entry.last_stop_reason = last_stop_reason
    if increment_runs:
        entry.runs = min(entry.runs + 1, 1_000_000)
        entry.last_run_at = utc_now()
    if note is not None:
        entry.note = note
    queue.entries[program_id] = entry
    persist_queue(queue_root, queue)
    return entry


def withdraw(queue_root: Path, program_id: str, *, note: str = "") -> QueueEntry:
    """Operator withdrawal. Kept as a record, never deleted."""
    return update_entry(
        queue_root,
        program_id,
        status=QueueEntryStatus.WITHDRAWN,
        note=note or "withdrawn by operator",
    )
