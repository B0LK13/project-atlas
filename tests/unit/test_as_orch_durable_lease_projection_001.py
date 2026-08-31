"""AS-ORCH-DURABLE-LEASE-PROJECTION-001 focused + concurrent + restart tests."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.lease_projection import (
    LOCK_NAME,
    PACKAGE_ID,
    PROJECTION_NAME,
    ProjectionError,
    load_projection,
    project_grant,
    project_release,
    reap_orphaned_lease_releases,
    visible_active_lease,
)
from project_atlas.orchestration.autonomy.leases import grant_lease, release_lease
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    EXPECTED_BASE_MAIN,
    EXPECTED_BASE_TREE,
    AdvancementReason,
    AgentCapability,
    AgentRecord,
    ExecutionHostClass,
    IvRequirements,
    MutationSurface,
    NodeState,
    TrustedAnchorRecord,
    WorkNode,
)
from project_atlas.orchestration.autonomy.trust import seal_anchor
from project_atlas.source_identity import ProjectIdentityLock

PIN = EXPECTED_BASE_MAIN
OTHER_PIN = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _anchor() -> TrustedAnchorRecord:
    predecessor = "1111111111111111111111111111111111111111"
    certified = "3333333333333333333333333333333333333333"
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=PIN,
            trusted_tree=EXPECTED_BASE_TREE,
            predecessor_main=predecessor,
            predecessor_tree="2222222222222222222222222222222222222222",
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-DURABLE-LEASE-PROJECTION-001",
            source_directive="D-AUTONOMOUS-NO-PROMPT-PERSISTENT-GOVERNOR-060",
            source_pr=1,
            merge_commit=PIN,
            merge_parent_1=predecessor,
            merge_parent_2=certified,
            merge_tree=EXPECTED_BASE_TREE,
            certified_head=certified,
            certified_tree=EXPECTED_BASE_TREE,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/unit/test_as_orch_durable_lease_projection_001.py",
            evidence_digest="bb" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def _node(
    package_id: str,
    *,
    paths: tuple[str, ...] = ("src/a",),
    surface: str = "surface-a",
    semantic: str = "SEMANTIC_A",
) -> WorkNode:
    return WorkNode(
        package_id=package_id,
        objective="project lease",
        base_pin=PIN,
        mutation_surface=MutationSurface(
            surface_id=surface,
            paths=paths,
            semantic=semantic,
        ),
        execution_host_class=ExecutionHostClass.IN_PROCESS,
        agent_capabilities_required=(AgentCapability.IMPLEMENT,),
        acceptance_criteria=("PASS",),
        iv_requirements=IvRequirements(certification_required=True),
        state=NodeState.READY,
    )


def _agent(agent_id: str) -> AgentRecord:
    return AgentRecord(agent_id=agent_id, capabilities=(AgentCapability.IMPLEMENT,))


def _lease(
    *,
    lease_id: str,
    agent_id: str,
    package_id: str,
    sequence: int,
    paths: tuple[str, ...] = ("src/a",),
    surface: str = "surface-a",
    semantic: str = "SEMANTIC_A",
):
    return grant_lease(
        lease_id=lease_id,
        agent=_agent(agent_id),
        node=_node(package_id, paths=paths, surface=surface, semantic=semantic),
        branch="feat/as-orch-durable-lease-projection-001",
        worktree="durable-lease-wt",
        sequence=sequence,
    )


def test_projection_is_not_authority(tmp_path: Path) -> None:
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    projection = project_grant(tmp_path, lease, live_main=PIN)
    assert projection.package == PACKAGE_ID
    assert projection.honesty.projection_is_authority is False
    assert projection.honesty.grant_source == "PRIMARY_GOVERNOR"
    assert projection.honesty.ack_source == "PRIMARY_GOVERNOR"
    assert projection.leases[0].projection_is_authority is False
    assert (tmp_path / PROJECTION_NAME).is_file()


def test_ack_visibility(tmp_path: Path) -> None:
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)
    row = visible_active_lease(
        tmp_path,
        lease_id="LEASE-1",
        agent_id="worker-a",
        package_id="PKG-A",
        live_main=PIN,
    )
    assert row.status == "ACTIVE"
    assert row.created_sequence == 1


def test_release_visibility(tmp_path: Path) -> None:
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)
    project_release(tmp_path, release_lease(lease), live_main=PIN)
    with pytest.raises(ProjectionError, match="active lease not visible") as exc:
        visible_active_lease(
            tmp_path,
            lease_id="LEASE-1",
            agent_id="worker-a",
            package_id="PKG-A",
            live_main=PIN,
        )
    assert exc.value.code == "LEASE_NOT_VISIBLE"
    loaded = load_projection(tmp_path)
    assert loaded.leases[0].status == "RELEASED"
    assert loaded.leases[0].released_sequence == 1


def test_process_restart_visibility(tmp_path: Path) -> None:
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)
    restarted = load_projection(tmp_path)
    assert restarted.leases[0].lease_id == "LEASE-1"
    assert restarted.leases[0].status == "ACTIVE"
    row = visible_active_lease(
        tmp_path,
        lease_id="LEASE-1",
        agent_id="worker-a",
        package_id="PKG-A",
        live_main=PIN,
    )
    assert row.package_id == "PKG-A"


def test_stale_lease_rejected(tmp_path: Path) -> None:
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    with pytest.raises(ProjectionError, match="stale lease") as exc:
        project_grant(tmp_path, lease, live_main=OTHER_PIN)
    assert exc.value.code == "STALE_LEASE"
    project_grant(tmp_path, lease, live_main=PIN)
    with pytest.raises(ProjectionError, match="stale lease") as stale_ack:
        visible_active_lease(
            tmp_path,
            lease_id="LEASE-1",
            agent_id="worker-a",
            package_id="PKG-A",
            live_main=OTHER_PIN,
        )
    assert stale_ack.value.code == "STALE_LEASE"


def test_duplicate_active_lease_rejected(tmp_path: Path) -> None:
    first = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    second = _lease(lease_id="LEASE-2", agent_id="worker-b", package_id="PKG-A", sequence=2)
    project_grant(tmp_path, first, live_main=PIN)
    with pytest.raises(ProjectionError, match="duplicate active lease") as exc:
        project_grant(tmp_path, second, live_main=PIN)
    assert exc.value.code == "DUPLICATE_ACTIVE_LEASE"


def test_foreign_worker_rejected(tmp_path: Path) -> None:
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)
    with pytest.raises(ProjectionError, match="foreign worker") as exc:
        visible_active_lease(
            tmp_path,
            lease_id="LEASE-1",
            agent_id="worker-b",
            package_id="PKG-A",
            live_main=PIN,
        )
    assert exc.value.code == "FOREIGN_WORKER"


def test_foreign_package_rejected(tmp_path: Path) -> None:
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)
    with pytest.raises(ProjectionError, match="foreign package") as exc:
        visible_active_lease(
            tmp_path,
            lease_id="LEASE-1",
            agent_id="worker-a",
            package_id="PKG-B",
            live_main=PIN,
        )
    assert exc.value.code == "FOREIGN_PACKAGE"


def test_released_lease_id_not_recyclable(tmp_path: Path) -> None:
    first = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, first, live_main=PIN)
    project_release(tmp_path, release_lease(first), live_main=PIN)
    recycled = _lease(lease_id="LEASE-1", agent_id="worker-b", package_id="PKG-B", sequence=2)
    with pytest.raises(ProjectionError, match="replay") as exc:
        project_grant(tmp_path, recycled, live_main=PIN)
    assert exc.value.code == "LEASE_REPLAY"


def test_replay_fail_closed(tmp_path: Path) -> None:
    first = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    replay = _lease(lease_id="LEASE-1", agent_id="worker-b", package_id="PKG-B", sequence=2)
    project_grant(tmp_path, first, live_main=PIN)
    with pytest.raises(ProjectionError, match="replay") as exc:
        project_grant(tmp_path, replay, live_main=PIN)
    assert exc.value.code == "LEASE_REPLAY"


def test_idempotent_same_grant(tmp_path: Path) -> None:
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    first = project_grant(tmp_path, lease, live_main=PIN)
    second = project_grant(tmp_path, lease, live_main=PIN)
    assert len(first.leases) == 1
    assert len(second.leases) == 1


def test_concurrent_distinct_packages(tmp_path: Path) -> None:
    errors: list[BaseException] = []

    def _grant(lease_id: str, package_id: str, agent_id: str, sequence: int) -> None:
        try:
            project_grant(
                tmp_path,
                _lease(
                    lease_id=lease_id,
                    agent_id=agent_id,
                    package_id=package_id,
                    sequence=sequence,
                    paths=("src/b",) if package_id == "PKG-B" else ("src/a",),
                    surface="surface-b" if package_id == "PKG-B" else "surface-a",
                    semantic="SEMANTIC_B" if package_id == "PKG-B" else "SEMANTIC_A",
                ),
                live_main=PIN,
            )
        except BaseException as exc:
            errors.append(exc)

    one = threading.Thread(target=_grant, args=("LEASE-1", "PKG-A", "worker-a", 1))
    two = threading.Thread(target=_grant, args=("LEASE-2", "PKG-B", "worker-b", 2))
    one.start()
    two.start()
    one.join()
    two.join()
    assert errors == []
    loaded = load_projection(tmp_path)
    assert {row.package_id for row in loaded.leases} == {"PKG-A", "PKG-B"}


def test_governor_default_does_not_project(tmp_path: Path) -> None:
    gov = AutonomousGovernor(
        current_main=PIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
    )
    gov.add_node(
        _node("PKG-A").model_copy(
            update={
                "agent_capabilities_required": (
                    AgentCapability.DISCOVER,
                    AgentCapability.IMPLEMENT,
                )
            }
        )
    )
    gov.lease(
        "PKG-A",
        "governor-pilot-local",
        branch="feat/as-orch-durable-lease-projection-001",
        worktree="durable-lease-wt",
    )
    assert not (tmp_path / PROJECTION_NAME).exists()


def test_governor_projects_grant_and_ack(tmp_path: Path) -> None:
    gov = AutonomousGovernor(
        current_main=PIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
        lease_projection_store=tmp_path,
    )
    gov.add_node(
        _node("PKG-A").model_copy(
            update={
                "agent_capabilities_required": (
                    AgentCapability.DISCOVER,
                    AgentCapability.IMPLEMENT,
                )
            }
        )
    )
    lease = gov.lease(
        "PKG-A",
        "governor-pilot-local",
        branch="feat/as-orch-durable-lease-projection-001",
        worktree="durable-lease-wt",
    )
    row = visible_active_lease(
        tmp_path,
        lease_id=lease.lease_id,
        agent_id="governor-pilot-local",
        package_id="PKG-A",
        live_main=PIN,
    )
    assert row.status == "ACTIVE"
    assert row.projection_is_authority is False


def test_planted_tmp_symlink_does_not_escape_outside_file(tmp_path: Path) -> None:
    """ORCH-LEASE-SYMLINK-ESCAPE-001: ignore predictable .leases.json.tmp symlink."""
    store = tmp_path / "store-a"
    store.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("FOREIGN_SENTINEL\n", encoding="utf-8")
    planted = store / f".{PROJECTION_NAME}.tmp"
    planted.symlink_to(outside)
    project_grant(
        store,
        _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1),
        live_main=PIN,
    )
    assert outside.read_text(encoding="utf-8") == "FOREIGN_SENTINEL\n"
    projection = store / PROJECTION_NAME
    assert projection.is_file()
    assert not projection.is_symlink()
    assert planted.is_symlink()
    loaded = load_projection(store)
    assert loaded.leases[0].lease_id == "LEASE-1"
    assert loaded.leases[0].projection_is_authority is False


def test_planted_tmp_symlink_does_not_overwrite_foreign_store(tmp_path: Path) -> None:
    store_a = tmp_path / "store-a"
    store_b = tmp_path / "store-b"
    store_a.mkdir()
    store_b.mkdir()
    foreign = store_b / PROJECTION_NAME
    foreign.write_text("FOREIGN_SENTINEL\n", encoding="utf-8")
    planted = store_a / f".{PROJECTION_NAME}.tmp"
    planted.symlink_to(foreign)
    project_grant(
        store_a,
        _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1),
        live_main=PIN,
    )
    assert foreign.read_text(encoding="utf-8") == "FOREIGN_SENTINEL\n"
    assert not foreign.is_symlink()
    local = store_a / PROJECTION_NAME
    assert local.is_file()
    assert not local.is_symlink()
    assert load_projection(store_a).leases[0].lease_id == "LEASE-1"
    with pytest.raises(ProjectionError, match="unreadable") as exc:
        load_projection(store_b)
    assert exc.value.code == "STATE_CORRUPT"


def test_symlink_projection_file_fail_closed(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    planted = tmp_path / PROJECTION_NAME
    planted.symlink_to(outside)
    with pytest.raises(ProjectionError, match="symlink") as exc:
        load_projection(tmp_path)
    assert exc.value.code == "PATH_UNSAFE"


# --------------------------------------------------------------------------- #
# AUTONOMY_PROJECTION_ERROR_RECOVERY_BOUNDARY (post-#654 follow-up):
# reap_orphaned_lease_releases().
# --------------------------------------------------------------------------- #
def test_reap_releases_a_proven_complete_active_lease(tmp_path: Path) -> None:
    """Matrix A: normal release. ``completed_lease_ids`` durably proves
    this lease's governed work already finished; the row is still ACTIVE
    only because the original release write never happened (crash/
    contention). Reaping it is the exact recovery this function exists
    for.
    """
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)

    reaped = reap_orphaned_lease_releases(tmp_path, ("LEASE-1",))

    assert reaped == ("LEASE-1",)
    row = load_projection(tmp_path).leases[0]
    assert row.status == "RELEASED"


def test_reap_survives_real_lock_contention_then_retries_to_completion(
    tmp_path: Path,
) -> None:
    """Matrix B + C: a genuine held OS lock (not a monkeypatch) during the
    reap attempt must not corrupt anything, raise, or silently "succeed"
    -- the row must stay durably ACTIVE, exactly the proof needed for a
    later retry to still find it. Once the lock clears, the very same
    call (same durable evidence, no new state needed) completes it.
    """
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)

    lock_path = (tmp_path.expanduser().resolve() / LOCK_NAME).resolve()
    holder_ready = threading.Event()
    release_holder = threading.Event()

    def _hold_lock() -> None:
        with ProjectIdentityLock(lock_path, wait_seconds=2.0, stale_seconds=30.0):
            holder_ready.set()
            release_holder.wait(timeout=10.0)

    holder = threading.Thread(target=_hold_lock, daemon=True)
    holder.start()
    try:
        assert holder_ready.wait(timeout=5.0), "background lock holder never acquired the lock"
        during_contention = reap_orphaned_lease_releases(tmp_path, ("LEASE-1",))
    finally:
        release_holder.set()
        holder.join(timeout=5.0)

    # B: contention swallowed, nothing reaped, row untouched -- no silent
    # success, no exception, no lost proof.
    assert during_contention == ()
    assert load_projection(tmp_path).leases[0].status == "ACTIVE"

    # C: lock is clear now; the exact same durable evidence recovers it.
    after_contention = reap_orphaned_lease_releases(tmp_path, ("LEASE-1",))
    assert after_contention == ("LEASE-1",)
    assert load_projection(tmp_path).leases[0].status == "RELEASED"


def test_reap_is_idempotent_on_an_already_released_lease(tmp_path: Path) -> None:
    """Matrix E: repeated reaper. Safe to call on every rehydration, not
    just once -- an already-RELEASED row is left untouched, including its
    ``released_sequence``.
    """
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)
    project_release(tmp_path, release_lease(lease), live_main=PIN)
    released_sequence_before = load_projection(tmp_path).leases[0].released_sequence

    reaped = reap_orphaned_lease_releases(tmp_path, ("LEASE-1",))

    assert reaped == ()
    row = load_projection(tmp_path).leases[0]
    assert row.status == "RELEASED"
    assert row.released_sequence == released_sequence_before


def test_reap_never_touches_a_different_active_lease(tmp_path: Path) -> None:
    """Matrix F + G + I + L: proves exact-``lease_id`` matching, not
    package-level matching. LEASE-1 (completed, proven via
    ``completed_lease_ids``) and LEASE-2 (a genuinely new, still-ACTIVE
    lease for a REVISED work item under the SAME package_id -- the exact
    D-PHASE2A-2 "same package_id, new revision" scenario) coexist. Only
    LEASE-1's id is in the durable proof; LEASE-2 must never be looked
    up, reconstructed, or released, no matter how similar its identity.
    """
    completed = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, completed, live_main=PIN)
    project_release(tmp_path, release_lease(completed), live_main=PIN)

    still_active = _lease(lease_id="LEASE-2", agent_id="worker-b", package_id="PKG-A", sequence=2)
    project_grant(tmp_path, still_active, live_main=PIN)

    reaped = reap_orphaned_lease_releases(tmp_path, ("LEASE-1",))

    assert reaped == ()  # LEASE-1 was already RELEASED -- nothing new to do
    rows = {row.lease_id: row for row in load_projection(tmp_path).leases}
    assert rows["LEASE-1"].status == "RELEASED"
    assert rows["LEASE-2"].status == "ACTIVE"  # untouched, never even considered


def test_reap_uses_the_leases_own_base_pin_not_live_main(tmp_path: Path) -> None:
    """Design proof: the reaper must reconstruct with ``live_main=row.
    base_pin`` (this lease's OWN recorded pin), never the caller's
    current live main -- otherwise ``project_release()``'s own
    ``reject_stale_base`` (still enforced and unmodified; see
    ``test_stale_lease_rejected`` above) would wrongly refuse to release
    old, already-completed work purely because main has since advanced.
    Simulated here by granting under ``PIN`` and never even passing
    ``OTHER_PIN`` anywhere in this call -- if the implementation ever
    regressed to using a caller-supplied "current main" instead, this is
    the scenario (main has moved on) that would start failing.
    """
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)
    assert PIN != OTHER_PIN  # sanity: main really would look "moved" by now

    reaped = reap_orphaned_lease_releases(tmp_path, ("LEASE-1",))

    assert reaped == ("LEASE-1",)
    assert load_projection(tmp_path).leases[0].status == "RELEASED"


def test_reap_fails_closed_on_corrupt_projection_file(tmp_path: Path) -> None:
    """Matrix J: a corrupt store must never be interpreted as empty/no-
    work-to-do -- it must propagate loudly, matching this module's
    existing STATE_CORRUPT policy everywhere else.
    """
    (tmp_path / PROJECTION_NAME).write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ProjectionError) as exc:
        reap_orphaned_lease_releases(tmp_path, ("LEASE-1",))
    assert exc.value.code == "STATE_CORRUPT"


def test_reap_fails_closed_on_a_corrupt_individual_row(tmp_path: Path) -> None:
    """Matrix J (row-level variant): the projection file itself is valid
    JSON/schema (so ``load_projection()`` succeeds), but the specific
    completed lease's row cannot reconstruct into a valid ``AgentLease``
    (an unrecognized capability value). Must fail closed with
    STATE_CORRUPT, not silently skip the row as if it were merely absent.
    """
    lease = _lease(lease_id="LEASE-1", agent_id="worker-a", package_id="PKG-A", sequence=1)
    project_grant(tmp_path, lease, live_main=PIN)
    raw = json.loads((tmp_path / PROJECTION_NAME).read_text(encoding="utf-8"))
    raw["leases"][0]["capabilities"] = ["NOT_A_REAL_CAPABILITY"]
    (tmp_path / PROJECTION_NAME).write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ProjectionError) as exc:
        reap_orphaned_lease_releases(tmp_path, ("LEASE-1",))
    assert exc.value.code == "STATE_CORRUPT"


def test_reap_no_ops_safely_with_nothing_to_do(tmp_path: Path) -> None:
    """Defensive coverage: empty completed_lease_ids, and a completed id
    with no matching durable row at all (e.g. the durable lease
    projection was never configured for the process that completed it),
    are both benign no-ops -- never an error.
    """
    assert reap_orphaned_lease_releases(tmp_path, ()) == ()
    assert reap_orphaned_lease_releases(tmp_path, ("LEASE-NEVER-GRANTED",)) == ()
