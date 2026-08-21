"""AS-ORCH-DURABLE-LEASE-PROJECTION-001 focused + concurrent + restart tests."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.lease_projection import (
    PACKAGE_ID,
    PROJECTION_NAME,
    ProjectionError,
    load_projection,
    project_grant,
    project_release,
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
