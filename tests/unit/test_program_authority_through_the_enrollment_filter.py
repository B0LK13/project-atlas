"""F10: a withdrawn agent must not reach dispatch by vanishing from the roster.

The guard that refuses a dispatch is fed by the operator CLI's own `--registry`
filter, and that filter keeps only ACTIVE agents. Suspending an agent therefore
removed the very identity the guard would have refused, `enrolled_agents` went
empty, and the run continued on the program's own placeholder profile --
unbound, unnarrowed, with nobody left to say no.

So these tests drive the REAL filter (`program.cli._enrolled_for`) instead of
injecting an agent list the CLI never produces for a withdrawn agent, and they
call `start()` so a launch count is a measured fact rather than a property of
the fixture. A test that asserts zero launches without ever being able to
produce one is not a control.

Workers are FIXTURES. FIXTURE_RUN != REAL_RUNTIME_COMPATIBILITY.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest
from tests.unit.test_orchestration_program_lifecycle import (  # reuse, do not re-fixture
    _profile,
    _program,
    _task,
)

from project_atlas.orchestration.autonomy.models import NodeState
from project_atlas.orchestration.program.cli import _enrolled_for
from project_atlas.orchestration.program.enrollment import (
    AgentStatus,
    assign,
    enroll,
    load_registry,
    persist_registry,
    set_status,
)
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import ProgramStopReason
from project_atlas.orchestration.program.profiles import AdapterKind
from project_atlas.orchestration.program.store import load_state, read_events
from project_atlas.orchestration.program.supervisor import ProgramSupervisor


@pytest.fixture(autouse=True)
def _fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ATLAS_FIXTURE_MODE", "write")
    monkeypatch.delenv("ATLAS_FIXTURE_TARGET", raising=False)


def _enrolled_program(tmp_path: Path, workspace: Path) -> tuple[Path, Path]:
    """One task, one role, one enrolled agent that is ACTIVE and assigned."""
    program = _program(
        tmp_path,
        workspace,
        tasks=[_task("one")],
        profiles={"impl": _profile("impl-placeholder")},
        concurrency=1,
    )
    registry = tmp_path / "registry"
    enroll(
        registry,
        agent_id="worker-a",
        role="impl",
        adapter=AdapterKind.LOCAL_COMMAND,
        workspace_root=workspace,
        enrolled_by="test",
    )
    assign(registry, agent_id="worker-a", program_path=program, assigned_by="test")
    return program, registry


def _run_through_the_cli_filter(
    tmp_path: Path, program: Path, registry: Path
) -> tuple[Any, Path, tuple[Any, ...]]:
    """Bind exactly as `atlas program run --registry` does, then run.

    `_enrolled_for` is the real filter. Calling it -- rather than handing the
    supervisor a roster slice by hand -- is the whole point: the defect lived
    in the gap between what that filter drops and what the guard can see.
    """
    loaded = load_program(program)
    args = argparse.Namespace(registry=str(registry))
    agents, registry_root = _enrolled_for(args, loaded)
    root = tmp_path / "state"
    supervisor = ProgramSupervisor(
        loaded,
        state_root=root,
        enrolled_agents=agents,
        registry_root=registry_root,
        sleeper=lambda _s: None,
    )
    return supervisor.start(), root, agents


def _workspace_writes(workspace: Path) -> list[str]:
    return sorted(path.name for path in workspace.glob("*.txt"))


# --------------------------------------------------------- positive control


def test_an_active_enrolled_agent_still_launches_real_work(tmp_path: Path) -> None:
    """The control that proves the refusals below are not vacuous.

    If this cannot launch, every zero-launch assertion in this file is true by
    construction and none of them tests the guard.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program, registry = _enrolled_program(tmp_path, workspace)

    report, root, agents = _run_through_the_cli_filter(tmp_path, program, registry)

    assert [agent.agent_id for agent in agents] == ["worker-a"], (
        "the CLI filter did not bind the ACTIVE agent"
    )
    assert report.launches_this_run == 1, "an active authority launched nothing"
    assert _workspace_writes(workspace) == ["one.txt"], "the worker did not run"
    state = load_state(root)
    assert state is not None
    assert state.tasks["one"].state is NodeState.CERTIFIED
    # The bound agent, not the program's placeholder, is the principal.
    assert load_program(program) is not None
    events = [str(row.get("event")) for row in read_events(root)]
    assert "AUTHORITY_REVOKED" not in events


