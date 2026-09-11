"""G1 -- registry binding across all three dispatch paths.

No production code accompanies this module: F10 (`cd99d835`) already closed the
empty-roster escape on the shared authority path. These are the negative
controls that keep it closed, because the defect it fixed was invisible from
the outside -- an unbound run and a bound one produced the same output.

Every case asserts **zero launches**, not merely a non-zero exit: a refusal
that still started a worker is not a refusal. The program's placeholder
`agent_id` exists in no registry, so a lease carrying it proves the dispatch ran
unattributed.

FIXTURE adapter only; zero model calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.program import service
from project_atlas.orchestration.program.enrollment import (
    AgentStatus,
    EnrollmentError,
    assign,
    enroll,
    set_status,
)
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.profiles import AdapterKind
from project_atlas.orchestration.program.store import load_state
from project_atlas.orchestration.program.supervisor import ProgramSupervisor

FIXTURE_WORKER = Path(__file__).with_name("_program_fixture_worker.py")
PLACEHOLDER = "PROGRAM-PLACEHOLDER-BOUND-TO-NOBODY"


def _profile(agent_id: str) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "adapter": "local-command",
        "credential": "NOT_APPLICABLE",
        "capabilities": ["IMPLEMENT"],
        "permission_mode": "acceptEdits",
        "limits": {"max_seconds": 60, "max_attempts": 1},
        "env_allowlist": ["ATLAS_FIXTURE_MODE", "ATLAS_PROGRAM_TASK"],
        "adapter_options": {"argv": [sys.executable, str(FIXTURE_WORKER)]},
    }


def _write_program(tmp_path: Path, workspace: Path, *, name: str = "program.json",
                   program_id: str = "g1") -> Path:
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": program_id,
            "objective": "G1 authority coverage",
            "approved_by": "test",
            "approval_reference": "HARDENING-006",
            "workspace_root": str(workspace),
            "base_pin": "0" * 40,
            "limits": {"max_cycles": 6, "idle_sleep_seconds": 0.0},
            "tasks": [
                {
                    "task_id": "only",
                    "title": "only",
                    "instruction": "fixture",
                    "profile_ref": "implementer",
                    "mutation_paths": ["only.txt"],
                    "surface_id": "only",
                    "surface_semantic": "ONLY",
                    "capabilities_required": ["IMPLEMENT"],
                    "acceptance": [
                        {
                            "check_id": "out",
                            "kind": "FILE_EXISTS",
                            "description": "only.txt exists",
                            "path": "only.txt",
                        }
                    ],
                }
            ],
        },
        "profiles": {"implementer": _profile(PLACEHOLDER)},
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)


def _assert_nothing_ran(workspace: Path, state_root: Path) -> None:
    """Zero launches, and no lease under an unenrolled principal."""
    assert not (workspace / "only.txt").exists(), "a refused dispatch still ran a worker"
    state = load_state(state_root)
    if state is None:
        return
    assert state.total_launches == 0, f"launches={state.total_launches}, expected 0"
    principals = {a.agent_id for a in state.attempts.values()}
    assert PLACEHOLDER not in principals, (
        f"a lease carries the program placeholder, so the run was unattributed: {principals}"
    )


def _supervisor(program: Path, state_root: Path, registry: Path, agents: tuple[Any, ...]):
    return ProgramSupervisor(
        load_program(program),
        state_root=state_root,
        enrolled_agents=agents,
        registry_root=registry,
    )


# ---------------------------------------------------------------- foreground

@pytest.mark.parametrize(
    "enrollment",
    ["missing", "suspended", "retired", "mismatched", "unassigned"],
)
def test_foreground_refuses_and_launches_nothing(tmp_path: Path, enrollment: str) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = tmp_path / "registry"
    state_root = tmp_path / "state"
    program = _write_program(tmp_path, workspace)
    other = _write_program(tmp_path, workspace, name="other.json", program_id="other")

    agents: tuple[Any, ...] = ()
    if enrollment != "missing":
        agent = enroll(
            registry,
            agent_id="a1",
            role="implementer",
            adapter=AdapterKind.LOCAL_COMMAND,
            workspace_root=workspace,
            enrolled_by="test",
        )
        if enrollment in ("suspended", "retired"):
            assign(registry, agent_id="a1", program_path=program, assigned_by="test")
            set_status(
                registry,
                agent_id="a1",
                status=AgentStatus.SUSPENDED
                if enrollment == "suspended"
                else AgentStatus.RETIRED,
            )
            # `cli._enrolled_for` keeps only ACTIVE agents, so the supervisor is
            # built with an empty roster -- exactly the shape that used to run
            # unbound.
            agents = ()
        elif enrollment == "mismatched":
            assign(registry, agent_id="a1", program_path=other, assigned_by="test")
            agents = (agent,)
        else:  # unassigned
            agents = (agent,)

    _supervisor(program, state_root, registry, agents).start()
    _assert_nothing_ran(workspace, state_root)


# ------------------------------------------------------------------ detached

@pytest.mark.parametrize(
    "enrollment",
    ["missing", "suspended", "retired", "mismatched", "unassigned"],
)
def test_detached_refuses_before_it_detaches(tmp_path: Path, enrollment: str) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = tmp_path / "registry"
    state_root = tmp_path / "state"
    program = _write_program(tmp_path, workspace)
    other = _write_program(tmp_path, workspace, name="other.json", program_id="other")

    if enrollment != "missing":
        enroll(
            registry,
            agent_id="a1",
            role="implementer",
            adapter=AdapterKind.LOCAL_COMMAND,
            workspace_root=workspace,
            enrolled_by="test",
        )
        if enrollment in ("suspended", "retired"):
            assign(registry, agent_id="a1", program_path=program, assigned_by="test")
            set_status(
                registry,
                agent_id="a1",
                status=AgentStatus.SUSPENDED
                if enrollment == "suspended"
                else AgentStatus.RETIRED,
            )
        elif enrollment == "mismatched":
            assign(registry, agent_id="a1", program_path=other, assigned_by="test")

    with pytest.raises(service.ServiceError) as excinfo:
        service.run(state_root, program, registry_root=registry, max_rounds=1)
    assert excinfo.value.code == "REGISTRY_BINDING_MISSING"
    _assert_nothing_ran(workspace, state_root)


# -------------------------------------------------------------- agent launch

@pytest.mark.parametrize(
    ("enrollment", "expected_code"),
    [
        ("missing", "UNKNOWN_AGENT"),
        ("suspended", "AGENT_NOT_ACTIVE"),
        ("retired", "AGENT_NOT_ACTIVE"),
        ("unassigned", "NO_ASSIGNMENT"),
    ],
)
def test_agent_launch_refuses_and_launches_nothing(
    tmp_path: Path, enrollment: str, expected_code: str
) -> None:
    """`agent launch` is program-FOLLOWING: it runs the agent's own assignment.

    There is deliberately no "mismatched" case here. The command takes no
    `--program`, so an agent assigned elsewhere runs that other program by
    design rather than running this one under the wrong binding. Asserting a
    refusal there would encode a misunderstanding of the command as a
    requirement.
    """
    from project_atlas.orchestration.program import cli as program_cli

    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = tmp_path / "registry"
    state_root = tmp_path / "state"
    program = _write_program(tmp_path, workspace)

    if enrollment != "missing":
        enroll(
            registry,
            agent_id="a1",
            role="implementer",
            adapter=AdapterKind.LOCAL_COMMAND,
            workspace_root=workspace,
            enrolled_by="test",
        )
        if enrollment in ("suspended", "retired"):
            assign(registry, agent_id="a1", program_path=program, assigned_by="test")
            set_status(
                registry,
                agent_id="a1",
                status=AgentStatus.SUSPENDED
                if enrollment == "suspended"
                else AgentStatus.RETIRED,
            )

    import argparse

    args = argparse.Namespace(
        registry=str(registry), agent_id="a1", state_root=str(state_root)
    )
    with pytest.raises(EnrollmentError) as excinfo:
        program_cli.run_agent_launch(args)
    assert excinfo.value.code == expected_code
    _assert_nothing_ran(workspace, state_root)
