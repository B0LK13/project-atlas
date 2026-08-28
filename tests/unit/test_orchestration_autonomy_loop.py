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


def test_orphaned_dispatch_recovery_reconciles_completed(tmp_path: Path) -> None:
    """ORCH001E-008 P3 remediation: a crash between dispatch_once()
    persisting its own 001D-side record and the loop persisting
    active_dispatch_id must not be silently treated as "nothing was
    dispatched". If the dispatch port can independently find what it
    actually started, the loop must reconcile from that, not stay stuck.
    """
    gov = _governor(_node("AS-ORCH-ORPHAN-001", host=ExecutionHostClass.EXTERNAL_AGENT))
    calls: list[str] = []
    port = CallableDispatchPort(
        lambda _root: calls.append("dispatch") or {"dispatch_id": "orphan-1", "status": "RUNNING"},
        recover=lambda _root, _id: {"status": "COMPLETED", "digest": "aa" * 32},
        find_active_dispatch_id=lambda _root: "orphan-1",
    )
    loop = _loop(tmp_path, gov, port)
    loop.tick()  # LEASED -> DISPATCHING -> AWAITING_RESULT (normal path)
    # Simulate the exact crash window: DISPATCHING persisted, but
    # active_dispatch_id was never recorded (as if the process had just
    # crashed between dispatch_once() returning and the loop's own save).
    loop._save(phase=LoopPhase.DISPATCHING, active_dispatch_id=None)
    result = loop.recover()
    assert calls == ["dispatch"]  # never re-dispatched a duplicate process
    assert result.stop_reason is None
    node = next(item for item in gov.snapshot().nodes if item.package_id == "AS-ORCH-ORPHAN-001")
    assert node.state in {NodeState.CERTIFIED, NodeState.OWNER_HELD, NodeState.CLOSED}


def test_orphaned_dispatch_recovery_reconciles_still_running(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-ORPHAN-002", host=ExecutionHostClass.EXTERNAL_AGENT))
    port = CallableDispatchPort(
        lambda _root: {"dispatch_id": "orphan-2", "status": "RUNNING"},
        recover=lambda _root, _id: {"status": "RUNNING"},
        find_active_dispatch_id=lambda _root: "orphan-2",
    )
    loop = _loop(tmp_path, gov, port)
    loop.tick()
    loop._save(phase=LoopPhase.DISPATCHING, active_dispatch_id=None)
    result = loop.recover()
    assert result.phase is LoopPhase.AWAITING_RESULT
    assert loop.state.active_dispatch_id == "orphan-2"  # identity recovered, not lost


def test_orphaned_dispatch_recovery_finds_nothing_retries_cleanly(tmp_path: Path) -> None:
    """When the port genuinely has no record either (crash happened before
    even the 001D-side persist), retry from LEASED is safe -- no process is
    known to exist, so re-dispatching cannot duplicate one.
    """
    gov = _governor(_node("AS-ORCH-ORPHAN-003", host=ExecutionHostClass.EXTERNAL_AGENT))
    calls: list[str] = []
    port = CallableDispatchPort(
        lambda _root: calls.append("dispatch") or {"dispatch_id": "orphan-3", "status": "RUNNING"},
        find_active_dispatch_id=lambda _root: None,
    )
    loop = _loop(tmp_path, gov, port)
    loop.tick()
    assert calls == ["dispatch"]  # the original, pre-crash dispatch
    loop._save(phase=LoopPhase.DISPATCHING, active_dispatch_id=None)
    result = loop.recover()
    assert calls == ["dispatch", "dispatch"]  # one clean retry, not a hang
    assert result.dispatch_id == "orphan-3"
    assert result.phase is LoopPhase.AWAITING_RESULT


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
