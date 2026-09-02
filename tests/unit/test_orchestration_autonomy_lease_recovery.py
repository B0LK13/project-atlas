"""AS-ORCH-LEASE-RECOVERY-001 adversarial test matrix.

Real repo, real governor lease, real dispatch receipts (via the same
private helpers `test_orchestration_local_dispatch_port.py` already uses),
real `LoopState` persistence -- no mocking of the evidence gate itself.
Every refusal below was confirmed, during authorship, to genuinely fire
against the vulnerable precondition (the single condition each test
removes), matching this codebase's own IV discipline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.unit.test_orchestration_local_dispatch_port import (
    _anchor,
    _governor,
    _make_repo,
    _node,
    _repo_main_tree,
)

from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.lease_projection import (
    RELATIVE_DEFAULT as LEASE_RELATIVE,
)
from project_atlas.orchestration.autonomy.lease_projection import load_projection
from project_atlas.orchestration.autonomy.lease_recovery import (
    LeaseRecoveryError,
    release_stalled_lease_after_exhausted_dispatch,
)
from project_atlas.orchestration.autonomy.local_dispatch_port import (
    _dispatch_id_for,
    _write_receipt,
)
from project_atlas.orchestration.autonomy.loop import (
    STATE_DIR_RELATIVE,
    LoopPhase,
    LoopState,
    initial_loop_state,
    persist_loop_state,
    seal_loop_state,
)
from project_atlas.orchestration.autonomy.models import StopReason


def _loop_store(repo: Path) -> Path:
    return repo / STATE_DIR_RELATIVE


def _stopped_state(
    repo: Path,
    *,
    main: str,
    tree: str,
    active_lease_id: str | None,
    active_package_id: str | None,
    stop_reason: StopReason,
    phase: LoopPhase = LoopPhase.STOPPED,
) -> LoopState:
    base = initial_loop_state(_anchor(main, tree))
    updated = base.model_copy(
        update={
            "phase": phase,
            "sequence": 8,
            "ticks_in_invocation": 8,
            "active_lease_id": active_lease_id,
            "active_package_id": active_package_id,
            "stop_reason": stop_reason,
        }
    )
    sealed = seal_loop_state(updated)
    persist_loop_state(_loop_store(repo), sealed)
    return sealed


def _lease_and_receipts(
    repo: Path,
    main: str,
    tree: str,
    *,
    package_id: str = "PKG-RECOVERY-1",
    receipt_statuses: tuple[tuple[str, bool | None], ...] = (("FAILED", False),),
    receipt_lease_id_override: str | None = None,
) -> tuple[AutonomousGovernor, object]:
    node = _node(package_id, base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    lease = gov.lease(package_id, "governor-pilot-local", branch="b", worktree="w")
    for attempt, (status, authority_clean) in enumerate(receipt_statuses):
        dispatch_id = f"{_dispatch_id_for(lease.lease_id)}:{attempt}"
        _write_receipt(
            repo,
            dispatch_id,
            {
                "dispatch_id": dispatch_id,
                "lease_id": receipt_lease_id_override or lease.lease_id,
                "package_id": package_id,
                "status": status,
                "authority_clean": authority_clean,
                "exit_code": 0,
                "timed_out": False,
            },
        )
    return gov, lease


# ---------------------------------------------------------------------------
# Positive: genuine RESOURCE_BOUNDARY stall, every receipt a real failure.
# ---------------------------------------------------------------------------


def test_releases_when_every_receipt_genuinely_failed(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(
        repo,
        main,
        tree,
        receipt_statuses=(("FAILED", False), ("FAILED", False)),
    )
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    result = release_stalled_lease_after_exhausted_dispatch(
        repo,
        lease_id=lease.lease_id,
        loop_store=_loop_store(repo),
        lease_projection_store=repo / LEASE_RELATIVE,
    )

    assert result["abandoned"] is True
    assert result["evidence_receipt_count"] == 2
    projection = load_projection(repo / LEASE_RELATIVE)
    row = next(r for r in projection.leases if r.lease_id == lease.lease_id)
    # ABANDONED, never RELEASED -- see module docstring: RELEASED is
    # reserved for a real success, and _originate()'s CERTIFIED-witness
    # set only ever looks at RELEASED rows.
    assert row.status == "ABANDONED"


# ---------------------------------------------------------------------------
# Adversarial: each refusal, one precondition removed at a time.
# ---------------------------------------------------------------------------


def test_refuses_when_loop_is_not_stopped(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(repo, main, tree)
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
        phase=LoopPhase.LEASED,  # still live -- not this mechanism's business
    )

    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id=lease.lease_id,
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "LOOP_NOT_STOPPED"


@pytest.mark.parametrize(
    "stop_reason",
    [StopReason.OWNER_GATE, StopReason.HARD_BLOCKER, StopReason.SAFETY_BOUNDARY],
)
def test_refuses_for_any_stop_reason_other_than_resource_boundary(
    tmp_path: Path, stop_reason: StopReason
) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(repo, main, tree)
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=stop_reason,
    )

    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id=lease.lease_id,
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "NOT_RESOURCE_BOUNDARY_STOP"


def test_refuses_when_requested_lease_is_not_the_loops_own_stalled_lease(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(repo, main, tree)
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id="LEASE-SOME-OTHER-ONE",
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id=lease.lease_id,
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "LEASE_ID_MISMATCH"


def test_refuses_unknown_lease_id(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id="LEASE-DOES-NOT-EXIST",
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id="LEASE-DOES-NOT-EXIST",
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "LEASE_UNKNOWN"


def test_refuses_when_lease_already_released(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    gov, lease = _lease_and_receipts(repo, main, tree)
    gov.release_lease(lease.lease_id)  # the real, legitimate release path
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id=lease.lease_id,
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "LEASE_NOT_ACTIVE"


def test_refuses_with_zero_dispatch_evidence(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PKG-RECOVERY-1", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    lease = gov.lease("PKG-RECOVERY-1", "governor-pilot-local", branch="b", worktree="w")
    # No receipt ever written for this lease.
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id=lease.lease_id,
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "NO_DISPATCH_EVIDENCE"


def test_refuses_a_receipt_that_does_not_self_consistently_name_this_lease(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(
        repo,
        main,
        tree,
        receipt_statuses=(("FAILED", False),),
        receipt_lease_id_override="LEASE-FORGED",
    )
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id=lease.lease_id,
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "RECEIPT_LEASE_MISMATCH"


def test_refuses_when_any_receipt_is_a_genuine_authority_clean_completion(
    tmp_path: Path,
) -> None:
    """The core anti-fabrication property: a real success anywhere in the
    attempt history must never be discarded by this recovery path."""
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(
        repo,
        main,
        tree,
        receipt_statuses=(
            ("FAILED", False),
            ("COMPLETED", True),  # a genuine success buried among failures
            ("FAILED", False),
        ),
    )
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id=lease.lease_id,
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "HIDDEN_SUCCESSFUL_COMPLETION"

    # And the ledger genuinely was not touched.
    projection = load_projection(repo / LEASE_RELATIVE)
    row = next(r for r in projection.leases if r.lease_id == lease.lease_id)
    assert row.status == "ACTIVE"


def test_completed_but_not_authority_clean_is_not_treated_as_success(
    tmp_path: Path,
) -> None:
    """A COMPLETED status alone (without authority_clean=True) is exactly
    the real INT-013 incident shape -- exit_code 0, but the scope-diff
    guard rejected it. That must still count as a genuine failure, not a
    hidden success."""
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(
        repo,
        main,
        tree,
        receipt_statuses=(("FAILED", False),),
    )
    dispatch_id = f"{_dispatch_id_for(lease.lease_id)}:1"
    _write_receipt(
        repo,
        dispatch_id,
        {
            "dispatch_id": dispatch_id,
            "lease_id": lease.lease_id,
            "package_id": "PKG-RECOVERY-1",
            "status": "COMPLETED",
            "authority_clean": False,
            "exit_code": 0,
            "timed_out": False,
        },
    )
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    result = release_stalled_lease_after_exhausted_dispatch(
        repo,
        lease_id=lease.lease_id,
        loop_store=_loop_store(repo),
        lease_projection_store=repo / LEASE_RELATIVE,
    )
    assert result["abandoned"] is True


# ---------------------------------------------------------------------------
# The deep regression: an evidence-gated abandonment must not be
# misread by rehydration._originate()'s CERTIFIED-witness inference as
# proof of a real success. Real origination pipeline, real lease, real
# (planted) failed receipt, real fresh-governor rehydration.
# ---------------------------------------------------------------------------


def test_abandoned_lease_does_not_fabricate_a_certified_witness(tmp_path: Path) -> None:
    from tests.unit.test_orchestration_origination_rehydration import (
        _lease_origination_node,
        _make_trust_store,
        _run_git,
        _write_specified_project,
    )
    from tests.unit.test_orchestration_origination_rehydration import (
        _make_repo as _make_origin_repo,
    )

    from project_atlas.orchestration.autonomy.models import NodeState
    from project_atlas.orchestration.autonomy.rehydration import rehydrate_governor

    repo = _make_origin_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"
    origination_store = tmp_path / "origination"
    project_root = tmp_path / "project"
    _write_specified_project(project_root)

    trusted, inventory, lease, package_id = _lease_origination_node(
        repo, trust_store, lease_store, origination_store, project_root
    )

    # Real receipt proving genuine, exhausted failure for this lease --
    # the exact shape of the real INT-013 incident (exit_code 0, but not
    # authority_clean).
    dispatch_id = f"{_dispatch_id_for(lease.lease_id)}:0"
    _write_receipt(
        repo,
        dispatch_id,
        {
            "dispatch_id": dispatch_id,
            "lease_id": lease.lease_id,
            "package_id": package_id,
            "status": "FAILED",
            "authority_clean": False,
            "exit_code": 0,
            "timed_out": False,
        },
    )

    stopped = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.STOPPED,
            "active_package_id": package_id,
            "active_lease_id": lease.lease_id,
            "sequence": 8,
            "ticks_in_invocation": 8,
            "stop_reason": StopReason.RESOURCE_BOUNDARY,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(stopped))

    result = release_stalled_lease_after_exhausted_dispatch(
        repo,
        lease_id=lease.lease_id,
        loop_store=loop_store,
        lease_projection_store=lease_store,
    )
    assert result["abandoned"] is True

    # Process C: a brand-new governor + a brand-new (never-before-seen)
    # loop session -- simulates exactly what the real M3 resume driver
    # does after an abandonment: start a fresh session and let discovery
    # run again.
    fresh = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    fresh_loop_store = tmp_path / "loop-session-2"
    rehydrate_governor(
        fresh,
        inventory=inventory,
        trusted=trusted,
        loop_store=fresh_loop_store,
        lease_projection_store=lease_store,
        origination_projection_store=origination_store,
    )

    node = next(item for item in fresh.snapshot().nodes if item.package_id == package_id)
    # The core assertion: NOT fabricated as CERTIFIED ...
    assert node.state != NodeState.CERTIFIED
    # ... but genuinely re-offered for a real retry.
    assert node.state == NodeState.READY
    assert fresh.snapshot().leases == ()


# ---------------------------------------------------------------------------
# Real call site: run_release_stalled_lease() (Codex's PR #672 finding --
# "the new precondition is never invoked by production code" -- applies
# equally here; this is the fix for that class of gap on this mechanism).
# ---------------------------------------------------------------------------


def test_cli_entrypoint_succeeds_with_real_evidence(tmp_path: Path) -> None:
    from project_atlas.orchestration.autonomy.cli import (
        EXIT_ERROR,
        EXIT_OK,
        run_release_stalled_lease,
    )

    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(repo, main, tree)
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    report, exit_code = run_release_stalled_lease(root=repo, lease_id=lease.lease_id)
    assert exit_code == EXIT_OK
    assert report["abandoned"] is True
    assert report["merge_authorized"] is False
    assert report["execution_authorized"] is False

    # Same evidence gate, real CLI path: a second call against the now-
    # ABANDONED lease refuses rather than silently no-op'ing.
    report2, exit_code2 = run_release_stalled_lease(root=repo, lease_id=lease.lease_id)
    assert exit_code2 == EXIT_ERROR
    assert report2["blocker"] == "LEASE_NOT_ACTIVE"


def test_cli_entrypoint_refuses_without_real_evidence(tmp_path: Path) -> None:
    from project_atlas.orchestration.autonomy.cli import EXIT_ERROR, run_release_stalled_lease

    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PKG-RECOVERY-1", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    lease = gov.lease("PKG-RECOVERY-1", "governor-pilot-local", branch="b", worktree="w")
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    report, exit_code = run_release_stalled_lease(root=repo, lease_id=lease.lease_id)
    assert exit_code == EXIT_ERROR
    assert report["blocker"] == "NO_DISPATCH_EVIDENCE"
    assert report["abandoned"] is False


# ---------------------------------------------------------------------------
# IV round 2 (independent verification, fresh subagent) regression tests --
# 3 confirmed findings, each proven against the vulnerable code before the
# fix (see the reverts below), fixed, and locked in here.
# ---------------------------------------------------------------------------


def test_reap_orphaned_lease_releases_does_not_flip_abandoned_to_released(
    tmp_path: Path,
) -> None:
    """IV finding 1 (MEDIUM): reap_orphaned_lease_releases()'s skip guard
    used to check only `!= "RELEASED"`, so an ABANDONED row whose
    lease_id happened to appear in completed_lease_ids would be silently
    reconstructed and passed to project_release() -- flipping it
    ABANDONED -> RELEASED, exactly the CERTIFIED-witness fabrication this
    whole mechanism exists to prevent. `!= "ACTIVE"` closes it."""
    from project_atlas.orchestration.autonomy.lease_projection import (
        reap_orphaned_lease_releases,
    )

    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    _gov, lease = _lease_and_receipts(repo, main, tree)
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )
    result = release_stalled_lease_after_exhausted_dispatch(
        repo,
        lease_id=lease.lease_id,
        loop_store=_loop_store(repo),
        lease_projection_store=repo / LEASE_RELATIVE,
    )
    assert result["abandoned"] is True

    # A row genuinely ABANDONED must never be touched by the reaper, no
    # matter what completed_lease_ids claims.
    reaped = reap_orphaned_lease_releases(repo / LEASE_RELATIVE, (lease.lease_id,))
    assert reaped == ()
    projection = load_projection(repo / LEASE_RELATIVE)
    row = next(r for r in projection.leases if r.lease_id == lease.lease_id)
    assert row.status == "ABANDONED"


def test_list_dispatch_receipts_does_not_hide_a_later_receipt_past_a_gap(
    tmp_path: Path,
) -> None:
    """IV finding 2 (MEDIUM): list_dispatch_receipts() used to scan
    attempts 0,1,2,... and stop at the first missing index -- an
    intermediate receipt lost/deleted would silently hide every later
    receipt, including a genuine success, from the evidence gate."""
    from project_atlas.orchestration.autonomy.local_dispatch_port import (
        list_dispatch_receipts,
    )

    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PKG-RECOVERY-1", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    lease = gov.lease("PKG-RECOVERY-1", "governor-pilot-local", branch="b", worktree="w")

    # Attempt 0: FAILED. Attempt 1: deliberately never written (the gap).
    # Attempt 2: a genuine, authority-clean success.
    dispatch_id_0 = f"{_dispatch_id_for(lease.lease_id)}:0"
    _write_receipt(
        repo,
        dispatch_id_0,
        {
            "dispatch_id": dispatch_id_0,
            "lease_id": lease.lease_id,
            "package_id": "PKG-RECOVERY-1",
            "status": "FAILED",
            "authority_clean": False,
        },
    )
    dispatch_id_2 = f"{_dispatch_id_for(lease.lease_id)}:2"
    _write_receipt(
        repo,
        dispatch_id_2,
        {
            "dispatch_id": dispatch_id_2,
            "lease_id": lease.lease_id,
            "package_id": "PKG-RECOVERY-1",
            "status": "COMPLETED",
            "authority_clean": True,
        },
    )

    receipts = list_dispatch_receipts(repo, lease_id=lease.lease_id)
    dispatch_ids = {str(r["dispatch_id"]) for r in receipts}
    assert dispatch_ids == {dispatch_id_0, dispatch_id_2}

    # And the evidence gate genuinely refuses, because it now sees the
    # real success past the gap.
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )
    with pytest.raises(LeaseRecoveryError) as exc:
        release_stalled_lease_after_exhausted_dispatch(
            repo,
            lease_id=lease.lease_id,
            loop_store=_loop_store(repo),
            lease_projection_store=repo / LEASE_RELATIVE,
        )
    assert exc.value.code == "HIDDEN_SUCCESSFUL_COMPLETION"


def test_cli_entrypoint_fails_closed_on_a_corrupt_receipt(tmp_path: Path) -> None:
    """IV finding 3 (MEDIUM): run_release_stalled_lease()'s except tuple
    omitted LocalDispatchError, so a corrupt/tampered receipt (which
    list_dispatch_receipts() correctly fails closed on, via
    _read_receipt()) crashed the CLI entrypoint uncaught instead of
    returning the designed (report, EXIT_ERROR)."""
    from project_atlas.orchestration.autonomy.cli import EXIT_ERROR, run_release_stalled_lease
    from project_atlas.orchestration.autonomy.local_dispatch_port import (
        RECEIPTS_RELATIVE,
        _receipt_filename,
    )

    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PKG-RECOVERY-1", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    lease = gov.lease("PKG-RECOVERY-1", "governor-pilot-local", branch="b", worktree="w")
    _stopped_state(
        repo,
        main=main,
        tree=tree,
        active_lease_id=lease.lease_id,
        active_package_id="PKG-RECOVERY-1",
        stop_reason=StopReason.RESOURCE_BOUNDARY,
    )

    dispatch_id = f"{_dispatch_id_for(lease.lease_id)}:0"
    receipt_path = repo / RECEIPTS_RELATIVE / _receipt_filename(dispatch_id)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text("{not valid json", encoding="utf-8")

    report, exit_code = run_release_stalled_lease(root=repo, lease_id=lease.lease_id)
    assert exit_code == EXIT_ERROR
    assert report["blocker"] == "CORRUPT_RECEIPT"
    assert report["abandoned"] is False
