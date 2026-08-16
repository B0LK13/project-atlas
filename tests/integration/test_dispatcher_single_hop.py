"""AS-ORCH-001D integration: one hop, no loop, explicit completion, fake transport."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.agent_transport import ProcessRunOutcome, ProcessRunRequest
from project_atlas.orchestration.cursor_bridge import complete_staged_handoff, stage_result
from project_atlas.orchestration.dispatcher import (
    DispatchStatus,
    recover_dispatch,
    run_dispatch_once,
    submit_target_result,
)


def _dispatch_id_from_request(request: ProcessRunRequest) -> str:
    if request.stdin is None:
        raise AssertionError("dispatch prompt must travel on stdin")
    return request.stdin.decode("utf-8").rsplit("dispatch-submit-result ", 1)[1].split()[0]


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "AGENTS.md").write_text("# Atlas\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "project-atlas"\n',
        encoding="utf-8",
    )
    return tmp_path.resolve()


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
    for key, value in overrides.items():
        if key == "observations" and isinstance(value, dict):
            merged = dict(data["observations"])
            merged.update(value)
            data["observations"] = merged
        else:
            data[key] = value
    return data


class RecordingRunner:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.requests: list[ProcessRunRequest] = []

    def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
        self.requests.append(request)
        dispatch_id = _dispatch_id_from_request(request)
        submit_target_result(
            dispatch_id,
            {
                "schema_version": 1,
                "producer": {"role": "integration", "agent_id": "iv-agent"},
                "task": {"id": f"d.{dispatch_id}", "attempt": 1},
                "outcome": "PASS",
                "state": "CERTIFIED",
                "observations": {"target_moved": False, "unauthorized_mutations": 0},
                "receipt": {"receipt_id": "ASR-1234567890abcdef", "status": "valid"},
                "blockers": [],
                "requested_transition": "MERGE",
            },
            root=self.workspace,
        )
        return ProcessRunOutcome(
            exit_code=0,
            stdout=json.dumps(
                {"type": "result", "is_error": False, "result": "done"}
            ).encode(),
            stderr=b"",
            timed_out=False,
            duration_ms=5,
        )


def test_single_hop_produces_next_handoff_and_stops(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    source = complete_staged_handoff(root=workspace)
    assert source.state == "HANDOFF_READY"
    runner = RecordingRunner(workspace)
    receipt = run_dispatch_once(root=workspace, runner=runner)
    assert receipt.status is DispatchStatus.COMPLETED
    assert len(runner.requests) == 1
    assert receipt.next_handoff_state is not None
    assert receipt.next_handoff_autodispatched is False
    nxt = complete_staged_handoff(root=workspace)
    assert nxt.route_digest == receipt.next_route_digest
    assert nxt.dispatch_performed is False
    assert nxt.execution_authorized is False
    assert receipt.target_role is not None
    assert receipt.target_role.value == "integration"
    runtime = workspace / ".atlas" / "orchestration" / "dispatcher"
    assert runtime.is_dir()


def test_recertification_is_read_only_dispatchable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(observations={"target_moved": True}), root=workspace)
    runner = RecordingRunner(workspace)
    receipt = run_dispatch_once(root=workspace, runner=runner)
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.task_type is not None
    assert receipt.task_type.value == "recertification"
    assert len(runner.requests) == 1


def test_recover_cli_without_respawn(tmp_path: Path, monkeypatch: Any) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    from project_atlas.orchestration import dispatcher as dispatcher_mod

    real = dispatcher_mod.finalize_dispatch
    state = {"boom": True}

    def once(*args: Any, **kwargs: Any) -> Any:
        if state["boom"]:
            state["boom"] = False
            raise RuntimeError("crash")
        return real(*args, **kwargs)

    monkeypatch.setattr(dispatcher_mod, "finalize_dispatch", once)
    runner = RecordingRunner(workspace)
    with pytest.raises(RuntimeError):
        run_dispatch_once(root=workspace, runner=runner)
    dispatch_id = _dispatch_id_from_request(runner.requests[0])
    monkeypatch.setattr(dispatcher_mod, "finalize_dispatch", real)
    recover_code = main(
        ["orchestrator", "dispatch-recover", dispatch_id, "--root", str(workspace)]
    )
    assert recover_code == EXIT_OK
    recovered = recover_dispatch(dispatch_id, root=workspace)
    assert recovered.status is DispatchStatus.COMPLETED
    assert len(runner.requests) == 1


def test_requested_merge_is_advisory_only(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    receipt = run_dispatch_once(root=workspace, runner=RecordingRunner(workspace))
    assert receipt.execution_authorized is False
    assert receipt.authority_granted is False
    nxt = complete_staged_handoff(root=workspace)
    assert nxt.state != "OWNER_REQUIRED" or nxt.execution_authorized is False
    assert nxt.dispatch_performed is False
