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
from collections.abc import Iterable
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

RecordState = Literal["PROPOSED", "MATERIALIZED", "OWNER_HELD_ROUTED", "TERMINAL", "SUPERSEDED"]

#: States under which a record no longer holds live execution authority for
#: its ``work_node`` (if any): ``TERMINAL`` (the governed node reached
#: ``dag.TERMINAL_STATES`` -- an execution outcome) and ``SUPERSEDED`` (a
#: later authoritative-source revision for the same ``work_id`` replaced it
#: -- a source-lineage outcome, never an execution claim; see
#: ``reconcile_revision()``). Every "is this record still active/current"
#: check in this module is defined as ``row.state not in _INACTIVE_STATES``
#: so a future third inactive state only needs to be added here once.
_INACTIVE_STATES: frozenset[str] = frozenset({"TERMINAL", "SUPERSEDED"})


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
    matches = tuple(
        row
        for row in projection.records
        if row.state not in _INACTIVE_STATES
        and row.work_node is not None
        and row.work_node.get("package_id") == package_id
    )
    if len(matches) != 1:
        # A logical item may have multiple specification revisions over
        # time, but at most one may be CURRENT (active, not SUPERSEDED/
        # TERMINAL). Ambiguity is not authority.
        return None
    try:
        return WorkNode.model_validate(matches[0].work_node)
    except Exception:
        # Any validation failure means "not safely rehydratable" --
        # fail closed to None rather than propagate a raw pydantic
        # error out of a function documented to never raise.
        return None


def find_active_record_by_package_id(store: Path, package_id: str) -> OriginationRecord | None:
    """The first non-``TERMINAL`` durable record whose materialized
    ``work_node.package_id`` equals ``package_id``, regardless of its
    ``origination_identity``.

    ``origination_identity`` is a hash of ``project_id + location +
    item_id + item_digest`` (``identity.py``) -- it changes whenever a
    roadmap item's own content is revised. ``package_id``
    (``work_id_for()``) is a hash of only ``project_id + item_id`` -- it
    stays IDENTICAL across such a revision. A content revision to a
    roadmap item while the PRIOR governed work for that same item is
    still in flight (anything short of ``TERMINAL``) therefore produces
    a second, distinct, non-``TERMINAL`` origination record that shares
    the first one's ``package_id`` -- ordinary use of the unmodified
    pipeline, not a corrupted store.

    This is a plain, UNLOCKED point-in-time read -- like ``find_by_
    identity()`` and ``find_materialized_work_node()`` above, it does
    not itself serialize against a concurrent writer. D-PHASE2A-2
    delta-IV finding: a caller that reads this, then separately decides
    whether to call ``persist_materialized()``, leaves a TOCTOU window
    open -- two concurrent callers could both observe "no conflict"
    before either writes, and both materialize, producing two live
    records sharing one ``package_id``. Callers that need the
    check-then-write to be atomic MUST use
    ``persist_materialized_if_no_active_conflict()`` below instead,
    which performs both inside the same lock. This function remains
    useful on its own only for read-only/diagnostic callers that do not
    themselves write based on the result.

    Returns ``None`` (never raises) when no conflicting active record
    exists or the store is unreadable.
    """
    try:
        projection = load_projection(store)
    except OriginationProjectionError:
        return None
    return next(
        (
            row
            for row in projection.records
            if row.state not in _INACTIVE_STATES
            and row.work_node is not None
            and row.work_node.get("package_id") == package_id
        ),
        None,
    )


