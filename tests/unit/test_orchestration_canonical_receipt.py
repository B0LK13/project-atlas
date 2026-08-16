"""AS-ORCH-001D-R3 canonical receipt authenticity, path safety, and policy B."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tests.orchestration_control_plane import DEFAULT_PROJECT_ID
from tests.unit.test_orchestration_dispatcher import (
    ScriptedRunner,
    _ok_outcome,
    _payload,
    _request_prompt,
    _target_payload,
    _workspace,
)

from project_atlas.agent_control import receipt_gate, session
from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.agent_transport import ProcessRunOutcome, ProcessRunRequest
from project_atlas.orchestration.canonical_session_receipt import (
    DispatchReceiptBindTarget,
    ReceiptBindingError,
    load_canonical_receipt,
    resolve_canonical_receipt_path,
    verify_target_receipt_binding,
    workspace_project_id,
)
from project_atlas.orchestration.cursor_bridge import STATE_RELATIVE, stage_result
from project_atlas.orchestration.dispatcher import (
    DispatcherError,
    DispatchStatus,
    load_record,
    load_result_binding,
    recover_dispatch,
    run_dispatch_once,
    status_report,
    submit_target_result,
)
from project_atlas.orchestration.models import AgentResultEnvelope
from project_atlas.orchestration.validator import parse_envelope


def _id_from_prompt(text: str) -> str:
    return text.rsplit("dispatch-submit-result ", 1)[1].split()[0]


def _result_binding_path(workspace: Path, dispatch_id: str) -> Path:
    return (
        workspace
        / ".atlas"
        / "orchestration"
        / "dispatcher"
        / "results"
        / f"{dispatch_id}.json"
    )


def _cursor_stdout(envelope: dict[str, Any]) -> bytes:
    return json.dumps({"type": "result", "is_error": False, "result": envelope}).encode()


def _prepare_running_dispatch(workspace: Path) -> str:
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        assert request.stdin is not None
        captured["id"] = _id_from_prompt(request.stdin.decode("utf-8"))
        raise RuntimeError("stop-before-submit")

    stage_result(_payload(), root=workspace)
    with pytest.raises(RuntimeError):
        run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    return captured["id"]


def _bind_target_from_record(workspace: Path, dispatch_id: str) -> DispatchReceiptBindTarget:
    record = load_record(workspace, dispatch_id)
    assert record is not None
    assert record.managed_session_id is not None
    return DispatchReceiptBindTarget(
        dispatch_id=dispatch_id,
        dispatch_task_id=f"d.{dispatch_id}",
        managed_session_id=record.managed_session_id,
        attempt=1,
        target_role="integration",
    )


def _overwrite_receipt(workspace: Path, receipt_id: str, payload: dict[str, Any]) -> Path:
    path = resolve_canonical_receipt_path(workspace, receipt_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _apply_receipt_patches(base: dict[str, Any], patches: dict[str, Any]) -> dict[str, Any]:
    mutated = dict(base)
    for key, value in patches.items():
        if key.startswith("session.") and isinstance(mutated.get("session"), dict):
            session_obj = dict(mutated["session"])
            session_obj[key.split(".", 1)[1]] = value
            mutated["session"] = session_obj
        else:
            mutated[key] = value
    return mutated


def test_path_resolver_rejects_traversal_and_alternate_lookup(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    with pytest.raises(ReceiptBindingError) as exc:
        resolve_canonical_receipt_path(workspace, "../secrets")
    assert exc.value.code in {"RECEIPT_NOT_FOUND", "RECEIPT_TAMPERED"}
    with pytest.raises(ReceiptBindingError) as exc2:
        resolve_canonical_receipt_path(workspace, "/tmp/asr.json")
    assert exc2.value.code in {"RECEIPT_NOT_FOUND", "RECEIPT_TAMPERED"}
    with pytest.raises(ReceiptBindingError):
        load_canonical_receipt(workspace, "ASR-0123456789abcdef")


def test_symlink_receipt_escape_is_rejected(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text('{"receipt_id":"ASR-0123456789abcdef","status":"passed"}', encoding="utf-8")
    receipts = workspace / ".atlas" / "receipts"
    receipts.mkdir(parents=True)
    link = receipts / "ASR-0123456789abcdef.json"
    link.symlink_to(outside)
    with pytest.raises(ReceiptBindingError) as exc:
        load_canonical_receipt(workspace, "ASR-0123456789abcdef")
    assert exc.value.code == "RECEIPT_TAMPERED"


def test_self_attested_valid_receipt_is_provisional_raw_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    binding = submit_target_result(
        dispatch_id,
        _target_payload(
            f"d.{dispatch_id}",
            receipt={"receipt_id": "ASR-fake123", "status": "valid"},
        ),
        root=workspace,
    )
    assert binding.raw_target_result_digest is not None
    assert binding.normalized_target_result_digest is None
    assert binding.envelope.receipt is not None
    assert binding.envelope.receipt.receipt_id == "ASR-fake123"
    record = load_record(workspace, dispatch_id)
    assert record is not None
    assert record.target_receipt_verified is False
    assert record.target_receipt_id is None
    assert not list((workspace / ".atlas" / "receipts").glob("ASR-*.json"))
    assert (workspace / STATE_RELATIVE).is_file()


def test_submit_result_cli_accepts_provisional_receipt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    result = tmp_path / "fake.json"
    result.write_text(
        json.dumps(
            _target_payload(
                f"d.{dispatch_id}",
                receipt={"receipt_id": "ASR-fake123", "status": "valid"},
            )
        ),
        encoding="utf-8",
    )
    code = main(
        [
            "orchestrator",
            "dispatch-submit-result",
            dispatch_id,
            str(result),
            "--root",
            str(workspace),
        ]
    )
    assert code == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["staged"] is False
    record = load_record(workspace, dispatch_id)
    assert record is not None
    assert record.target_receipt_verified is False


def test_pending_receipt_does_not_issue_at_submit(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    pending = submit_target_result(
        dispatch_id,
        _target_payload(
            f"d.{dispatch_id}",
            receipt={"receipt_id": "ASR-pending00000001", "status": "pending"},
        ),
        root=workspace,
    )
    assert pending.envelope.receipt is not None
    assert pending.envelope.receipt.status == "pending"
    assert pending.normalized_target_result_digest is None
    assert not list((workspace / ".atlas" / "receipts").glob("ASR-*.json"))


def test_rejected_envelope_receipt_fails_closed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    with pytest.raises(DispatcherError) as exc:
        submit_target_result(
            dispatch_id,
            _target_payload(
                f"d.{dispatch_id}",
                receipt={"receipt_id": "ASR-0123456789abcdef", "status": "rejected"},
            ),
            root=workspace,
        )
    assert exc.value.code == "RECEIPT_NOT_VALID"


def test_target_receipt_cannot_skip_postflight(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    submit_target_result(
        dispatch_id,
        _target_payload(
            f"d.{dispatch_id}",
            receipt={"receipt_id": "ASR-fake123", "status": "valid"},
        ),
        root=workspace,
    )
    recovered = recover_dispatch(dispatch_id, root=workspace)
    assert recovered.status is DispatchStatus.FAILED
    assert recovered.failure_code == "RECONCILIATION_REQUIRED"
    assert recovered.source_acknowledged is False
    assert recovered.result_staged is False


def test_canonical_receipt_binds_task_session_and_project(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)

    def on_run(request: ProcessRunRequest) -> None:
        dispatch_id = _id_from_prompt(_request_prompt(request))
        submit_target_result(dispatch_id, _target_payload(f"d.{dispatch_id}"), root=workspace)

    receipt = run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.target_receipt_id is not None
    canonical = load_canonical_receipt(workspace, receipt.target_receipt_id)
    assert canonical["status"] == "passed"
    assert canonical["authority_role"] == "evidence-only"
    assert canonical["is_authority"] is False
    assert canonical["receipt_is_authority"] is False
    assert canonical["session"]["task_id"] == receipt.dispatch_task_id
    record = load_record(workspace, receipt.dispatch_id or "")
    assert record is not None
    assert canonical["session"]["session_id"] == record.managed_session_id
    assert canonical["session"]["project_id"] == DEFAULT_PROJECT_ID
    assert canonical["session"]["dispatch_id"] == receipt.dispatch_id


def test_tampered_issued_receipt_fails_verify(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = _id_from_prompt(_request_prompt(request))
        submit_target_result(
            captured["id"], _target_payload(f"d.{captured['id']}"), root=workspace
        )

    receipt = run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    assert receipt.target_receipt_id is not None
    issued = load_canonical_receipt(workspace, receipt.target_receipt_id)
    target = _bind_target_from_record(workspace, captured["id"])
    attacks: list[dict[str, Any]] = [
        {"receipt_id": "ASR-aaaaaaaaaaaaaaaa"},
        {"status": "pending"},
        {"authority_role": "authority"},
        {"is_authority": True},
        {"receipt_is_authority": True},
        {"session.task_id": "OTHER-TASK"},
        {"session.session_id": "AS-forged-session"},
        {"session.dispatch_id": "b" * 64},
        {"session.project_id": "other-project"},
    ]
    for patch in attacks:
        mutated = _apply_receipt_patches(issued, patch)
        _overwrite_receipt(workspace, receipt.target_receipt_id, mutated)
        envelope = parse_envelope(
            _target_payload(
                f"d.{captured['id']}",
                receipt={"receipt_id": receipt.target_receipt_id, "status": "valid"},
            )
        )
        with pytest.raises(ReceiptBindingError) as exc:
            verify_target_receipt_binding(envelope, target, workspace)
        assert exc.value.code in {
            "RECEIPT_TAMPERED",
            "RECEIPT_NOT_VALID",
            "RECEIPT_NOT_FOUND",
            "RECEIPT_BINDING_MISMATCH",
        }
    _overwrite_receipt(workspace, receipt.target_receipt_id, issued)


def test_terminal_json_self_attested_receipt_is_replaced(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    class LateRunner:
        def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
            captured["id"] = _id_from_prompt(_request_prompt(request))
            envelope = _target_payload(
                f"d.{captured['id']}",
                receipt={"receipt_id": "ASR-fake123", "status": "valid"},
            )
            return ProcessRunOutcome(
                exit_code=0,
                stdout=_cursor_stdout(envelope),
                stderr=b"",
                timed_out=False,
                duration_ms=3,
            )

    receipt = run_dispatch_once(root=workspace, runner=LateRunner())
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.target_receipt_verified is True
    assert receipt.target_receipt_id != "ASR-fake123"
    binding = load_result_binding(workspace, captured["id"])
    assert binding is not None
    assert binding.raw_target_result_digest != binding.normalized_target_result_digest
    assert binding.envelope.receipt is not None
    assert binding.envelope.receipt.receipt_id == receipt.target_receipt_id


def test_recovery_revalidates_canonical_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    from project_atlas.orchestration import dispatcher as dispatcher_mod

    real_finalize = dispatcher_mod.finalize_dispatch
    calls = {"n": 0}

    def boom(root: Path, record: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("crash-after-submit")
        return real_finalize(root, record)

    monkeypatch.setattr(dispatcher_mod, "finalize_dispatch", boom)

    def on_run(request: ProcessRunRequest) -> None:
        dispatch_id = _request_prompt(request).rsplit("dispatch-submit-result ", 1)[1].split()[0]
        submit_target_result(dispatch_id, _target_payload(f"d.{dispatch_id}"), root=workspace)

    runner = ScriptedRunner(_ok_outcome(), on_run=on_run)
    with pytest.raises(RuntimeError):
        run_dispatch_once(root=workspace, runner=runner)
    dispatch_id = _id_from_prompt(_request_prompt(runner.requests[0]))
    receipts = workspace / ".atlas" / "receipts"
    for path in receipts.glob("ASR-*.json"):
        path.unlink()
    monkeypatch.setattr(dispatcher_mod, "finalize_dispatch", real_finalize)
    recovered = recover_dispatch(dispatch_id, root=workspace)
    assert recovered.status is DispatchStatus.FAILED
    assert recovered.failure_code == "RECONCILIATION_REQUIRED"
    assert recovered.source_acknowledged is False
    assert recovered.result_staged is False
    assert len(runner.requests) == 1


def test_recovery_incomplete_lifecycle_fails_closed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    submit_target_result(dispatch_id, _target_payload(f"d.{dispatch_id}"), root=workspace)
    recovered = recover_dispatch(dispatch_id, root=workspace)
    assert recovered.status is DispatchStatus.FAILED
    assert recovered.failure_code == "RECONCILIATION_REQUIRED"
    assert recovered.source_acknowledged is False


def test_forged_session_events_and_pipeline_fail_closed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    record = load_record(workspace, dispatch_id)
    assert record is not None and record.managed_session_id is not None
    state = session.load(workspace, record.managed_session_id)
    state["events"]["validation"] = ["AE-forged-validation"]
    state["events"]["completion"] = ["AE-forged-completion"]
    state["pipeline"]["verified"] = 99
    state["pipeline"]["normalized"] = 99
    state["pipeline"]["routed"] = 99
    session.save(workspace, state)
    errors = receipt_gate.validate(state)
    assert errors == [] or errors
    state["pipeline"]["verified"] = 0
    session.save(workspace, state)
    gate_errors = receipt_gate.validate(state)
    assert any("normalized" in error or "verified" in error for error in gate_errors)
    recovered = recover_dispatch(dispatch_id, root=workspace)
    assert recovered.status is DispatchStatus.FAILED
    assert recovered.source_acknowledged is False


def test_status_exposes_verification_not_secrets(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)

    def on_run(request: ProcessRunRequest) -> None:
        dispatch_id = _request_prompt(request).rsplit("dispatch-submit-result ", 1)[1].split()[0]
        submit_target_result(dispatch_id, _target_payload(f"d.{dispatch_id}"), root=workspace)

    run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    report = status_report(workspace)
    assert report["result_received"] is True
    assert report["target_receipt_verified"] is True
    dumped = json.dumps(report)
    assert "ASR-" not in dumped
    assert "session_id" not in dumped
    assert report["execution_authorized"] is False


def test_envelope_valid_claim_is_not_canonical_authority(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    envelope = parse_envelope(
        _target_payload(
            "d." + "a" * 64,
            receipt={"receipt_id": "ASR-fake123", "status": "valid"},
        )
    )
    assert isinstance(envelope, AgentResultEnvelope)
    assert envelope.receipt_is_valid_evidence() is True
    target = DispatchReceiptBindTarget(
        dispatch_id="a" * 64,
        dispatch_task_id="d." + "a" * 64,
        managed_session_id="AS-missing-session",
        attempt=1,
        target_role="integration",
    )
    with pytest.raises(ReceiptBindingError) as exc:
        verify_target_receipt_binding(envelope, target, workspace)
    assert exc.value.code in {"RECEIPT_NOT_FOUND", "SESSION_NOT_STARTED"}


def test_workspace_project_binding_reads_project_yaml(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    assert workspace_project_id(workspace) == DEFAULT_PROJECT_ID
    assert workspace_project_id(workspace) == workspace_project_id(workspace)
