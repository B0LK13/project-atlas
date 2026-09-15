"""T003F role-separated coding/reviewer budget counters.

Proves the T003E failure mode cannot recur under the new contract:
coding retries must not consume the reviewer reservation, and a candidate
at coding max must still be able to launch VERIFY.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.autonomy.models import NodeState
from project_atlas.orchestration.program.control import control_view
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import ProgramLimits, ProgramStopReason
from project_atlas.orchestration.program.store import (
    TaskRecord,
    load_state,
    persist_state,
)
from project_atlas.orchestration.program.supervisor import (
    CycleResult,
    DispatchMode,
    ProgramSupervisor,
)

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")


def _git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _git(workspace, "init", "--quiet")
    _git(workspace, "config", "user.email", "fixture@example.invalid")
    _git(workspace, "config", "user.name", "Fixture")
    (workspace / "README.md").write_text("fixture workspace\n", encoding="utf-8")
    _git(workspace, "add", "README.md")
    _git(workspace, "commit", "--quiet", "-m", "seed")
    return workspace


def _head(workspace: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return completed.stdout.strip()


def _profile(
    *,
    profile_id: str = "implementer",
    agent_id: str = "fixture-implementer",
    max_attempts: int = 3,
    capabilities: tuple[str, ...] = ("IMPLEMENT",),
) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": list(capabilities),
        "limits": {"max_seconds": 60, "max_attempts": max_attempts},
        "env_allowlist": [
            "ATLAS_FIXTURE_MODE",
            "ATLAS_FIXTURE_TARGET",
            "ATLAS_PROGRAM_ATTEMPT",
            "ATLAS_PROGRAM_TASK",
        ],
        "adapter_options": {
            "argv": [sys.executable, str(FIXTURE_WORKER)],
        },
        "description": f"FIXTURE {profile_id}",
    }


def _task(
    task_id: str,
    *,
    output: str,
    iv: bool = False,
    verifier: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "task_id": task_id,
        "title": f"fixture task {task_id}",
        "instruction": f"write {output}",
        "profile_ref": "implementer",
        "depends_on": [],
        "mutation_paths": [output],
        "surface_id": f"surface-{task_id}",
        "surface_semantic": task_id.upper().replace("-", "_"),
        "capabilities_required": ["IMPLEMENT"],
        "acceptance": [
            {
                "check_id": f"{task_id}-output",
                "kind": "FILE_EXISTS",
                "description": f"{output} exists",
                "path": output,
            }
        ],
        "retry_safe_when_no_launch_evidence": False,
    }
    if iv:
        body["requires_independent_verification"] = True
    if verifier:
        body["verifier_profile_ref"] = verifier
    return body


def _write_program(
    tmp_path: Path,
    workspace: Path,
    *,
    tasks: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]] | None = None,
    limits: dict[str, Any] | None = None,
) -> Path:
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "t003f-budget",
            "objective": "role-separated budget fixture",
            "approved_by": "fixture-owner",
            "approval_reference": "docs/orchestration/program/ACCEPTANCE.md",
            "workspace_root": str(workspace),
            "base_pin": _head(workspace),
            "tasks": tasks,
            "limits": limits
            or {
                "max_cycles": 20,
                "idle_sleep_seconds": 0.0,
                "max_coding_attempts": 2,
                "reserved_reviewer_launches": 1,
                "max_task_launches": 3,
            },
        },
        "profile_defaults": {
            "adapter": "local-command",
            "credential": "NOT_APPLICABLE",
        },
        "profiles": profiles or {"implementer": _profile()},
    }
    path = tmp_path / "program.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _supervisor(program_path: Path, tmp_path: Path) -> ProgramSupervisor:
    loaded = load_program(program_path)
    return ProgramSupervisor(
        loaded, state_root=tmp_path / "state", sleeper=lambda _seconds: None
    )


def test_reserved_plus_coding_must_fit_total_launches() -> None:
    with pytest.raises(ValidationError, match="max_coding_attempts \\+ reserved_reviewer"):
        ProgramLimits(
            max_coding_attempts=2,
            reserved_reviewer_launches=2,
            max_task_launches=3,
        )
    ok = ProgramLimits(
        max_coding_attempts=2,
        reserved_reviewer_launches=1,
        max_task_launches=3,
    )
    assert ok.max_coding_attempts == 2
    assert ok.reserved_reviewer_launches == 1
    legacy = ProgramLimits()
    assert legacy.max_coding_attempts is None
    assert legacy.reserved_reviewer_launches == 0


def test_coding_retry_cannot_consume_reviewer_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two failed coding attempts leave the reserved launch unused."""
    workspace = _make_workspace(tmp_path)
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "claim-only")
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("prime-a1", output="never.txt")],
        profiles={"implementer": _profile(max_attempts=2)},
        limits={
            "max_cycles": 10,
            "idle_sleep_seconds": 0.0,
            "max_idle_cycles": 2,
            "max_coding_attempts": 2,
            "reserved_reviewer_launches": 1,
            "max_task_launches": 3,
            "max_attempts_per_task": 2,
        },
    )
    _supervisor(program, tmp_path).start()
    state = load_state(tmp_path / "state")
    assert state is not None
    record = state.tasks["prime-a1"]
    assert record.coding_attempts == 2
    assert record.reviewer_launches == 0
    assert record.candidate_present is False
    assert "FAIL_NO_CANDIDATE" in record.reason
    # Reservation held: coding used at most max_task_launches - reserved.
    assert state.total_launches == 2
    assert record.launches == 2
    assert supervisor_coding_room(state, max_task_launches=3, reserved=1) == 0


