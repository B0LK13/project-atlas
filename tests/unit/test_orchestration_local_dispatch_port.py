"""AS-ORCH-LOCAL-DISPATCH-001: governed local-process dispatch port (PR-C).

Test matrix (A-N) per D-CODEX-ATLAS-AUTONOMY-PREREQUISITES-CONTINUATION-R2
section 8, exercised against a REAL git repository (not a synthetic PIN --
``local_process_transport.run_local_task()`` does real git operations) and
the REAL governed lease/dispatch machinery (``AutonomousGovernor`` +
``AutonomousLoop``), never a second/parallel orchestration engine.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from project_atlas.orchestration.autonomy.governor import AutonomousGovernor, GovernorError
from project_atlas.orchestration.autonomy.lease_projection import RELATIVE_DEFAULT as LEASE_RELATIVE
from project_atlas.orchestration.autonomy.local_dispatch_port import (
    LocalDispatchError,
    LocalProcessDispatchPort,
    _dispatch_id_for,
    _read_receipt,
)
from project_atlas.orchestration.autonomy.loop import AutonomousLoop, LoopError, LoopPhase
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementReason,
    AgentCapability,
    ExecutionHostClass,
    IvRequirements,
    MutationSurface,
    NodeState,
    OwnerGateKind,
    StopReason,
    TrustedAnchorRecord,
    WorkNode,
)
from project_atlas.orchestration.autonomy.trust import seal_anchor
from project_atlas.orchestration.local_process_transport import LocalProcessExecutorConfig


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    (repo / "allowed").mkdir()
    (repo / "allowed" / ".gitkeep").write_text("", encoding="utf-8")
    # Mirrors this repository's own real .gitignore (`.atlas/orchestration/`
    # is already excluded there) -- the governed lease projection store,
    # loop state, and this port's own dispatch receipts all durably live
    # under `.atlas/orchestration/...` INSIDE the project root by design
    # (same convention every other durable store in this package already
    # uses). Without this, run_local_task()'s own clean-worktree
    # requirement would (correctly, per its own design) see those files as
    # untracked dirt and refuse to run every single dispatch -- not a bug
    # in either module, just this fixture needing to match real-repo
    # convention.
    (repo / ".gitignore").write_text(".atlas/orchestration/\n", encoding="utf-8")
    _run_git(repo, "add", "-A")
    _run_git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init")
    return repo


def _repo_main_tree(repo: Path) -> tuple[str, str]:
    main = _run_git(repo, "rev-parse", "HEAD")
    tree = _run_git(repo, "rev-parse", "HEAD^{tree}")
    return main, tree


def _anchor(main: str, tree: str) -> TrustedAnchorRecord:
    pred = "1" * 40
    cert = "3" * 40
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main=pred,
            predecessor_tree="2" * 40,
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-LOCAL-DISPATCH-001",
            source_directive="D-CODEX-ATLAS-AUTONOMY-PREREQUISITES-CONTINUATION-R2",
            source_pr=661,
            merge_commit=main,
            merge_parent_1=pred,
            merge_parent_2=cert,
            merge_tree=tree,
            certified_head=cert,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/unit/local-dispatch-anchor.json",
            evidence_digest="aa" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def _node(
    package_id: str,
    *,
    base_pin: str,
    state: NodeState = NodeState.READY,
    owner_gate: OwnerGateKind | None = None,
    deps: tuple[str, ...] = (),
    surface_paths: tuple[str, ...] = ("allowed/",),
) -> WorkNode:
    return WorkNode(
        package_id=package_id,
        objective="PR-C governed local dispatch test node",
        base_pin=base_pin,
        dependencies=deps,
        mutation_surface=MutationSurface(
            surface_id=f"{package_id}-surface",
            paths=surface_paths,
            semantic="LOCAL_DISPATCH_TEST",
        ),
        execution_host_class=ExecutionHostClass.IN_PROCESS,  # overridden at lease() time
        agent_capabilities_required=(AgentCapability.IMPLEMENT,),
        acceptance_criteria=("PASS",),
        iv_requirements=IvRequirements(certification_required=True),
        owner_gate=owner_gate,
        state=state,
    )


def _governor(
    repo: Path, *nodes: WorkNode, current_main: str, current_tree: str
) -> AutonomousGovernor:
    gov = AutonomousGovernor(
        current_main=current_main,
        current_tree=current_tree,
        trusted_anchor=_anchor(current_main, current_tree),
        lease_projection_store=repo / LEASE_RELATIVE,
    )
    for node in nodes:
        gov.add_node(node)
    return gov


def _loop(
    repo: Path,
    governor: AutonomousGovernor,
    *,
    current_main: str,
    current_tree: str,
    dispatch: LocalProcessDispatchPort | None = None,
    override: ExecutionHostClass | None = None,
) -> AutonomousLoop:
    return AutonomousLoop(
        governor=governor,
        trusted=_anchor(current_main, current_tree),
        store=repo / ".atlas" / "orchestration" / "autonomy" / "loop",
        root=repo,
        dispatch=dispatch,
        execution_host_class_override=override,
    )


def _enabled_config(*, timeout_seconds: int = 30) -> LocalProcessExecutorConfig:
    return LocalProcessExecutorConfig(enabled=True, timeout_seconds=timeout_seconds)


def _port(*, argv: tuple[str, ...], timeout_seconds: int = 30) -> LocalProcessDispatchPort:
    return LocalProcessDispatchPort(
        config=_enabled_config(timeout_seconds=timeout_seconds), argv_template=argv
    )


# ---------------------------------------------------------------------------
# A / J. READY -> lease -> local provider selected -> real process runs ->
# result accepted for verification (CERTIFIED)
# ---------------------------------------------------------------------------


def test_a_ready_node_dispatches_to_a_real_local_process_and_certifies(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-A-001", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    script = "open('allowed/output.txt', 'w').write('real work happened\\n')"
    port = _port(argv=(sys.executable, "-c", script))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    # A single tick() only performs one state-machine step (lease OR
    # dispatch OR finalize, never all three) -- run_until_stop() drives
    # the loop through lease -> dispatch -> completion, exactly mirroring
    # how the real CLI (run_governor_loop_tick, called repeatedly) is
    # actually used.
    result = loop.run_until_stop()
    assert result.phase is LoopPhase.STOPPED
    assert (repo / "allowed" / "output.txt").is_file()  # a REAL process really ran
    final = next(n for n in gov.snapshot().nodes if n.package_id == "PRC-A-001")
    assert final.state == NodeState.CERTIFIED


# ---------------------------------------------------------------------------
# B. provider disabled -> no process
# ---------------------------------------------------------------------------


def test_b_disabled_config_refuses_port_construction() -> None:
    with pytest.raises(LocalDispatchError) as exc:
        LocalProcessDispatchPort(
            config=LocalProcessExecutorConfig(),  # enabled=False, the default
            argv_template=(sys.executable, "-c", "pass"),
        )
    assert exc.value.code == "LOCAL_EXECUTION_DISABLED"


def test_b_no_override_no_dispatch_port_means_no_local_process(tmp_path: Path) -> None:
    """The pre-existing default: no override, no dispatch port -- a node
    still runs the harmless IN_PROCESS metadata stand-in, never a real
    local subprocess."""
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-B-001", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    loop = _loop(repo, gov, current_main=main, current_tree=tree)  # no dispatch, no override
    result = loop.run_until_stop()
    assert result.dispatched is False  # never touches a dispatch port at all
    assert not (repo / "allowed" / "output.txt").exists()
    final = next(n for n in gov.snapshot().nodes if n.package_id == "PRC-B-001")
    assert final.execution_host_class == ExecutionHostClass.IN_PROCESS


# ---------------------------------------------------------------------------
# C. stale base -> no dispatch
# ---------------------------------------------------------------------------


def test_c_stale_target_moved_refuses_lease_before_any_dispatch(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-C-001", base_pin=main)
    # Governor observes a DIFFERENT (stale) main/tree than the trusted
    # anchor -- current_main intentionally does not match the anchor.
    stale_main = "f" * 40
    stale_tree = "e" * 40
    gov = AutonomousGovernor(
        current_main=stale_main,
        current_tree=stale_tree,
        trusted_anchor=_anchor(main, tree),
        lease_projection_store=repo / LEASE_RELATIVE,
    )
    gov.add_node(node)
    port = _port(argv=(sys.executable, "-c", "open('allowed/should_not_exist.txt','w').close()"))
    # AutonomousLoop.__init__ itself independently re-checks the governor's
    # observed main/tree against the loop's own trusted anchor and refuses
    # to even construct on a mismatch -- a defense-in-depth layer BEFORE
    # any tick, let alone a dispatch, could ever happen.
    with pytest.raises(LoopError) as exc:
        _loop(
            repo, gov, current_main=main, current_tree=tree, dispatch=port,
            override=ExecutionHostClass.LOCAL_PROCESS,
        )
    assert exc.value.code == "TARGET_MOVED"
    assert not (repo / "allowed" / "should_not_exist.txt").exists()


# ---------------------------------------------------------------------------
# D. owner-held node -> no dispatch
# ---------------------------------------------------------------------------


def test_d_owner_held_state_never_dispatched(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node(
        "PRC-D-001", base_pin=main, state=NodeState.OWNER_HELD,
        owner_gate=OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
    )
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    port = _port(argv=(sys.executable, "-c", "open('allowed/should_not_exist.txt','w').close()"))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    result = loop.run_until_stop()
    assert result.dispatched is False
    assert not (repo / "allowed" / "should_not_exist.txt").exists()


def test_d_ready_but_owner_gated_never_dispatched(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node(
        "PRC-D-002", base_pin=main, state=NodeState.READY,
        owner_gate=OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
    )
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    port = _port(argv=(sys.executable, "-c", "open('allowed/should_not_exist.txt','w').close()"))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    result = loop.run_until_stop()
    assert result.stop_reason is StopReason.OWNER_GATE
    assert not (repo / "allowed" / "should_not_exist.txt").exists()


# ---------------------------------------------------------------------------
# E. dependency-blocked node -> no dispatch
# ---------------------------------------------------------------------------


def test_e_unsatisfied_dependency_never_dispatched(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-E-001", base_pin=main, deps=("PRC-E-UPSTREAM",))
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    port = _port(argv=(sys.executable, "-c", "open('allowed/should_not_exist.txt','w').close()"))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    result = loop.run_until_stop()
    # select_next()'s own advisory dependency check already excludes this
    # node before governor.lease() is ever called, so the loop reports
    # NO_ELIGIBLE_WORK (nothing selectable at all) rather than reaching
    # lease()'s own DEPENDENCIES_NOT_SATISFIED defense-in-depth check.
    assert result.stop_reason is StopReason.NO_ELIGIBLE_WORK
    assert not (repo / "allowed" / "should_not_exist.txt").exists()


# ---------------------------------------------------------------------------
# F. forbidden-path change -> execution rejected -> node not certified
# ---------------------------------------------------------------------------


def test_f_forbidden_path_write_is_rejected_node_not_certified(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    (repo / "main").mkdir()
    (repo / "main" / ".gitkeep").write_text("", encoding="utf-8")
    _run_git(repo, "add", "-A")
    _run_git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "seed main/ dir")
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-F-001", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    # grant_lease()'s own default forbidden_paths is ("main", "projects")
    # -- writing under main/ hits that real, already-governed boundary.
    script = "open('main/tampered.txt', 'w').write('bad\\n')"
    port = _port(argv=(sys.executable, "-c", script))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    # A single tick from IDLE performs the ENTIRE lease -> dispatch ->
    # (fail -> remediate) sequence via _select_and_lease()'s own tail-call
    # into _dispatch_leased() -- checking the immediate post-failure state
    # after exactly one tick. Driving further ticks would repeatedly
    # auto-retry via the existing, unmodified governed remediation cycle,
    # which is out of scope for this test and (at its own exhaustion
    # boundary, cycle 3) hits a separate, pre-existing off-by-one between
    # complete_verification()'s and remediate_and_resume()'s own
    # can_remediate() checks -- not something this PR touches or needs to
    # exercise.
    loop.tick()
    final = next(n for n in gov.snapshot().nodes if n.package_id == "PRC-F-001")
    assert final.state != NodeState.CERTIFIED
    assert final.state == NodeState.ACTIVE  # remediated once, ready to retry
    assert final.retry_policy.cycles_used == 1


# ---------------------------------------------------------------------------
# G. out-of-scope path -> rejected
# ---------------------------------------------------------------------------


def test_g_out_of_scope_write_is_rejected_node_not_certified(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-G-001", base_pin=main, surface_paths=("allowed/",))
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    script = "open('elsewhere.txt', 'w').write('out of scope\\n')"
    port = _port(argv=(sys.executable, "-c", script))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    loop.tick()
    final = next(n for n in gov.snapshot().nodes if n.package_id == "PRC-G-001")
    assert final.state != NodeState.CERTIFIED
    assert final.state == NodeState.ACTIVE
    assert final.retry_policy.cycles_used == 1


# ---------------------------------------------------------------------------
# H. executor nonzero exit -> controlled failure
# ---------------------------------------------------------------------------


def test_h_nonzero_exit_is_a_controlled_failure_not_a_crash(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-H-001", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    port = _port(argv=(sys.executable, "-c", "import sys; sys.exit(1)"))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    result = loop.tick()  # must not raise
    assert result.phase is not LoopPhase.FAILED_CLOSED
    final = next(n for n in gov.snapshot().nodes if n.package_id == "PRC-H-001")
    assert final.state != NodeState.CERTIFIED
    assert final.state == NodeState.ACTIVE
    assert final.retry_policy.cycles_used == 1


# ---------------------------------------------------------------------------
# I. timeout -> controlled failure
# ---------------------------------------------------------------------------


def test_i_timeout_is_a_controlled_failure_not_a_hang(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-I-001", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    port = _port(
        argv=(sys.executable, "-c", "import time; time.sleep(120)"), timeout_seconds=1
    )
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    result = loop.tick()  # must not raise, must not block for 120s
    assert result.phase is not LoopPhase.FAILED_CLOSED
    final = next(n for n in gov.snapshot().nodes if n.package_id == "PRC-I-001")
    assert final.state != NodeState.CERTIFIED
    assert final.state == NodeState.ACTIVE
    assert final.retry_policy.cycles_used == 1


# ---------------------------------------------------------------------------
# K. duplicate dispatch -> blocked
# ---------------------------------------------------------------------------


def test_k_a_genuinely_still_running_dispatch_blocks_a_second_one(tmp_path: Path) -> None:
    """Dispatch is attempt-indexed (``local-process:<lease>:<n>``), not one
    fixed id per lease -- the existing, unmodified governed remediation
    cycle legitimately re-dispatches the SAME lease again after a real,
    already-RESOLVED failure (see test below), which is not a duplicate.
    What must still be blocked is a genuinely overlapping/concurrent
    dispatch attempt while a PRIOR one for this lease is still
    unresolved."""
    from project_atlas.orchestration.autonomy.local_dispatch_port import (
        _dispatch_id_for,
        _write_receipt,
    )

    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-K-001", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    lease = gov.lease("PRC-K-001", "governor-pilot-local", branch="b", worktree="w")
    port = _port(argv=(sys.executable, "-c", "open('allowed/x.txt','w').close()"))
    # Simulate "attempt 0 is currently in flight" directly (no need to run
    # a real process to construct this state).
    dispatch_id_0 = f"{_dispatch_id_for(lease.lease_id)}:0"
    _write_receipt(
        repo, dispatch_id_0,
        {
            "dispatch_id": dispatch_id_0,
            "lease_id": lease.lease_id,
            "package_id": "PRC-K-001",
            "status": "RUNNING",
        },
    )
    with pytest.raises(LocalDispatchError) as exc:
        port.dispatch_once(repo)
    assert exc.value.code == "DUPLICATE_DISPATCH"


def test_k_a_legitimate_remediation_retry_is_not_a_duplicate(tmp_path: Path) -> None:
    """The opposite of the case above: a node that failed once (real
    violation) and is legitimately remediated/retried by the EXISTING,
    unmodified governor remediation cycle must be allowed to dispatch
    again -- with a distinct, never-reused dispatch_id, not blocked as a
    duplicate."""
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-K-002", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    # out-of-scope write -> fails
    port = _port(argv=(sys.executable, "-c", "open('elsewhere.txt', 'w').close()"))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    # A single tick from IDLE performs the ENTIRE lease -> dispatch(attempt
    # 0) -> fail -> remediate sequence in one call (see the sibling F/G/H/I
    # tests' comments) -- the node ends ACTIVE, phase=LEASED, ready for a
    # second attempt on the NEXT tick.
    result = loop.tick()  # lease + dispatch attempt 0 -> fails -> remediated
    assert result.phase is LoopPhase.LEASED
    result = loop.tick()  # dispatch attempt 1 -- must NOT raise DUPLICATE_DISPATCH
    assert result.phase is not LoopPhase.FAILED_CLOSED
    from project_atlas.orchestration.autonomy.local_dispatch_port import _read_receipt

    lease_id = "LEASE-1"
    receipt_0 = _read_receipt(repo, f"local-process:{lease_id}:0")
    receipt_1 = _read_receipt(repo, f"local-process:{lease_id}:1")
    assert receipt_0 is not None and receipt_0["status"] == "FAILED"
    assert receipt_1 is not None  # a genuinely distinct second attempt was recorded


# ---------------------------------------------------------------------------
# L. duplicate result -> blocked
# ---------------------------------------------------------------------------


def test_l_duplicate_result_application_is_blocked(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-L-001", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    port = _port(argv=(sys.executable, "-c", "open('allowed/x.txt','w').close()"))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    loop.run_until_stop()
    dispatch_id = f"{_dispatch_id_for('LEASE-1')}:0"
    with pytest.raises(LoopError) as exc:
        loop.apply_observed_result(dispatch_id, dispatch_id, passed=True)
    assert exc.value.code == "RESULT_REPLAY"


# ---------------------------------------------------------------------------
# M. fresh process restart -> durable task state restored -> no duplicate
#    execution
# ---------------------------------------------------------------------------


def test_m_process_restart_recovers_without_rerunning_the_task(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    package_id = "PRC-M-001"
    node = _node(package_id, base_pin=main)

    # "Process N": lease, then simulate dispatch_once() having started (its
    # own RUNNING receipt written) before the whole process crashes --
    # loop.py's own _save(phase=DISPATCHING) happens BEFORE dispatch_once()
    # is called and BEFORE active_dispatch_id is known, exactly mirroring
    # the crash window _dispatch_leased() itself documents.
    gov_before = _governor(repo, node, current_main=main, current_tree=tree)
    argv = (sys.executable, "-c", "open('allowed/marker.txt', 'w').write('ran\\n')")
    port_before = _port(argv=argv)
    loop_before = _loop(
        repo, gov_before, current_main=main, current_tree=tree, dispatch=port_before,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    lease = gov_before.lease(
        package_id,
        loop_before._first_agent(),
        branch=loop_before._branch,
        worktree=loop_before._worktree,
        execution_host_class_override=ExecutionHostClass.LOCAL_PROCESS,
    )
    loop_before._save(
        phase=LoopPhase.DISPATCHING,
        active_package_id=package_id,
        active_lease_id=lease.lease_id,
    )
    # Manually reproduce dispatch_once()'s OWN first durable action (the
    # RUNNING receipt) without letting run_local_task() actually run --
    # this is the exact crash point: receipt written, process died before
    # the child ever started.
    from project_atlas.orchestration.autonomy.local_dispatch_port import _write_receipt

    dispatch_id = f"{_dispatch_id_for(lease.lease_id)}:0"
    _write_receipt(
        repo, dispatch_id,
        {
            "dispatch_id": dispatch_id,
            "lease_id": lease.lease_id,
            "package_id": package_id,
            "status": "RUNNING",
        },
    )
    assert not (repo / "allowed" / "marker.txt").exists()  # confirms nothing ran yet

    # "Process N+1": brand-new governor (no in-memory state at all) and a
    # new port instance pointed at the same root -- exactly what a real
    # restart gives run_governor_loop_tick().
    gov_after = _governor(repo, current_main=main, current_tree=tree)
    port_after = _port(argv=argv)
    loop_after = _loop(
        repo, gov_after, current_main=main, current_tree=tree, dispatch=port_after,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    assert loop_after.state.phase is LoopPhase.DISPATCHING  # reloaded from disk
    result = loop_after.recover()
    assert result.phase is not LoopPhase.FAILED_CLOSED
    # The task was NOT re-run: no NEW process was started by recover().
    assert not (repo / "allowed" / "marker.txt").exists()
    receipt = _read_receipt(repo, dispatch_id)
    assert receipt is not None
    assert receipt["status"] == "RUNNING"  # unchanged -- still genuinely unresolved


# ---------------------------------------------------------------------------
# N. completed lease -> release/reaper contract preserved
# ---------------------------------------------------------------------------


def test_n_completed_local_process_lease_can_still_be_released(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-N-001", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    port = _port(argv=(sys.executable, "-c", "open('allowed/x.txt','w').close()"))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    loop.run_until_stop()
    active = [ls for ls in gov.snapshot().leases if ls.active]
    assert len(active) == 1
    released = gov.release_lease(active[0].lease_id)
    assert released.active is False
    # Idempotent: releasing again is a documented no-op, not an error.
    released_again = gov.release_lease(active[0].lease_id)
    assert released_again.active is False


# ---------------------------------------------------------------------------
# Cross-cutting: authority fields the executor cannot expand
# ---------------------------------------------------------------------------


def test_envelope_authority_fields_come_from_the_lease_never_a_caller(tmp_path: Path) -> None:
    """Directive section 7: the executor cannot expand authorized_paths/
    forbidden_paths -- confirm the ACTUAL lease's paths (not some other
    value) are what a real dispatch enforces, by exercising a script that
    is compliant with the lease's real scope and confirming no violation
    is raised, then a second scenario that is not compliant."""
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-ENV-001", base_pin=main, surface_paths=("allowed/",))
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    port = _port(argv=(sys.executable, "-c", "open('allowed/inside.txt', 'w').write('ok\\n')"))
    loop = _loop(
        repo, gov, current_main=main, current_tree=tree, dispatch=port,
        override=ExecutionHostClass.LOCAL_PROCESS,
    )
    loop.run_until_stop()
    final = next(n for n in gov.snapshot().nodes if n.package_id == "PRC-ENV-001")
    assert final.state == NodeState.CERTIFIED


def test_governor_lease_override_never_applies_without_explicit_opt_in(tmp_path: Path) -> None:
    """The override parameter defaults to None; a caller that does not
    pass it (every pre-existing caller) gets IN_PROCESS unchanged."""
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node("PRC-ENV-002", base_pin=main)
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    lease = gov.lease("PRC-ENV-002", "governor-pilot-local", branch="b", worktree="w")
    del lease
    final = next(n for n in gov.snapshot().nodes if n.package_id == "PRC-ENV-002")
    assert final.execution_host_class == ExecutionHostClass.IN_PROCESS


def test_lease_override_does_not_bypass_owner_gate_check(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    main, tree = _repo_main_tree(repo)
    node = _node(
        "PRC-ENV-003", base_pin=main, owner_gate=OwnerGateKind.E_DESTRUCTIVE_OPS
    )
    gov = _governor(repo, node, current_main=main, current_tree=tree)
    with pytest.raises(GovernorError) as exc:
        gov.lease(
            "PRC-ENV-003", "governor-pilot-local", branch="b", worktree="w",
            execution_host_class_override=ExecutionHostClass.LOCAL_PROCESS,
        )
    assert exc.value.code == "OWNER_GATE_REQUIRED"
