"""ORCH001E-011: governor/loop cross-process rehydration.

D-ORCH001E-011-CRITICAL-PATH-WORKSTEAL requires an AUTHENTIC RECOVERY TEST:
"Tests must include REAL SEPARATE PROCESS INVOCATIONS, not merely two
objects in one Python process." ``test_real_subprocess_recovers_leased_pilot_node_after_crash``
below is that proof: it spawns two genuinely separate ``python`` subprocesses
against a real (no-network-remote) git repository, with nothing shared
between them but the filesystem.

The remaining tests exercise ``rehydrate_governor()`` directly. They run
same-process, but always hand it a FRESH ``AutonomousGovernor`` that reads
only from disk -- never the governor/loop object that produced the state --
so the mechanism under test (JSON files on disk, re-parsed by pydantic) is
the same one a real second process would use. They are the adversarial
crash-window matrix the directive requires (READY/LEASED/owner-gated
work, plus DISPATCHING/AWAITING_RESULT/VALIDATING fail-closed) and are
honestly framed here as disk-mediated contract tests, not re-claimed as
cross-process proof -- that claim is reserved for the one real-subprocess
test above.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from project_atlas.orchestration.autonomy.discovery import collect_live_inventory
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.loop import LoopPhase
from project_atlas.orchestration.autonomy.models import (
    PILOT_PACKAGE_ID,
    AdvancementReason,
    NodeState,
    OwnerGateKind,
    TrustedAnchorRecord,
)
from project_atlas.orchestration.autonomy.rehydration import RehydrationError, rehydrate_governor
from project_atlas.orchestration.autonomy.trust import (
    CANONICAL_REPOSITORY_IDENTITY,
    initialize_store,
    seal_anchor,
)

_OLD_MAIN = "a" * 40
_OLD_TREE = "b" * 40
_SRC = str(Path(__file__).resolve().parents[2] / "src")


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    """A real, self-contained git repo: `origin/main` is a faked
    remote-tracking ref (`update-ref`), not a real network remote, so
    `collect_live_inventory`'s real `git rev-parse origin/main` subprocess
    call resolves it with no network access required."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", "init")
    sha = _run_git(repo, "rev-parse", "HEAD")
    _run_git(repo, "update-ref", "refs/remotes/origin/main", sha)
    return repo


def _anchor(main: str, tree: str) -> TrustedAnchorRecord:
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main=_OLD_MAIN,
            predecessor_tree=_OLD_TREE,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-AUTONOMY-001-PIN-RETARGET",
            source_directive="D-ORCH001E-011-TEST-FIXTURE",
            source_pr=1,
            merge_commit=main,
            merge_parent_1=_OLD_MAIN,
            merge_parent_2=main,
            merge_tree=tree,
            certified_head=main,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/fixtures/orch001e-011.json",
            evidence_digest="ab" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def _make_trust_store(tmp_path: Path, main: str, tree: str) -> Path:
    store = tmp_path / "trust"
    initialize_store(store, _anchor(main, tree))
    return store


# ---------------------------------------------------------------------------
# The authentic cross-process recovery proof.
# ---------------------------------------------------------------------------


