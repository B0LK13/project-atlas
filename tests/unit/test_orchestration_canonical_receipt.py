"""AS-ORCH-001D-R2 canonical receipt authenticity and path safety."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from project_atlas.cli import EXIT_ERROR, main
from project_atlas.orchestration.agent_transport import ProcessRunOutcome, ProcessRunRequest
from project_atlas.orchestration.canonical_session_receipt import (
    DispatchReceiptBindTarget,
    ReceiptBindingError,
    issue_managed_dispatch_receipt,
    load_canonical_receipt,
    managed_session_id_for,
    resolve_canonical_receipt_path,
    verify_target_receipt_binding,
    workspace_project_id,
)
from project_atlas.orchestration.cursor_bridge import STATE_RELATIVE, stage_result
from project_atlas.orchestration.dispatcher import (
    DispatcherError,
    DispatchStatus,
    compute_dispatch_id,
    recover_dispatch,
    run_dispatch_once,
    status_report,
    submit_target_result,
)
from project_atlas.orchestration.models import AgentResultEnvelope
from project_atlas.orchestration.validator import parse_envelope

from tests.unit.test_orchestration_dispatcher import (
    ScriptedRunner,
    _ok_outcome,
    _payload,
    _request_prompt,
    _target_payload,
    _workspace,
)


def _prepare_running_dispatch(workspace: Path) -> str:
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = request.stdin.decode("utf-8").rsplit("dispatch-submit-result ", 1)[1].split()[0]
        raise RuntimeError("stop-before-submit")

    stage_result(_payload(), root=workspace)
    with pytest.raises(RuntimeError):
        run_dispatch_once(root=workspace, runner=ScriptedRunner(_ok_outcome(), on_run=on_run))
    return captured["id"]


def _bind_target(workspace: Path, dispatch_id: str, *, role: str = "integration") -> DispatchReceiptBindTarget:
    return DispatchReceiptBindTarget(
        dispatch_id=dispatch_id,
        dispatch_task_id=f"d.{dispatch_id}",
        managed_session_id=managed_session_id_for(dispatch_id),
        attempt=1,
        target_role=role,
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
            session = dict(mutated["session"])
            session[key.split(".", 1)[1]] = value
            mutated["session"] = session
        elif key.startswith("validation.") and isinstance(mutated.get("validation"), dict):
            validation = dict(mutated["validation"])
            validation[key.split(".", 1)[1]] = value
            mutated["validation"] = validation
        elif key.startswith("pipeline.") and isinstance(mutated.get("pipeline"), dict):
            pipeline = dict(mutated["pipeline"])
            pipeline[key.split(".", 1)[1]] = value
            mutated["pipeline"] = pipeline
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


def test_self_attested_valid_receipt_is_rejected(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    with pytest.raises(DispatcherError) as exc:
        submit_target_result(
            dispatch_id,
            _target_payload(
                f"d.{dispatch_id}",
                receipt={"receipt_id": "ASR-fake123", "status": "valid"},
            ),
            root=workspace,
        )
    assert exc.value.code == "RECEIPT_NOT_FOUND"
    assert not (workspace / ".atlas" / "orchestration" / "dispatcher" / "results" / f"{dispatch_id}.json").is_file()
    assert (workspace / STATE_RELATIVE).is_file()


def test_submit_result_cli_rejects_self_attested_receipt(
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
    assert code == EXIT_ERROR
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert report["error"] == "RECEIPT_NOT_FOUND"
    assert not (workspace / ".atlas" / "orchestration" / "dispatcher" / "results" / f"{dispatch_id}.json").is_file()


def test_pending_and_missing_receipt_are_issued(tmp_path: Path) -> None:
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
    assert pending.envelope.receipt.status == "valid"
    assert pending.raw_target_result_digest != pending.normalized_target_result_digest
    canonical = load_canonical_receipt(workspace, pending.envelope.receipt.receipt_id)
    assert canonical["status"] == "passed"
    assert canonical["authority_role"] == "evidence-only"
    assert canonical["is_authority"] is False
    assert canonical["receipt_is_authority"] is False
    assert canonical["session"]["task_id"] == f"d.{dispatch_id}"


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


def test_wrong_task_session_dispatch_and_project_mismatch(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    target = _bind_target(workspace, dispatch_id)
    issued = issue_managed_dispatch_receipt(workspace, target)
    receipt_id = str(issued["receipt_id"])
    cases = (
        ("session.task_id", "OTHER-TASK"),
        ("session.session_id", "ds." + "b" * 64),
        ("session.dispatch_id", "b" * 64),
        ("session.project_id", "ws.otherproject000"),
    )
    for field, value in cases:
        mutated = _apply_receipt_patches(issued, {field: value})
        _overwrite_receipt(workspace, receipt_id, mutated)
        with pytest.raises(DispatcherError) as exc:
            submit_target_result(
                dispatch_id,
                _target_payload(
                    f"d.{dispatch_id}",
                    receipt={"receipt_id": receipt_id, "status": "valid"},
                ),
                root=workspace,
            )
        assert exc.value.code == "RECEIPT_BINDING_MISMATCH", field
    _overwrite_receipt(workspace, receipt_id, issued)


def test_tampered_and_authority_confused_receipts_fail(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    target = _bind_target(workspace, dispatch_id)
    issued = issue_managed_dispatch_receipt(workspace, target)
    receipt_id = str(issued["receipt_id"])
    attacks: list[dict[str, Any]] = [
        {"receipt_id": "ASR-aaaaaaaaaaaaaaaa"},
        {"status": "pending"},
        {"authority_role": "authority"},
        {"is_authority": True},
        {"receipt_is_authority": True},
        {"validation.session": "failed"},
        {"pipeline.failed": 1},
        {"pipeline.verified": 0},
    ]
    for patch in attacks:
        _overwrite_receipt(workspace, receipt_id, _apply_receipt_patches(issued, patch))
        with pytest.raises(DispatcherError) as exc:
            submit_target_result(
                dispatch_id,
                _target_payload(
                    f"d.{dispatch_id}",
                    receipt={"receipt_id": receipt_id, "status": "valid"},
                ),
                root=workspace,
            )
        assert exc.value.code in {"RECEIPT_TAMPERED", "RECEIPT_NOT_VALID", "RECEIPT_NOT_FOUND"}


def test_foreign_dispatch_receipt_is_not_reusable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    dispatch_id = _prepare_running_dispatch(workspace)
    other_id = compute_dispatch_id(
        route_digest="c" * 64,
        target_role="integration",
        task_type="candidate_verification",
        source_task="OTHER",
    )
    foreign = issue_managed_dispatch_receipt(workspace, _bind_target(workspace, other_id))
    with pytest.raises(DispatcherError) as exc:
        submit_target_result(
            dispatch_id,
            _target_payload(
                f"d.{dispatch_id}",
                receipt={"receipt_id": foreign["receipt_id"], "status": "valid"},
            ),
            root=workspace,
        )
    assert exc.value.code == "RECEIPT_BINDING_MISMATCH"


def test_terminal_json_self_attested_receipt_does_not_ack(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = _request_prompt(request).rsplit("dispatch-submit-result ", 1)[1].split()[0]

    class LateRunner:
        def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
            on_run(request)
            envelope = _target_payload(
                f"d.{captured['id']}",
                receipt={"receipt_id": "ASR-fake123", "status": "valid"},
            )
            return ProcessRunOutcome(
                exit_code=0,
                stdout=json.dumps({"type": "result", "is_error": False, "result": envelope}).encode(),
                stderr=b"",
                timed_out=False,
                duration_ms=3,
            )

    receipt = run_dispatch_once(root=workspace, runner=LateRunner())
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.failure_code == "RECEIPT_NOT_FOUND"
    assert receipt.source_acknowledged is False
    assert receipt.result_staged is False
    assert receipt.next_handoff_state is None
    assert (workspace / STATE_RELATIVE).is_file()


def test_terminal_json_with_bound_canonical_receipt(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    stage_result(_payload(), root=workspace)
    captured: dict[str, str] = {}

    def on_run(request: ProcessRunRequest) -> None:
        captured["id"] = _request_prompt(request).rsplit("dispatch-submit-result ", 1)[1].split()[0]
        target = _bind_target(workspace, captured["id"])
        captured["receipt_id"] = issue_managed_dispatch_receipt(workspace, target)["receipt_id"]

    class LateRunner:
        def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
            on_run(request)
            envelope = _target_payload(
                f"d.{captured['id']}",
                receipt={"receipt_id": captured["receipt_id"], "status": "valid"},
            )
            return ProcessRunOutcome(
                exit_code=0,
                stdout=json.dumps({"type": "result", "is_error": False, "result": envelope}).encode(),
                stderr=b"",
                timed_out=False,
                duration_ms=3,
            )

    receipt = run_dispatch_once(root=workspace, runner=LateRunner())
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.target_receipt_verified is True
    assert receipt.target_receipt_id == captured["receipt_id"]
    assert receipt.source_acknowledged is True


def test_recovery_revalidates_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    dispatch_id = _request_prompt(runner.requests[0]).rsplit("dispatch-submit-result ", 1)[1].split()[0]
    receipts = workspace / ".atlas" / "receipts"
    for path in receipts.glob("ASR-*.json"):
        path.unlink()
    monkeypatch.setattr(dispatcher_mod, "finalize_dispatch", real_finalize)
    recovered = recover_dispatch(dispatch_id, root=workspace)
    assert recovered.status is DispatchStatus.FAILED
    assert recovered.failure_code == "RECEIPT_NOT_FOUND"
    assert recovered.source_acknowledged is False
    assert recovered.result_staged is False
    assert len(runner.requests) == 1


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
        managed_session_id=managed_session_id_for("a" * 64),
        attempt=1,
        target_role="integration",
    )
    with pytest.raises(ReceiptBindingError) as exc:
        verify_target_receipt_binding(envelope, target, workspace)
    assert exc.value.code == "RECEIPT_NOT_FOUND"


def test_workspace_project_binding_is_stable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    assert workspace_project_id(workspace) == workspace_project_id(workspace)
    assert workspace_project_id(workspace).startswith("ws.")