def persist_materialized_if_no_active_conflict(
    store: Path,
    origination_identity: str,
    work_node: WorkNode,
    *,
    state: RecordState = "MATERIALIZED",
) -> tuple[OriginationRecord | None, OriginationRecord | None]:
    """Atomic check-and-materialize: attach ``work_node`` to the
    already-``persist_proposed()``-ed record for ``origination_identity``
    UNLESS a non-``TERMINAL`` record already holds the same
    ``work_node.package_id`` -- in which case nothing is written.

    A DIFFERENT identity already holding that ``package_id`` is a
    conflict (``(None, conflicting_record)``). The SAME identity
    already holding a non-``TERMINAL`` ``work_node`` is returned
    unchanged -- not rebuilt. ``run_origination_scan()`` can miss its
    own skip from a stale unlocked snapshot; a second persist for the
    same evidence must not clobber ``base_pin`` / ``state`` on a record
    a governor may already have leased.

    D-PHASE2A-2 delta-IV finding: this replaces the two-step sequence of
    a caller reading ``find_active_record_by_package_id()`` and then
    separately calling ``persist_materialized()``, which left a TOCTOU
    window between the check and the write (two concurrent callers could
    both pass the check before either wrote, producing two live records
    sharing one ``package_id`` -- the exact ambiguity
    ``sync_terminal_governed_states()`` cannot safely resolve). The
    check and the write now happen inside ONE ``ProjectIdentityLock``
    critical section, exactly like ``persist_proposed()``'s own
    identity-based idempotency check already does -- this now genuinely
    mirrors ``governor.add_node()``'s atomic ``DUPLICATE_NODE`` check,
    which the pre-delta-IV version of this guard only claimed to.

    Returns ``(materialized_record, None)`` on success (including
    same-identity already-materialized idempotent return), or
    ``(None, conflicting_record)`` if a different-identity conflict
    was found under the lock -- the caller reports this exactly as it
    would have reported a pre-check conflict (``materialization_error_code=
    "PACKAGE_ID_ALREADY_ACTIVE"``). Fails closed with
    ``RECORD_UNKNOWN`` if no proposed row exists for
    ``origination_identity`` yet, same as ``persist_materialized()``.
    """
    root = store.expanduser().resolve()
    lock_path = (root / LOCK_NAME).resolve()
    if not _inside(root, lock_path):
        raise OriginationProjectionError("lock path escapes store", code="PATH_UNSAFE")
    package_id = work_node.package_id
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            current = load_projection(store)
            conflict = next(
                (
                    row
                    for row in current.records
                    if row.origination_identity != origination_identity
                    and row.state not in _INACTIVE_STATES
                    and row.work_node is not None
                    and row.work_node.get("package_id") == package_id
                ),
                None,
            )
            if conflict is not None:
                return None, conflict
            rows: list[OriginationRecord] = []
            found = False
            already_active: OriginationRecord | None = None
            for row in current.records:
                if row.origination_identity != origination_identity:
                    rows.append(row)
                    continue
                found = True
                if row.work_node is not None and row.state != "TERMINAL":
                    already_active = row
                    rows.append(row)
                    continue
                rows.append(
                    row.model_copy(
                        update={"work_node": work_node.model_dump(mode="json"), "state": state}
                    )
                )
            if not found:
                raise OriginationProjectionError(
                    "no proposed record to materialize", code="RECORD_UNKNOWN"
                )
            if already_active is not None:
                return already_active, None
            updated = OriginationProjection(records=tuple(rows))
            _write_atomic(root / PROJECTION_NAME, updated.model_dump(mode="json"))
    except IdentityLockError as exc:
        raise OriginationProjectionError(
            "projection lock is held", code="CONCURRENT_PROJECTION"
        ) from exc
    materialized = next(row for row in rows if row.origination_identity == origination_identity)
    return materialized, None


class ReconciliationOutcome(BaseModel):
    """What ``reconcile_revision()`` actually did, one durable transition."""

    model_config = ConfigDict(extra="forbid")

    #: Any OTHER active (differently-identified) record for this
    #: `work_id`/`package_id` this call transitioned to SUPERSEDED. Empty
    #: when no prior active revision existed.
    superseded: tuple[OriginationRecord, ...] = Field(default_factory=tuple)
    #: This identity's own row, if `work_node` was attached (this call's
    #: own new materialization, OR an idempotent replay of one it already
    #: held). ``None`` when `work_node` was not given (the new revision is
    #: blocked / not execution-ready) -- nothing materializes, even though
    #: a prior revision may still have been superseded.
    materialized: OriginationRecord | None = None
    #: True when this identity's own row already held a current, active
    #: `work_node` before this call (idempotent replay) -- nothing was
    #: written, including no re-supersession of any sibling.
    already_current: bool = False


