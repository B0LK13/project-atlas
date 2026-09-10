"""B1 reproducer: in-flight process identity is not durable until adapter return.

Owner: program-supervisor package (#797 lane).
Integration agent MUST NOT patch supervisor spawn paths — deliver this
reproducer and integrate only a transferable owner fix.

Finding (from ATLAS-END-TO-END-INTEGRATION-PROOF-001 / 03-RAPPORT.md §B1):
  adapters/base.py computes pid + process_start_identity at spawn, but
  AttemptRecord only receives them in supervisor._settle_running on
  ADAPTER_RETURNED. At ADAPTER_INVOKED, process_pid is None, so
  recovery.worker_still_alive() cannot return True on the interrupt path
  that exists for this purpose.

This module reconfirms the finding against the live-integration candidate
without mutating supervisor ownership.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program.recovery import worker_still_alive
from project_atlas.orchestration.program.store import AttemptPhase, load_state
from project_atlas.orchestration.program.supervisor import ProgramSupervisor
from tests.unit.test_orchestration_program_supervisor import (
    _make_workspace,
    _profile,
    _supervisor,
    _task,
    _write_program,
)


def test_b1_process_identity_absent_while_adapter_still_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """While a hang fixture is alive, durable AttemptRecord has no PID."""
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "hang")
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("hangs", output="never.txt")],
        profiles={"implementer": _profile(max_seconds=3600)},
        limits={"max_cycles": 4, "idle_sleep_seconds": 0.0, "max_task_seconds": 30},
    )
    supervisor = _supervisor(program, tmp_path)
    seen: dict[str, Any] = {}
    original_begin = supervisor._begin_dispatch

    def begin_and_probe(state: Any, choice: Any, result: Any) -> Any:
        running = original_begin(state, choice, result)
        # Persist already flipped to ADAPTER_INVOKED inside _begin_dispatch.
        reloaded = load_state(tmp_path / "state")
        assert reloaded is not None
        attempt = reloaded.attempts[running.attempt_id]
        seen["phase"] = attempt.phase
        seen["process_pid"] = attempt.process_pid
        seen["process_start_identity"] = attempt.process_start_identity
        seen["attempt_id"] = running.attempt_id
        # Cancel so the hang does not block the suite forever.
        state.cancel_requested = True
        return running

    supervisor._begin_dispatch = begin_and_probe  # type: ignore[method-assign]
    report = supervisor.start()
    assert seen.get("phase") is AttemptPhase.ADAPTER_INVOKED
    assert seen.get("process_pid") is None
    assert seen.get("process_start_identity") is None
    # Missing durable PID must not be read as "worker gone" certainty.
    reloaded = load_state(tmp_path / "state")
    assert reloaded is not None
    attempt = reloaded.attempts[seen["attempt_id"]]
    alive = worker_still_alive(attempt)
    assert alive is False  # current API: no record ⇒ not confirmed alive
    # Document the honesty gap for the owner: UNKNOWN, not GONE.
    finding = {
        "finding_id": "B1",
        "status": "CONFIRMED",
        "IN_FLIGHT_PROCESS_VISIBILITY": "NO",
        "observed": {
            "phase_at_probe": str(seen["phase"]),
            "process_pid": seen["process_pid"],
            "process_start_identity": seen["process_start_identity"],
            "worker_still_alive_return": alive,
            "stop_reason": report.stop_reason.value,
        },
        "required_fix_properties": [
            "persist pid+start_identity before adapter return without weakening fail-closed recovery",
            "missing PID record ⇒ UNKNOWN, never authorize launch/lease release",
            "PID alone insufficient; use existing start-identity check",
        ],
        "owner": "program-supervisor (#797)",
        "integration_agent_action": "HANDOFF_ONLY — no supervisor spawn edit in this lane",
    }
    out = tmp_path / "B1_FINDING.json"
    out.write_text(json.dumps(finding, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert finding["status"] == "CONFIRMED"


def test_b1_fast_exit_still_records_pid_only_after_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.setenv("ATLAS_FIXTURE_TARGET", "out.txt")
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("fast", output="out.txt")],
        profiles={"implementer": _profile()},
    )
    report = _supervisor(program, tmp_path).start()
    state = load_state(tmp_path / "state")
    assert state is not None
    attempt = next(iter(state.attempts.values()))
    # After return, identity is present — proves the post-return path works.
    assert attempt.process_pid is not None
    assert attempt.process_start_identity is not None
    assert report.complete or report.stop_reason is not None