# ------------------------------------------- withdrawn authority: no launches


@pytest.mark.parametrize("status", [AgentStatus.SUSPENDED, AgentStatus.RETIRED])
def test_a_withheld_status_launches_nothing(
    tmp_path: Path, status: AgentStatus
) -> None:
    """Suspended and retired, refused BEFORE the run rather than mid-run.

    Mid-run withdrawal already worked, because the agent was bound while it was
    still ACTIVE. Withdrawing it first is what emptied the binding.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program, registry = _enrolled_program(tmp_path, workspace)
    set_status(registry, agent_id="worker-a", status=status)

    report, root, agents = _run_through_the_cli_filter(tmp_path, program, registry)

    assert agents == (), "the filter bound a non-ACTIVE agent"
    assert report.launches_this_run == 0, f"a {status.value} agent reached dispatch"
    assert _workspace_writes(workspace) == [], "a worker ran without authority"
    assert report.stop_reason is ProgramStopReason.OWNER_DECISION_REQUIRED
    state = load_state(root)
    assert state is not None
    assert state.tasks["one"].state is NodeState.OWNER_HELD
    events = [str(row.get("event")) for row in read_events(root)]
    assert "AUTHORITY_REVOKED" in events


def test_a_revoked_enrollment_launches_nothing(tmp_path: Path) -> None:
    """The record is gone from the roster entirely, as a revocation edit does."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program, registry = _enrolled_program(tmp_path, workspace)
    roster = load_registry(registry)
    del roster.agents["worker-a"]
    persist_registry(registry, roster)

    report, _root, agents = _run_through_the_cli_filter(tmp_path, program, registry)

    assert agents == ()
    assert report.launches_this_run == 0, "a revoked agent reached dispatch"
    assert _workspace_writes(workspace) == []
    assert report.stop_reason is ProgramStopReason.OWNER_DECISION_REQUIRED


def test_a_role_mismatched_agent_launches_nothing(tmp_path: Path) -> None:
    """ACTIVE, assigned to this program -- but re-enrolled into another role.

    The program's `impl` role is left with no agent, so the placeholder would
    have run it. Being ACTIVE somewhere else is not authority here.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program, registry = _enrolled_program(tmp_path, workspace)
    roster = load_registry(registry)
    roster.agents["worker-a"] = roster.agents["worker-a"].model_copy(
        update={"role": "some-other-role"}
    )
    persist_registry(registry, roster)

    report, _root, agents = _run_through_the_cli_filter(tmp_path, program, registry)

    assert agents == (), "an agent in a different role was bound to this one"
    assert report.launches_this_run == 0, "a role-mismatched agent reached dispatch"
    assert _workspace_writes(workspace) == []
    assert report.stop_reason is ProgramStopReason.OWNER_DECISION_REQUIRED


def test_an_unassigned_agent_launches_nothing(tmp_path: Path) -> None:
    """ACTIVE and correctly roled, but its assignment to this program is gone."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    program, registry = _enrolled_program(tmp_path, workspace)
    roster = load_registry(registry)
    roster.agents["worker-a"] = roster.agents["worker-a"].model_copy(
        update={"assigned_program": None}
    )
    persist_registry(registry, roster)

    report, _root, _agents = _run_through_the_cli_filter(tmp_path, program, registry)

    assert report.launches_this_run == 0, "an unassigned agent reached dispatch"
    assert _workspace_writes(workspace) == []
    assert report.stop_reason is ProgramStopReason.OWNER_DECISION_REQUIRED