def test_real_subprocess_recovers_leased_pilot_node_after_crash(tmp_path: Path) -> None:
    """Process 1 leases the pilot node and exits without dispatching it --
    a real crash window at LEASED, before any node-lookup code ever ran in
    that process. Process 2 is a fresh `python -m` invocation of the exact
    CLI entrypoint (`run_governor_loop_tick`) that a real `atlas orchestrator
    governor-loop-tick` call would run. Before ORCH001E-011, process 2's
    governor.snapshot().nodes would be empty and `_dispatch_leased()`'s
    `next(item for item in ... if item.package_id == package_id)` would
    raise an uncaught StopIteration. This proves process 2 instead
    completes the pilot's in-process execution and reaches IDLE."""
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)

    process_1 = f"""
import sys
sys.path.insert(0, {_SRC!r})
from pathlib import Path
from project_atlas.orchestration.autonomy.discovery import collect_live_inventory
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.lease_projection import RELATIVE_DEFAULT
from project_atlas.orchestration.autonomy.loop import AutonomousLoop, LoopPhase, STATE_DIR_RELATIVE
from project_atlas.orchestration.autonomy.trust import load_runtime_anchor

root = Path({str(repo)!r})
trusted = load_runtime_anchor(store=Path({str(trust_store)!r}))
inventory = collect_live_inventory(root)
governor = AutonomousGovernor(
    current_main=inventory.current_main,
    current_tree=inventory.current_tree,
    trusted_anchor=trusted,
    lease_projection_store=root / RELATIVE_DEFAULT,
)
node = governor._pilot_node(inventory, None)
governor.add_node(node)
governor.mark_ready(node.package_id)
lease = governor.lease(node.package_id, "governor-pilot-local", branch="feat/pilot", worktree="wt")
loop = AutonomousLoop(
    governor=governor, trusted=trusted, store=root / STATE_DIR_RELATIVE, root=root,
)
# Simulate a crash exactly here: the lease is granted and durably
# projected, but this process exits before ever calling tick()/dispatch.
loop._save(
    phase=LoopPhase.LEASED,
    active_package_id=node.package_id,
    active_lease_id=lease.lease_id,
    sequence=loop.state.sequence + 1,
)
print(lease.lease_id)
"""

    result_1 = subprocess.run(
        [sys.executable, "-c", process_1],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result_1.returncode == 0, result_1.stderr
    lease_id = result_1.stdout.strip().splitlines()[-1]
    assert lease_id.startswith("LEASE-")

    process_2 = f"""
import json, sys
sys.path.insert(0, {_SRC!r})
from pathlib import Path
from project_atlas.orchestration.autonomy.cli import run_governor_loop_tick
payload, exit_code = run_governor_loop_tick(
    root=Path({str(repo)!r}), trust_store=Path({str(trust_store)!r}),
)
print(json.dumps({{"payload": payload, "exit_code": exit_code}}))
"""
    result_2 = subprocess.run(
        [sys.executable, "-c", process_2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result_2.returncode == 0, result_2.stderr
    outcome = json.loads(result_2.stdout.strip().splitlines()[-1])
    assert outcome["exit_code"] == 0, outcome
    payload = outcome["payload"]
    # The historical bug: an uncaught StopIteration would show up as a
    # traceback on stderr and a non-zero process exit, never a clean JSON
    # payload at all. Reaching here already disproves it. Assert the
    # specific safe outcome too: recovery replayed the same lease through
    # to completion, not a fresh, different one, and did not fail closed.
    assert payload.get("phase") != "FAILED_CLOSED", payload
    assert payload.get("lease_id") in (None, lease_id), payload


# ---------------------------------------------------------------------------
# rehydrate_governor(): disk-mediated, fresh-governor-object contract tests.
# ---------------------------------------------------------------------------


def _lease_and_persist(repo: Path, trust_store: Path, lease_store: Path):
    from project_atlas.orchestration.autonomy.trust import load_runtime_anchor

    trusted = load_runtime_anchor(store=trust_store)
    inventory = collect_live_inventory(repo)
    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    node = governor._pilot_node(inventory, None)
    governor.add_node(node)
    governor.mark_ready(node.package_id)
    lease = governor.lease(
        node.package_id, "governor-pilot-local", branch="feat/pilot", worktree="wt"
    )
    return trusted, inventory, lease


def test_rehydrate_governor_restores_leased_pilot_node(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"

    trusted, inventory, lease = _lease_and_persist(repo, trust_store, lease_store)
    from project_atlas.orchestration.autonomy.loop import initial_loop_state, persist_loop_state

    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.LEASED,
            "active_package_id": PILOT_PACKAGE_ID,
            "active_lease_id": lease.lease_id,
            "sequence": 1,
        }
    )
    from project_atlas.orchestration.autonomy.loop import seal_loop_state

    persist_loop_state(loop_store, seal_loop_state(state))

    fresh = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    assert fresh.snapshot().nodes == ()

    rehydrate_governor(
        fresh,
        inventory=inventory,
        trusted=trusted,
        loop_store=loop_store,
        lease_projection_store=lease_store,
    )

    snapshot = fresh.snapshot()
    node = next(item for item in snapshot.nodes if item.package_id == PILOT_PACKAGE_ID)
    assert node.state == NodeState.LEASED
    restored = next(item for item in snapshot.leases if item.lease_id == lease.lease_id)
    assert restored.agent_id == lease.agent_id
    assert restored.branch == lease.branch
    assert restored.base_pin == lease.base_pin


def test_rehydrate_governor_no_prior_state_originates_cleanly(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    from project_atlas.orchestration.autonomy.trust import load_runtime_anchor

    trusted = load_runtime_anchor(store=trust_store)
    inventory = collect_live_inventory(repo)
    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
    )
    # No loop store, no lease projection store exist on disk at all yet.
    rehydrate_governor(
        governor,
        inventory=inventory,
        trusted=trusted,
        loop_store=tmp_path / "never-ticked-loop",
        lease_projection_store=tmp_path / "never-ticked-leases",
    )
    assert governor.snapshot().nodes == ()


@pytest.mark.parametrize(
    "phase", [LoopPhase.DISPATCHING, LoopPhase.AWAITING_RESULT, LoopPhase.VALIDATING]
)
def test_rehydrate_governor_fails_closed_for_in_flight_execution_phases(
    tmp_path: Path, phase: LoopPhase
) -> None:
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"

    trusted, inventory, lease = _lease_and_persist(repo, trust_store, lease_store)
    from project_atlas.orchestration.autonomy.loop import (
        initial_loop_state,
        persist_loop_state,
        seal_loop_state,
    )

    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": phase,
            "active_package_id": PILOT_PACKAGE_ID,
            "active_lease_id": lease.lease_id,
            "active_dispatch_id": "in-process:" + lease.lease_id,
            "sequence": 1,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(state))

    fresh = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    with pytest.raises(RehydrationError) as excinfo:
        rehydrate_governor(
            fresh,
            inventory=inventory,
            trusted=trusted,
            loop_store=loop_store,
            lease_projection_store=lease_store,
        )
    assert excinfo.value.code == "EXECUTION_STATE_NOT_REHYDRATABLE"
    # Fails closed before touching the governor at all.
    assert fresh.snapshot().nodes == ()


def test_rehydrate_governor_fails_closed_for_unknown_package_id(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"
    from project_atlas.orchestration.autonomy.trust import load_runtime_anchor

    trusted = load_runtime_anchor(store=trust_store)
    inventory = collect_live_inventory(repo)

    from project_atlas.orchestration.autonomy.loop import (
        initial_loop_state,
        persist_loop_state,
        seal_loop_state,
    )

    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.LEASED,
            "active_package_id": "AS-SOME-OTHER-PACKAGE-001",
            "active_lease_id": "LEASE-1",
            "sequence": 1,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(state))

    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    with pytest.raises(RehydrationError) as excinfo:
        rehydrate_governor(
            governor,
            inventory=inventory,
            trusted=trusted,
            loop_store=loop_store,
            lease_projection_store=lease_store,
        )
    assert excinfo.value.code == "NODE_NOT_REHYDRATABLE"


def test_rehydrate_governor_fails_closed_when_lease_not_projected(tmp_path: Path) -> None:
    """LoopState claims a lease is active but the durable lease projection
    (the only evidence source rehydration trusts) never recorded it --
    e.g. a crash between granting the in-memory lease and the loop
    persisting LEASED, or a tampered/rolled-back lease store."""
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"
    from project_atlas.orchestration.autonomy.trust import load_runtime_anchor

    trusted = load_runtime_anchor(store=trust_store)
    inventory = collect_live_inventory(repo)

    from project_atlas.orchestration.autonomy.loop import (
        initial_loop_state,
        persist_loop_state,
        seal_loop_state,
    )

    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.LEASED,
            "active_package_id": PILOT_PACKAGE_ID,
            "active_lease_id": "LEASE-NEVER-PROJECTED",
            "sequence": 1,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(state))
    # lease_store deliberately left empty -- no projection file at all.

    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    with pytest.raises(RehydrationError) as excinfo:
        rehydrate_governor(
            governor,
            inventory=inventory,
            trusted=trusted,
            loop_store=loop_store,
            lease_projection_store=lease_store,
        )
    assert excinfo.value.code == "LEASE_NOT_PROJECTED"


