"""AS-ORCH-ORIGINATION-PROJECTION-001 — durable origination persistence.

The missing piece identified in ADR-033 "MISSING_BOUNDARY" §2: today only
the pilot node can be rehydrated across a process restart because its
full ``WorkNode`` definition can be deterministically rebuilt from
inventory alone. An origination-derived node cannot -- its mutation
surface, acceptance criteria, and risk classification came from real
project evidence, not from anything inventory-observable. This module
durably persists the *full* materialized ``WorkNode`` (plus the proposal
and policy result that produced it), keyed by ``origination_identity``,
so a later process can rebuild the exact same node from disk rather than
fabricate one.

PROJECTION_IS_AUTHORITY = NO -- same posture as ``lease_projection.py``.
This is recovery evidence, not a grant of anything; the governed DAG/lease
machinery (``orchestration.autonomy``) remains the sole execution
authority once a node is added.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.autonomy.lease_projection import _inside, _write_atomic
from project_atlas.orchestration.autonomy.models import WorkNode
from project_atlas.orchestration.origination.policy import PolicyResult
from project_atlas.orchestration.origination.proposal import OriginationProposal
from project_atlas.source_identity import IdentityLockError, ProjectIdentityLock

PACKAGE_ID: Final[Literal["AS-ORCH-ORIGINATION-PROJECTION-001"]] = (
    "AS-ORCH-ORIGINATION-PROJECTION-001"
)
PROJECTION_NAME: Final[str] = "origination.json"
LOCK_NAME: Final[str] = "origination.lock"
RELATIVE_DEFAULT: Final[Path] = Path(".atlas") / "orchestration" / "origination"

RecordState = Literal["PROPOSED", "MATERIALIZED", "OWNER_HELD_ROUTED", "TERMINAL"]


class OriginationProjectionError(ValueError):
    code = "ORIGINATION_PROJECTION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class OriginationRecord(BaseModel):
    """One durable row: a proposal, its policy result, and (once
    materialized) the exact ``WorkNode`` a process built from it."""

    model_config = ConfigDict(extra="forbid")

    origination_identity: str = Field(min_length=64, max_length=64)
    project_id: str = Field(min_length=1, max_length=128)
    proposal: dict[str, object]
    policy_result: dict[str, object]
    work_node: dict[str, object] | None = None
    state: RecordState
    terminal_node_state: str | None = None
    projection_is_authority: Literal[False] = False


class OriginationProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package: Literal["AS-ORCH-ORIGINATION-PROJECTION-001"] = PACKAGE_ID
    records: tuple[OriginationRecord, ...] = Field(default_factory=tuple, max_length=256)


def _store_file(store: Path) -> Path:
    root = store.expanduser().resolve()
    candidate = root / PROJECTION_NAME
    if candidate.is_symlink():
        raise OriginationProjectionError("projection path is a symlink", code="PATH_UNSAFE")
    target = candidate.resolve()
    if not _inside(root, target):
        raise OriginationProjectionError("projection path escapes store", code="PATH_UNSAFE")
    return target


def load_projection(store: Path) -> OriginationProjection:
    path = _store_file(store)
    if not path.is_file():
        return OriginationProjection()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OriginationProjectionError("projection is unreadable", code="STATE_CORRUPT") from exc
    if not isinstance(raw, dict):
        raise OriginationProjectionError("projection is schema-invalid", code="STATE_CORRUPT")
    try:
        return OriginationProjection.model_validate(raw)
    except Exception as exc:
        raise OriginationProjectionError(
            "projection is schema-invalid", code="STATE_CORRUPT"
        ) from exc


def find_by_identity(store: Path, origination_identity: str) -> OriginationRecord | None:
    projection = load_projection(store)
    return next(
        (row for row in projection.records if row.origination_identity == origination_identity),
        None,
    )


def find_materialized_work_node(store: Path, package_id: str) -> WorkNode | None:
    """The durable, general ``WorkNode`` rehydration lookup ADR-033
    exists to provide: given a ``package_id``, find the exact
    materialized node a prior process built for it (if any) so a new
    process can rebuild it from disk rather than fabricate one.

    Returns ``None`` (never raises) when no record exists, no record is
    yet materialized, or ``store`` itself does not exist -- all valid
    "nothing to rehydrate from here" outcomes; the caller
    (``rehydration.py``) is responsible for deciding whether that's an
    error in its own context.
    """
    try:
        projection = load_projection(store)
    except OriginationProjectionError:
        return None
    for row in projection.records:
        if row.work_node is None:
            continue
        if row.work_node.get("package_id") != package_id:
            continue
        try:
            return WorkNode.model_validate(row.work_node)
        except Exception:
            # Any validation failure means "not safely rehydratable" --
            # fail closed to None rather than propagate a raw pydantic
            # error out of a function documented to never raise.
            return None
    return None


def persist_proposed(
    store: Path, proposal: OriginationProposal, policy: PolicyResult
) -> OriginationRecord:
    """Idempotently record a freshly-derived proposal. Same
    ``origination_identity`` as an existing row is treated as already
    known -- NO_DUPLICATE_ORIGINATION -- and the existing row is returned
    unchanged rather than appended a second time."""
    root = store.expanduser().resolve()
    lock_path = (root / LOCK_NAME).resolve()
    if not _inside(root, lock_path):
        raise OriginationProjectionError("lock path escapes store", code="PATH_UNSAFE")
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            current = load_projection(store)
            target_identity = proposal.origination_identity
            existing = next(
                (row for row in current.records if row.origination_identity == target_identity),
                None,
            )
            if existing is not None:
                return existing
            record = OriginationRecord(
                origination_identity=proposal.origination_identity,
                project_id=proposal.project_id,
                proposal=proposal.model_dump(mode="json"),
                policy_result=policy.model_dump(mode="json"),
                work_node=None,
                state="PROPOSED",
            )
            updated = OriginationProjection(records=(*current.records, record))
            _write_atomic(root / PROJECTION_NAME, updated.model_dump(mode="json"))
    except IdentityLockError as exc:
        raise OriginationProjectionError(
            "projection lock is held", code="CONCURRENT_PROJECTION"
        ) from exc
    return record


def persist_materialized(
    store: Path,
    origination_identity: str,
    work_node: WorkNode,
    *,
    state: RecordState = "MATERIALIZED",
) -> OriginationRecord:
    """Attach the exact materialized ``WorkNode`` to an already-proposed
    record. Fails closed if no proposed row exists -- a ``WorkNode``
    cannot be durably attached to evidence that was never itself
    recorded."""
    root = store.expanduser().resolve()
    lock_path = (root / LOCK_NAME).resolve()
    if not _inside(root, lock_path):
        raise OriginationProjectionError("lock path escapes store", code="PATH_UNSAFE")
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            current = load_projection(store)
            rows: list[OriginationRecord] = []
            found = False
            for row in current.records:
                if row.origination_identity != origination_identity:
                    rows.append(row)
                    continue
                found = True
                rows.append(
                    row.model_copy(
                        update={"work_node": work_node.model_dump(mode="json"), "state": state}
                    )
                )
            if not found:
                raise OriginationProjectionError(
                    "no proposed record to materialize", code="RECORD_UNKNOWN"
                )
            updated = OriginationProjection(records=tuple(rows))
            _write_atomic(root / PROJECTION_NAME, updated.model_dump(mode="json"))
    except IdentityLockError as exc:
        raise OriginationProjectionError(
            "projection lock is held", code="CONCURRENT_PROJECTION"
        ) from exc
    return next(row for row in rows if row.origination_identity == origination_identity)


def mark_terminal(store: Path, origination_identity: str, *, node_state: str) -> OriginationRecord:
    """Record the final observed ``NodeState`` once a node reaches a
    terminal state (CERTIFIED/OWNER_HELD/BLOCKED/CLOSED/...), so a later
    successor-discovery scan can see this identity is already resolved
    without re-deriving a duplicate proposal for the same evidence."""
    root = store.expanduser().resolve()
    lock_path = (root / LOCK_NAME).resolve()
    if not _inside(root, lock_path):
        raise OriginationProjectionError("lock path escapes store", code="PATH_UNSAFE")
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            current = load_projection(store)
            rows: list[OriginationRecord] = []
            found = False
            for row in current.records:
                if row.origination_identity != origination_identity:
                    rows.append(row)
                    continue
                found = True
                rows.append(
                    row.model_copy(update={"state": "TERMINAL", "terminal_node_state": node_state})
                )
            if not found:
                raise OriginationProjectionError("no record to finalize", code="RECORD_UNKNOWN")
            updated = OriginationProjection(records=tuple(rows))
            _write_atomic(root / PROJECTION_NAME, updated.model_dump(mode="json"))
    except IdentityLockError as exc:
        raise OriginationProjectionError(
            "projection lock is held", code="CONCURRENT_PROJECTION"
        ) from exc
    return next(row for row in rows if row.origination_identity == origination_identity)