def reconcile_revision(
    store: Path,
    *,
    origination_identity: str,
    package_id: str,
    work_node: WorkNode | None,
    state: RecordState = "MATERIALIZED",
) -> ReconciliationOutcome:
    """AS-ORIGIN-MATERIALIZED-SUPERSESSION-001 (owner directive
    D-ATLAS-ORIGINATION-MATERIALIZED-REVISION-SUPERSESSION): the one
    durable state transition a scan uses to reconcile ``origination_
    identity`` (a specific authoritative-source revision, already
    ``persist_proposed()``-ed) against whatever revision currently holds
    execution authority for the same logical work (``package_id`` /
    ``work_id`` -- identical concept, see ``identity.py``).

    Required invariant this enforces: *a materialized revision is
    rehydratable iff it is still the current authoritative eligible
    revision for its work_id*. Concretely, in ONE atomic, locked
    transition:

    1. Any OTHER non-``TERMINAL``/non-``SUPERSEDED`` record sharing
       ``package_id`` under a DIFFERENT ``origination_identity`` is
       transitioned to ``SUPERSEDED`` -- never deleted, never rewritten
       as though it had never been materialized (its ``proposal``,
       ``policy_result``, and frozen ``work_node`` -- including its own
       ``base_pin`` -- are preserved exactly; only ``state`` changes).
       This happens REGARDLESS of whether ``work_node`` is given below:
       source truth supersedes a prior revision whether or not the NEW
       revision itself goes on to materialize (a newly-BLOCKED revision
       must still revoke a stale unblocked one).
    2. If ``work_node`` is given, THIS identity's own row (which must
       already exist as a ``persist_proposed()``-ed record) is attached
       and transitioned to ``state``. If ``work_node`` is ``None`` (the
       new revision is blocked / not execution-ready), this identity's
       row is left exactly as ``persist_proposed()`` left it (normally
       ``PROPOSED``) -- nothing new materializes.

    Fails closed with ``AMBIGUOUS_ACTIVE_REVISION`` (superseding and
    materializing NOTHING) if MORE THAN ONE other active record shares
    ``package_id`` -- corrupt or pre-migration lineage; never resolved by
    picking one to revoke arbitrarily.

    Idempotent: if this identity's own row ALREADY holds a current,
    active ``work_node`` (a repeat scan for the same evidence, or a
    concurrent caller that already won), nothing is written -- in
    particular, no sibling is re-superseded a second time -- and the
    existing row is returned with ``already_current=True``. This mirrors
    ``persist_materialized_if_no_active_conflict()``'s own same-identity
    idempotence, and is checked FIRST, before any supersession, so a
    replay can never re-trigger supersession side effects.

    Fails closed with ``RECORD_UNKNOWN`` if no ``persist_proposed()``-ed
    row exists yet for ``origination_identity`` -- a revision cannot be
    reconciled before it is itself durably recorded as proposed.

    Everything above happens inside ONE ``ProjectIdentityLock`` critical
    section -- there is no window where a crash could leave the store
    with the old revision superseded but the new one not yet reflected
    (or vice versa) in a way that resurrects revoked authority; worst
    case after an interrupted call is "no revision is currently active
    for this work_id", which the next scan self-heals exactly like any
    other first-time materialization.
    """
    root = store.expanduser().resolve()
    lock_path = (root / LOCK_NAME).resolve()
    if not _inside(root, lock_path):
        raise OriginationProjectionError("lock path escapes store", code="PATH_UNSAFE")
    try:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            current = load_projection(store)

            own_row = next(
                (
                    row
                    for row in current.records
                    if row.origination_identity == origination_identity
                ),
                None,
            )
            if own_row is None:
                raise OriginationProjectionError(
                    "no proposed record to reconcile", code="RECORD_UNKNOWN"
                )

            if own_row.state not in _INACTIVE_STATES and own_row.work_node is not None:
                # Idempotent replay -- checked BEFORE any supersession so a
                # repeat call (same evidence, re-scanned) can never
                # re-supersede a sibling a second time.
                return ReconciliationOutcome(materialized=own_row, already_current=True)

            others = [
                row
                for row in current.records
                if row.origination_identity != origination_identity
                and row.state not in _INACTIVE_STATES
                and row.work_node is not None
                and row.work_node.get("package_id") == package_id
            ]
            if len(others) > 1:
                raise OriginationProjectionError(
                    f"more than one OTHER active origination record shares "
                    f"package_id {package_id!r} -- corrupt/ambiguous "
                    "lineage; refusing to supersede or materialize until "
                    "resolved",
                    code="AMBIGUOUS_ACTIVE_REVISION",
                )
            incumbent_identity = others[0].origination_identity if others else None

            rows: list[OriginationRecord] = []
            superseded: list[OriginationRecord] = []
            for row in current.records:
                if row.origination_identity == incumbent_identity:
                    updated_row = row.model_copy(update={"state": "SUPERSEDED"})
                    rows.append(updated_row)
                    superseded.append(updated_row)
                    continue
                if row.origination_identity == origination_identity and work_node is not None:
                    rows.append(
                        row.model_copy(
                            update={"work_node": work_node.model_dump(mode="json"), "state": state}
                        )
                    )
                    continue
                rows.append(row)

            updated = OriginationProjection(records=tuple(rows))
            _write_atomic(root / PROJECTION_NAME, updated.model_dump(mode="json"))
    except IdentityLockError as exc:
        raise OriginationProjectionError(
            "projection lock is held", code="CONCURRENT_PROJECTION"
        ) from exc

    materialized_row = (
        next(r for r in rows if r.origination_identity == origination_identity)
        if work_node is not None
        else None
    )
    return ReconciliationOutcome(
        superseded=tuple(superseded), materialized=materialized_row, already_current=False
    )


