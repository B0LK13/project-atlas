"""D-095 fail-closed independent cloud-audit provenance (A-A through A-L)."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.orchestration.sdk.audit_provenance import (
    REPO_EVIDENCE_REL,
    CloudAuditAssignment,
    apply_cloud_audit_from_plane,
    consume_identity,
    evaluate_cloud_audit,
    invalidate_cloud_audit_assignment,
    mint_cloud_audit_assignment,
    persist_cloud_audit_assignment,
    persist_consumed_identities,
)
from project_atlas.orchestration.sdk.ci_observer import CiObservation, PrHeadRef
from project_atlas.orchestration.sdk.live_dag import (
    LiveDagController,
    LiveDagState,
    persist_live_dag,
)
from project_atlas.orchestration.sdk.models import PACKAGE_ID, AgentRole, SdkRuntimeError
from project_atlas.orchestration.sdk.result_plane import ResultEnvelope, append_result
from project_atlas.orchestration.sdk.security_gates import BoundWorkerResult, WorkerBackend

HEAD = "ca7368ff3bde9895b14cc90069a7036dd435f250"
TREE = "5eeb51235afd7a6b818fb9c3fffed85255aae6c8"
PARENT = "6ae66f2bbd569e1f29a93a9bd0df5e3387047789"
DIGEST = "a" * 64
AUDITOR = "cli-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
WRITER = "cli-ffffffff-1111-2222-3333-444444444444"
RUN = "run-cloud-audit-1"
ASSIGN = "assign-cloud-audit-1"


def _assignment(**kwargs: object) -> CloudAuditAssignment:
    base: dict[str, object] = dict(
        assignment_id=ASSIGN,
        dag_generation=92,
        candidate_head=HEAD,
        candidate_tree=TREE,
        worker_id=AUDITOR,
        run_id=RUN,
        attempt=1,
        implementer_worker_id=WRITER,
    )
    base.update(kwargs)
    return CloudAuditAssignment(**base)  # type: ignore[arg-type]


def _binding(**kwargs: object) -> BoundWorkerResult:
    base: dict[str, object] = dict(
        worker_backend=WorkerBackend.CURSOR_AGENT_CLI,
        session_or_agent_id=AUDITOR,
        run_id=RUN,
        package_id=PACKAGE_ID,
        dag_node="CLOUD-AUDIT-LIVE",
        dag_generation=92,
        role=AgentRole.CLOUD_RUNTIME_AUDITOR,
        lease_id="lease-cloud-audit-92",
        attempt=1,
        result_digest=DIGEST,
        candidate_head=HEAD,
        candidate_tree=TREE,
    )
    base.update(kwargs)
    return BoundWorkerResult(**base)  # type: ignore[arg-type]


def _pass_payload(**kwargs: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ASSIGNMENT_ID": ASSIGN,
        "SIX_P1_RUNTIME_OPEN_COUNT": 0,
        "WIRING_VERIFIED": {
            "RESULT_BINDING": "PASS",
            "LEASE_GATING": "PASS",
            "ALLOWED_PATHS": "PASS",
            "HOST_ROLLBACK": "PASS",
            "WORKER_LINEAGE": "PASS",
            "TRANSIENT_RECOVERY": "PASS",
        },
        "AUDIT_RESULT": "PASS",
    }
    payload.update(kwargs)
    return payload


def _repo_pass_claim() -> dict[str, object]:
    return {"six_p1_runtime_open_count": 0, "wiring_verified": {"x": True}}


def test_aa_repo_json_without_assignment_blocks() -> None:
    decision = evaluate_cloud_audit(
        assignment=None,
        binding=None,
        payload=None,
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        repo_json=_repo_pass_claim(),
    )
    assert decision.accepted is False
    assert decision.gate == "NOT_PASS"
    assert decision.reason == "NO_ASSIGNMENT"


def test_ab_registered_audit_wrong_head_blocks() -> None:
    decision = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(candidate_head=PARENT),
        payload=_pass_payload(),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    assert decision.gate == "NOT_PASS"
    assert decision.reason == "WRONG_HEAD"


def test_ac_registered_audit_wrong_tree_blocks() -> None:
    decision = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(candidate_tree="b" * 40),
        payload=_pass_payload(),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    assert decision.gate == "NOT_PASS"
    assert decision.reason == "WRONG_TREE"


def test_ad_stale_generation_blocks() -> None:
    decision = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(dag_generation=91),
        payload=_pass_payload(),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    assert decision.gate == "NOT_PASS"
    assert decision.reason == "STALE_GENERATION"


def test_ae_writer_identity_cannot_be_auditor(tmp_path: Path) -> None:
    with pytest.raises(SdkRuntimeError, match="implementer"):
        mint_cloud_audit_assignment(
            tmp_path,
            assignment_id=ASSIGN,
            dag_generation=92,
            candidate_head=HEAD,
            candidate_tree=TREE,
            worker_id=WRITER,
            run_id=RUN,
            implementer_worker_id=WRITER,
        )
    decision = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(role=AgentRole.IMPLEMENTER, session_or_agent_id=WRITER),
        payload=_pass_payload(),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    assert decision.reason == "REJECT_INDEPENDENCE"


def test_af_valid_fail_blocks_and_is_remediation_ready() -> None:
    decision = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(),
        payload=_pass_payload(AUDIT_RESULT="FAIL"),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    assert decision.accepted is True
    assert decision.gate == "FAIL"
    assert decision.remediation_ready is True


def test_ag_pass_with_open_count_blocks() -> None:
    decision = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(),
        payload=_pass_payload(SIX_P1_RUNTIME_OPEN_COUNT=2),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    assert decision.gate == "FAIL"
    assert decision.reason == "OPEN_COUNT"


def test_ah_valid_independent_pass_arms_gate() -> None:
    decision = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(),
        payload=_pass_payload(),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    assert decision.gate == "PASS"
    assert decision.accepted is True
    assert decision.gate_transition is True


def test_ai_replay_does_not_transition_again() -> None:
    identity = consume_identity(ASSIGN, RUN, DIGEST)
    first = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(),
        payload=_pass_payload(),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset(),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    replay = evaluate_cloud_audit(
        assignment=_assignment(),
        binding=_binding(),
        payload=_pass_payload(),
        live_head=HEAD,
        live_tree=TREE,
        live_generation=92,
        already_consumed=frozenset({identity}),
        source="CLOUD_RUNTIME_AUDITOR",
    )
    assert first.gate_transition is True
    assert replay.reason == "REPLAY"
    assert replay.gate_transition is False


def test_aj_head_move_invalidates_audit(tmp_path: Path) -> None:
    persist_live_dag(
        tmp_path,
        LiveDagState(
            bound_head=HEAD,
            bound_tree=TREE,
            ci_status="PASS",
            ci_run_id="1",
            cloud_runtime_audit_pass=True,
            cloud_audit_consume_id=consume_identity(ASSIGN, RUN, DIGEST),
            dag_generation=92,
        ),
    )
    persist_cloud_audit_assignment(tmp_path, _assignment())
    persist_consumed_identities(tmp_path, {consume_identity(ASSIGN, RUN, DIGEST)})
    live = PrHeadRef(pr_number=429, head_sha=PARENT, tree_sha="c" * 40)
    controller = LiveDagController(
        tmp_path,
        refresh=lambda: live,
        observe=lambda sha: CiObservation(
            head_sha=sha, run_id="2", status="PENDING", conclusion=None
        ),
        real_sdk_backend=True,
    )
    state, items = controller.tick()
    assert state.cloud_runtime_audit_pass is False
    assert state.iv_dispatched is False
    assert items == []
    stored = tmp_path / ".atlas" / "orchestration" / "sdk-runtime" / "cloud-audit-assignment.json"
    assert '"stale": true' in stored.read_text(encoding="utf-8")


def test_ak_candidate_evidence_file_cannot_arm_gate(tmp_path: Path) -> None:
    evidence = tmp_path / REPO_EVIDENCE_REL
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        '{"six_p1_runtime_open_count": 0, "wiring_verified": {"x": true}}\n',
        encoding="utf-8",
    )
    persist_live_dag(
        tmp_path,
        LiveDagState(
            bound_head=HEAD,
            bound_tree=TREE,
            ci_status="PASS",
            ci_run_id="1",
            dag_generation=92,
        ),
    )
    live = PrHeadRef(pr_number=429, head_sha=HEAD, tree_sha=TREE)
    controller = LiveDagController(
        tmp_path,
        refresh=lambda: live,
        observe=lambda _sha: CiObservation(
            head_sha=HEAD, run_id="1", status="PASS", conclusion="success"
        ),
        real_sdk_backend=True,
    )
    state, items = controller.tick()
    assert state.cloud_runtime_audit_pass is False
    assert all(i.role != AgentRole.INDEPENDENT_VERIFIER for i in items)
    assert all(i.role != AgentRole.SECURITY_REVIEWER for i in items)
    assert any(i.role == AgentRole.CLOUD_RUNTIME_AUDITOR for i in items)


def test_ah_transported_but_not_consumed_does_not_pass(tmp_path: Path) -> None:
    persist_cloud_audit_assignment(tmp_path, _assignment())
    append_result(
        tmp_path,
        ResultEnvelope(
            source="CLOUD_RUNTIME_AUDITOR",
            binding=_binding(),
            payload=_pass_payload(),
        ),
    )
    persist_live_dag(
        tmp_path,
        LiveDagState(
            bound_head=HEAD,
            bound_tree=TREE,
            ci_status="PASS",
            ci_run_id="1",
            dag_generation=92,
        ),
    )
    # Simulate "transported but not consumed": no apply call, gate stays false.
    state = LiveDagState.model_validate_json(
        (tmp_path / ".atlas" / "orchestration" / "sdk-runtime" / "live-dag.json").read_text(
            encoding="utf-8"
        )
    )
    assert state.cloud_runtime_audit_pass is False


def test_ai_apply_consumes_once_then_replay_is_noop(tmp_path: Path) -> None:
    persist_cloud_audit_assignment(tmp_path, _assignment())
    append_result(
        tmp_path,
        ResultEnvelope(
            source="CLOUD_RUNTIME_AUDITOR",
            binding=_binding(),
            payload=_pass_payload(),
        ),
    )
    first = apply_cloud_audit_from_plane(
        tmp_path, live_head=HEAD, live_tree=TREE, live_generation=92
    )
    second = apply_cloud_audit_from_plane(
        tmp_path, live_head=HEAD, live_tree=TREE, live_generation=92
    )
    assert first.gate == "PASS"
    assert first.gate_transition is True
    assert second.reason == "REPLAY"
    assert second.gate_transition is False


def test_al_evidence_modify_after_valid_audit_no_authority_change(tmp_path: Path) -> None:
    identity = consume_identity(ASSIGN, RUN, DIGEST)
    persist_cloud_audit_assignment(tmp_path, _assignment())
    persist_consumed_identities(tmp_path, {identity})
    evidence = tmp_path / REPO_EVIDENCE_REL
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        '{"six_p1_runtime_open_count": 99, "wiring_verified": {}, "AUDIT_RESULT": "FAIL"}\n',
        encoding="utf-8",
    )
    persist_live_dag(
        tmp_path,
        LiveDagState(
            bound_head=HEAD,
            bound_tree=TREE,
            ci_status="PASS",
            ci_run_id="1",
            cloud_runtime_audit_pass=True,
            cloud_audit_consume_id=identity,
            cloud_audit_dispatched=True,
            dag_generation=92,
        ),
    )
    live = PrHeadRef(pr_number=429, head_sha=HEAD, tree_sha=TREE)
    controller = LiveDagController(
        tmp_path,
        refresh=lambda: live,
        observe=lambda _sha: CiObservation(
            head_sha=HEAD, run_id="1", status="PASS", conclusion="success"
        ),
        real_sdk_backend=True,
    )
    state, items = controller.tick()
    assert state.cloud_runtime_audit_pass is True
    assert state.cloud_audit_consume_id == identity
    assert any(i.role == AgentRole.INDEPENDENT_VERIFIER for i in items)


def test_writer_forged_repo_json_does_not_dispatch_iv_adv(tmp_path: Path) -> None:
    evidence = tmp_path / REPO_EVIDENCE_REL
    evidence.parent.mkdir(parents=True)
    evidence.write_text(
        '{"six_p1_runtime_open_count": 0, "wiring_verified": {"RESULT_BINDING": "PASS"}}\n',
        encoding="utf-8",
    )
    persist_live_dag(
        tmp_path,
        LiveDagState(
            bound_head=HEAD,
            bound_tree=TREE,
            ci_status="PASS",
            ci_run_id="32407694619",
            cloud_runtime_audit_pass=True,
            dag_generation=92,
        ),
    )
    live = PrHeadRef(pr_number=429, head_sha=HEAD, tree_sha=TREE)
    controller = LiveDagController(
        tmp_path,
        refresh=lambda: live,
        observe=lambda _sha: CiObservation(
            head_sha=HEAD, run_id="32407694619", status="PASS", conclusion="success"
        ),
        real_sdk_backend=True,
    )
    state, items = controller.tick()
    assert state.cloud_runtime_audit_pass is False
    assert all(i.role != AgentRole.INDEPENDENT_VERIFIER for i in items)
    assert all(i.role != AgentRole.SECURITY_REVIEWER for i in items)
    assert any(i.role == AgentRole.CLOUD_RUNTIME_AUDITOR for i in items)


def test_invalidate_marks_assignment_stale(tmp_path: Path) -> None:
    persist_cloud_audit_assignment(tmp_path, _assignment())
    invalidate_cloud_audit_assignment(tmp_path)
    from project_atlas.orchestration.sdk.audit_provenance import (
        load_cloud_audit_assignment,
    )

    stored = load_cloud_audit_assignment(tmp_path)
    assert stored is not None
    assert stored.stale is True
