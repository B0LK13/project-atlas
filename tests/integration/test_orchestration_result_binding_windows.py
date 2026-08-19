"""Authentic Windows process capture for AS-ORCH-001D result binding."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from project_atlas.orchestration.agent_transport import (
    ProcessRunOutcome,
    ProcessRunRequest,
    SubprocessProcessRunner,
    build_launch_plan,
    frame_result_payload,
    resolve_cursor_transport,
    sanitize_inherited_env,
)
from project_atlas.orchestration.cursor_bridge import require_verified_state, stage_result
from project_atlas.orchestration.dispatcher import (
    DispatcherConfig,
    DispatchStatus,
    compute_dispatch_id,
    dispatch_task_id_for,
    load_result_binding,
    run_dispatch_once,
    submit_target_result,
)


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "AGENTS.md").write_text("# Atlas\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "project-atlas"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "project_atlas").mkdir(parents=True)
    return tmp_path


def _source_payload() -> dict[str, object]:
    return {
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


def _target_envelope(root: Path) -> dict[str, object]:
    verified = require_verified_state(root)
    assert verified.route.target.role is not None
    assert verified.route.task_type is not None
    dispatch_id = compute_dispatch_id(
        route_digest=verified.route_digest,
        target_role=verified.route.target.role,
        task_type=verified.route.task_type,
        source_task=verified.envelope.task.id,
    )
    return {
        "schema_version": 1,
        "producer": {"role": verified.route.target.role.value, "agent_id": "iv-agent"},
        "task": {"id": dispatch_task_id_for(dispatch_id), "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {
            "target_moved": False,
            "unauthorized_mutations": 0,
            "extras": {
                "dispatch_id": dispatch_id,
                "lease_id": "LEASE-WIN-001",
                "package_id": "D-137",
                "base_main": "a" * 40,
                "candidate_head": "b" * 40,
                "candidate_tree": "c" * 40,
                "evidence_reference": "tests/integration/result-binding",
            },
        },
        "receipt": {"receipt_id": "ASR-winbind0001", "status": "valid"},
        "blockers": [],
        "requested_transition": None,
    }


@pytest.mark.skipif(os.name != "nt", reason="authentic Windows CreateProcess result binding")
def test_windows_process_captures_and_binds_framed_result(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    envelope = _target_envelope(root)
    stdout_obj = {
        "type": "result",
        "result": "notes\n" + frame_result_payload(envelope),
        "session_id": "win-s1",
    }
    (root / "result-stdout.txt").write_text(
        json.dumps(stdout_obj, sort_keys=True) + "\n",
        encoding="ascii",
    )
    launcher = tmp_path / "agent.cmd"
    launcher.write_text(
        "@echo off\r\n"
        "type result-stdout.txt\r\n"
        "exit /b 0\r\n",
        encoding="ascii",
    )
    resolved = resolve_cursor_transport(str(launcher))
    plan = build_launch_plan(resolved, "trusted prompt body", cwd=root)
    assert plan.launcher_kind.value == "windows_cmd_wrapper"
    assert plan.argv[1:3] == ("/d", "/c")
    assert "--force" not in plan.argv
    assert plan.cursor_mode == "ask"
    smoke = SubprocessProcessRunner().run(
        ProcessRunRequest(
            argv=tuple(plan.argv),
            cwd=root,
            timeout_seconds=15,
            env=sanitize_inherited_env(),
            stdin=plan.stdin_payload.encode("utf-8"),
        )
    )
    assert smoke.timed_out is False
    assert smoke.exit_code == 0

    class _Runner:
        def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
            assert request.argv[1:3] == ("/d", "/c")
            assert "--force" not in request.argv
            return SubprocessProcessRunner().run(request)

    receipt = run_dispatch_once(
        root=root,
        runner=_Runner(),
        config=DispatcherConfig(
            lease_id="LEASE-WIN-001",
            bound_package_id="D-137",
            base_main="a" * 40,
            candidate_head="b" * 40,
            candidate_tree="c" * 40,
            executable=str(launcher),
        ),
    )
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.process_started is True
    assert receipt.result_received is True
    assert receipt.result_staged is True
    assert receipt.execution_authorized is False
    assert receipt.dispatch_id is not None
    binding = load_result_binding(root, receipt.dispatch_id)
    assert binding is not None
    with pytest.raises(Exception) as exc:
        submit_target_result(receipt.dispatch_id, envelope, root=root)
    assert getattr(exc.value, "code", "") in {"DUPLICATE_RESULT", "RESULT_AFTER_FINALIZATION"}


@pytest.mark.skipif(os.name != "nt", reason="authentic Windows CreateProcess result binding")
def test_windows_process_rejects_wrong_dispatch_id(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    envelope = _target_envelope(root)
    extras = envelope["observations"]["extras"]  # type: ignore[index]
    assert isinstance(extras, dict)
    extras["dispatch_id"] = "d" * 64
    (root / "result-stdout.txt").write_text(
        json.dumps(
            {"type": "result", "result": frame_result_payload(envelope), "session_id": "win-bad"},
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )
    launcher = tmp_path / "agent.cmd"
    launcher.write_text(
        "@echo off\r\n"
        "type result-stdout.txt\r\n"
        "exit /b 0\r\n",
        encoding="ascii",
    )

    class _Runner:
        def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
            assert request.argv[1:3] == ("/d", "/c")
            return SubprocessProcessRunner().run(request)

    receipt = run_dispatch_once(
        root=root,
        runner=_Runner(),
        config=DispatcherConfig(
            lease_id="LEASE-WIN-001",
            bound_package_id="D-137",
            base_main="a" * 40,
            candidate_head="b" * 40,
            candidate_tree="c" * 40,
            executable=str(launcher),
        ),
    )
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code == "WRONG_DISPATCH_ID"
    assert receipt.result_received is False
    assert receipt.execution_authorized is False
