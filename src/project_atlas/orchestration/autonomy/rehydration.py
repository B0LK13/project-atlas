"""ORCH001E-011: cross-process governor/loop rehydration.

``run_governor_loop_tick()`` (cli.py) constructs a brand-new, empty
``AutonomousGovernor`` on every CLI invocation. Only the loop's own
``LoopState`` (phase, active_package_id, active_lease_id, ...) survives a
process restart on disk; the governor's in-memory node list does not. Any
code path that looks up a node by package_id against ``governor.snapshot()
.nodes`` (``AutonomousLoop._dispatch_leased``, ``AutonomousLoop.
apply_observed_result``) then raises an uncaught ``StopIteration`` for any
loop_state that reflects in-flight work, because the freshly-constructed
governor never saw that work.

This module is the fix: given a fresh governor, the live inventory, and the
persisted loop/lease-projection state, reconstruct just enough of the
governor's node list for process N+1 to continue where process N left off
-- or fail closed when the durable evidence is not sufficient to safely do
so. It deliberately reuses the existing durable artifacts already in the
repository (``AS-ORCH-DURABLE-LEASE-PROJECTION-001`` in
``lease_projection.py``, ``discover()``/``ingest_discovery()`` in
discovery.py/governor.py) rather than inventing a second, competing
persisted-DAG model.

PERSISTED_AUTHORITY != AGENT_CLAIM: every fact this module trusts comes from
a durable, previously-written artifact (the loop store, the lease
projection) -- never from an unverified in-memory claim, and never from a
freshly-recomputed value that merely happens to match by coincidence.

Scope, deliberately narrow:

- IDLE / STOPPED / FAILED_CLOSED / no persisted loop state at all: nothing
  is in flight. Only the harmless, already-existing origination pass
  (``discover()`` + ``ingest_discovery()``) runs.
- LEASED (with both ``active_package_id`` and ``active_lease_id`` set): the
  one case where durable evidence -- the lease projection row, cross-checked
  against the live inventory's current main -- is sufficient to safely
  reconstruct the exact node and lease that was granted. Reconstruction is
  possible today only for ``PILOT_PACKAGE_ID``, the only node shape the
  governor knows how to deterministically rebuild from inventory alone
  (``AutonomousGovernor._pilot_node``); any other package_id fails closed
  with ``NODE_NOT_REHYDRATABLE`` rather than fabricate a ``WorkNode`` whose
  mutation surface, acceptance criteria, and IV requirements were never
  durably recorded anywhere.
- DISPATCHING / AWAITING_RESULT / VALIDATING: execution may already be
  in-flight (an external 001D dispatch, or a not-yet-finalized verification
  outcome) with no durable record of exactly how far it got. Guessing here
  risks re-running, under-running, or double-counting a real side effect.
  This module fails closed immediately with
  ``EXECUTION_STATE_NOT_REHYDRATABLE`` rather than reconstruct a node whose
  state might not match reality.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from project_atlas.orchestration.autonomy.dag import IllegalTransitionError
from project_atlas.orchestration.autonomy.discovery import discover
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor, GovernorError
from project_atlas.orchestration.autonomy.lease_projection import (
    ProjectedLease,
    ProjectionError,
    active_rows,
    load_projection,
)
from project_atlas.orchestration.autonomy.loop import LoopError, LoopPhase, load_loop_state
from project_atlas.orchestration.autonomy.models import (
    PILOT_PACKAGE_ID,
    AgentCapability,
    AgentLease,
    AgentRecord,
    DiscoveryReport,
    LiveInventory,
    NodeState,
    OwnerGateKind,
    TrustedAnchorRecord,
    WorkNode,
)

#: Loop phases where execution may already be in flight with no durable
#: record of exactly how far it got. Reconstructing a node here would mean
#: guessing at reality rather than reading it from evidence -- forbidden.
_EXECUTION_IN_FLIGHT_PHASES: frozenset[LoopPhase] = frozenset(
    {LoopPhase.DISPATCHING, LoopPhase.AWAITING_RESULT, LoopPhase.VALIDATING}
)

#: Loop phases with nothing in flight for the governor to rehydrate.
_NO_ACTIVE_LEASE_PHASES: frozenset[LoopPhase] = frozenset(
    {LoopPhase.IDLE, LoopPhase.STOPPED, LoopPhase.FAILED_CLOSED}
)


class RehydrationError(ValueError):
    """Fail-closed rehydration error. Never an authority grant."""

    code = "REHYDRATION_FAILED_CLOSED"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


def rehydrate_governor(
    governor: AutonomousGovernor,
    *,
    inventory: LiveInventory,
    trusted: TrustedAnchorRecord,
    loop_store: Path,
    lease_projection_store: Path,
    origination_projection_store: Path | None = None,
) -> None:
    """Bring a freshly-constructed ``governor`` up to date with durable
    state a prior process persisted, or fail closed.

    Must run before constructing ``AutonomousLoop`` / calling ``tick()`` /
    ``recover()`` on ``governor``, so that any node lookup those perform
    against ``governor.snapshot().nodes`` finds what a prior process would
    have found -- or the caller never reaches those lookups at all, because
    this function already raised.

    ``origination_projection_store`` (D-PHASE2A, ADR-033): optional, and
    ``None`` by default -- every existing caller that does not pass it
    gets byte-identical behavior to before this parameter existed (the
    pilot-only rehydration path). When provided, a leased package_id that
    is not the pilot is additionally checked against the durable
    origination projection (``orchestration.origination.projection``)
    before falling back to the pre-existing ``NODE_NOT_REHYDRATABLE``
    fail-closed outcome.
    """
    try:
        loop_state = load_loop_state(loop_store)
    except LoopError as exc:
        if exc.code == "STATE_MISSING":
            # No process has ever ticked this root. Nothing to rehydrate;
            # AutonomousLoop's own constructor will create fresh IDLE state.
            _originate(governor, inventory=inventory, trusted=trusted)
            return
        # STATE_CORRUPT / TARGET_MOVED / etc: genuinely fail closed. The
        # caller's own except clause for LoopError already handles this the
        # same way AutonomousLoop's constructor would have.
        raise

    if loop_state.phase in _EXECUTION_IN_FLIGHT_PHASES:
        raise RehydrationError(
            f"cannot safely rehydrate governor state for in-flight phase "
            f"{loop_state.phase.value}: no durable record of exactly how far "
            f"execution progressed before the prior process exited",
            code="EXECUTION_STATE_NOT_REHYDRATABLE",
        )

    origin_node, report = _originate(governor, inventory=inventory, trusted=trusted)

    if loop_state.phase in _NO_ACTIVE_LEASE_PHASES:
        return

    if loop_state.phase != LoopPhase.LEASED:  # pragma: no cover - defensive
        raise RehydrationError(
            f"unrecognized loop phase {loop_state.phase.value!r} during rehydration",
            code="STATE_INCONSISTENT",
        )

    package_id = loop_state.active_package_id
    lease_id = loop_state.active_lease_id
    if package_id is None or lease_id is None:
        raise RehydrationError(
            "LEASED phase is missing active_package_id or active_lease_id",
            code="STATE_INCONSISTENT",
        )
    _restore_leased_node(
        governor,
        inventory=inventory,
        package_id=package_id,
        lease_id=lease_id,
        origin_node_package_id=origin_node.package_id if origin_node is not None else None,
        candidate_owner_gates={c.package_id: c.owner_gate for c in report.candidates},
        lease_projection_store=lease_projection_store,
        origination_projection_store=origination_projection_store,
    )


def _originate(
    governor: AutonomousGovernor,
    *,
    inventory: LiveInventory,
    trusted: TrustedAnchorRecord,
) -> tuple[WorkNode | None, DiscoveryReport]:
    """Run the existing, already-deterministic discovery pass. Fixes
    "originate new work on a fresh process" for the IDLE case, and is a
    harmless no-op read whenever nothing is currently eligible. Returns the
    node it added (if any) and the full report, so callers needing evidence
    about a specific package_id (e.g. its owner_gate) don't have to call
    ``discover()`` a second time.

    ORCH001E-011 finding #1 (independent-IV): ``ingest_discovery()`` only
    ever creates a node in ``DISCOVERED`` -- never ``READY`` -- and
    ``AutonomousLoop._select_and_lease()`` (via ``select_next()``) only
    ever considers ``READY`` nodes. ``run_controlled_pilot()`` already
    knows this and calls ``mark_ready()`` right after ``ingest_discovery()``
    (see below in this same module); rehydration's own origination pass
    must run the identical transition, or a freshly-originated node sits
    in ``DISCOVERED`` forever and the very next tick reports
    ``NO_ELIGIBLE_WORK`` despite discovery having just found real work."""
    report = discover(inventory, trusted=trusted)
    node = governor.ingest_discovery(report)
    if node is not None:
        governor.mark_ready(node.package_id)
    return node, report


def _restore_leased_node(
    governor: AutonomousGovernor,
    *,
    inventory: LiveInventory,
    package_id: str,
    lease_id: str,
    origin_node_package_id: str | None,
    candidate_owner_gates: dict[str, OwnerGateKind | None],
    lease_projection_store: Path,
    origination_projection_store: Path | None = None,
) -> None:
    origination_node: WorkNode | None = None
    if package_id != PILOT_PACKAGE_ID:
        # D-PHASE2A (ADR-033): the governor's one deterministic
        # inventory-only node factory (the pilot node) is not the only
        # source of durable truth any more. An origination-derived
        # package's full WorkNode -- mutation surface, acceptance
        # criteria, IV requirements, risk classification -- IS durably
        # persisted, by ``orchestration.origination.projection``, exactly
        # so it can be honestly rebuilt here instead of failing closed.
        if origination_projection_store is not None:
            from project_atlas.orchestration.origination.projection import (
                find_materialized_work_node,
            )

            origination_node = find_materialized_work_node(
                origination_projection_store, package_id
            )
        if origination_node is None:
            # No pilot factory, and no durable origination record either
            # (or none was even configured for this caller) -- there is
            # genuinely nothing trustworthy to rebuild this package_id's
            # WorkNode from. Same fail-closed outcome as before this
            # parameter existed.
            raise RehydrationError(
                f"package {package_id!r} has no durable node definition to "
                f"rehydrate from",
                code="NODE_NOT_REHYDRATABLE",
            )

    try:
        projection = load_projection(lease_projection_store)
    except ProjectionError as exc:
        raise RehydrationError(str(exc), code=exc.code) from exc

    row = next((item for item in active_rows(projection) if item.lease_id == lease_id), None)
    if row is None:
        raise RehydrationError(
            f"lease {lease_id!r} for package {package_id!r} has no durable "
            f"active projection row -- cannot confirm it was ever really "
            f"granted",
            code="LEASE_NOT_PROJECTED",
        )
    if row.package_id != package_id:
        raise RehydrationError(
            f"projected lease {lease_id!r} belongs to package "
            f"{row.package_id!r}, not the loop-persisted {package_id!r}",
            code="FOREIGN_PACKAGE",
        )
    if row.base_pin != inventory.current_main:
        raise RehydrationError(
            f"projected lease {lease_id!r} is pinned to {row.base_pin!r}, "
            f"which is stale against the current main {inventory.current_main!r}",
            code="STALE_LEASE",
        )

    try:
        capabilities = tuple(AgentCapability(value) for value in row.capabilities)
    except ValueError as exc:
        raise RehydrationError(
            f"projected lease {lease_id!r} has an unrecognized capability value",
            code="STATE_CORRUPT",
        ) from exc

    try:
        lease = AgentLease(
            lease_id=row.lease_id,
            agent_id=row.agent_id,
            package_id=row.package_id,
            branch=row.branch,
            worktree=row.worktree,
            base_pin=row.base_pin,
            authorized_paths=row.authorized_paths,
            forbidden_paths=row.forbidden_paths,
            capabilities=capabilities,
            start_state=row.start_state,
            # The only two AgentLease fields the durable projection does not
            # carry are always these two fixed constants -- see
            # leases.py:grant_lease, the sole place an AgentLease is ever
            # minted. A full lease is therefore losslessly reconstructable
            # from a ProjectedLease row plus these constants.
            expected_output="EVIDENCE_BUNDLE",
            expiry_or_terminal_condition="UNTIL_NODE_TERMINAL",
            active=True,
            sequence=row.created_sequence,
        )
    except ValidationError as exc:
        # ORCH001E-011 finding #5 (independent-IV): the projection file
        # already passed its own pydantic schema (`load_projection()`), but
        # a `ProjectedLease` row's fields are individually less constrained
        # than `AgentLease`'s (e.g. `authorized_paths`/`forbidden_paths`
        # content, id patterns). A tampered/edited-but-still-schema-valid
        # row can therefore fail *this* reconstruction. Fail closed with a
        # structured RehydrationError instead of letting a raw
        # ValidationError crash `run_governor_loop_tick()` uncaught.
        raise RehydrationError(
            f"projected lease {lease_id!r} does not reconstruct into a valid "
            f"AgentLease: {exc}",
            code="STATE_CORRUPT",
        ) from exc

    try:
        if origin_node_package_id != package_id:
            # discover()/ingest_discovery() did not (re)add this node --
            # build it fresh via the same deterministic factory `lease()`
            # itself would have used, then walk it through the real
            # transition machinery (DISCOVERED -> READY) rather than
            # fabricating a node that starts life already in a state no
            # real code path produces.
            if origination_node is not None:
                # D-PHASE2A: the exact WorkNode a prior process
                # materialized and durably recorded -- not rebuilt from
                # inventory, because it cannot be (its mutation surface,
                # acceptance criteria, and risk classification came from
                # real project evidence, not from anything the live
                # inventory alone could ever reconstruct).
                node = origination_node
            else:
                if package_id not in candidate_owner_gates:
                    # discover()'s candidate table is the single source of
                    # truth for a pilot node's owner_gate (see discovery.py).
                    # If the package isn't even a known candidate there is
                    # nothing trustworthy to build the node's owner_gate from.
                    raise RehydrationError(
                        f"package {package_id!r} is not a known discovery candidate",
                        code="NODE_NOT_REHYDRATABLE",
                    )
                owner_gate = candidate_owner_gates[package_id]
                node = governor._pilot_node(inventory, owner_gate)
            governor.add_node(node)
            governor.mark_ready(package_id)

        rebuilt_node = next(
            (item for item in governor.snapshot().nodes if item.package_id == package_id),
            None,
        )
        if rebuilt_node is None:  # pragma: no cover - defensive, see add_node/mark_ready above
            raise RehydrationError(
                f"package {package_id!r} has no rebuilt node to validate the "
                f"projected lease against",
                code="NODE_NOT_REHYDRATABLE",
            )
        _validate_lease_row_against_node(
            row,
            lease,
            node=rebuilt_node,
            agents=governor.snapshot().agents,
        )

        governor.restore_lease(lease)
    except (GovernorError, IllegalTransitionError) as exc:
        # A prior process's real governor would have gone through these
        # exact same transitions successfully to reach LEASED in the first
        # place (add_node -> mark_ready -> restore_lease mirrors
        # discovered -> ready -> leased). If any step fails here against
        # the live inventory, the durable evidence and current reality
        # have genuinely diverged (e.g. a surface overlap that did not
        # exist before, or the target moved) -- fail closed rather than
        # leave the governor in a partially-rehydrated state.
        code = getattr(exc, "code", "REHYDRATION_FAILED_CLOSED")
        raise RehydrationError(str(exc), code=code) from exc


def _validate_lease_row_against_node(
    row: ProjectedLease,
    lease: AgentLease,
    *,
    node: WorkNode,
    agents: tuple[AgentRecord, ...],
) -> None:
    """ORCH001E-011 finding #3 (independent-IV): ``AutonomousGovernor.
    restore_lease()`` deliberately does not repeat ``grant_lease()``'s
    agent/capability/state/scope checks -- by its own documented contract,
    because a genuine prior ``lease()`` call already enforced them once.
    That makes this function, called just before ``restore_lease()``, the
    ONLY remaining checkpoint before a projected ``leases.json`` row --
    schema-valid, but possibly corrupted, hand-edited, or adversarial -- is
    trusted as a real historical grant. Re-run every check ``grant_lease()``
    performs (``leases.py``), against the CURRENT agent registry and the
    just-rebuilt ``node`` -- never the row's own unverified claims -- and
    fail closed on the first mismatch.
    """
    agent = next((item for item in agents if item.agent_id == row.agent_id), None)
    if agent is None:
        raise RehydrationError(
            f"projected lease {row.lease_id!r} references unregistered agent "
            f"{row.agent_id!r}",
            code="UNKNOWN_AGENT",
        )
    if not agent.available:
        raise RehydrationError(
            f"projected lease {row.lease_id!r} references unavailable agent "
            f"{row.agent_id!r}",
            code="AGENT_UNAVAILABLE",
        )
    have = frozenset(agent.capabilities)
    if not all(item in have for item in node.agent_capabilities_required):
        raise RehydrationError(
            f"projected lease {row.lease_id!r} agent {row.agent_id!r} does not "
            f"hold the capabilities node {node.package_id!r} requires",
            code="CAPABILITY_MISMATCH",
        )
    if lease.capabilities != node.agent_capabilities_required:
        raise RehydrationError(
            f"projected lease {row.lease_id!r} recorded capabilities do not "
            f"match node {node.package_id!r}'s required capabilities",
            code="CAPABILITY_MISMATCH",
        )
    if row.start_state != NodeState.READY:
        raise RehydrationError(
            f"projected lease {row.lease_id!r} records start_state "
            f"{row.start_state.value!r}: only READY is a valid lease start state",
            code="INVALID_START_STATE",
        )
    surface = frozenset(node.mutation_surface.paths)
    extra_authorized = frozenset(row.authorized_paths) - surface
    if extra_authorized:
        raise RehydrationError(
            f"projected lease {row.lease_id!r} authorized_paths "
            f"{sorted(extra_authorized)!r} exceed node {node.package_id!r}'s "
            f"mutation surface {sorted(surface)!r}",
            code="SCOPE_EXPANSION",
        )
    # grant_lease()'s own default_forbidden = ("main", "projects")
    # (leases.py) is the baseline protection every genuine lease carries
    # unless a caller explicitly narrows it -- no call site in this
    # codebase ever does. A row whose forbidden_paths dropped that
    # baseline would let a rehydrated lease legitimately touch surfaces a
    # real grant never could have.
    baseline_forbidden = frozenset(("main", "projects"))
    if not baseline_forbidden <= frozenset(row.forbidden_paths):
        raise RehydrationError(
            f"projected lease {row.lease_id!r} forbidden_paths "
            f"{sorted(row.forbidden_paths)!r} do not include the baseline "
            f"protected paths {sorted(baseline_forbidden)!r}",
            code="SCOPE_EXPANSION",
        )
