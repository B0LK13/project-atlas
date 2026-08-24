"""AS-ORCH-INTEGRATION-IV-001C — independent IV for AS-ORCH-001C explicit completion.

CLI chain: cursor-stage-result → cursor-complete. Handoff != dispatch.
IV != merge authorization. Authentic Cursor stop delivery is not required.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "producer": {"role": "local", "agent_id": "iv-linux-001c"},
        "task": {"id": "D-137", "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {"target_moved": False, "unauthorized_mutations": 0},
        "receipt": {
            "receipt_id": "ASR-1234567890abcdef",
            "status": "valid",
            "event_id": "AE-orch-iv-001c",
        },
        "blockers": [],
        "requested_transition": None,
    }
    payload.update(overrides)
    return payload


def _write_payload(path: Path, payload: dict[str, Any] | str) -> None:
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _run(root: Path, *args: str) -> tuple[int, dict[str, Any]]:
    proc = subprocess.run(
        [sys.executable, "-m", "project_atlas.cli", "orchestrator", *args, "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, report


def _assert_no_authority(report: dict[str, Any]) -> None:
    assert report.get("execution_authorized") is False
    assert report.get("dispatch_performed") is False
    assert report.get("merge_authorized", False) is False


def test_iv_001c_a_stage_and_complete_task_handoff(tmp_path: Path) -> None:
    envelope = tmp_path / "pass.json"
    _write_payload(envelope, _valid_payload())
    code, staged = _run(tmp_path, "cursor-stage-result", str(envelope))
    assert code == 0
    assert staged.get("execution_authorized") is False
    code, packet = _run(tmp_path, "cursor-complete")
    assert code == 0
    assert packet["state"] == "HANDOFF_READY"
    assert packet["transport"] == "explicit"
    assert packet["target_role"] == "integration"
    assert packet["task_type"] == "candidate_verification"
    _assert_no_authority(packet)


def test_iv_001c_b_merge_eligible_owner_required(tmp_path: Path) -> None:
    envelope = tmp_path / "merge.json"
    _write_payload(
        envelope,
        _valid_payload(
            producer={"role": "integration", "agent_id": "iv-int"},
            state="MERGE_ELIGIBLE",
            requested_transition="MERGE",
        ),
    )
    code, _staged = _run(tmp_path, "cursor-stage-result", str(envelope))
    assert code == 0
    code, packet = _run(tmp_path, "cursor-complete")
    assert code == 0
    assert packet["state"] == "OWNER_REQUIRED"
    assert packet.get("task_type") in {None, ""}
    _assert_no_authority(packet)


def test_iv_001c_c_tampered_staged_state_fail_closed(tmp_path: Path) -> None:
    envelope = tmp_path / "pass.json"
    _write_payload(envelope, _valid_payload())
    code, _staged = _run(tmp_path, "cursor-stage-result", str(envelope))
    assert code == 0
    state_path = tmp_path / ".atlas" / "orchestration" / "cursor" / "state.json"
    if not state_path.is_file():
        matches = list((tmp_path / ".atlas").rglob("*.json"))
        assert matches, "staged state file missing"
        state_path = matches[0]
    dumped = json.loads(state_path.read_text(encoding="utf-8"))
    if "route" in dumped and isinstance(dumped["route"], dict):
        dumped["route"].setdefault("permissions", {})
        dumped["route"]["permissions"]["merge"] = True
    else:
        dumped["route_digest"] = "0" * 64
    state_path.write_text(json.dumps(dumped), encoding="utf-8")
    code, report = _run(tmp_path, "cursor-complete")
    assert code != 0
    assert report.get("execution_authorized", False) is False
    assert report.get("dispatch_performed", False) is False


def test_iv_001c_d_terminal_receipt_missing(tmp_path: Path) -> None:
    envelope = tmp_path / "terminal.json"
    _write_payload(envelope, _valid_payload(receipt=None))
    code, _staged = _run(tmp_path, "cursor-stage-result", str(envelope))
    assert code == 0
    code, packet = _run(tmp_path, "cursor-complete")
    assert code == 0
    assert packet["state"] == "TERMINAL"
    _assert_no_authority(packet)


def test_iv_001c_e_status_never_authorizes(tmp_path: Path) -> None:
    envelope = tmp_path / "pass.json"
    _write_payload(envelope, _valid_payload())
    _run(tmp_path, "cursor-stage-result", str(envelope))
    code, status = _run(tmp_path, "cursor-status")
    assert code == 0
    assert status.get("execution_authorized", False) is False
    assert status.get("dispatch_performed", False) is False