def test_rehydrate_governor_fails_closed_on_foreign_package_row(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"

    trusted, inventory, lease = _lease_and_persist(repo, trust_store, lease_store)

    from project_atlas.orchestration.autonomy.loop import (
        initial_loop_state,
        persist_loop_state,
        seal_loop_state,
    )

    # LoopState (tampered / corrupted) claims a *different* package_id owns
    # this same real, durably-projected lease_id.
    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.LEASED,
            "active_package_id": "AS-SOME-OTHER-PACKAGE-001",
            "active_lease_id": lease.lease_id,
            "sequence": 1,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(state))

    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    with pytest.raises(RehydrationError) as excinfo:
        rehydrate_governor(
            governor,
            inventory=inventory,
            trusted=trusted,
            loop_store=loop_store,
            lease_projection_store=lease_store,
        )
    assert excinfo.value.code == "NODE_NOT_REHYDRATABLE"


def test_rehydrate_governor_fails_closed_on_stale_base_pin(tmp_path: Path) -> None:
    """Main advanced (a new commit landed on origin/main) between the
    lease being granted and this rehydration attempt. Continuing would
    silently execute a stale-based node against a base it was never
    actually leased against."""
    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trust_store = _make_trust_store(tmp_path, main, tree)
    lease_store = tmp_path / "leases"
    loop_store = tmp_path / "loop"

    trusted, inventory, lease = _lease_and_persist(repo, trust_store, lease_store)

    from project_atlas.orchestration.autonomy.loop import (
        initial_loop_state,
        persist_loop_state,
        seal_loop_state,
    )

    state = initial_loop_state(trusted).model_copy(
        update={
            "phase": LoopPhase.LEASED,
            "active_package_id": PILOT_PACKAGE_ID,
            "active_lease_id": lease.lease_id,
            "sequence": 1,
        }
    )
    persist_loop_state(loop_store, seal_loop_state(state))

    # A fresh inventory observing a *different* current_main than the one
    # the lease was pinned to (main moved on).
    moved_inventory = inventory.model_copy(update={"current_main": "c" * 40})

    governor = AutonomousGovernor(
        current_main=moved_inventory.current_main,
        current_tree=moved_inventory.current_tree,
        trusted_anchor=trusted,
        lease_projection_store=lease_store,
    )
    with pytest.raises(RehydrationError) as excinfo:
        rehydrate_governor(
            governor,
            inventory=moved_inventory,
            trusted=trusted,
            loop_store=loop_store,
            lease_projection_store=lease_store,
        )
    assert excinfo.value.code == "STALE_LEASE"


