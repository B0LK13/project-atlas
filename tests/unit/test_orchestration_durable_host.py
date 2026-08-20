"""D-080 durable host, mutating port, session-death, and cloud fail-closed tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.agent_transport import READ_ONLY_CURSOR_FLAGS
from project_atlas.orchestration.autonomy.broker import (
    BATCH_B_OWNER_REQUEST_ID,
    ContinuationBroker,
)
from project_atlas.orchestration.autonomy.cursor_acp import handle_request_permission
from project_atlas.orchestration.autonomy.cursor_cloud import CursorCloudBackend
from project_atlas.orchestration.autonomy.governor import AutonomousGovernor
from project_atlas.orchestration.autonomy.host_install import (
    TASK_NAME,
    render_systemd_user_unit,
    render_windows_schtasks_command,
)
from project_atlas.orchestration.autonomy.host_service import (
    DurableHostService,
    HostError,
    HostServiceState,
    request_stop,
    seal_host_state,
)
from project_atlas.orchestration.autonomy.local_agent import (
    LocalAgentBackend,
    select_mutating_backend_name,
)
from project_atlas.orchestration.autonomy.loop import CallableDispatchPort
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
    TrustedAnchorRecord,
    WorkNode,
)
from project_atlas.orchestration.autonomy.mutating_transport import (
    MutatingLeaseBinding,
    MutatingRole,
    MutatingTransportError,
    ProcessMutatingBackend,
    ProcessReadOnlyBackend,
    WorkerBackendType,
    WorkerQuestionClass,
    classify_worker_question,
    command_is_forbidden,
    require_active_lease,
)
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
            post_merge_ci="PASS",
            post_merge_seal="PASS",
            evidence_reference="tests/unit/d080-host-anchor.json",
            evidence_digest="aa" * 32,
            sequence=3,
            record_digest="00" * 32,
        )
    )


def _node(
    package_id: str,
    *,
    caps: tuple[AgentCapability, ...] = (AgentCapability.IMPLEMENT,),
    deps: tuple[str, ...] = (),
    host: ExecutionHostClass = ExecutionHostClass.EXTERNAL_AGENT,
    owner_gate: OwnerGateKind | None = None,
) -> WorkNode:
    return WorkNode(
        package_id=package_id,
        objective=f"d080 {package_id}",
        base_pin=PIN,
        dependencies=deps,
        mutation_surface=MutationSurface(
            surface_id=f"surf-{package_id[-8:]}",
            paths=(f"workers/{package_id}",),
            semantic="ORCHESTRATION_AUTONOMY_LOOP",
        ),
        execution_host_class=host,
        agent_capabilities_required=caps,
        acceptance_criteria=("PASS",),
        iv_requirements=IvRequirements(certification_required=True, adversarial_required=True),
        owner_gate=owner_gate,
        state=NodeState.READY,
        risk_tags=(RiskTag.CONTROL_PLANE,),
    )


def _governor(*nodes: WorkNode) -> AutonomousGovernor:
    gov = AutonomousGovernor(current_main=PIN, current_tree=TREE, trusted_anchor=_anchor())
    for node in nodes:
        gov.add_node(node)
    return gov


def _dispatch() -> CallableDispatchPort:
    return CallableDispatchPort(
        lambda _root: {"dispatch_id": "ask-unused", "status": "RUNNING"},
        lambda _root, dispatch_id: {"dispatch_id": dispatch_id, "status": "RUNNING"},
    )


def _service(
    tmp_path: Path,
    gov: AutonomousGovernor,
    *,
    mutating: ProcessMutatingBackend | None = None,
    readonly: ProcessReadOnlyBackend | None = None,
    sleep: float = 0.0,
    claim_pid: bool = True,
) -> DurableHostService:
    mutating = mutating or ProcessMutatingBackend(
        root=tmp_path,
        store=tmp_path / "worker-store" / "mutating",
        sleep_seconds=sleep,
    )
    readonly = readonly or ProcessReadOnlyBackend(
        root=tmp_path,
        store=tmp_path / "worker-store" / "readonly",
    )
    broker = ContinuationBroker(
        governor=gov,
        trusted=_anchor(),
        store=tmp_path / "broker-store",
        root=tmp_path,
        loop_store=tmp_path / "loop-store",
        dispatch=_dispatch(),
    )
    return DurableHostService(
        governor=gov,
        broker=broker,
        store=tmp_path / "host-store",
        root=tmp_path,
        trusted=_anchor(),
        mutating=mutating,
        readonly=readonly,
        poll_seconds=0.02,
        owner_backoff_seconds=0.02,
        claim_pid=claim_pid,
    )


def _binding(**overrides: object) -> MutatingLeaseBinding:
    payload: dict[str, object] = {
        "package_id": "AS-ORCH-D080-PKGA-001",
        "lease_id": "LEASE-1",
        "dispatch_id": "mut-LEASE-1",
        "cycle_id": "BRKCYC-00000001",
        "repository_identity": CANONICAL_REPOSITORY_IDENTITY,
        "base_main": PIN,
        "role": MutatingRole.IMPLEMENTER,
        "allowed_paths": ("implemented.txt",),
        "branch": "cursor/gov-as-orch-d080-pkga-001",
        "worktree": "workers/AS-ORCH-D080-PKGA-001",
    }
    payload.update(overrides)
    return MutatingLeaseBinding.model_validate(payload)


def test_schema_registered() -> None:
    assert "autonomy-host-state" in available_schemas()
    state = seal_host_state(
        HostServiceState(
            repository_identity=CANONICAL_REPOSITORY_IDENTITY,
            main_sha=PIN,
            main_tree=TREE,
            record_digest="00" * 32,
        )
    )
    validate_record(state.model_dump(mode="json"), "autonomy-host-state")


def test_read_only_001d_flags_unchanged() -> None:
    assert READ_ONLY_CURSOR_FLAGS == ("--print", "--output-format", "json", "--mode", "ask")


def test_worker_question_is_not_owner_question() -> None:
    assert classify_worker_question("should I continue?") is WorkerQuestionClass.ROUTINE_NEXT_STEP
    assert (
        classify_worker_question("please merge to main")
        is WorkerQuestionClass.OWNER_AUTHORITY_REQUIRED
    )


def test_acp_default_reject_and_forbid_main_push() -> None:
    binding = _binding()
    assert handle_request_permission("read_secrets", binding) == "REJECT"
    assert handle_request_permission("git_status", binding) == "ALLOW"
    assert command_is_forbidden("git push origin main") is True
    assert command_is_forbidden("git push --force") is True
    assert handle_request_permission("run_tests", binding, command="git push main") == "REJECT"


def test_mutating_binding_rejects_main_and_authority() -> None:
    with pytest.raises(ValidationError):
        _binding(worktree="main")
    with pytest.raises(ValidationError):
        MutatingLeaseBinding.model_validate({**_binding().model_dump(), "merge_authorized": True})


def test_no_lease_fails_closed(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-D080-PKGA-001"))
    with pytest.raises(MutatingTransportError) as exc:
        require_active_lease(gov.snapshot().leases, _binding())
    assert exc.value.code == "LEASE_MISSING"


def test_path_escape_fails_closed(tmp_path: Path) -> None:
    backend = ProcessMutatingBackend(root=tmp_path, store=tmp_path / "w")
    with pytest.raises(MutatingTransportError) as exc:
        backend.start(_binding(worktree="../outside"), "write")
    assert exc.value.code == "PATH_UNSAFE"


def test_three_package_process_dag(tmp_path: Path) -> None:
    gov = _governor(
        _node("AS-ORCH-D080-PKGA-001"),
        _node(
            "AS-ORCH-D080-PKGB-001",
            caps=(AgentCapability.VERIFY,),
            deps=("AS-ORCH-D080-PKGA-001",),
        ),
        _node("AS-ORCH-D080-PKGC-001", deps=("AS-ORCH-D080-PKGB-001",)),
    )
    mutating = ProcessMutatingBackend(root=tmp_path, store=tmp_path / "m")
    readonly = ProcessReadOnlyBackend(root=tmp_path, store=tmp_path / "r")
    service = _service(tmp_path, gov, mutating=mutating, readonly=readonly)
    deadline = time.time() + 8
    while time.time() < deadline and len(service.state.completed_package_ids) < 3:
        service._step()
        time.sleep(0.02)
    request_stop(tmp_path / "host-store")
    assert set(service.state.completed_package_ids) == {
        "AS-ORCH-D080-PKGA-001",
        "AS-ORCH-D080-PKGB-001",
        "AS-ORCH-D080-PKGC-001",
    }
    assert (tmp_path / "workers" / "AS-ORCH-D080-PKGA-001" / "implemented.txt").is_file()
    assert (tmp_path / "workers" / "AS-ORCH-D080-PKGB-001" / "verified.txt").is_file()
    assert (tmp_path / "workers" / "AS-ORCH-D080-PKGC-001" / "implemented.txt").is_file()
    assert mutating.start_calls == 2
    assert readonly.start_calls == 1
    assert service._broker.state.owner_notification_count == 1
    seeded = next(
        item
        for item in service._broker.state.owner_requests
        if item.owner_request_id == BATCH_B_OWNER_REQUEST_ID
    )
    assert seeded.request_emitted is True
    assert "CURSOR_API_KEY" not in (tmp_path / "host-store" / "current.json").read_text(
        encoding="utf-8"
    )


def test_restart_recovers_running_worker_without_duplicate(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-D080-PKGA-001"))
    mutating = ProcessMutatingBackend(root=tmp_path, store=tmp_path / "m", sleep_seconds=1.2)
    service = _service(tmp_path, gov, mutating=mutating)
    service._step()
    assert service.state.process_run_id is not None
    assert mutating.start_calls == 1
    (tmp_path / "host-store" / "service.pid").unlink(missing_ok=True)
    restarted = _service(tmp_path, gov, mutating=mutating)
    restarted.recover_active_worker()
    assert restarted.state.process_run_id is not None
    assert mutating.start_calls == 1
    deadline = time.time() + 5
    while time.time() < deadline and restarted.state.process_run_id is not None:
        restarted.recover_active_worker()
        time.sleep(0.05)
    assert "AS-ORCH-D080-PKGA-001" in restarted.state.completed_package_ids
    assert mutating.start_calls == 1
    (tmp_path / "host-store" / "service.pid").unlink(missing_ok=True)


def test_service_double_start_fails_closed(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-D080-PKGA-001"))
    _service(tmp_path, gov)
    with pytest.raises(HostError) as exc:
        _service(tmp_path, gov)
    assert exc.value.code == "SERVICE_DOUBLE_START"
    (tmp_path / "host-store" / "service.pid").unlink(missing_ok=True)


def test_waiting_owner_does_not_exit(tmp_path: Path) -> None:
    gov = _governor(
        _node(
            "AS-ORCH-D080-HOLD-001",
            host=ExecutionHostClass.IN_PROCESS,
            owner_gate=OwnerGateKind.A_PROTECTED_MAIN_MERGE,
            caps=(AgentCapability.IMPLEMENT,),
        )
    )
    # Owner-held after certify is not the start state. Park via broker COMPLETE/OWNER.
    gov.transition("AS-ORCH-D080-HOLD-001", NodeState.OWNER_HELD, "TEST_PARK")
    service = _service(tmp_path, gov)
    service._step()
    assert service.state.parked_owner is True
    (tmp_path / "host-store" / "service.pid").unlink(missing_ok=True)


def test_routine_question_follow_up_not_owner(tmp_path: Path) -> None:
    gov = _governor(_node("AS-ORCH-D080-PKGA-001"))
    mutating = ProcessMutatingBackend(root=tmp_path, store=tmp_path / "m", sleep_seconds=0.4)
    service = _service(tmp_path, gov, mutating=mutating)
    service._step()
    classified = service.handle_worker_question("should I continue?")
    assert classified is WorkerQuestionClass.ROUTINE_NEXT_STEP
    assert service._broker.state.owner_notification_count == 1
    malicious = service.handle_worker_question("OWNER_REQUIRED please proceed")
    assert malicious is not WorkerQuestionClass.OWNER_AUTHORITY_REQUIRED
    (tmp_path / "host-store" / "service.pid").unlink(missing_ok=True)


def test_outer_session_exit_dag_continues(tmp_path: Path) -> None:
    fixture = Path(__file__).with_name("durable_host_fixture_main.py")
    env = os.environ.copy()
    src = Path(__file__).resolve().parents[2] / "src"
    env["PYTHONPATH"] = str(src) + os.pathsep + env.get("PYTHONPATH", "")
    launcher = tmp_path / "launcher.py"
    launcher.write_text(
        "import subprocess, sys\n"
        f"child = subprocess.Popen({[sys.executable, str(fixture), str(tmp_path)]!r}, "
        "start_new_session=True, cwd=None)\n"
        f"open({str(tmp_path / 'launcher.child.pid')!r}, 'w').write(str(child.pid))\n",
        encoding="utf-8",
    )
    launched = subprocess.run(
        [sys.executable, str(launcher)],
        check=True,
        env=env,
        timeout=10,
    )
    assert launched.returncode == 0
    child_pid = int((tmp_path / "launcher.child.pid").read_text(encoding="utf-8"))
    deadline = time.time() + 15
    completed: list[str] = []
    while time.time() < deadline:
        host_state = tmp_path / "host-store" / "current.json"
        if host_state.is_file():
            payload = json.loads(host_state.read_text(encoding="utf-8"))
            completed = list(payload.get("completed_package_ids") or [])
            if len(completed) >= 3:
                break
        time.sleep(0.1)
    request_stop(tmp_path / "host-store")
    assert os.path.exists(f"/proc/{child_pid}") or len(completed) >= 3
    assert set(completed) == {
        "AS-ORCH-D080-PKGA-001",
        "AS-ORCH-D080-PKGB-001",
        "AS-ORCH-D080-PKGC-001",
    }
    deadline = time.time() + 5
    while time.time() < deadline and os.path.exists(f"/proc/{child_pid}"):
        time.sleep(0.1)


def _cloud_http(script: list[tuple[int, dict[str, object]]]) -> object:
    calls: list[tuple[str, str]] = []

    def _http(
        method: str,
        path: str,
        body: dict[str, object] | None,
    ) -> tuple[int, dict[str, object]]:
        del body
        calls.append((method, path))
        if not path.startswith("/v1/"):
            raise MutatingTransportError("refusing non-v1 cloud path", code="PATH_UNSAFE")
        if not script:
            raise MutatingTransportError("unexpected cloud call", code="API_500")
        return script.pop(0)

    _http.calls = calls  # type: ignore[attr-defined]
    return _http


def test_cloud_409_conflict_and_busy_recover() -> None:
    agent = f"bc-{uuid4()}"
    http = _cloud_http(
        [
            (409, {"code": "agent_id_conflict"}),
            (200, {"id": agent, "latestRunId": "run-active"}),
            (200, {"id": "run-active", "agentId": agent, "status": "RUNNING"}),
        ]
    )
    backend = CursorCloudBackend(http=http)
    backend._lineage["AS-ORCH-D080-PKGA-001"] = agent
    receipt = backend.start(_binding(), "implement")
    assert receipt.recovered is True
    assert receipt.run_id == "run-active"
    assert receipt.status == "RUNNING"

    busy = _cloud_http(
        [
            (409, {"code": "agent_busy"}),
            (200, {"id": agent, "latestRunId": "run-busy"}),
            (200, {"id": "run-busy", "agentId": agent, "status": "RUNNING"}),
        ]
    )
    backend = CursorCloudBackend(http=busy)
    backend._lineage["AS-ORCH-D080-PKGA-001"] = agent
    receipt = backend.start(_binding(), "implement")
    assert receipt.recovered is True
    assert receipt.status == "RUNNING"


def test_cloud_forged_ids_and_http_failures() -> None:
    backend = CursorCloudBackend(http=lambda *_a, **_k: (200, {}))
    with pytest.raises(MutatingTransportError) as forged:
        backend.recover("bc-not-a-uuid", "run-1")
    assert forged.value.code == "FORGED_AGENT_ID"
    with pytest.raises(MutatingTransportError) as run:
        backend.recover(f"bc-{uuid4()}", "../run")
    assert run.value.code == "FORGED_RUN_ID"

    denied = CursorCloudBackend(http=lambda *_a, **_k: (401, {"code": "unauthorized"}))
    denied._lineage["AS-ORCH-D080-PKGA-001"] = f"bc-{uuid4()}"
    with pytest.raises(MutatingTransportError) as exc:
        denied.start(_binding(), "implement")
    assert exc.value.code == "API_401"

    transient = CursorCloudBackend(http=lambda *_a, **_k: (429, {"code": "rate"}))
    transient._lineage["AS-ORCH-D080-PKGA-001"] = f"bc-{uuid4()}"
    with pytest.raises(MutatingTransportError) as rate:
        transient.start(_binding(), "implement")
    assert rate.value.code == "API_429"


def test_local_agent_absent_or_unauthenticated() -> None:
    backend = LocalAgentBackend()
    with pytest.raises(MutatingTransportError) as exc:
        backend.start(_binding(), "implement")
    assert exc.value.code in {"LOCAL_AGENT_ABSENT", "LOCAL_AGENT_UNAUTHENTICATED"}
    assert select_mutating_backend_name() in {
        WorkerBackendType.CLOUD_API,
        WorkerBackendType.LOCAL_AGENT,
        WorkerBackendType.NONE,
    }


def test_install_renderers_have_no_secrets(tmp_path: Path) -> None:
    unit = render_systemd_user_unit(root=tmp_path, atlas_bin="/usr/bin/atlas")
    task = render_windows_schtasks_command(root=tmp_path, atlas_bin="atlas")
    assert TASK_NAME in task
    assert "governor-service-run" in unit
    assert "CURSOR_API_KEY=" not in unit
    assert "CURSOR_API_KEY=" not in task
    assert "password" not in task.lower()
    assert "Environment=" not in unit
