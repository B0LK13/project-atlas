"""AS-ORCH-AUTONOMY-001 governor, DAG, leases, overlap, owner gates, evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.orchestration.autonomy.adversarial import requires_adversarial_review
from project_atlas.orchestration.autonomy.continuation import select_next
from project_atlas.orchestration.autonomy.dag import IllegalTransitionError, apply_transition
from project_atlas.orchestration.autonomy.discovery import (
    DiscoveryError,
    collect_live_inventory,
    discover,
)
from project_atlas.orchestration.autonomy.evidence import (
    EvidenceError,
    file_sha256,
    make_bundle,
    write_bundle,
)
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.leases import (
    ScopeExpansionError,
    expand_lease,
    grant_lease,
)
from project_atlas.orchestration.autonomy.models import (
    CANONICAL_REPOSITORY_IDENTITY,
    EXPECTED_BASE_MAIN,
    EXPECTED_BASE_TREE,
    INITIAL_RETARGET_MAIN,
    INITIAL_RETARGET_TREE,
    PILOT_PACKAGE_ID,
    AdvancementReason,
    AgentCapability,
    ExecutionHostClass,
    ExecutionPlan,
    IvRequirements,
    LiveInventory,
    MutationSurface,
    NodeState,
    OwnerGateKind,
    RiskTag,
    StopReason,
    TrustedAnchorRecord,
    WorkNode,
)
from project_atlas.orchestration.autonomy.overlap import overlap_gate, would_overlap
from project_atlas.orchestration.autonomy.owner_gates import (
    OwnerGateError,
    classify_requested_action,
)
from project_atlas.orchestration.autonomy.remediation import (
    MAX_AUTONOMOUS_REMEDIATION_CYCLES,
    RemediationExhausted,
    consume_remediation_cycle,
)
from project_atlas.orchestration.autonomy.trust import seal_anchor
from project_atlas.schema import available_schemas, validate_record

PIN = EXPECTED_BASE_MAIN


def _anchor(main: str = EXPECTED_BASE_MAIN, tree: str = EXPECTED_BASE_TREE) -> TrustedAnchorRecord:
    predecessor = "1111111111111111111111111111111111111111"
    certified = "3333333333333333333333333333333333333333"
    return seal_anchor(
        TrustedAnchorRecord(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            trusted_main=main,
            trusted_tree=tree,
            predecessor_main=predecessor,
            predecessor_tree="2222222222222222222222222222222222222222",
            advancement_reason=AdvancementReason.VERIFIED_OWNER_AUTHORIZED_MERGE,
            source_package="AS-ORCH-AUTONOMY-001-TEST",
            source_directive="D-AUTONOMY-TEST-001",
            source_pr=1,
            merge_commit=main,
            merge_parent_1=predecessor,
            merge_parent_2=certified,
            merge_tree=tree,
            certified_head=certified,
            certified_tree=tree,
            certification_status="CERTIFIED",
            independent_verification_status="PASS",
            post_merge_seal="PASS",
            post_merge_ci="PASS",
            evidence_reference="tests/unit/test-anchor.json",
            evidence_digest="aa" * 32,
            sequence=1,
            record_digest="00" * 32,
        )
    )


def _inventory(**overrides: Any) -> LiveInventory:
    payload: dict[str, Any] = {
        "current_main": EXPECTED_BASE_MAIN,
        "current_tree": EXPECTED_BASE_TREE,
        "worktree_status": "CLEAN",
        "open_relevant_prs": ("396",),
        "active_successor_packages": (),
        "r2_created": "NO",
        "r7_created": "NO",
        "authentic_r6_resumed": "NO",
        "as_orch_001e_started": "NO",
        "pr396_mutated": "NO",
    }
    payload.update(overrides)
    return LiveInventory.model_validate(payload)


def _node(
    package_id: str,
    *,
    state: NodeState = NodeState.READY,
    surface: str = "surface-a",
    semantic: str = "SEMANTIC_A",
    paths: tuple[str, ...] = ("src/a",),
    owner_gate: OwnerGateKind | None = None,
    deps: tuple[str, ...] = (),
    capabilities: tuple[AgentCapability, ...] = (AgentCapability.IMPLEMENT,),
) -> WorkNode:
    return WorkNode(
        package_id=package_id,
        objective="test node",
        base_pin=PIN,
        dependencies=deps,
        mutation_surface=MutationSurface(
            surface_id=surface,
            paths=paths,
            semantic=semantic,
        ),
        execution_host_class=ExecutionHostClass.IN_PROCESS,
        agent_capabilities_required=capabilities,
        acceptance_criteria=("PASS",),
        iv_requirements=IvRequirements(certification_required=True),
        owner_gate=owner_gate,
        state=state,
    )


def test_schemas_registered() -> None:
    kinds = available_schemas()
    assert "autonomy-governor-report" in kinds
    assert "autonomy-work-node" in kinds
    assert "autonomy-lease" in kinds
    assert "autonomy-trusted-anchor" in kinds


def test_work_node_and_plan_schema_parity() -> None:
    node = _node("PKG-A")
    validate_record(node, "autonomy-work-node")
    plan = ExecutionPlan(
        what_can_run_now=("PKG-A",),
        what_must_wait=(),
        what_can_run_in_parallel=(),
        what_requires_owner_authority=(),
    )
    validate_record(plan, "autonomy-governor-report")


def test_illegal_dag_transition_fail_closed() -> None:
    node = _node("PKG-A", state=NodeState.DISCOVERED)
    with pytest.raises(IllegalTransitionError):
        apply_transition(node, NodeState.MERGED, reason="nope", sequence=1)


def test_legal_ready_to_leased() -> None:
    node = _node("PKG-A", state=NodeState.READY)
    updated, record = apply_transition(node, NodeState.LEASED, reason="lease", sequence=1)
    assert updated.state is NodeState.LEASED
    assert record.from_state is NodeState.READY
    assert record.to_state is NodeState.LEASED


def test_governor_cannot_merge() -> None:
    gov = AutonomousGovernor(
        current_main=EXPECTED_BASE_MAIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
    )
    gov.add_node(_node("PKG-A", state=NodeState.MERGE_ELIGIBLE))
    with pytest.raises(OwnerGateError):
        gov.request_merge("PKG-A")
    with pytest.raises(IllegalTransitionError):
        apply_transition(
            gov.snapshot().nodes[0],
            NodeState.MERGED,
            reason="merge",
            sequence=1,
        )


def test_owner_gates_a_through_f_fail_closed() -> None:
    gov = AutonomousGovernor(
        current_main=EXPECTED_BASE_MAIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
    )
    gates = classify_requested_action(
        merge_to_protected_main=True,
        waive_acceptance=True,
        mutate_certified_object=True,
        change_security_or_governance_policy=True,
        destructive_ops=True,
        material_external_spend=True,
    )
    assert set(gates) == set(OwnerGateKind)
    with pytest.raises(OwnerGateError):
        gov.request_acceptance_waiver()


def test_lease_and_forbidden_scope_expansion() -> None:
    gov = AutonomousGovernor(
        current_main=EXPECTED_BASE_MAIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
    )
    gov.add_node(
        _node(
            "PKG-A",
            capabilities=(AgentCapability.DISCOVER, AgentCapability.IMPLEMENT),
        )
    )
    lease = gov.lease(
        "PKG-A",
        "governor-pilot-local",
        branch="feat/as-orch-autonomy-001",
        worktree="repo",
    )
    validate_record(lease, "autonomy-lease")
    with pytest.raises(ScopeExpansionError):
        expand_lease(lease)
    agent = next(item for item in gov.snapshot().agents if item.agent_id == "governor-pilot-local")
    ready = _node(
        "PKG-B",
        capabilities=(AgentCapability.DISCOVER, AgentCapability.IMPLEMENT),
        surface="surface-b",
        semantic="SEMANTIC_B",
        paths=("src/b",),
    )
    with pytest.raises(ScopeExpansionError):
        grant_lease(
            lease_id="LEASE-WIDE",
            agent=agent,
            node=ready,
            branch="feat/x",
            worktree="repo",
            sequence=9,
            authorized_paths=("src/b", "src/outside"),
        )


def test_overlap_gate_blocks_shared_surface() -> None:
    left = _node("PKG-A", state=NodeState.LEASED, surface="shared", paths=("src/x",))
    right = _node("PKG-B", state=NodeState.READY, surface="shared", paths=("src/x",))
    assert would_overlap((left,), right)
    decision = overlap_gate((left, right.model_copy(update={"state": NodeState.ACTIVE})))
    assert decision.parallel_execution is False
    assert "shared" in decision.conflict_surfaces


def test_overlap_allows_disjoint_surfaces() -> None:
    left = _node(
        "PKG-A",
        state=NodeState.LEASED,
        surface="one",
        semantic="SEM_ONE",
        paths=("src/one",),
    )
    right = _node(
        "PKG-B",
        state=NodeState.ACTIVE,
        surface="two",
        semantic="SEM_TWO",
        paths=("src/two",),
    )
    decision = overlap_gate((left, right))
    assert decision.parallel_execution is True


def test_continuation_stops_at_owner_gate() -> None:
    held = _node(
        "PKG-A",
        state=NodeState.OWNER_HELD,
        owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
    )
    decision = select_next((held,))
    assert decision.next_package_id is None
    assert decision.stop_reason is StopReason.OWNER_GATE


def test_continuation_selects_ready_when_no_owner_gate() -> None:
    ready = _node("PKG-B", state=NodeState.READY)
    decision = select_next((ready,))
    assert decision.next_package_id == "PKG-B"
    assert decision.stop_reason is None


def test_evidence_hash_is_reconstructable(tmp_path: Path) -> None:
    first = make_bundle("PILOT_EXECUTION", {"a": 1, "b": "x"})
    second = make_bundle("PILOT_EXECUTION", {"b": "x", "a": 1})
    assert first.payload_sha256 == second.payload_sha256
    path = write_bundle(tmp_path, "bundle.json", first)
    assert len(file_sha256(path)) == 64
    with pytest.raises(EvidenceError):
        write_bundle(tmp_path, "../escape.json", first)


def test_iv_implementer_cannot_verify() -> None:
    gov = AutonomousGovernor(
        current_main=EXPECTED_BASE_MAIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
    )
    gov.add_node(
        _node(
            "PKG-A",
            capabilities=(AgentCapability.DISCOVER, AgentCapability.IMPLEMENT),
            owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
        )
    )
    gov.lease("PKG-A", "governor-pilot-local", branch="feat/x", worktree="repo")
    gov.execute_leased(gov.snapshot().leases[0].lease_id)
    verifier = gov.route_and_verify("PKG-A", implementer_id="governor-pilot-local")
    assert verifier == "governor-pilot-iv"
    assert verifier != "governor-pilot-local"


def test_remediation_blocks_after_three_cycles() -> None:
    node = _node("PKG-A")
    used = node
    for _ in range(MAX_AUTONOMOUS_REMEDIATION_CYCLES):
        used = consume_remediation_cycle(used)
    assert used.retry_policy.cycles_used == 3
    with pytest.raises(RemediationExhausted):
        consume_remediation_cycle(used)


def test_adversarial_trigger_for_control_plane() -> None:
    assert requires_adversarial_review((RiskTag.CONTROL_PLANE, RiskTag.AUTHORIZATION))


def test_discovery_selects_dispatch_primitive_not_closed_slots() -> None:
    report = discover(_inventory(), trusted=_anchor())
    assert report.case == "A-A-PREFLIGHT"
    assert report.selected_package_id is None
    assert report.blocker == "OWNER_GATE"
    rejected = {item.package_id: item.reason for item in report.candidates if not item.eligible}
    assert rejected["AS-ORCH-001D-R2"] == "SUPERSEDED_CLOSED_SEMANTIC_DELTA_ZERO"
    assert rejected["AS-ORCH-001D-R7"] == "OBSOLETE_NO_DEFINED_SEMANTIC"
    assert rejected["AS-ORCH-001E"] == "BLOCKED_BY_DEPENDENCY_AS_ORCH_001D"
    assert rejected["AS-ORCH-001D-R6"] == "SUPERSEDED_CLOSED_DO_NOT_MUTATE_PR_396"
    assert rejected["AS-ORCH-001D"] == "IMPLEMENTED_CERTIFIED_PENDING_OWNER_MERGE"
    assert PILOT_PACKAGE_ID in rejected


def test_live_inventory_fails_closed_without_git(tmp_path: Path) -> None:
    with pytest.raises(DiscoveryError):
        collect_live_inventory(tmp_path)


def test_live_inventory_does_not_walk_parent_repo() -> None:
    nested = Path(__file__).resolve().parents[2] / "src"
    with pytest.raises(DiscoveryError, match="not a git repository"):
        collect_live_inventory(nested)


def test_discovery_drift_is_case_a_b() -> None:
    report = discover(
        _inventory(current_main="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
        trusted=_anchor(),
    )
    assert report.case == "A-B"
    assert report.blocker == "TARGET_MOVED"


def test_governor_plan_answers() -> None:
    gov = AutonomousGovernor(
        current_main=EXPECTED_BASE_MAIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
    )
    gov.add_node(_node("PKG-A", owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE))
    gov.add_node(
        _node(
            "PKG-B",
            state=NodeState.BLOCKED,
            surface="other",
            semantic="SEM_B",
            paths=("src/b",),
        )
    )
    plan = gov.plan()
    assert "PKG-A" in plan.what_can_run_now
    assert "PKG-B" in plan.what_must_wait
    assert "PKG-A" in plan.what_requires_owner_authority
    assert plan.merge_authorized is False


def test_controlled_pilot_stops_at_owner_gate(tmp_path: Path) -> None:
    gov = AutonomousGovernor(
        current_main=EXPECTED_BASE_MAIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
    )
    result = gov.run_controlled_pilot(
        _inventory(),
        branch="feat/as-orch-autonomy-001",
        worktree="repo",
        evidence_dir=tmp_path,
    )
    assert result["discovered"] is True
    assert result["selected_package_id"] is None
    assert result["implementer_equals_verifier"] is False
    assert result["stop_reason"] == "OWNER_GATE"
    assert result["node_state"] == "OWNER_HELD"
    assert result["merge_authorized"] is False
    assert result["r2_created"] == "NO"
    assert result["as_orch_001e_started"] == "NO"
    assert (tmp_path / "pilot-evidence.json").is_file()


def test_controlled_pilot_bounded_remediation() -> None:
    gov = AutonomousGovernor(
        current_main=EXPECTED_BASE_MAIN,
        current_tree=EXPECTED_BASE_TREE,
        trusted_anchor=_anchor(),
    )
    result = gov.run_controlled_pilot(
        _inventory(),
        branch="feat/as-orch-autonomy-001",
        worktree="repo",
        inject_iv_failure=True,
    )
    assert result["remediation_cycles"] == 1
    assert result["node_state"] == "OWNER_HELD"


def test_cli_governor_discover(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    inventory = tmp_path / "inv.json"
    inventory.write_text(
        _inventory(current_main=INITIAL_RETARGET_MAIN, current_tree=INITIAL_RETARGET_TREE)
        .model_dump_json(),
        encoding="utf-8",
    )
    code = main(
        [
            "orchestrator",
            "governor-discover",
            "--root",
            str(tmp_path),
            "--inventory",
            str(inventory),
        ]
    )
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["selected_package_id"] is None
    assert payload["blocker"] == "OWNER_GATE"


def test_cli_governor_pilot(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    inventory = tmp_path / "inv.json"
    inventory.write_text(
        _inventory(current_main=INITIAL_RETARGET_MAIN, current_tree=INITIAL_RETARGET_TREE)
        .model_dump_json(),
        encoding="utf-8",
    )
    evidence = tmp_path / "ev"
    code = main(
        [
            "orchestrator",
            "governor-pilot",
            "--root",
            str(tmp_path),
            "--inventory",
            str(inventory),
            "--evidence-dir",
            str(evidence),
        ]
    )
    assert code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["package_id"] == "AS-ORCH-AUTONOMY-001"
    assert payload["merge_authorized"] is False


def test_cli_governor_status_moved_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _fake_inventory(_root: Path) -> LiveInventory:
        return _inventory(current_main="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    monkeypatch.setattr(
        "project_atlas.orchestration.autonomy.cli.collect_live_inventory",
        _fake_inventory,
    )
    code = main(["orchestrator", "governor-status", "--root", str(tmp_path)])
    assert code == EXIT_ERROR
    payload = json.loads(capsys.readouterr().out)
    assert payload["target_moved"] is True


def test_001a_authority_invariants_untouched() -> None:
    from project_atlas.orchestration.models import (
        NextTransition,
        OrchestrationDecision,
        WorkflowState,
    )

    decision = OrchestrationDecision(
        valid=True,
        workflow_state=WorkflowState.OWNER_REQUIRED,
        next_transition=NextTransition.OWNER_REQUIRED,
        owner_required=True,
    )
    assert decision.execution_authorized is False
    assert decision.merge_authorized is False