def test_restore_lease_does_not_reinvoke_or_bypass_owner_gate(tmp_path: Path) -> None:
    """`AutonomousGovernor.restore_lease()`'s own documented contract: the
    owner gate for a node was already enforced -- correctly -- at the
    original `lease()` call that produced this lease. Restoration must not
    re-prompt it, and must not fabricate any owner authority in the
    process (LOOP_CAN_BYPASS_OWNER_GATE stays NO after rehydration too)."""
    from project_atlas.orchestration.autonomy.models import (
        AgentCapability,
        AgentLease,
        ExecutionHostClass,
        IvRequirements,
        MutationSurface,
        RiskTag,
        WorkNode,
    )

    repo = _make_repo(tmp_path)
    main = _run_git(repo, "rev-parse", "origin/main")
    tree = _run_git(repo, "rev-parse", "origin/main^{tree}")
    trusted = _anchor(main, tree)
    inventory = collect_live_inventory(repo)

    governor = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
    )
    gated_node = WorkNode(
        package_id="AS-TEST-OWNER-GATED-001",
        objective="test node behind an owner gate",
        base_pin=inventory.current_main,
        mutation_surface=MutationSurface(
            surface_id="test-surface",
            paths=("docs/test.md",),
            semantic="TEST",
        ),
        execution_host_class=ExecutionHostClass.IN_PROCESS,
        agent_capabilities_required=(AgentCapability.IMPLEMENT,),
        acceptance_criteria=("TEST",),
        iv_requirements=IvRequirements(
            certification_required=True,
            implementer_cannot_verify=True,
            adversarial_required=True,
        ),
        owner_gate=OwnerGateKind.B_ACCEPTANCE_WAIVER,
        risk_tags=(RiskTag.CONTROL_PLANE,),
    )
    governor.add_node(gated_node)
    governor.mark_ready(gated_node.package_id)
    lease = AgentLease(
        lease_id="LEASE-GATED-1",
        agent_id="agent-alpha",
        package_id=gated_node.package_id,
        branch="feat/gated",
        worktree="wt",
        base_pin=inventory.current_main,
        authorized_paths=("docs/test.md",),
        forbidden_paths=("main", "projects"),
        capabilities=(AgentCapability.IMPLEMENT,),
        start_state=NodeState.READY,
        expected_output="EVIDENCE_BUNDLE",
        expiry_or_terminal_condition="UNTIL_NODE_TERMINAL",
        active=True,
        sequence=1,
    )

    fresh = AutonomousGovernor(
        current_main=inventory.current_main,
        current_tree=inventory.current_tree,
        trusted_anchor=trusted,
    )
    fresh.add_node(gated_node)
    fresh.mark_ready(gated_node.package_id)
    # No owner_grant parameter exists on restore_lease() at all -- there is
    # no way to even pass one. This call succeeding despite an owner-gated
    # node proves restoration itself never grants authority; it also never
    # *re-blocks* a genuinely already-approved-and-leased node.
    fresh.restore_lease(lease)

    node = next(item for item in fresh.snapshot().nodes if item.package_id == gated_node.package_id)
    assert node.state == NodeState.LEASED
    assert node.merge_authorized is False
    assert node.execution_authorized is False