def supervisor_coding_room(state: Any, *, max_task_launches: int, reserved: int) -> int:
    return max(0, max_task_launches - reserved - state.total_launches)


def test_reviewer_budget_never_becomes_coding_capacity(tmp_path: Path) -> None:
    """When only the reserved slot remains, coding dispatch is refused."""
    workspace = _make_workspace(tmp_path)
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("prime-a1", output="never.txt")],
        profiles={"implementer": _profile(max_attempts=2)},
        limits={
            "max_cycles": 8,
            "idle_sleep_seconds": 0.0,
            "max_idle_cycles": 2,
            "max_coding_attempts": 2,
            "reserved_reviewer_launches": 1,
            "max_task_launches": 3,
            "max_attempts_per_task": 2,
        },
    )
    supervisor = _supervisor(program, tmp_path)
    state = supervisor.load_or_init_state()
    record = state.tasks["prime-a1"]
    record.state = NodeState.REMEDIATING
    record.coding_attempts = 1  # coding budget remains, launch room does not
    record.attempts = 1
    record.launches = 2
    state.total_launches = 2
    persist_state(supervisor.root, state)

    result = CycleResult(cycle=0)
    choice = supervisor._choose(state, result)
    assert choice is None
    assert any("coding launch room exhausted" in note for note in result.notes)
    assert state.tasks["prime-a1"].reviewer_launches == 0
    assert supervisor._coding_launch_room(state) == 0


def test_no_candidate_after_coding_budget_fail_no_candidate(tmp_path: Path) -> None:
    workspace = _make_workspace(tmp_path)
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("prime-a1", output="never.txt")],
        profiles={"implementer": _profile(max_attempts=2)},
        limits={
            "max_cycles": 8,
            "idle_sleep_seconds": 0.0,
            "max_coding_attempts": 2,
            "reserved_reviewer_launches": 1,
            "max_task_launches": 3,
            "max_attempts_per_task": 2,
        },
    )
    supervisor = _supervisor(program, tmp_path)
    state = supervisor.load_or_init_state()
    record = state.tasks["prime-a1"]
    record.state = NodeState.REMEDIATING
    record.coding_attempts = 2
    record.attempts = 2
    record.candidate_present = False
    persist_state(supervisor.root, state)

    result = CycleResult(cycle=0)
    choice = supervisor._choose(state, result)
    assert choice is None
    assert state.tasks["prime-a1"].state is NodeState.BLOCKED
    assert "FAIL_NO_CANDIDATE" in state.tasks["prime-a1"].reason


