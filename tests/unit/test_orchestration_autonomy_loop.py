"""AS-ORCH-001E persistent loop matrices and adversarial cases."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.autonomy.continuation_broker import (
    SuccessorKind,
    recover_broker,
)
from project_atlas.orchestration.autonomy.evidence import hash_payload
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.loop import (
    LOOP_PACKAGE_ID,
    MAX_TICKS_PER_INVOCATION,
    AutonomousLoop,
    CallableDispatchPort,
    LoopError,
    LoopPhase,
    LoopState,
    initial_loop_state,
    load_loop_state,
    persist_loop_state,
    seal_loop_state,
    verify_loop_state,
)
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    AdvancementReason,
    AgentCapability,
    ExecutionHostClass,
    IvRequirements,
    MutationSurface,
    NodeState,
    OwnerGateKind,
    RiskTag,
    StopReason,
    TrustedAnchorRecord,
    WorkNode,
)
from project_atlas.orchestration.autonomy.owner_gates import OwnerGateError
from project_atlas.orchestration.autonomy.trust import seal_anchor
from project_atlas.schema import available_schemas, validate_record

PIN = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
TREE = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _anchor() -> TrustedAnchorRecord:
    pred = "1111111111111111111111111111111111111111"
    cert = "3333333333333333333333333333333333333333"
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=PIN,
            trusted_tree=TREE,
            predecessor_main=pred,
            predecessor_tree="2222222222222222222222222222222222222222",
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-001D",
            source_directive="D-AS-ORCH-001D-OWNER-MERGE-010",
            source_pr=400,
            merge_commit=PIN,
            merge_parent_1=pred,
            merge_parent_2=cert,
            merge_tree=TREE,
            certified_head=cert,
            certified_tree=TREE,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/unit/loop-anchor.json",
            evidence_digest="aa" * 32,
            sequence=3,
            record_digest="00" * 32,
        )
    )


def _node(
    package_id: str,
    *,
    state: NodeState = NodeState.READY,
    host: ExecutionHostClass = ExecutionHostClass.IN_PROCESS,
    owner_gate: OwnerGateKind | None = None,
    deps: tuple[str, ...] = (),
    surface: str = "loop-surface",
) -> WorkNode:
    return WorkNode(
        package_id=package_id,
        objective="001e test node",
        base_pin=PIN,
        dependencies=deps,
        mutation_surface=MutationSurface(
            surface_id=surface,
            paths=("src/project_atlas/orchestration/autonomy",),
            semantic="ORCHESTRATION_AUTONOMY_LOOP",
        ),
        execution_host_class=host,
        agent_capabilities_required=(AgentCapability.IMPLEMENT,),
        acceptance_criteria=("PASS",),
        iv_requirements=IvRequirements(certification_required=True, adversarial_required=True),
        owner_gate=owner_gate,
        state=state,
        risk_tags=(RiskTag.CONTROL_PLANE, RiskTag.HIGH_BLAST_RADIUS),
    )


def _governor(*nodes: WorkNode) -> AutonomousGovernor:
    gov = AutonomousGovernor(current_main=PIN, current_tree=TREE, trusted_anchor=_anchor())
    for node in nodes:
        gov.add_node(node)
    return gov


def _loop(
    tmp_path: Path,
    governor: AutonomousGovernor,
    dispatch: CallableDispatchPort | None = None,
) -> AutonomousLoop:
    return AutonomousLoop(
        governor=governor,
        trusted=_anchor(),
        store=tmp_path / "loop-store",
        root=tmp_path,
        dispatch=dispatch,
    )


def test_schema_registered() -> None:
    assert "autonomy-loop-state" in available_schemas()
    validate_record(initial_loop_state(_anchor()).model_dump(mode="json"), "autonomy-loop-state")


def test_in_process_ready_completes_and_stops_without_owner(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-NEXT-001"))
    loop = _loop(tmp_path, gov)
    result = loop.run_until_stop()
    assert result.phase is LoopPhase.STOPPED
    assert result.stop_reason is StopReason.NO_ELIGIBLE_WORK
    assert result.merge_authorized is False
    assert result.authority_granted is False
    node = next(item for item in gov.snapshot().nodes if item.package_id == "AS-ORCH-NEXT-001")
    assert node.state in {NodeState.CERTIFIED, NodeState.OWNER_HELD, NodeState.CLOSED}


def test_in_process_recovery_after_crash_before_apply_observed_result(
    tmp_path: Path,
) -> None:
    """Pre-existing recovery defect (found during PR #635 independent IV,
    confirmed pre-existing via a control test, not introduced by that PR):
    a crash between `governor.execute_leased()` succeeding (node -> ACTIVE)
    and `apply_observed_result()` running (which is what would move the
    loop's own phase away from LEASED) leaves the loop's persisted state at
    `phase=LEASED` with a node that is no longer `LEASED`. On restart,
    `recover()`'s LEASED branch used to call `execute_leased()` again
    unconditionally, attempting an illegal `ACTIVE -> ACTIVE` transition
    that raised `IllegalTransitionError` uncaught -- escaping `cli.py`'s
    handler (which only catches `TrustError`/`DiscoveryError`/`LoopError`)
    and permanently re-crashing on every subsequent tick.
    """
    gov = _governor(_node("AS-ORCH-CRASH-001"))
    loop = _loop(tmp_path, gov)
    # Lease directly through the governor (the same call _select_and_lease()
    # makes) and persist the matching loop state by hand, mirroring exactly
    # what _select_and_lease() itself saves just before calling
    # _dispatch_leased() -- this does not go through the loop's own
    # _select_and_lease()/_dispatch_leased() machinery at all.
    lease = gov.lease(
        "AS-ORCH-CRASH-001", loop._first_agent(), branch=loop._branch, worktree=loop._worktree
    )
    loop._save(
        phase=LoopPhase.LEASED,
        active_package_id="AS-ORCH-CRASH-001",
        active_lease_id=lease.lease_id,
    )
    # Simulate "the crash happened right after execute_leased() succeeded,
    # before apply_observed_result() ran" -- call it directly, exactly what
    # _dispatch_leased()'s IN_PROCESS branch does as its first step, without
    # the loop's own state file ever finding out.
    gov.execute_leased(lease.lease_id)
    node_state = next(
        item for item in gov.snapshot().nodes if item.package_id == "AS-ORCH-CRASH-001"
    ).state
    assert node_state is NodeState.ACTIVE  # confirms the precise crash window
    assert loop.state.phase is LoopPhase.LEASED  # loop is unaware

    # A fresh process would call exactly this on restart.
    result = loop.recover()  # must not raise IllegalTransitionError
    assert result.phase is not LoopPhase.FAILED_CLOSED
    node = next(item for item in gov.snapshot().nodes if item.package_id == "AS-ORCH-CRASH-001")
    assert node.state in {NodeState.CERTIFIED, NodeState.OWNER_HELD, NodeState.CLOSED}


def test_in_process_recovery_fails_closed_on_unexpected_node_state(tmp_path: Path) -> None:
    """Independent-IV finding: `node.state != LEASED` alone does not mean
    "safe to finalize" -- `apply_observed_result()` itself unconditionally
    attempts `transition(..., VERIFYING, ...)`, which is only legal from
    `ACTIVE`. A node in some other unexpected state (e.g. `BLOCKED`) would
    reintroduce an uncaught `IllegalTransitionError` one level down --
    exactly the crash loop this whole fix exists to close. Must fail
    closed with a clear diagnostic instead.
    """
    gov = _governor(_node("AS-ORCH-CRASH-002"))
    loop = _loop(tmp_path, gov)
    lease = gov.lease(
        "AS-ORCH-CRASH-002", loop._first_agent(), branch=loop._branch, worktree=loop._worktree
    )
    loop._save(
        phase=LoopPhase.LEASED,
        active_package_id="AS-ORCH-CRASH-002",
        active_lease_id=lease.lease_id,
    )
    # Force the node into some other, unexpected state (LEASED -> BLOCKED
    # is itself a legal transition, e.g. a concurrent hard-blocker) while
    # the loop's own state still says LEASED.
    gov.transition("AS-ORCH-CRASH-002", NodeState.BLOCKED, "test-unexpected-state")

    with pytest.raises(LoopError) as exc:
        loop.recover()
    assert exc.value.code == "EXECUTION_STATE_CONFLICT"
    assert loop.state.phase is LoopPhase.FAILED_CLOSED
    node = next(item for item in gov.snapshot().nodes if item.package_id == "AS-ORCH-CRASH-002")
    assert node.state is NodeState.BLOCKED  # untouched, not corrupted by a partial transition


def test_owner_gate_stop_no_dispatch(tmp_path: Path) -> None:
    gov = _governor(
        _node(
            "AS-ORCH-OWN-001",
            state=NodeState.OWNER_HELD,
            owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
        )
    )
    calls: list[str] = []
    port = CallableDispatchPort(
        lambda _root: calls.append("dispatch") or {"dispatch_id": "x", "status": "COMPLETED"}
    )
    loop = _loop(tmp_path, gov, port)
    result = loop.run_until_stop()
    assert result.stop_reason is StopReason.OWNER_GATE
    assert calls == []
    assert result.dispatched is False


def test_merge_eligible_never_dispatched(tmp_path: Path) -> None:
    gov = _governor(
        _node(
            "AS-ORCH-MER-001",
            state=NodeState.MERGE_ELIGIBLE,
            owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
        )
    )
    loop = _loop(tmp_path, gov)
    result = loop.run_until_stop()
    assert result.stop_reason is StopReason.OWNER_GATE
    with pytest.raises(OwnerGateError):
        loop.refuse_owner_actions()


def test_refuse_owner_actions_checks_every_gate_not_just_a(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ORCHAUT-010 (2026-08-28): ``refuse_owner_actions`` previously called
    ``require_owner`` for gate A only, while its own docstring and the
    module's ``LOOP_CAN_BYPASS_OWNER_GATE = NO`` contract claimed the
    general property for all six gates. Because the real (unpatched)
    ``require_owner`` always raises with no grant, a plain
    ``pytest.raises(OwnerGateError)`` on the whole call can't distinguish
    "checked gate A only, then stopped" from "checked all six" -- both
    look identical from outside. Patches ``require_owner`` in the loop
    module's own namespace with a non-raising recorder to observe every
    gate the method actually attempts, proving it doesn't short-circuit
    after A."""
    seen: list[OwnerGateKind] = []

    def _record(gate: OwnerGateKind, *, owner_grant: bool = False) -> None:
        assert owner_grant is False
        seen.append(gate)

    import project_atlas.orchestration.autonomy.loop as loop_module

    monkeypatch.setattr(loop_module, "require_owner", _record)

    gov = _governor(_node("AS-ORCH-REFUSE-001"))
    loop = _loop(tmp_path, gov)
    loop.refuse_owner_actions()

    assert seen == list(OwnerGateKind)


@pytest.mark.parametrize(
    "gate",
    [
        OwnerGateKind.C_CERTIFIED_OBJECT_MUTATION,
        OwnerGateKind.D_SECURITY_GOVERNANCE_POLICY,
        OwnerGateKind.E_DESTRUCTIVE_OPS,
        OwnerGateKind.F_MATERIAL_EXTERNAL_SPEND,
    ],
)
def test_ready_owner_gated_node_never_leased_or_dispatched(
    tmp_path: Path, gate: OwnerGateKind
) -> None:
    """ORCHAUT-010 regression: gates C-F must fail closed at the real
    select/lease boundary, not just via the standalone, never-called
    `request_*` primitives. A node reaching READY while tagged with an
    owner_gate must stop the loop before any lease or dispatch, exactly
    like OWNER_HELD/MERGE_ELIGIBLE already does for gate A.
    """
    gov = _governor(
        _node("AS-ORCH-GATE-001", state=NodeState.READY, owner_gate=gate)
    )
    calls: list[str] = []
    port = CallableDispatchPort(
        lambda _root: calls.append("dispatch") or {"dispatch_id": "x", "status": "COMPLETED"}
    )
    loop = _loop(tmp_path, gov, port)
    result = loop.run_until_stop()
    assert result.stop_reason is StopReason.OWNER_GATE
    assert calls == []
    assert result.dispatched is False
    node = next(
        item for item in gov.snapshot().nodes if item.package_id == "AS-ORCH-GATE-001"
    )
    assert node.state is NodeState.READY


def test_hard_blocker_stop(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-BLK-001", state=NodeState.BLOCKED))
    result = _loop(tmp_path, gov).run_until_stop()
    assert result.stop_reason is StopReason.HARD_BLOCKER


def test_external_dispatch_once_then_await(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-EXT-001", host=ExecutionHostClass.EXTERNAL_AGENT))
    port = CallableDispatchPort(lambda _root: {"dispatch_id": "disp-1", "status": "RUNNING"})
    loop = _loop(tmp_path, gov, port)
    result = loop.tick()
    assert result.dispatched is True
    assert result.dispatch_id == "disp-1"
    assert result.phase is LoopPhase.AWAITING_RESULT
    again = loop.tick()
    assert again.recovered is True
    assert again.dispatched is False
    assert again.phase is LoopPhase.AWAITING_RESULT


def test_duplicate_result_replay_rejected(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-DUP-001", host=ExecutionHostClass.EXTERNAL_AGENT))
    port = CallableDispatchPort(
        lambda _root: {"dispatch_id": "disp-dup", "status": "COMPLETED", "digest": "ff" * 32}
    )
    loop = _loop(tmp_path, gov, port)
    loop.tick()
    with pytest.raises(LoopError, match="duplicate"):
        loop.apply_observed_result("disp-dup", "ff" * 32, passed=True)


def test_lease_replay_rejected(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-LSR-001"))
    loop = _loop(tmp_path, gov)
    loop.tick()
    loop._save(phase=LoopPhase.IDLE, active_package_id=None, active_lease_id=None)
    assert loop.state.completed_lease_ids


def test_corrupt_state_fails_closed(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-COR-001"))
    loop = _loop(tmp_path, gov)
    raw = (tmp_path / "loop-store" / "current.json").read_text(encoding="utf-8")
    (tmp_path / "loop-store" / "current.json").write_text(
        raw.replace(loop.state.record_digest, "ab" * 32),
        encoding="utf-8",
    )
    with pytest.raises(LoopError) as exc:
        AutonomousLoop(
            governor=gov,
            trusted=_anchor(),
            store=tmp_path / "loop-store",
            root=tmp_path,
        )
    assert exc.value.code == "STATE_CORRUPT"


def test_cross_project_rejected(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-XPR-001"))
    with pytest.raises(LoopError) as exc:
        AutonomousLoop(
            governor=gov,
            trusted=_anchor(),
            store=tmp_path / "loop-store",
            root=tmp_path,
            expected_repository_identity="github.com/other/repo",
        )
    assert exc.value.code == "CROSS_PROJECT"


def test_target_moved_refuses_loop(tmp_path: Path) -> None:
    other = "cccccccccccccccccccccccccccccccccccccccc"
    gov = AutonomousGovernor(current_main=other, current_tree=TREE, trusted_anchor=_anchor())
    gov.add_node(_node("AS-ORCH-MOV-001"))
    with pytest.raises(LoopError) as exc:
        AutonomousLoop(
            governor=gov,
            trusted=_anchor(),
            store=tmp_path / "loop-store",
            root=tmp_path,
        )
    assert exc.value.code == "TARGET_MOVED"


def test_crash_recover_does_not_respawn(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-CRASH-001", host=ExecutionHostClass.EXTERNAL_AGENT))
    recover_calls: list[str] = []
    port = CallableDispatchPort(
        lambda _root: {"dispatch_id": "disp-crash", "status": "RUNNING"},
        recover=lambda _root, did: recover_calls.append(did)
        or {"dispatch_id": did, "status": "RUNNING"},
    )
    loop = _loop(tmp_path, gov, port)
    loop.tick()
    recovered = loop.recover()
    assert recovered.recovered is True
    assert recover_calls == ["disp-crash"]
    assert recovered.dispatched is False


def test_max_ticks_resource_boundary(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-RUN-001", host=ExecutionHostClass.EXTERNAL_AGENT))
    port = CallableDispatchPort(lambda _root: {"dispatch_id": "disp-run", "status": "RUNNING"})
    loop = _loop(tmp_path, gov, port)
    last = loop.run_until_stop()
    assert last.phase in {LoopPhase.AWAITING_RESULT, LoopPhase.STOPPED}
    loop._save(ticks_in_invocation=MAX_TICKS_PER_INVOCATION)
    bounded = loop.tick()
    assert bounded.stop_reason is StopReason.RESOURCE_BOUNDARY


def test_state_cannot_carry_authority() -> None:
    with pytest.raises(ValidationError):
        LoopState(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=PIN,
            trusted_tree=TREE,
            phase=LoopPhase.IDLE,
            sequence=0,
            ticks_in_invocation=0,
            merge_authorized=True,  # type: ignore[arg-type]
            record_digest="00" * 32,
        )


def test_digest_roundtrip(tmp_path: Path) -> None:
    state = initial_loop_state(_anchor())
    persisted = persist_loop_state(tmp_path / "s", state)
    assert verify_loop_state(persisted).record_digest == hash_payload(persisted.unsigned_payload())
    assert persisted.record_digest != seal_loop_state(
        persisted.model_copy(update={"sequence": 1, "record_digest": "00" * 32})
    ).record_digest


def test_package_id_constant() -> None:
    assert LOOP_PACKAGE_ID == "AS-ORCH-001E"


def test_resource_boundary_enqueues_yield_not_owner(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-NEXT-001"))
    loop = _loop(tmp_path, gov)
    persist_loop_state(
        tmp_path / "loop-store",
        seal_loop_state(
            loop.state.model_copy(
                update={
                    "ticks_in_invocation": MAX_TICKS_PER_INVOCATION,
                    "record_digest": "00" * 32,
                }
            )
        ),
    )
    loop._state = load_loop_state(tmp_path / "loop-store")
    result = loop.tick()
    assert result.stop_reason is StopReason.RESOURCE_BOUNDARY
    recovered = recover_broker(tmp_path)
    assert recovered is not None
    assert recovered.kind is SuccessorKind.RESOURCE_YIELD
    assert recovered.execution_authorized is False
