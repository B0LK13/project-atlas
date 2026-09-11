"""G2 -- pause must stop the next dispatch, and silence must explain itself.

FIXTURE adapter only; zero model calls. The first worker writes the pause from
inside its own run, so the request arrives from OUTSIDE a live supervisor
without threads or timing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program.enrollment import (
    assign,
    enroll,
)
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.profiles import AdapterKind
from project_atlas.orchestration.program.supervisor import ProgramSupervisor

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")
PAUSING_WORKER = Path(__file__).with_name("_security_003_pausing_worker.py")
PROBE_WORKER = Path(__file__).with_name("_hardening_004_status_probe_worker.py")


def _profile(agent_id: str, *, argv: list[str] | None = None) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["IMPLEMENT"],
        "permission_mode": "acceptEdits",
        "limits": {"max_seconds": 120, "max_attempts": 1},
        "env_allowlist": [
            "ATLAS_FIXTURE_MODE",
            "ATLAS_FIXTURE_TARGET",
            "ATLAS_PROGRAM_ATTEMPT",
            "ATLAS_PROGRAM_TASK",
            "ATLAS_SEC003_STATE_ROOT",
            "ATLAS_H004_STATE_ROOT",
            "ATLAS_H004_PROBE_OUT",
            "ATLAS_H004_PROGRAM",
        ],
        "adapter_options": {"argv": argv or [sys.executable, str(FIXTURE_WORKER)]},
    }


def _task(task_id: str, profile_ref: str, out: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "title": task_id,
        "instruction": "fixture",
        "profile_ref": profile_ref,
        "mutation_paths": [out],
        "surface_id": task_id,
        "surface_semantic": task_id.upper().replace("-", "_"),
        "capabilities_required": ["IMPLEMENT"],
        "acceptance": [
            {
                "check_id": "out",
                "kind": "FILE_EXISTS",
                "description": f"{out} exists",
                "path": out,
            }
        ],
    }


def _write_program(
    tmp_path: Path,
    workspace: Path,
    *,
    tasks: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    name: str = "program.json",
) -> Path:
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "sec003",
            "objective": "security-003 regression",
            "approved_by": "test",
            "approval_reference": "SECURITY-003",
            "workspace_root": str(workspace),
            "base_pin": "0" * 40,
            "limits": {"max_cycles": 12, "idle_sleep_seconds": 0.0},
            "tasks": tasks,
        },
        "profiles": profiles,
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)



def test_g2_external_pause_stops_a_running_supervisor(tmp_path: Path) -> None:
    """G2: een pause die tijdens de run wordt gezet moet de volgende dispatch stoppen.

    De eerste worker schrijft zelf de pause naar de state-root, dus de pause
    komt van BUITEN terwijl de supervisor draait -- deterministisch, zonder
    threads of timing.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    state_root = tmp_path / "state"
    registry = tmp_path / "registry"
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("first", "pauser", "first.txt"), _task("second", "impl", "second.txt")],
        profiles={
            "pauser": _profile(
                "program-placeholder",
                argv=[sys.executable, str(PAUSING_WORKER)],
            ),
            "impl": _profile("program-placeholder"),
        },
    )
    agent = enroll(
        registry,
        agent_id="real-implementer",
        role="pauser",
        adapter=AdapterKind.LOCAL_COMMAND,
        workspace_root=workspace,
        enrolled_by="test",
    )
    assign(registry, agent_id=agent.agent_id, program_path=program, assigned_by="test")
    agent2 = enroll(
        registry,
        agent_id="real-impl2",
        role="impl",
        adapter=AdapterKind.LOCAL_COMMAND,
        workspace_root=workspace,
        enrolled_by="test",
    )
    assign(registry, agent_id=agent2.agent_id, program_path=program, assigned_by="test")

    import os

    os.environ["ATLAS_SEC003_STATE_ROOT"] = str(state_root)
    try:
        loaded = load_program(program)
        supervisor = ProgramSupervisor(
            loaded,
            state_root=state_root,
            enrolled_agents=(agent, agent2),
            registry_root=registry,
        )
        supervisor.start()
    finally:
        os.environ.pop("ATLAS_SEC003_STATE_ROOT", None)

    assert (workspace / "first.txt").exists(), "de eerste taak had moeten lopen"
    assert not (workspace / "second.txt").exists(), (
        "pause werd genegeerd: de volgende taak is alsnog gedispatcht"
    )


# --------------------------------------------------------------------- G3


def test_g2_stale_pause_sentinel_from_another_program_is_not_adopted(
    tmp_path: Path,
) -> None:
    """G2: een sentinel van een ANDER programma mag een verse run niet stoppen."""
    from project_atlas.orchestration.program.store import state_dir
    from project_atlas.orchestration.sdk.host import request_supervisor_pause

    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = tmp_path / "registry"
    state_root = tmp_path / "state"
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("only", "implementer", "only.txt")],
        profiles={"implementer": _profile("program-placeholder")},
    )
    agent = enroll(
        registry,
        agent_id="real-implementer",
        role="implementer",
        adapter=AdapterKind.LOCAL_COMMAND,
        workspace_root=workspace,
        enrolled_by="test",
    )
    assign(registry, agent_id=agent.agent_id, program_path=program, assigned_by="test")

    request_supervisor_pause(
        state_dir(state_root),
        program_id="a-completely-different-program",
        requested_by="someone-else",
        requested_at="2026-01-01T00:00:00Z",
    )

    loaded = load_program(program)
    supervisor = ProgramSupervisor(
        loaded,
        state_root=state_root,
        enrolled_agents=(agent,),
        registry_root=registry,
    )
    report = supervisor.start()

    assert (workspace / "only.txt").exists(), (
        "een pause-sentinel van een ander programma blokkeerde deze run stilzwijgend"
    )
    assert report.to_public_dict()["total_launches"] == 1


def test_g2_status_names_why_dispatch_is_withheld(tmp_path: Path) -> None:
    """G2: stilte moet zelfverklarend zijn, niet een raadsel."""
    from project_atlas.orchestration.program.control import pause

    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = tmp_path / "registry"
    state_root = tmp_path / "state"
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("only", "implementer", "only.txt")],
        profiles={"implementer": _profile("program-placeholder")},
    )
    agent = enroll(
        registry,
        agent_id="real-implementer",
        role="implementer",
        adapter=AdapterKind.LOCAL_COMMAND,
        workspace_root=workspace,
        enrolled_by="test",
    )
    assign(registry, agent_id=agent.agent_id, program_path=program, assigned_by="test")

    loaded = load_program(program)
    supervisor = ProgramSupervisor(
        loaded,
        state_root=state_root,
        enrolled_agents=(agent,),
        registry_root=registry,
    )
    supervisor.start()
    pause(state_root, requested_by="wesley", loaded=loaded)

    reasons = supervisor.status()["dispatch_withheld_because"]
    named = {item["reason"] for item in reasons}
    assert "PAUSED" in named or "PAUSE_SENTINEL_PRESENT" in named, (
        f"status noemt de pause niet als reden: {reasons}"
    )
    for item in reasons:
        assert item.get("clears_with"), f"reden zonder uitweg: {item}"