def test_candidate_present_reviewer_still_available_at_coding_max(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Coding at max with a candidate must not seal VERIFY behind attempt budget."""
    workspace = _make_workspace(tmp_path)
    (workspace / "verified.txt").write_text("candidate\n", encoding="utf-8")
    monkeypatch.setenv("ATLAS_FIXTURE_TARGET", "verified.txt")
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[
            _task("prime-a1", output="verified.txt", iv=True, verifier="verifier"),
        ],
        profiles={
            "implementer": _profile(agent_id="fixture-implementer", max_attempts=2),
            "verifier": _profile(
                profile_id="verifier",
                agent_id="fixture-verifier",
                max_attempts=1,
                capabilities=("VERIFY",),
            ),
        },
        limits={
            "max_cycles": 6,
            "idle_sleep_seconds": 0.0,
            "max_idle_cycles": 2,
            "max_coding_attempts": 2,
            "reserved_reviewer_launches": 1,
            "max_task_launches": 3,
            "max_attempts_per_task": 2,
        },
    )
    supervisor = _supervisor(program, tmp_path)
    state = supervisor.load_or_init_state()
    record = state.tasks["prime-a1"]
    record.coding_attempts = 2
    record.attempts = 2
    record.launches = 2
    record.reviewer_launches = 0
    record.candidate_present = True
    record.awaiting_independent_verification = True
    record.state = NodeState.VERIFYING
    state.total_launches = 2
    persist_state(supervisor.root, state)

    # Gate: VERIFY is chosen even though coding attempts are at max.
    probe = CycleResult(cycle=0)
    choice = supervisor._choose(state, probe)
    assert choice is not None
    assert choice.mode is DispatchMode.VERIFY

    report = supervisor.start()
    state_after = load_state(tmp_path / "state")
    assert state_after is not None
    record_after = state_after.tasks["prime-a1"]
    assert record_after.coding_attempts == 2, "VERIFY must not burn coding budget"
    assert record_after.reviewer_launches == 1
    assert record_after.state is NodeState.CERTIFIED
    assert report.stop_reason is ProgramStopReason.PROGRAM_COMPLETE

    view = control_view(tmp_path / "state", load_program(program))
    budget = view["limits"]["budget"]
    assert budget["reserved_reviewer_launches"] == 1
    assert budget["tasks"]["prime-a1"]["coding_attempts"] == 2
    assert budget["tasks"]["prime-a1"]["reviewer_launches"] == 1


def test_crash_resume_counters_survive_reload(tmp_path: Path) -> None:
    """Persisted role counters keep VERIFY eligible after supervisor reload."""
    workspace = _make_workspace(tmp_path)
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[
            _task("prime-a1", output="out.txt", iv=True, verifier="verifier"),
        ],
        profiles={
            "implementer": _profile(agent_id="fixture-implementer", max_attempts=2),
            "verifier": _profile(
                profile_id="verifier",
                agent_id="fixture-verifier",
                max_attempts=1,
                capabilities=("VERIFY",),
            ),
        },
        limits={
            "max_cycles": 6,
            "idle_sleep_seconds": 0.0,
            "max_idle_cycles": 1,
            "max_coding_attempts": 2,
            "reserved_reviewer_launches": 1,
            "max_task_launches": 3,
            "max_attempts_per_task": 2,
        },
    )
    first = _supervisor(program, tmp_path)
    state = first.load_or_init_state()
    record = state.tasks["prime-a1"]
    record.coding_attempts = 2
    record.attempts = 2
    record.launches = 2
    record.reviewer_launches = 0
    record.candidate_present = True
    record.awaiting_independent_verification = True
    record.state = NodeState.VERIFYING
    state.total_launches = 2
    persist_state(tmp_path / "state", state)

    reloaded = load_state(tmp_path / "state")
    assert reloaded is not None
    restored = reloaded.tasks["prime-a1"]
    assert restored.coding_attempts == 2
    assert restored.reviewer_launches == 0
    assert restored.candidate_present is True
    assert restored.awaiting_independent_verification is True

    resumed = _supervisor(program, tmp_path)
    result = CycleResult(cycle=0)
    choice = resumed._choose(reloaded, result)
    assert choice is not None
    assert choice.mode is DispatchMode.VERIFY
    assert choice.task_id == "prime-a1"

    blank = TaskRecord(task_id="fresh")
    assert blank.coding_attempts == 0
    assert blank.reviewer_launches == 0
    assert blank.candidate_present is False
