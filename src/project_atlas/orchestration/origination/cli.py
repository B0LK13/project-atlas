"""CLI runner for specification-backed work origination (D-PHASE2A-3).

Before this module, an origination scan required a caller to sequence 4
separate Python API calls by hand (``collect_live_inventory``,
``originate_new_only``, ``risk.classify``, ``materialize_work_node``,
``projection.persist_proposed``/``persist_materialized`` -- see
``docs/evidence/d-phase2a/run_three_process_demo.py`` for exactly that
by-hand sequence). ``run_origination_scan()`` is the single consolidated
entry point, mirroring ``orchestration.autonomy.cli.run_governor_loop_tick``
's own pattern: a pure function returning a JSON-serializable payload plus
an exit code, fail-closed on trust errors, no wall-clock fields, never an
authority grant.

Not yet wired into the top-level ``atlas`` argparse command -- neither is
``run_governor_loop_tick`` itself, which this module deliberately mirrors
rather than diverges from. That wiring is a separate, larger UX/product
surface decision (command name, flag conventions, `--help` text, CI smoke
test coverage) than this fix's own scope: closing "no consolidated,
directly-callable origination-scan API" without widening into "design the
atlas CLI's origination UX."

SPECIFICATION_BACKED_WORK_ORIGINATION still holds: every materialized node
this module can produce traces back through ``eligible_roadmap_items()``
to real project evidence. Never leases, never dispatches, never merges.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from project_atlas.orchestration.autonomy.discovery import collect_live_inventory
from project_atlas.orchestration.autonomy.models import TrustedAnchorRecord, WorkNode
from project_atlas.orchestration.autonomy.trust import TrustError, load_runtime_anchor
from project_atlas.orchestration.origination.materialize import (
    MaterializationError,
    materialize_work_node,
)
from project_atlas.orchestration.origination.pipeline import originate_new_only
from project_atlas.orchestration.origination.projection import (
    RELATIVE_DEFAULT as ORIGINATION_PROJECTION_RELATIVE_DEFAULT,
)
from project_atlas.orchestration.origination.projection import (
    OriginationProjectionError,
    persist_materialized_if_no_active_conflict,
    persist_proposed,
)
from project_atlas.orchestration.origination.proposal import RiskClass
from project_atlas.orchestration.origination.risk import classify as classify_risk

EXIT_OK = 0
EXIT_ERROR = 1

#: Independent-IV finding (D-PHASE2A-3, PR #647 round 1): SourceFact
#: .project_id (facts.py, module-private there) allows up to 128 chars,
#: but this module builds `surface_id=f"{project_id}-{work_id}"`, and
#: work_id_for() always returns exactly 21 chars ("ORIG-" + 16 hex).
#: MutationSurface.surface_id caps at 128 (autonomy/models.py). A
#: project_id longer than 106 chars (128 - 1 separator - 21) therefore
#: overflows surface_id and raises a raw pydantic.ValidationError deep
#: inside materialize_work_node() -- not a MaterializationError, so the
#: existing `except MaterializationError` around that call never caught
#: it. Bounding here, before any downstream call, closes both that gap
#: and the sibling one (a project_id whose characters are unsafe at all,
#: which used to escape uncaught from inside originate_new_only() ->
#: SourceFact construction). Character class mirrors facts.py's own
#: _PROJECT_ID_RE exactly; the length bound is this module's own,
#: stricter than SourceFact's 128 because of the -{work_id} suffix.
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,105}$")


def _fail_closed(detail: str, *, blocker: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "package_id": "AS-ORIGIN-001",
        "blocker": blocker,
        "detail": detail,
        "merge_authorized": False,
        "execution_authorized": False,
    }


def run_origination_scan(
    *,
    root: Path,
    project_id: str,
    trust_store: Path | None = None,
    origination_store: Path | None = None,
    explicit_trusted: TrustedAnchorRecord | None = None,
) -> tuple[dict[str, object], int]:
    """One origination scan against ``root``: derive every specification-
    backed candidate (``originate_new_only`` -- deduplicated against
    already-``TERMINAL`` durable records, the correct successor-scan
    semantic), durably record each as ``PROPOSED``, and attempt to
    materialize+durably-record each into a real ``WorkNode``.

    A proposal that fails materialization (``proposal.blockers`` non-empty,
    or a classification/proposal mismatch -- see ``materialize_work_node``'s
    own fail-closed checks) is reported under ``not_materialized``, not
    silently dropped. A proposal that materializes with an ``owner_gate``
    tag (risk_class OWNER_HELD) is still reported under ``materialized`` --
    materialization is not the same claim as "ready to lease without an
    owner grant"; that distinction lives on the node's own ``owner_gate``
    field, exactly as it does for every other governed node.

    Returns ``EXIT_OK`` whenever the scan itself completed (including zero
    eligible candidates -- the correct, honest ``NO_ELIGIBLE_WORK``
    outcome, not an error). Returns ``EXIT_ERROR`` only for a fail-closed
    trust/projection-store failure that prevented the scan from running at
    all.

    Never raises -- a malformed or oversized ``project_id`` (or any other
    unanticipated validation failure surfaced by the pipeline this
    consolidates) is reported as a fail-closed payload, not an escaping
    exception. See ``_PROJECT_ID_RE``.
    """
    if not _PROJECT_ID_RE.fullmatch(project_id):
        return (
            _fail_closed(
                f"project_id {project_id!r} is not a safe identifier of at most "
                "106 characters",
                blocker="INVALID_PROJECT_ID",
            ),
            EXIT_ERROR,
        )
    try:
        trusted = load_runtime_anchor(
            store=trust_store,
            explicit=explicit_trusted,
            allow_shipped=trust_store is None and explicit_trusted is None,
        )
        inventory = collect_live_inventory(root)
    except TrustError as exc:
        code = getattr(exc, "code", "TRUST_UNVERIFIABLE")
        return _fail_closed(str(exc), blocker=code), EXIT_ERROR

    del trusted  # not consulted further: origination never leases/dispatches
    store = origination_store or (root / ORIGINATION_PROJECTION_RELATIVE_DEFAULT)

    try:
        outcomes = originate_new_only(root, project_id, store)
    except OriginationProjectionError as exc:
        code = getattr(exc, "code", "ORIGINATION_PROJECTION_FAILED")
        return _fail_closed(str(exc), blocker=code), EXIT_ERROR
    except ValidationError as exc:
        # Defense-in-depth: the precheck above already rejects the one
        # known way a bad project_id reaches this point, but this is the
        # "never raises" contract's own backstop for anything else the
        # pipeline this consolidates might someday validate strictly.
        return _fail_closed(str(exc), blocker="ORIGINATION_VALIDATION_FAILED"), EXIT_ERROR

    materialized: list[dict[str, object]] = []
    not_materialized: list[dict[str, object]] = []
    try:
        for outcome in outcomes:
            proposal, policy = outcome.proposal, outcome.policy
            # persist_proposed() is already locked and returns the
            # existing row unchanged when this identity is known --
            # including a MATERIALIZED / OWNER_HELD_ROUTED row written
            # by a concurrent scan. An unlocked find_by_identity()
            # taken BEFORE that call can still see None / PROPOSED
            # after the first write completed, which would miss the
            # skip below.
            existing = persist_proposed(store, proposal, policy)
            # D-PHASE2A-2 finding: `originate_new_only()` only excludes
            # TERMINAL identities, so a non-terminal MATERIALIZED (or
            # OWNER_HELD_ROUTED) record for THIS SAME evidence is a
            # legitimate, expected outcome of running a scan more than
            # once while a governed loop is actively working the node --
            # not a stale/erroneous one. Unconditionally re-materializing
            # here previously rebuilt a FRESH WorkNode (state=DISCOVERED,
            # a possibly-different base_pin if main moved since) and
            # overwrote the durable projection's `work_node` field with
            # it, which would silently clobber real in-progress governed
            # state a rehydrating process depends on (`find_materialized_
            # work_node()` in projection.py -- the exact function
            # `rehydration.py` uses to reconstruct a LEASED node after a
            # crash). An already-materialized, non-terminal identity is
            # therefore now reported AS-IS from the existing durable
            # record -- never rebuilt -- so a repeated scan is safe to
            # run at any time, including while that same node is actively
            # leased.
            if (
                existing is not None
                and existing.work_node is not None
                and existing.state in {"MATERIALIZED", "OWNER_HELD_ROUTED"}
            ):
                try:
                    node = WorkNode.model_validate(existing.work_node)
                except ValidationError as exc:
                    not_materialized.append(
                        {
                            "work_id": proposal.work_id,
                            "execution_ready": policy.execution_ready,
                            "reason": policy.reason.value,
                            "materialization_error": str(exc),
                            "materialization_error_code": "DURABLE_RECORD_CORRUPT",
                        }
                    )
                    continue
                materialized.append(
                    {
                        "work_id": node.package_id,
                        "execution_ready": policy.execution_ready,
                        "reason": policy.reason.value,
                        # WorkNode itself has no risk_class field (that is a
                        # proposal/classification-level concept); derived
                        # from owner_gate presence, which owner_gate_for()
                        # (materialize.py) sets if and only if risk_class
                        # was OWNER_HELD -- a reliable inverse, not a guess.
                        "risk_class": (
                            RiskClass.OWNER_HELD.value
                            if node.owner_gate is not None
                            else RiskClass.O1_LOW_RISK_SPECIFICATION_BOUND_IMPLEMENTATION.value
                        ),
                        "owner_gate": node.owner_gate.value if node.owner_gate else None,
                        "already_materialized": True,
                    }
                )
                continue
            classification = classify_risk(
                proposed_scope=proposal.proposed_scope,
                success_criteria=proposal.success_criteria,
            )
            try:
                node = materialize_work_node(
                    proposal,
                    classification,
                    base_pin=inventory.current_main,
                    surface_id=f"{proposal.project_id}-{proposal.work_id}",
                )
            except MaterializationError as exc:
                not_materialized.append(
                    {
                        "work_id": proposal.work_id,
                        "execution_ready": policy.execution_ready,
                        "reason": policy.reason.value,
                        "materialization_error": str(exc),
                        "materialization_error_code": exc.code,
                    }
                )
                continue
            # D-PHASE2A-2 independent-IV finding, round 2 (+ delta-IV
            # follow-up): `origination_identity` includes the item's
            # content digest (identity.py), but `proposal.work_id` (->
            # WorkNode.package_id) does not -- it is stable across a
            # content revision to the same roadmap item (`work_id_for()`
            # hashes only project_id+item_id). A revision to an item
            # while the PRIOR non-TERMINAL record for that same item is
            # still in flight therefore reaches this point as a
            # genuinely NEW origination_identity (the `existing is not
            # None` branch above does not catch it) that would otherwise
            # materialize a SECOND live record sharing the first one's
            # package_id -- exactly the ambiguity
            # `sync_terminal_governed_states()` cannot safely resolve.
            # `persist_materialized_if_no_active_conflict()` performs
            # this check and the write inside ONE lock, closing the
            # TOCTOU window a separate check-then-write pair would leave
            # open (delta-IV finding: two concurrent scans could both
            # pass a standalone pre-check before either wrote).
            materialized_record, conflict = persist_materialized_if_no_active_conflict(
                store, proposal.origination_identity, node
            )
            if conflict is not None:
                not_materialized.append(
                    {
                        "work_id": proposal.work_id,
                        "execution_ready": policy.execution_ready,
                        "reason": policy.reason.value,
                        "materialization_error": (
                            "a different non-terminal origination record "
                            f"(origination_identity={conflict.origination_identity!r}) "
                            "already holds this package_id -- this looks like a "
                            "content revision to the same roadmap item while prior "
                            "governed work for it is still in flight; not "
                            "materialized as a second live node for the same "
                            "package_id"
                        ),
                        "materialization_error_code": "PACKAGE_ID_ALREADY_ACTIVE",
                    }
                )
                continue
            assert materialized_record is not None  # guaranteed by the (None, conflict) contract
            materialized.append(
                {
                    "work_id": node.package_id,
                    "execution_ready": policy.execution_ready,
                    "reason": policy.reason.value,
                    "risk_class": classification.risk_class.value,
                    "owner_gate": node.owner_gate.value if node.owner_gate else None,
                    "already_materialized": False,
                }
            )
    except OriginationProjectionError as exc:
        code = getattr(exc, "code", "ORIGINATION_PROJECTION_FAILED")
        return _fail_closed(str(exc), blocker=code), EXIT_ERROR
    except ValidationError as exc:
        # Defense-in-depth for the materialize_work_node() surface_id
        # overflow this same round's IV found (a project_id passing the
        # precheck above but combined with an as-yet-unforeseen work_id
        # shape) and any other validation failure inside this loop that
        # is not itself a MaterializationError.
        return _fail_closed(str(exc), blocker="ORIGINATION_VALIDATION_FAILED"), EXIT_ERROR

    payload: dict[str, object] = {
        "schema_version": 1,
        "package_id": "AS-ORIGIN-001",
        "project_id": project_id,
        "eligible_count": len(outcomes),
        "materialized_count": len(materialized),
        "materialized": materialized,
        "not_materialized_count": len(not_materialized),
        "not_materialized": not_materialized,
        "merge_authorized": False,
        "execution_authorized": False,
    }
    return payload, EXIT_OK
