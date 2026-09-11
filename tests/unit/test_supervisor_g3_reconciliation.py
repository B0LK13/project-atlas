"""G3 -- status and reconcile must agree, via B1 rather than a wider predicate.

The widened `ended_at is None` predicate an earlier round tried is NOT used:
it reported every RUNNING attempt as needing reconciliation. B1's in-flight
launch record is what separates a live worker from a killed one, so status
asks it -- the same source classify_attempt consults. The second test is the
false-positive control that caught the earlier mistake.
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
from project_atlas.orchestration.program.models import AttemptPhase
from project_atlas.orchestration.program.profiles import AdapterKind
from project_atlas.orchestration.program.store import load_state, persist_state
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



def test_g3_status_reports_what_reconcile_reports(tmp_path: Path) -> None:
    """G3: status en reconcile moeten dezelfde openstaande attempts noemen."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = tmp_path / "registry"
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

    state_root = tmp_path / "state"
    loaded = load_program(program)
    supervisor = ProgramSupervisor(
        loaded,
        state_root=state_root,
        enrolled_agents=(agent,),
        registry_root=registry,
    )
    supervisor.start()

    # Simuleer een supervisor die is gekilld VOOR hij de uitkomst vastlegde:
    # de attempt is niet TERMINAL en heeft geen confidence. Dat is precies de
    # toestand die na een kill op schijf achterblijft.
    state = load_state(state_root)
    assert state is not None
    attempt = next(iter(state.attempts.values()))
    attempt.phase = AttemptPhase.ADAPTER_INVOKED
    attempt.confidence = None
    attempt.ended_at = None
    persist_state(state_root, state)

    status = supervisor.status()
    reconcile = supervisor.reconcile()

    open_per_reconcile = {
        item["attempt_id"]
        for item in reconcile["interrupted_attempts"]
        if item["recovery_action"] == "NEEDS_RECONCILIATION"
    }
    open_per_status = {item["attempt_id"] for item in status["needs_reconciliation"]}

    assert open_per_reconcile, "opzetfout: reconcile zag geen onderbroken attempt"
    assert open_per_status == open_per_reconcile, (
        "status en reconcile spreken elkaar tegen over dezelfde state: "
        f"status={open_per_status} reconcile={open_per_reconcile}"
    )


# -------------------------------------------------------------------- G4a


def test_g3_running_attempt_is_not_reported_as_needing_reconciliation(
    tmp_path: Path,
) -> None:
    """G3 mag geen vals-positief geven voor een attempt die gewoon draait.

    Dit is de controle die een eerdere reparatieronde betrapte: een predicaat
    dat breed genoeg is om een gekillde attempt te vangen, meldt ook elke
    lopende -- en een signaal dat bij elke draaiende taak afgaat, wordt
    genegeerd. De worker vraagt hier tijdens zijn eigen run status() op.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = tmp_path / "registry"
    state_root = tmp_path / "state"
    probe_out = tmp_path / "probe.json"
    program = _write_program(
        tmp_path,
        workspace,
        tasks=[_task("probe", "implementer", "probe.txt")],
        profiles={
            "implementer": _profile(
                "program-placeholder",
                argv=[sys.executable, str(PROBE_WORKER)],
            )
        },
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

    import os

    os.environ["ATLAS_H004_STATE_ROOT"] = str(state_root)
    os.environ["ATLAS_H004_PROBE_OUT"] = str(probe_out)
    os.environ["ATLAS_H004_PROGRAM"] = str(program)
    try:
        loaded = load_program(program)
        ProgramSupervisor(
            loaded,
            state_root=state_root,
            enrolled_agents=(agent,),
            registry_root=registry,
        ).start()
    finally:
        for name in (
            "ATLAS_H004_STATE_ROOT",
            "ATLAS_H004_PROBE_OUT",
            "ATLAS_H004_PROGRAM",
        ):
            os.environ.pop(name, None)

    observed = json.loads(probe_out.read_text(encoding="utf-8"))
    assert observed["running"] == ["probe"], "opzetfout: de taak liep niet"
    assert observed["needs_reconciliation"] == [], (
        "een lopende attempt werd gemeld als te verzoenen: "
        f"{observed['needs_reconciliation']}"
    )