def list_materialized_work_nodes(store: Path) -> tuple[WorkNode, ...]:
    """D-PHASE2A-2 / AS-ORIGIN-MATERIALIZED-SUPERSESSION-001: every
    ``WorkNode`` a prior process durably materialized that is still the
    CURRENT active revision for its ``work_id`` (``row.state not in
    _INACTIVE_STATES`` -- ``"MATERIALIZED"`` and ``"OWNER_HELD_ROUTED"``
    rows both count; ``"PROPOSED"`` rows have no ``work_node`` yet,
    ``"TERMINAL"`` rows already reached a governed execution outcome, and
    ``"SUPERSEDED"`` rows were replaced by a later authoritative-source
    revision for the same ``work_id`` -- see ``reconcile_revision()`` --
    all three correctly excluded).

    This is the "governor discovery" read side of the origination ->
    governor bridge: unlike ``find_materialized_work_node()`` (a single
    lookup for a package_id ALREADY known to be leased, used to recover
    from a crash), this enumerates every candidate a fresh or continuing
    governor has not yet seen at all, so it can decide which ones to
    bring into its own node list for the first time.

    A malformed individual row (fails ``WorkNode.model_validate``) is
    skipped, not fatal to the others -- one corrupt durable record must
    not hide every other legitimate one from discovery. An unreadable/
    missing store returns an empty tuple, matching
    ``find_materialized_work_node()``'s own fail-closed-to-empty
    posture.

    AS-ORIGIN-MATERIALIZED-SUPERSESSION-001 (owner-directed hardening,
    D-ATLAS-ORIGINATION-MATERIALIZED-REVISION-SUPERSESSION §7): unlike
    every other read in this module, this function DOES raise --
    ``OriginationProjectionError(code="AMBIGUOUS_ACTIVE_REVISION")`` --
    if more than one active row shares a single ``package_id``. That
    shape should be impossible once ``reconcile_revision()`` is the only
    write path that ever attaches a second active revision to an
    existing ``work_id`` (it supersedes the incumbent first, atomically,
    before attaching a new one), but this is the read side's own
    independent, defense-in-depth check: the caller here is exactly the
    governor-rehydration bridge that would otherwise pick whichever
    candidate happened to come first in file/record order and silently
    grant it execution authority -- picking one arbitrarily is never
    correct for a corrupt or pre-migration store, so this fails the
    whole read closed rather than guess. The sole caller
    (``rehydration.py``) converts this into its own ``RehydrationError``,
    matching how every other load-bearing store failure on that path is
    already handled -- this is why this function no longer documents
    "never raises" unconditionally.
    """
    try:
        projection = load_projection(store)
    except OriginationProjectionError:
        return ()
    nodes: list[WorkNode] = []
    seen_package_ids: set[str] = set()
    for row in projection.records:
        if row.state in _INACTIVE_STATES or row.work_node is None:
            continue
        package_id = row.work_node.get("package_id")
        if isinstance(package_id, str):
            if package_id in seen_package_ids:
                raise OriginationProjectionError(
                    f"more than one active (non-TERMINAL, non-SUPERSEDED) "
                    f"origination record shares package_id {package_id!r} -- "
                    "corrupt or pre-supersession-migration lineage; refusing "
                    "to pick one arbitrarily",
                    code="AMBIGUOUS_ACTIVE_REVISION",
                )
            seen_package_ids.add(package_id)
        try:
            nodes.append(WorkNode.model_validate(row.work_node))
        except Exception:
            continue
    return tuple(nodes)


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


