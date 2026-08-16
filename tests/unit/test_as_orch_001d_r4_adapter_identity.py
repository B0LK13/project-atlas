"""AS-ORCH-001D-R4 Cursor CLI adapter identity honesty."""

from __future__ import annotations

import json
from pathlib import Path

from tests.unit.test_orchestration_dispatcher import (
    ScriptedRunner,
    _ok_outcome,
    _payload,
    _request_prompt,
    _target_payload,
    _workspace,
)

from project_atlas.orchestration.agent_transport import ProcessRunRequest
from project_atlas.orchestration.canonical_session_receipt import (
    CANONICAL_ADAPTER_ID,
    MANAGED_AGENT_ID,
    MANAGED_AGENT_TRANSPORT,
    MANAGED_AGENT_TYPE,
    load_canonical_receipt,
    load_managed_session,
)
from project_atlas.orchestration.cursor_bridge import stage_result
from project_atlas.orchestration.dispatcher import (
    DispatchStatus,
    load_record,
    run_dispatch_once,
    submit_target_result,
)


def _dispatch_id(request: ProcessRunRequest) -> str:
    return _request_prompt(request).rsplit("dispatch-submit-result ", 1)[1].split()[0]


def test_cursor_cli_constants_are_truthful() -> None:
    assert MANAGED_AGENT_TRANSPORT == "CURSOR_CLI"
    assert MANAGED_AGENT_TYPE == "cli"
    assert MANAGED_AGENT_ID == "cursor-agent-cli"
    assert CANONICAL_ADAPTER_ID == "generic-cli-v1"


def test_cursor_cli_dispatch_uses_canonical_cli_adapter(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = _dispatch_id(request)
        submit_target_result(
            captured["id"],
            _target_payload(f"d.{captured['id']}"),
            root=workspace,
        )

    receipt = run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    assert receipt.status is DispatchStatus.COMPLETED
    record = load_record(workspace, captured["id"])
    assert record is not None and record.managed_session_id is not None
    state = load_managed_session(workspace, record.managed_session_id)
    agent = state["agent"]
    preflight = state["preflight"]
    assert agent["agent_id"] == "cursor-agent-cli"
    assert agent["adapter_id"] == "generic-cli-v1"
    assert agent["agent_type"] == "cli-agent"
    assert preflight["ok"] is True
    assert preflight["agent"]["adapter_id"] == "generic-cli-v1"
    assert preflight["agent"]["agent_type"] == "cli-agent"
    assert preflight["readiness"]["authorized"] is True
    assert preflight["readiness"]["reason"] != "pending"
    serialized = json.dumps(state, sort_keys=True)
    assert "ide-agent-v1" not in serialized
    assert '"agent_type": "ide"' not in serialized
    assert "cursor-ide" not in serialized
    issued = load_canonical_receipt(workspace, str(state["receipt_id"]))
    assert issued["agent"]["adapter_id"] == "generic-cli-v1"
    assert issued["agent"]["agent_id"] == "cursor-agent-cli"
    assert issued["agent"]["agent_type"] == "cli-agent"
    assert "ide-agent-v1" not in json.dumps(issued)


def test_ide_pending_readiness_is_not_used(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    readiness = (workspace / ".atlas" / "readiness.yaml").read_text(encoding="utf-8")
    assert "generic-cli-v1:" in readiness
    assert "rehearsal_status: passed" in readiness
    assert "ide-agent-v1:" in readiness
    assert readiness.index("ide-agent-v1:") < readiness.rindex("rehearsal_status: pending")
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = _dispatch_id(request)
        submit_target_result(
            captured["id"],
            _target_payload(f"d.{captured['id']}"),
            root=workspace,
        )

    receipt = run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    assert receipt.status is DispatchStatus.COMPLETED
    record = load_record(workspace, captured["id"])
    assert record is not None and record.managed_session_id is not None
    state = load_managed_session(workspace, record.managed_session_id)
    assert state["preflight"]["agent"]["adapter_id"] == "generic-cli-v1"
    assert state["agent"]["adapter_id"] != "ide-agent-v1"


def test_revoked_cli_adapter_fails_closed_without_override(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    registry = workspace / ".atlas" / "readiness.yaml"
    registry.write_text(
        registry.read_text(encoding="utf-8").replace(
            "  generic-cli-v1:\n"
            "    skill_version: 1.0.0\n"
            "    skill_sha256: e830c4fcec547640ecb618c4d80d0256c39b49cf7075f4af57aaf7b38dc40ee9\n"
            "    rehearsal_status: passed\n"
            "    revoked: false\n",
            "  generic-cli-v1:\n"
            "    skill_version: 1.0.0\n"
            "    skill_sha256: e830c4fcec547640ecb618c4d80d0256c39b49cf7075f4af57aaf7b38dc40ee9\n"
            "    rehearsal_status: passed\n"
            "    revoked: true\n",
            1,
        ),
        encoding="utf-8",
    )
    stage_result(_payload(), root=workspace)
    runner = ScriptedRunner(_ok_outcome())
    receipt = run_dispatch_once(root=workspace, runner=runner)
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code == "PREFLIGHT_FAILED"
    assert receipt.process_started is False
    assert runner.requests == []
