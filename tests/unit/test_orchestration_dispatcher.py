"""AS-ORCH-001D single-hop dispatcher: eligibility, no auto-dispatch, no respawn."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.agent_transport import ProcessRunOutcome, ProcessRunRequest
from project_atlas.orchestration.cursor_bridge import stage_result
from project_atlas.orchestration.dispatcher import (
    DispatcherError,
    DispatchReceipt,
    DispatchStatus,
    compute_dispatch_id,
    dispatch_task_id_for,
    recover_dispatch,
    run_dispatch_once,
)
from project_atlas.orchestration.models import ProducerRole, TaskType
from project_atlas.schema import validate_record


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "AGENTS.md").write_text("# Atlas\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "project-atlas"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "project_atlas").mkdir(parents=True)
    return tmp_path


def _payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": 1,
        "producer": {"role": "local", "agent_id": "local-agent"},
        "task": {"id": "D-137", "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {"target_moved": False, "unauthorized_mutations": 0},
        "receipt": {"receipt_id": "ASR-1234567890abcdef", "status": "valid"},
        "blockers": [],
        "requested_transition": None,
    }
    data.update(overrides)
    return data


class _FakeRunner:
    def __init__(self, outcome: ProcessRunOutcome) -> None:
        self.requests: list[ProcessRunRequest] = []
        self.outcome = outcome

    def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
        self.requests.append(request)
        return self.outcome


def test_owner_gate_does_not_start_process(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(
        _payload(producer={"role": "integration", "agent_id": "iv"}, state="MERGE_ELIGIBLE"),
        root=root,
    )
    runner = _FakeRunner(
        ProcessRunOutcome(exit_code=0, stdout=b"", stderr=b"", timed_out=False, duration_ms=1)
    )
    receipt = run_dispatch_once(root=root, runner=runner)
    assert receipt.status is DispatchStatus.OWNER_REQUIRED
    assert receipt.process_started is False
    assert receipt.execution_authorized is False
    assert receipt.next_handoff_autodispatched is False
    assert runner.requests == []


def test_terminal_handoff_does_not_start_process(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_payload(receipt=None), root=root)
    runner = _FakeRunner(
        ProcessRunOutcome(exit_code=0, stdout=b"", stderr=b"", timed_out=False, duration_ms=1)
    )
    receipt = run_dispatch_once(root=root, runner=runner)
    assert receipt.status is DispatchStatus.TERMINAL
    assert receipt.process_started is False
    assert runner.requests == []


def test_mutating_task_is_rejected_without_process(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(
        _payload(
            producer={"role": "integration", "agent_id": "iv"},
            outcome="FAIL",
            state="RECERTIFY_REQUIRED",
        ),
        root=root,
    )
    runner = _FakeRunner(
        ProcessRunOutcome(exit_code=0, stdout=b"", stderr=b"", timed_out=False, duration_ms=1)
    )
    receipt = run_dispatch_once(root=root, runner=runner)
    assert receipt.process_started is False
    assert receipt.failure_code in {
        "CAPABILITY_REQUIRED",
        "ELIGIBILITY_REJECTED",
        "ROUTE_NOT_DISPATCHABLE",
    }
    if receipt.failure_code == "CAPABILITY_REQUIRED":
        assert receipt.mutating_remediation_auto_dispatch is not None
    assert runner.requests == []


def test_dispatch_id_is_deterministic() -> None:
    digest = "a" * 64
    first = compute_dispatch_id(
        route_digest=digest,
        target_role=ProducerRole.INTEGRATION,
        task_type=TaskType.CANDIDATE_VERIFICATION,
        source_task="D-137",
    )
    second = compute_dispatch_id(
        route_digest=digest,
        target_role="integration",
        task_type="candidate_verification",
        source_task="D-137",
    )
    assert first == second
    assert dispatch_task_id_for(first) == f"d.{first}"


def test_receipt_cannot_grant_authority() -> None:
    with pytest.raises(ValidationError):
        DispatchReceipt.model_validate(
            {
                "status": "completed",
                "execution_authorized": True,
                "authority_granted": False,
                "dispatch_receipt_is_authority": False,
                "next_handoff_autodispatched": False,
            }
        )


def test_recover_does_not_respawn(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    with pytest.raises(DispatcherError) as exc:
        recover_dispatch("b" * 64, root=root)
    assert exc.value.code in {"UNKNOWN_DISPATCH", "CRASH_RECOVERY_DOES_NOT_RESPAWN"}


def test_handoff_ready_without_submitted_result_fails_closed(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_payload(), root=root)
    runner = _FakeRunner(
        ProcessRunOutcome(
            exit_code=0,
            stdout=b'{"type":"result","result":"ok","session_id":"s1"}',
            stderr=b"",
            timed_out=False,
            duration_ms=5,
        )
    )
    receipt = run_dispatch_once(root=root, runner=runner)
    assert receipt.process_started is True
    assert receipt.next_handoff_autodispatched is False
    assert receipt.dispatch_receipt_is_authority is False
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code == "RESULT_NOT_SUBMITTED"
    assert len(runner.requests) == 1
    assert runner.requests[0].stdin is not None


def test_dispatch_receipt_schema() -> None:
    validate_record(
        {
            "schema_version": 1,
            "package_id": "AS-ORCH-001D",
            "status": "REJECTED",
            "process_started": False,
            "execution_authorized": False,
            "authority_granted": False,
            "dispatch_receipt_is_authority": False,
            "next_handoff_autodispatched": False,
        },
        "dispatch-receipt",
    )