def sync_terminal_governed_states(
    store: Path, governor_nodes: Iterable[WorkNode]
) -> tuple[str, ...]:
    """D-PHASE2A-2: the write-back half of the origination <-> governor
    bridge (``list_materialized_work_nodes()`` above is the read half).

    For every non-``TERMINAL`` durable record whose ``work_node.package_id``
    matches a node in ``governor_nodes`` that has reached
    ``orchestration.autonomy.dag.TERMINAL_STATES`` (today: ``CLOSED``
    only), call ``mark_terminal()`` so a later successor-discovery scan
    correctly excludes it (``originate_new_only()``).

    Deliberately scoped to ``dag.TERMINAL_STATES`` alone, not the wider
    "CERTIFIED/OWNER_HELD/BLOCKED/CLOSED/..." example list in
    ``mark_terminal()``'s own docstring: that is the single unambiguous
    source of truth for "this node's own governed lifecycle is over"
    (``dag.py`` itself defines it), rather than this function inventing
    a second, looser terminality concept. A node sitting at OWNER_HELD
    (or any other non-CLOSED state) is NOT synced here -- whether an
    owner-gated identity should stop being re-derived by future scans
    before an owner has actually acted on it is a real policy question
    left for a future, deliberate decision, not guessed at here.

    This is a pure optimization, not a correctness requirement:
    ``persist_proposed()`` is already idempotent by ``origination_identity``
    (a re-derived proposal for the same evidence never actually
    duplicates), and ``run_origination_scan()`` (D-PHASE2A-2) now skips
    re-materializing an already-materialized, non-TERMINAL record rather
    than clobbering it, AND (D-PHASE2A-2 independent-IV finding, same
    round) refuses to durably create a second live record for a
    ``package_id`` an existing non-TERMINAL record already holds under a
    different ``origination_identity`` (``persist_materialized_if_no_
    active_conflict()`` above, atomically -- delta-IV hardening; the
    plain ``find_active_record_by_package_id()`` read is no longer the
    write-time guard). Marking terminal here only avoids the wasted work of
    re-deriving an outcome whose fate is already fully decided; it does
    not change what is safe.

    Defense-in-depth for that same finding: this function does NOT
    itself trust that the guard above always held for every record ever
    written to ``store`` (a store predating this fix, or a future bug
    elsewhere, could still hand it two non-TERMINAL rows sharing one
    ``package_id``). If more than one non-TERMINAL row matches a single
    closed ``package_id``, NONE of them are synced -- picking one
    arbitrarily to mark ``TERMINAL`` could permanently and silently
    close a genuinely distinct, never-executed proposal. Ambiguity is
    not authority, exactly as ``find_materialized_work_node()`` already
    treats it.

    Never raises: any per-identity ``mark_terminal()`` failure (e.g. a
    concurrent writer holding the lock) is skipped for that identity
    rather than aborting the whole sync pass -- a transient miss here
    just means one more harmless re-derivation on the next scan, not a
    correctness problem. Returns the ``origination_identity`` values
    actually synced this call.
    """
    try:
        projection = load_projection(store)
    except OriginationProjectionError:
        return ()
    from project_atlas.orchestration.autonomy.dag import TERMINAL_STATES

    closed_package_ids = {
        node.package_id for node in governor_nodes if node.state in TERMINAL_STATES
    }
    if not closed_package_ids:
        return ()
    active_rows_by_package_id: dict[str, list[OriginationRecord]] = {}
    for row in projection.records:
        if row.state in _INACTIVE_STATES or row.work_node is None:
            continue
        package_id = row.work_node.get("package_id")
        if package_id in closed_package_ids:
            active_rows_by_package_id.setdefault(package_id, []).append(row)
    synced: list[str] = []
    for rows in active_rows_by_package_id.values():
        if len(rows) != 1:
            continue
        row = rows[0]
        try:
            mark_terminal(store, row.origination_identity, node_state="CLOSED")
        except OriginationProjectionError:
            continue
        synced.append(row.origination_identity)
    return tuple(synced)
