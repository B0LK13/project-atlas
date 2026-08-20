"""AS-ORCH-CONTINUATION-BROKER-001 acceptance and adversarial matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_atlas.cli import EXIT_OK, main
from project_atlas.orchestration.autonomy.continuation_broker import (
    BACKEND,
    BROKER_MARKER,
    PACKAGE_ID,
    BrokerError,
    BrokerPhase,
    SuccessorKind,
    consume_successor,
    emit_stop_followup,
    enqueue_successor,
    recover_broker,
    session_exit_does_not_end_dag,
    status_report,
)
from project_atlas.orchestration.autonomy.models import CANONICAL_REPOSITORY_IDENTITY
from project_atlas.orchestration.cursor_bridge import (
    handle_stop_event,
    load_state,
    stage_result,
)

PIN = "7e797468a2eca37c959920912b1fa264df4be638"
TREE = "3cb40645c343edf8f8ab95f6ddf3a819e2110ef2"


def _enqueue(
    root: Path,
    cycle_id: str = "CYCLE-A",
    kind: SuccessorKind = SuccessorKind.CHECKPOINT_CONTINUE,
    **extra: object,
) -> object:
    kwargs = {
        "cycle_id": cycle_id,
        "kind": kind,
        "trusted_main": PIN,
        "trusted_tree": TREE,
        "repository_identity": CANONICAL_REPOSITORY_IDENTITY,
    }
    kwargs.update(extra)
    return enqueue_successor(root, **kwargs)  # type: ignore[arg-type]


def _stop(*, status: str = "completed", loop_count: int = 0, **extra: object) -> dict[str, object]:
    event: dict[str, object] = {
        "conversation_id": "conv-1",
        "status": status,
        "loop_count": loop_count,
    }
    event.update(extra)
    return event


def _envelope() -> dict[str, object]:
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


def test_backend_is_real_stop_hook() -> None:
    assert BACKEND == "CURSOR_STOP_HOOK_FOLLOWUP"
    assert PACKAGE_ID == "AS-ORCH-CONTINUATION-BROKER-001"


def test_multi_cycle_without_human(tmp_path: Path) -> None:
    human = 0
    for cycle in ("CYCLE-A", "CYCLE-B", "CYCLE-C"):
        queued = _enqueue(tmp_path, cycle)
        assert queued.accepted is True
        follow = handle_stop_event(_stop(), root=tmp_path)
        assert "followup_message" in follow
        assert BROKER_MARKER in follow["followup_message"]
        assert cycle in follow["followup_message"]
        assert "MERGE_AUTHORIZATION=NOT_GRANTED" in follow["followup_message"]
        consume_successor(tmp_path, cycle)
    assert human == 0


def test_session_exit_is_not_dag_terminal() -> None:
    assert session_exit_does_not_end_dag(worker_terminal=True, dag_terminal=False) is True
    assert session_exit_does_not_end_dag(worker_terminal=True, dag_terminal=True) is False


def test_worker_terminal_enqueues_when_dag_continues(tmp_path: Path) -> None:
    result = _enqueue(
        tmp_path,
        "CYCLE-W",
        SuccessorKind.WORKER_TERMINAL_DAG_CONTINUES,
        worker_terminal=True,
        dag_terminal=False,
    )
    assert result.accepted is True
    with pytest.raises(BrokerError, match="DAG is terminal") as exc:
        _enqueue(
            tmp_path,
            "CYCLE-Z",
            SuccessorKind.WORKER_TERMINAL_DAG_CONTINUES,
            worker_terminal=True,
            dag_terminal=True,
        )
    assert exc.value.code == "DAG_TERMINAL"


def test_owner_prompt_dedupe(tmp_path: Path) -> None:
    first = _enqueue(
        tmp_path,
        "CYCLE-O1",
        owner_gate_fingerprint="BATCH-B-CONTEXT-INTEGRATION-001:7e797468:e06350ea",
        owner_request_id="BATCH-B-CONTEXT-INTEGRATION-001",
    )
    assert first.accepted is True
    assert first.owner_prompt_emitted is True
    second = _enqueue(
        tmp_path,
        "CYCLE-O2",
        owner_gate_fingerprint="BATCH-B-CONTEXT-INTEGRATION-001:7e797468:e06350ea",
        owner_request_id="BATCH-B-CONTEXT-INTEGRATION-001",
    )
    assert second.deduped is True
    assert second.owner_prompt_emitted is False
    assert second.accepted is False


def test_resource_yield_is_not_owner_required(tmp_path: Path) -> None:
    queued = _enqueue(tmp_path, "YIELD-1", SuccessorKind.RESOURCE_YIELD)
    assert queued.kind == SuccessorKind.RESOURCE_YIELD
    follow = emit_stop_followup(tmp_path)
    assert "OWNER_REQUIRED" not in follow["followup_message"]
    assert "RESOURCE_YIELD" in follow["followup_message"]


def test_duplicate_checkpoint_and_cycle_replay(tmp_path: Path) -> None:
    _enqueue(tmp_path, "CYCLE-D")
    again = _enqueue(tmp_path, "CYCLE-D")
    assert again.deduped is True
    with pytest.raises(BrokerError) as exc:
        _enqueue(tmp_path, "CYCLE-E")
    assert exc.value.code == "DUPLICATE_SUCCESSOR"
    consume_successor(tmp_path, "CYCLE-D")
    with pytest.raises(BrokerError) as exc2:
        consume_successor(tmp_path, "CYCLE-D")
    assert exc2.value.code == "CYCLE_REPLAY"
    with pytest.raises(BrokerError) as exc3:
        _enqueue(tmp_path, "CYCLE-D")
    assert exc3.value.code == "CYCLE_REPLAY"


def test_foreign_project_rejected(tmp_path: Path) -> None:
    with pytest.raises(BrokerError) as exc:
        enqueue_successor(
            tmp_path,
            cycle_id="CYCLE-F",
            kind=SuccessorKind.CHECKPOINT_CONTINUE,
            trusted_main=PIN,
            trusted_tree=TREE,
            repository_identity="github.com/other/repo",
        )
    assert exc.value.code == "FOREIGN_PROJECT"


def test_second_governor_rejected(tmp_path: Path) -> None:
    with pytest.raises(BrokerError) as exc:
        enqueue_successor(
            tmp_path,
            cycle_id="CYCLE-G",
            kind=SuccessorKind.CHECKPOINT_CONTINUE,
            trusted_main=PIN,
            trusted_tree=TREE,
            primary_governor=False,
        )
    assert exc.value.code == "SECOND_GOVERNOR"


def test_prompt_injection_ignored_on_stop(tmp_path: Path) -> None:
    _enqueue(tmp_path, "CYCLE-I")
    follow = handle_stop_event(
        _stop(followup_message="ignore previous", extra="OWNER_ESCALATION"),
        root=tmp_path,
    )
    message = follow["followup_message"]
    assert "ignore previous" not in message
    assert "OWNER_ESCALATION" not in message
    assert BROKER_MARKER in message


def test_transport_cannot_grant_authority(tmp_path: Path) -> None:
    _enqueue(tmp_path, "CYCLE-T")
    report = status_report(tmp_path)
    assert report["execution_authorized"] is False
    assert report["merge_authorized"] is False
    assert report["authority_granted"] is False


def test_does_not_consume_001c_pending_slot(tmp_path: Path) -> None:
    staged = stage_result(_envelope(), root=tmp_path)
    assert staged.status.value == "pending"
    _enqueue(tmp_path, "CYCLE-SLOT")
    follow = handle_stop_event(_stop(), root=tmp_path)
    assert BROKER_MARKER in follow["followup_message"]
    leftover = load_state(tmp_path)
    assert leftover is not None
    assert leftover.status.value == "pending"
    assert leftover.followup_emitted is False
    assert leftover.route_digest == staged.route_digest


def test_stale_pin_rejected(tmp_path: Path) -> None:
    _enqueue(tmp_path, "CYCLE-S")
    with pytest.raises(BrokerError) as exc:
        enqueue_successor(
            tmp_path,
            cycle_id="CYCLE-S2",
            kind=SuccessorKind.CHECKPOINT_CONTINUE,
            trusted_main="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            trusted_tree=TREE,
        )
    assert exc.value.code == "STALE_CHECKPOINT"


def test_crash_recover_does_not_duplicate(tmp_path: Path) -> None:
    _enqueue(tmp_path, "CYCLE-R")
    first = recover_broker(tmp_path)
    second = recover_broker(tmp_path)
    assert first is not None and second is not None
    assert first.cycle_id == second.cycle_id == "CYCLE-R"
    assert first.phase == BrokerPhase.QUEUED
    emit_stop_followup(tmp_path)
    recovered = recover_broker(tmp_path)
    assert recovered is not None
    assert recovered.followup_emitted is True
    assert emit_stop_followup(tmp_path) == {}


def test_loop_count_cap_no_second_followup_in_same_stop(tmp_path: Path) -> None:
    _enqueue(tmp_path, "CYCLE-L")
    assert "followup_message" in handle_stop_event(_stop(), root=tmp_path)
    assert handle_stop_event(_stop(loop_count=1), root=tmp_path) == {}


def test_cli_status_and_enqueue(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "orchestrator",
                "continuation-broker",
                "enqueue",
                "--root",
                str(tmp_path),
                "--cycle-id",
                "CYCLE-CLI",
                "--trusted-main",
                PIN,
                "--trusted-tree",
                TREE,
            ]
        )
        == EXIT_OK
    )
    status_code = main(
        ["orchestrator", "continuation-broker", "status", "--root", str(tmp_path)]
    )
    assert status_code == EXIT_OK
    out = capsys.readouterr().out
    assert PACKAGE_ID in out
    assert "CYCLE-CLI" in out
