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
from functools import partial
from pathlib import Path

from pydantic import ValidationError

from project_atlas.orchestration.autonomy.discovery import collect_live_inventory
from project_atlas.orchestration.autonomy.models import TrustedAnchorRecord, WorkNode
from project_atlas.orchestration.autonomy.trust import TrustError, load_runtime_anchor
from project_atlas.orchestration.origination.acceptance_contracts import (
    AcceptanceContractConfigError,
)
from project_atlas.orchestration.origination.identity import origination_identity_from_parts
from project_atlas.orchestration.origination.materialize import (
    MaterializationError,
    materialize_work_node,
)
from project_atlas.orchestration.origination.pipeline import (
    effective_authority_fields,
    originate_new_only,
)
from project_atlas.orchestration.origination.projection import (
    RELATIVE_DEFAULT as ORIGINATION_PROJECTION_RELATIVE_DEFAULT,
)
from project_atlas.orchestration.origination.projection import (
    OriginationProjectionError,
    persist_proposed,
    reconcile_revision,
)
from project_atlas.orchestration.origination.proposal import RiskClass
from project_atlas.orchestration.origination.risk import classify as classify_risk
from project_atlas.orchestration.origination.sources import (
    DuplicateItemIdError,
    OriginationSourceConfigError,
    eligible_work_items,
)

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


