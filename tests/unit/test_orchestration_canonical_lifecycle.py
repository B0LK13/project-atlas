"""AS-ORCH-001D-R3 real canonical lifecycle, parity, and structural guards."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from tests.unit.test_orchestration_dispatcher import (
    ScriptedRunner,
    _ok_outcome,
    _payload,
    _request_prompt,
    _target_payload,
    _workspace,
)

from project_atlas.agent_control import postflight as core_postflight
from project_atlas.agent_control import receipt_gate as core_receipt_gate
from project_atlas.agent_control.runtime import ensure_control_plane_importable
from project_atlas.orchestration.agent_transport import ProcessRunRequest
from project_atlas.orchestration.canonical_session_receipt import (
    load_managed_session,
    workspace_project_id,
)
from project_atlas.orchestration.cursor_bridge import stage_result
from project_atlas.orchestration.dispatcher import (
    DispatcherError,
    DispatchStatus,
    load_record,
    load_result_binding,
    run_dispatch_once,
    submit_target_result,
)


def _dispatch_id(request: ProcessRunRequest) -> str:
    return _request_prompt(request).rsplit("dispatch-submit-result ", 1)[1].split()[0]


def test_control_plane_parity_shares_validate_issue_and_postflight() -> None:
    ensure_control_plane_importable()
    from agent_control import postflight as sibling_postflight
    from agent_control import receipt_gate as sibling_receipt_gate

    assert sibling_receipt_gate.validate is core_receipt_gate.validate
    assert sibling_receipt_gate.issue is core_receipt_gate.issue
    assert sibling_postflight.run is core_postflight.run


def test_orchestration_does_not_reimplement_receipt_gate() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "project_atlas" / "orchestration"
    forbidden = (
        "def _validate_gate_state",
        "_REQUIRED_EVENTS",
        "DETERMINISTIC_EVENT_TIME",
        "1970-01-01T00:00:00Z",
        "def build_managed_session_state",
        "def issue_managed_dispatch_receipt",
        "capture pipeline is not normalized, verified and routed",
        "missing required event: session-start",
    )
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{path.name} reimplements {needle}"
    adapter = (root / "canonical_session_receipt.py").read_text(encoding="utf-8")
    assert "receipt_gate.validate" in adapter
    assert "canonical_postflight_run" in adapter
    assert "document_event" in adapter
    assert "bootstrap_start" in adapter


def test_real_lifecycle_records_canonical_events_then_issues_receipt(tmp_path: Path) -> None:
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
        mid_record = load_record(workspace, captured["id"])
        assert mid_record is not None and mid_record.managed_session_id is not None
        mid = load_managed_session(workspace, mid_record.managed_session_id)
        assert mid["events"]["session-start"]
        assert mid["events"]["validation"]
        assert not mid["events"].get("completion")
        assert mid["pipeline"]["captured"] >= 2
        assert mid["pipeline"]["verified"] == mid["pipeline"]["captured"]
        assert mid["pipeline"]["routed"] == mid["pipeline"]["captured"]

    receipt = run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    assert receipt.status is DispatchStatus.COMPLETED
    record = load_record(workspace, captured["id"])
    assert record is not None and record.managed_session_id is not None
    state = load_managed_session(workspace, record.managed_session_id)
    assert state["events"]["session-start"]
    assert state["events"]["validation"]
    assert state["events"]["completion"]
    assert state["receipt_id"] == receipt.target_receipt_id
    assert not any(str(item).startswith("1970-01-01") for item in str(state).split())
    assert core_receipt_gate.validate(state) == []
    binding = load_result_binding(workspace, captured["id"])
    assert binding is not None
    assert binding.raw_target_result_digest
    assert binding.normalized_target_result_digest
    assert binding.raw_target_result_digest != binding.normalized_target_result_digest
    assert binding.envelope.producer.role.value == "integration"
    assert binding.envelope.task.id == f"d.{captured['id']}"
    assert workspace_project_id(workspace) == state["session"]["project_id"]


def test_preflight_failure_does_not_start_process(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    (workspace / ".atlas" / "project.yaml").unlink()
    stage_result(_payload(), root=workspace)
    runner = ScriptedRunner(_ok_outcome())
    receipt = run_dispatch_once(root=workspace, runner=runner)
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code == "PREFLIGHT_FAILED"
    assert receipt.process_started is False
    assert receipt.source_acknowledged is False
    assert runner.requests == []


def test_pipeline_failure_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = _dispatch_id(request)
        monkeypatch.setenv("ATLAS_MDA_COMMAND", str(tmp_path / "missing-mda"))
        with pytest.raises(DispatcherError):
            submit_target_result(
                captured["id"],
                _target_payload(f"d.{captured['id']}"),
                root=workspace,
            )

    runner = ScriptedRunner(_ok_outcome(), on_run=on_run)
    receipt = run_dispatch_once(root=workspace, runner=runner)
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code in {
        "PIPELINE_UNAVAILABLE",
        "PIPELINE_FAILED",
        "VALIDATION_EVENT_FAILED",
        "RESULT_NOT_SUBMITTED",
    }
    assert receipt.source_acknowledged is False
    assert receipt.result_staged is False


def test_receipt_collision_fails_closed(tmp_path: Path) -> None:
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
        record = load_record(workspace, captured["id"])
        assert record is not None and record.managed_session_id is not None
        expected = "ASR-" + hashlib.sha256(record.managed_session_id.encode()).hexdigest()[:16]
        receipts = workspace / ".atlas" / "receipts"
        receipts.mkdir(parents=True, exist_ok=True)
        (receipts / f"{expected}.json").write_text(
            f'{{"receipt_id":"{expected}","status":"forged"}}\n',
            encoding="utf-8",
        )

    receipt = run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code in {"POSTFLIGHT_FAILED", "RECEIPT_TAMPERED", "RECEIPT_NOT_VALID"}
    assert receipt.source_acknowledged is False


def test_postflight_paths_produce_equivalent_receipt_semantics(tmp_path: Path) -> None:
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
    ensure_control_plane_importable()
    from agent_control.postflight import run as sibling_run

    second = sibling_run(workspace, record.managed_session_id)
    assert second["ok"] is True
    assert second["receipt"]["receipt_id"] == receipt.target_receipt_id
    assert second["receipt"]["is_authority"] is False
    assert second["receipt"]["receipt_is_authority"] is False
    assert sibling_run is core_postflight.run
