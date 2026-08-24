"""AS-ORCH-INTEGRATION-IV-001D — independent IV for owner/terminal non-dispatch.

CLI chain: stage → complete → dispatch-once. Owner/terminal routes must not
start a process. IV != merge authorization. Does not launch a real agent.
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
        "producer": {"role": "local", "agent_id": "iv-linux-001d"},
        "task": {"id": "D-137", "attempt": 1},
        "outcome": "PASS",
        "state": "CERTIFIED",
        "observations": {"target_moved": False, "unauthorized_mutations": 0},
        "receipt": {
            "receipt_id": "ASR-1234567890abcdef",
            "status": "valid",
            "event_id": "AE-orch-iv-001d",
        },
        "blockers": [],
        "requested_transition": None,
    }
    payload.update(overrides)
    return payload


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
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


def test_iv_001d_a_status_without_dispatch_has_no_authority(tmp_path: Path) -> None:
    _code, status = _run(tmp_path, "dispatch-status")
    assert status.get("execution_authorized", False) is False
    assert status.get("merge_authorized", False) is False
    assert status.get("process_started", False) is False


def test_iv_001d_b_owner_gate_dispatch_once_does_not_start_process(tmp_path: Path) -> None:
    envelope = tmp_path / "merge.json"
    _write_payload(
        envelope,
        _valid_payload(
            producer={"role": "integration", "agent_id": "iv-int"},
            state="MERGE_ELIGIBLE",
            requested_transition="MERGE",
        ),
    )
    assert _run(tmp_path, "cursor-stage-result", str(envelope))[0] == 0
    assert _run(tmp_path, "cursor-complete")[0] == 0
    code, report = _run(tmp_path, "dispatch-once")
    assert report.get("process_started", False) is False
    assert report.get("execution_authorized", False) is False
    assert report.get("merge_authorized", False) is False
    assert code != 0 or report.get("status") in {
        "OWNER_REQUIRED",
        "BLOCKED",
        "REJECTED",
        "NOT_ELIGIBLE",
        "OWNER_GATE",
    }


def test_iv_001d_c_terminal_dispatch_once_does_not_start_process(tmp_path: Path) -> None:
    envelope = tmp_path / "terminal.json"
    _write_payload(envelope, _valid_payload(receipt=None))
    assert _run(tmp_path, "cursor-stage-result", str(envelope))[0] == 0
    assert _run(tmp_path, "cursor-complete")[0] == 0
    code, report = _run(tmp_path, "dispatch-once")
    assert report.get("process_started", False) is False
    assert report.get("execution_authorized", False) is False
    assert code != 0 or report.get("status") in {"TERMINAL", "BLOCKED", "REJECTED", "NOT_ELIGIBLE"}


def test_iv_001d_d_missing_handoff_fail_closed(tmp_path: Path) -> None:
    code, report = _run(tmp_path, "dispatch-once")
    assert code != 0
    assert report.get("process_started", False) is False
    assert report.get("execution_authorized", False) is False