def _source_identity_still_current(root: Path, project_id: str, expected_identity: str) -> bool:
    """Re-read authoritative source truth NOW and report whether
    ``expected_identity`` is still one of the identities it yields.

    IV finding F2 on PR #677: ``reconcile_revision()`` was last-caller-
    wins -- a scan stalled across a source edit could replay a
    reconciliation derived from a STALE snapshot and dethrone the
    genuinely newer revision. This checker is handed to
    ``reconcile_revision(still_current=...)`` and runs INSIDE its
    projection lock, immediately before any write, so only evidence that
    matches CURRENT source truth at write time can supersede or
    materialize. A genuine source revert back to an earlier revision's
    exact content re-derives that revision's same identity and correctly
    passes (owner gate (d): revert semantics are unchanged).

    P1 finding on PR #678 (chatgpt-codex-connector), owner directive
    D-ATLAS-AUTHORITY-SNAPSHOT-CONVERGENCE: ``expected_identity`` now
    covers ``proposed_scope`` / ``success_criteria`` too (see
    ``identity.py``), so this recheck must derive the SAME two fields
    the same way ``_build_outcome()`` did -- via the shared
    ``effective_authority_fields()`` -- and fold them into the fresh
    identity it compares. A stalled scan holding an OLD acceptance
    contract's scope/criteria therefore recomputes a DIFFERENT identity
    from current source truth and correctly fails this check, exactly
    like a roadmap-content edit already did before this fix.

    Never raises: an unreadable/misconfigured source at this instant is
    UNVERIFIABLE evidence, and unverifiable fails closed to "not
    current" -- the item is denied with a per-item receipt, never
    reconciled on a guess.
    """
    try:
        items = eligible_work_items(root)
    except Exception:
        return False
    for item in items:
        proposed_scope, success_criteria = effective_authority_fields(item)
        if (
            origination_identity_from_parts(
                project_id,
                item.source_path,
                item.item_id,
                item.item_digest,
                proposed_scope,
                success_criteria,
            )
            == expected_identity
        ):
            return True
    return False


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
    except OriginationSourceConfigError as exc:
        # PR-A review finding (chatgpt-codex-connector, P2): a project's
        # own explicit origination_sources declaration can be malformed
        # (bad shape, unsupported format/path combination) -- that must
        # come back as this scan's own documented fail-closed payload,
        # not an escaping traceback, exactly like every other
        # configuration/trust failure this function already handles.
        return _fail_closed(str(exc), blocker="ORIGINATION_SOURCE_CONFIG_INVALID"), EXIT_ERROR
    except DuplicateItemIdError as exc:
        # Same contract: the same stable item_id declared authoritative by
        # two different sources is a real configuration ambiguity that
        # must be visible in the scan's own payload, not an uncaught
        # exception.
        return (
            _fail_closed(str(exc), blocker="ORIGINATION_DUPLICATE_ITEM_ID"),
            EXIT_ERROR,
        )
    except AcceptanceContractConfigError as exc:
        # IV finding (PR #663 review): eligible_work_items() (called
        # inside originate_new_only()) can raise this for a malformed,
        # ambiguous, or unmatched acceptance-contract declaration -- the
        # same "never raises" contract this function documents for every
        # other configuration failure applies here too.
        return (
            _fail_closed(str(exc), blocker="ACCEPTANCE_CONTRACT_CONFIG_INVALID"),
            EXIT_ERROR,
        )
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
            #
            # Formerly-disclosed gap (fresh IV round, PR #663, acceptance-
            # contracts work), CLOSED by AS-ORIGIN-MATERIALIZED-
            # SUPERSESSION-001: this AS-IS branch only ever fires for a
            # repeat scan of THIS SAME `origination_identity` -- it is
            # correctly silent about a REVOKED/altered acceptance contract
            # or a changed blocker, because that always produces a
            # DIFFERENT `origination_identity` (the content digest
            # changed) and is handled below, where `reconcile_revision()`
            # supersedes this exact AS-IS row once a newer revision for
            # the same `package_id` is scanned -- see
            # D-ATLAS-ORIGINATION-MATERIALIZED-REVISION-SUPERSESSION.
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
                        "superseded_prior_revisions": [],
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
                # AS-ORIGIN-MATERIALIZED-SUPERSESSION-001 (owner directive
                # D-ATLAS-ORIGINATION-MATERIALIZED-REVISION-SUPERSESSION
                # §5 Case B): even though THIS revision cannot itself
                # materialize (most commonly PROPOSAL_BLOCKED --
                # `proposal.blockers` non-empty), the fact that a NEWER
                # authoritative-source revision exists at all still
                # supersedes whatever OTHER revision currently holds
                # execution authority for this same `work_id` -- a
                # newly-blocked revision must revoke a stale unblocked
                # one's durable rehydratability, not merely fail to add
                # a second one alongside it.
                try:
                    reconciliation = reconcile_revision(
                        store,
                        origination_identity=proposal.origination_identity,
                        package_id=proposal.work_id,
                        work_node=None,
                        still_current=partial(
                            _source_identity_still_current,
                            root,
                            project_id,
                            proposal.origination_identity,
                        ),
                    )
                except OriginationProjectionError as reconcile_exc:
                    # IDENTITY_ALREADY_RESOLVED (owner directive §4: a
                    # TERMINAL/SUPERSEDED revision permanently cannot
                    # regain authority, even on an exact-content revert)
                    # and STALE_SOURCE_SNAPSHOT (IV F2, PR #677: this
                    # scan's snapshot of the item no longer matches
                    # current source truth; the store is untouched and a
                    # fresh scan will reconcile the genuinely current
                    # revision) -- both isolated to this one work_id,
                    # never fatal to the rest of the scan, matching every
                    # other per-item materialization failure in this loop.
                    not_materialized.append(
                        {
                            "work_id": proposal.work_id,
                            "execution_ready": policy.execution_ready,
                            "reason": policy.reason.value,
                            "materialization_error": str(reconcile_exc),
                            "materialization_error_code": reconcile_exc.code,
                            "superseded_prior_revisions": [],
                        }
                    )
                    continue
                not_materialized.append(
                    {
                        "work_id": proposal.work_id,
                        "execution_ready": policy.execution_ready,
                        "reason": policy.reason.value,
                        "materialization_error": str(exc),
                        "materialization_error_code": exc.code,
                        "superseded_prior_revisions": [
                            row.origination_identity for row in reconciliation.superseded
                        ],
                    }
                )
                continue
            # AS-ORIGIN-MATERIALIZED-SUPERSESSION-001: `origination_
            # identity` includes the item's content digest (identity.py),
            # but `proposal.work_id` (-> WorkNode.package_id) does not --
            # it is stable across a content revision to the same roadmap
            # item (`work_id_for()` hashes only project_id+item_id). A
            # revision to an item while a PRIOR active (non-TERMINAL,
            # non-SUPERSEDED) record for that same item still holds
            # `package_id` therefore reaches this point as a genuinely
            # NEW `origination_identity` (the `existing is not None`
            # branch above does not catch it) whose newly-eligible
            # proposal must REPLACE the incumbent -- supersede it, then
            # materialize this one -- not merely report a conflict and
            # leave stale authority durably rehydratable (owner directive
            # §5 Case C; this replaces the old refuse-only
            # `PACKAGE_ID_ALREADY_ACTIVE` behavior entirely).
            # `reconcile_revision()` performs the supersession and this
            # identity's own materialization inside ONE lock, closing the
            # same TOCTOU window the old check-then-write pair would
            # leave open (delta-IV finding, PR #654: two concurrent scans
            # could otherwise both observe "no conflict" before either
            # wrote).
            try:
                reconciliation = reconcile_revision(
                    store,
                    origination_identity=proposal.origination_identity,
                    package_id=proposal.work_id,
                    work_node=node,
                    still_current=partial(
                        _source_identity_still_current,
                        root,
                        project_id,
                        proposal.origination_identity,
                    ),
                )
            except OriginationProjectionError as reconcile_exc:
                # Same isolation as the blocked-path branch above --
                # IDENTITY_ALREADY_RESOLVED, STALE_SOURCE_SNAPSHOT (IV F2)
                # or, defensively, AMBIGUOUS_ACTIVE_REVISION/
                # PACKAGE_ID_MISMATCH must not abort the rest of this scan
                # batch.
                not_materialized.append(
                    {
                        "work_id": proposal.work_id,
                        "execution_ready": policy.execution_ready,
                        "reason": policy.reason.value,
                        "materialization_error": str(reconcile_exc),
                        "materialization_error_code": reconcile_exc.code,
                        "superseded_prior_revisions": [],
                    }
                )
                continue
            assert reconciliation.materialized is not None  # work_node was given above
            materialized_record = reconciliation.materialized
            # Cursor Bugbot finding on PR #654 (Low), still applicable to
            # `reconcile_revision()`'s own same idempotent-replay shape: a
            # concurrent scan for this SAME identity can win the lock
            # first (`reconciliation.already_current=True`) -- report
            # what is actually durable, not what this call would have
            # written had it won the race.
            #
            # Independent-verification note (delta round on PR #654): mirror
            # the sibling already-known-identity branch's per-item isolation
            # above -- a corrupt durable record must not abort every other
            # outcome in this same scan batch, only this one work_id.
            try:
                durable_node = WorkNode.model_validate(materialized_record.work_node)
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
            already_materialized = reconciliation.already_current
            reported_node = durable_node if already_materialized else node
            materialized.append(
                {
                    "work_id": reported_node.package_id,
                    "execution_ready": policy.execution_ready,
                    "reason": policy.reason.value,
                    "risk_class": classification.risk_class.value,
                    "owner_gate": reported_node.owner_gate.value
                    if reported_node.owner_gate
                    else None,
                    "already_materialized": already_materialized,
                    "superseded_prior_revisions": [
                        row.origination_identity for row in reconciliation.superseded
                    ],
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
