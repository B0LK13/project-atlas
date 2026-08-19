"""AS-ORCH-001D-RESULT-BINDING-001 framed capture, identity bind, fail-closed replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.agent_transport import (
    ProcessRunOutcome,
    ProcessRunRequest,
    ResultChannelStatus,
    extract_result_channel,
    frame_result_payload,
)
from project_atlas.orchestration.cursor_bridge import require_verified_state, stage_result
from project_atlas.orchestration.dispatcher import (
    DispatcherConfig,
    DispatcherError,
    DispatchStatus,
    bind_captured_result,
    compute_dispatch_id,
    dispatch_task_id_for,
    load_receipt,
    load_record,
    load_result_binding,
    persist_record,
    run_dispatch_once,
    submit_target_result,
)
from project_atlas.orchestration.validator import parse_envelope


def _workspace(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "AGENTS.md").write_text("# Atlas\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "project-atlas"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "project_atlas").mkdir(parents=True)
    return tmp_path


def _source_payload(**overrides: Any) -> dict[str, Any]:
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


_PINS = DispatcherConfig(
    lease_id="LEASE-TEST-001",
    bound_package_id="D-137",
    base_main="a" * 40,
    candidate_head="b" * 40,
    candidate_tree="c" * 40,
)


def _identity(root: Path) -> tuple[str, str, str]:
    verified = require_verified_state(root)
    assert verified.route.target.role is not None
    assert verified.route.task_type is not None
    dispatch_id = compute_dispatch_id(
        route_digest=verified.route_digest,
        target_role=verified.route.target.role,
        task_type=verified.route.task_type,
        source_task=verified.envelope.task.id,
    )
    return dispatch_id, dispatch_task_id_for(dispatch_id), verified.route.target.role.value


def _target_envelope(
    root: Path,
    *,
    extras: dict[str, bool | int | str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    dispatch_id, task_id, role = _identity(root)
    binding = {
        "dispatch_id": dispatch_id,
        "lease_id": "LEASE-TEST-001",
        "package_id": "D-137",
        "base_main": "a" * 40,
        "candidate_head": "b" * 40,
        "candidate_tree": "c" * 40,
        "evidence_reference": "tests/unit/result-binding",
    }
    if extras is not None:
        binding.update(extras)
    data: dict[str, Any] = {
        "schema_version": 1,
        "producer": {"role": role, "agent_id": "iv-agent"},
        "task": {"id": task_id, "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {
            "target_moved": False,
            "unauthorized_mutations": 0,
            "extras": binding,
        },
        "receipt": {"receipt_id": "ASR-ivresult0001", "status": "valid"},
        "blockers": [],
        "requested_transition": None,
    }
    data.update(overrides)
    return data


def _cursor_stdout(result_text: str, *, exit_wrapper: bool = False) -> bytes:
    payload = {
        "type": "result",
        "result": result_text,
        "session_id": "s1",
        "is_error": exit_wrapper,
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _framed_outcome(root: Path, **overrides: Any) -> ProcessRunOutcome:
    envelope = _target_envelope(root, **overrides)
    text = "human notes\n" + frame_result_payload(envelope)
    return ProcessRunOutcome(
        exit_code=0,
        stdout=_cursor_stdout(text),
        stderr=b"ignore me",
        timed_out=False,
        duration_ms=7,
    )


@pytest.mark.parametrize("kind", ["empty", "cursor_ok", "mixed", "raw_json"])
def test_no_result_payload_and_ambiguous_json_are_not_submitted(
    tmp_path: Path,
    kind: str,
) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    ambiguous = json.dumps(_target_envelope(root)).encode("utf-8")
    stdout = {
        "empty": b"",
        "cursor_ok": b'{"type":"result","result":"ok","session_id":"s1"}',
        "mixed": b'PASS CERTIFIED {"schema_version":1,"outcome":"PASS"}\n' + ambiguous,
        "raw_json": ambiguous,
    }[kind]
    runner = _FakeRunner(
        ProcessRunOutcome(exit_code=0, stdout=stdout, stderr=b"", timed_out=False, duration_ms=1)
    )
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.failure_code == "RESULT_NOT_SUBMITTED"
    assert receipt.result_received is False
    assert receipt.execution_authorized is False
    if receipt.dispatch_id:
        assert load_result_binding(root, receipt.dispatch_id) is None


def test_mixed_human_text_and_ambiguous_json_not_parsed(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    envelope = _target_envelope(root)
    stdout = ("notes PASS\n" + json.dumps(envelope) + "\n").encode("utf-8")
    captured = extract_result_channel(stdout, b"")
    assert captured.status is ResultChannelStatus.ABSENT
    runner = _FakeRunner(
        ProcessRunOutcome(exit_code=0, stdout=stdout, stderr=b"", timed_out=False, duration_ms=1)
    )
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.failure_code == "RESULT_NOT_SUBMITTED"


def test_malformed_oversized_multiple_and_authority_field(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    cases = [
        (
            "MALFORMED_RESULT",
            "<<<ATLAS_AGENT_RESULT_ENVELOPE_V1>>>{not-json}<<<END_ATLAS_AGENT_RESULT_ENVELOPE_V1>>>",
        ),
        (
            "OVERSIZED_RESULT",
            "<<<ATLAS_AGENT_RESULT_ENVELOPE_V1>>>"
            + ("x" * (256 * 1024 + 8))
            + "<<<END_ATLAS_AGENT_RESULT_ENVELOPE_V1>>>",
        ),
        (
            "MULTIPLE_RESULT_ENVELOPES",
            frame_result_payload({"schema_version": 1})
            + frame_result_payload({"schema_version": 1}),
        ),
    ]
    for index, (code, text) in enumerate(cases):
        case_root = root if index == 0 else _workspace(tmp_path / f"case-{index}")
        if index > 0:
            stage_result(_source_payload(), root=case_root)
        runner = _FakeRunner(
            ProcessRunOutcome(
                exit_code=0,
                stdout=_cursor_stdout(text),
                stderr=b"",
                timed_out=False,
                duration_ms=1,
            )
        )
        receipt = run_dispatch_once(root=case_root, runner=runner, config=_PINS)
        assert receipt.failure_code == code, receipt.failure_code
        assert receipt.status is DispatchStatus.FAILED


def test_result_with_extra_authority_field_rejected(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    payload = _target_envelope(root)
    payload["merge_authorized"] = True
    runner = _FakeRunner(
        ProcessRunOutcome(
            exit_code=0,
            stdout=_cursor_stdout(frame_result_payload(payload)),
            stderr=b"",
            timed_out=False,
            duration_ms=1,
        )
    )
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.failure_code == "RESULT_WITH_EXTRA_AUTHORITY_FIELD"
    assert receipt.result_received is False


def test_result_extras_cannot_smuggle_owner_authority(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    payload = _target_envelope(root, extras={"owner_authority": True, "evidence_reference": "x"})
    runner = _FakeRunner(
        ProcessRunOutcome(
            exit_code=0,
            stdout=_cursor_stdout(frame_result_payload(payload)),
            stderr=b"",
            timed_out=False,
            duration_ms=1,
        )
    )
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.failure_code == "RESULT_WITH_EXTRA_AUTHORITY_FIELD"


@pytest.mark.parametrize(
    ("extra_key", "extra_value", "code"),
    [
        ("dispatch_id", "d" * 64, "WRONG_DISPATCH_ID"),
        ("lease_id", "LEASE-OTHER", "WRONG_LEASE_ID"),
        ("package_id", "AS-ORCH-OTHER", "WRONG_PACKAGE"),
        ("base_main", "e" * 40, "WRONG_BASE"),
        ("candidate_head", "f" * 40, "WRONG_HEAD"),
        ("candidate_tree", "0" * 40, "WRONG_TREE"),
    ],
)
def test_wrong_identity_pins_are_rejected(
    tmp_path: Path,
    extra_key: str,
    extra_value: str,
    code: str,
) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    payload = _target_envelope(root, extras={extra_key: extra_value})
    runner = _FakeRunner(
        ProcessRunOutcome(
            exit_code=0,
            stdout=_cursor_stdout(frame_result_payload(payload)),
            stderr=b"",
            timed_out=False,
            duration_ms=1,
        )
    )
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.failure_code == code


def test_wrong_role_rejected(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    payload = _target_envelope(root, producer={"role": "autonomous", "agent_id": "x"})
    runner = _FakeRunner(
        ProcessRunOutcome(
            exit_code=0,
            stdout=_cursor_stdout(frame_result_payload(payload)),
            stderr=b"",
            timed_out=False,
            duration_ms=1,
        )
    )
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.failure_code == "WRONG_ROLE"


def test_exit_codes_are_not_semantic_results(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    empty = _FakeRunner(
        ProcessRunOutcome(exit_code=0, stdout=b"", stderr=b"", timed_out=False, duration_ms=1)
    )
    assert run_dispatch_once(root=root, runner=empty, config=_PINS).failure_code == (
        "RESULT_NOT_SUBMITTED"
    )

    root_one = _workspace(tmp_path / "one")
    stage_result(_source_payload(), root=root_one)
    failed = _FakeRunner(
        ProcessRunOutcome(
            exit_code=1, stdout=b"nope", stderr=b"err", timed_out=False, duration_ms=1
        )
    )
    receipt = run_dispatch_once(root=root_one, runner=failed, config=_PINS)
    assert receipt.failure_code == "PROCESS_FAILED"
    assert receipt.process_exit_code == 1
    assert receipt.result_received is False

    root_pass = _workspace(tmp_path / "claimed")
    stage_result(_source_payload(), root=root_pass)
    claimed = _framed_outcome(root_pass)
    claimed = ProcessRunOutcome(
        exit_code=1,
        stdout=claimed.stdout,
        stderr=claimed.stderr,
        timed_out=False,
        duration_ms=3,
    )
    receipt = run_dispatch_once(
        root=root_pass,
        runner=_FakeRunner(claimed),
        config=_PINS,
    )
    assert receipt.failure_code == "EXIT_CLAIMED_PASS"
    assert receipt.status is DispatchStatus.FAILED
    assert receipt.execution_authorized is False


def test_valid_terminal_result_is_bound_and_finalized(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    runner = _FakeRunner(_framed_outcome(root))
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.process_started is True
    assert receipt.result_received is True
    assert receipt.result_staged is True
    assert receipt.execution_authorized is False
    assert receipt.next_handoff_autodispatched is False
    assert receipt.dispatch_receipt_is_authority is False
    assert len(runner.requests) == 1
    assert runner.requests[0].argv
    dispatch_id = receipt.dispatch_id
    assert dispatch_id is not None
    binding = load_result_binding(root, dispatch_id)
    assert binding is not None
    parse_envelope(binding.envelope.model_dump(mode="json"))
    stored = load_record(root, dispatch_id)
    assert stored is not None
    assert stored.lease_id == "LEASE-TEST-001"
    persisted = load_receipt(root, dispatch_id)
    assert persisted is not None
    assert persisted.status is DispatchStatus.COMPLETED


def test_merge_eligible_result_cannot_authorize_merge(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    payload = _target_envelope(root, state="MERGE_ELIGIBLE", requested_transition="MERGE")
    runner = _FakeRunner(
        ProcessRunOutcome(
            exit_code=0,
            stdout=_cursor_stdout(frame_result_payload(payload)),
            stderr=b"",
            timed_out=False,
            duration_ms=1,
        )
    )
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.execution_authorized is False
    assert receipt.dispatch_receipt_is_authority is False
    assert receipt.next_handoff_autodispatched is False
    dump = receipt.to_public_dict()
    assert dump["execution_authorized"] is False
    assert "merge_authorized" not in dump or dump.get("merge_authorized") is False


def test_duplicate_and_after_finalization_rejected(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    receipt = run_dispatch_once(root=root, runner=_FakeRunner(_framed_outcome(root)), config=_PINS)
    assert receipt.status is DispatchStatus.COMPLETED
    assert receipt.dispatch_id is not None
    record = load_record(root, receipt.dispatch_id)
    assert record is not None
    with pytest.raises(DispatcherError) as exc:
        bind_captured_result(_target_envelope(root), root=root, record=record)
    assert exc.value.code == "RESULT_AFTER_FINALIZATION"
    with pytest.raises(DispatcherError) as submit_exc:
        submit_target_result(receipt.dispatch_id, _target_envelope(root), root=root)
    assert submit_exc.value.code in {"DUPLICATE_RESULT", "RESULT_AFTER_FINALIZATION"}


def test_stale_and_previous_dispatch_rejected(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    receipt = run_dispatch_once(root=root, runner=_FakeRunner(_framed_outcome(root)), config=_PINS)
    assert receipt.dispatch_id is not None
    first = load_record(root, receipt.dispatch_id)
    assert first is not None

    other = _workspace(tmp_path / "other")
    stage_result(_source_payload(task={"id": "D-138", "attempt": 1}), root=other)
    other_receipt = run_dispatch_once(
        root=other,
        runner=_FakeRunner(
            ProcessRunOutcome(
                exit_code=0,
                stdout=b'{"type":"result","result":"ok"}',
                stderr=b"",
                timed_out=False,
                duration_ms=1,
            )
        ),
        config=DispatcherConfig(
            lease_id="LEASE-TEST-002",
            bound_package_id="D-138",
            base_main="a" * 40,
            candidate_head="b" * 40,
            candidate_tree="c" * 40,
        ),
    )
    assert other_receipt.failure_code == "RESULT_NOT_SUBMITTED"
    other_record = load_record(other, other_receipt.dispatch_id or "")
    assert other_record is not None
    persist_record(root, other_record.model_copy(update={"workspace_root": str(root)}))
    payload = _target_envelope(root)
    assert isinstance(payload["observations"], dict)
    extras = payload["observations"]["extras"]
    assert isinstance(extras, dict)
    extras["dispatch_id"] = other_record.dispatch_id
    running = first.model_copy(update={"status": DispatchStatus.RUNNING, "result_received": False})
    persist_record(root, running)
    result_file = (
        root / ".atlas" / "orchestration" / "dispatcher" / "results" / f"{first.dispatch_id}.json"
    )
    result_file.unlink(missing_ok=True)
    with pytest.raises(DispatcherError) as prev:
        bind_captured_result(payload, root=root, record=running)
    assert prev.value.code in {"RESULT_FROM_PREVIOUS_DISPATCH", "WRONG_DISPATCH_ID"}

    bumped = running.model_copy(update={"attempt": 2})
    persist_record(root, bumped)
    stale = {
        "schema_version": 1,
        "producer": {"role": bumped.target_role.value, "agent_id": "iv-agent"},
        "task": {"id": bumped.dispatch_task_id, "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {
            "target_moved": False,
            "unauthorized_mutations": 0,
            "extras": {
                "dispatch_id": bumped.dispatch_id,
                "lease_id": bumped.lease_id or "LEASE-TEST-001",
                "package_id": bumped.bound_package_id or "D-137",
                "base_main": bumped.base_main or "a" * 40,
                "candidate_head": bumped.candidate_head or "b" * 40,
                "candidate_tree": bumped.candidate_tree or "c" * 40,
                "evidence_reference": "tests/unit/result-binding",
            },
        },
        "receipt": {"receipt_id": "ASR-stale0001", "status": "valid"},
        "blockers": [],
        "requested_transition": None,
    }
    with pytest.raises(DispatcherError) as stale_exc:
        bind_captured_result(stale, root=root, record=bumped)
    assert stale_exc.value.code == "STALE_RESULT"


def test_stderr_is_not_a_result_channel(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    framed = frame_result_payload(_target_envelope(root)).encode("utf-8")
    captured = extract_result_channel(b'{"type":"result","result":"plain"}', framed)
    assert captured.status is ResultChannelStatus.ABSENT
    runner = _FakeRunner(
        ProcessRunOutcome(
            exit_code=0,
            stdout=b'{"type":"result","result":"plain"}',
            stderr=framed,
            timed_out=False,
            duration_ms=1,
        )
    )
    receipt = run_dispatch_once(root=root, runner=runner, config=_PINS)
    assert receipt.failure_code == "RESULT_NOT_SUBMITTED"


def test_prompt_does_not_require_child_write_submit(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    runner = _FakeRunner(_framed_outcome(root))
    run_dispatch_once(root=root, runner=runner, config=_PINS)
    prompt = runner.requests[0].stdin
    assert prompt is not None
    text = prompt.decode("utf-8")
    assert "<<<ATLAS_AGENT_RESULT_ENVELOPE_V1>>>" in text
    assert "dispatch-submit-result" not in text
    assert "You do not need write authority" in text
    assert "LEASE-TEST-001" in text


def test_current_main_001a_accepts_binding_envelope(tmp_path: Path) -> None:
    root = _workspace(tmp_path)
    stage_result(_source_payload(), root=root)
    envelope = parse_envelope(_target_envelope(root))
    assert envelope.observations.extras["dispatch_id"]
    assert envelope.outcome.value == "PASS"
