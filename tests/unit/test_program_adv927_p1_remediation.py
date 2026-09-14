"""Regression for ADV #927 P1-1..P1-4 on the program supervisor carrier.

Each case was independently reproduced against ``95594566`` / ``71fb93c6``.
These tests bind the remediations; they do not transfer certification.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from project_atlas.orchestration.autonomy.lease_projection import (
    active_rows,
    load_projection,
    project_grant,
)
from project_atlas.orchestration.autonomy.models import (
    EXPECTED_BASE_MAIN,
    AgentCapability,
    AgentLease,
    ExecutionHostClass,
    IvRequirements,
    MutationSurface,
    NodeState,
    WorkNode,
)
from project_atlas.orchestration.autonomy.overlap import surfaces_overlap, would_overlap
from project_atlas.orchestration.program.adapters.base import (
    AdapterRequest,
    process_start_identity,
)
from project_atlas.orchestration.program.adapters.claude_code import ClaudeCodeAdapter
from project_atlas.orchestration.program.adapters.codex import CodexAdapter
from project_atlas.orchestration.program.blocked_work import handle_blocked_task
from project_atlas.orchestration.program.continuation import (
    CheckpointPolicy,
    ReplayClass,
    TaskBudgets,
    TaskEnvelope,
    persist_envelope,
)
from project_atlas.orchestration.program.decisions import DecisionKind
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import (
    AcceptanceCheck,
    AcceptanceKind,
    ExecutionConfidence,
)
from project_atlas.orchestration.program.path_safety import ContainmentError
from project_atlas.orchestration.program.profiles import AgentProfile
from project_atlas.orchestration.program.store import (
    AttemptRecord,
    ProgramStateRecord,
    TaskRecord,
    persist_state,
    state_dir,
)
from project_atlas.orchestration.program.supervisor import ProgramSupervisor

INSTALLED_STAND_IN = sys.executable


def _node(
    package_id: str,
    *,
    state: NodeState = NodeState.READY,
    surface: str = "surface-a",
    semantic: str = "SEMANTIC_A",
    paths: tuple[str, ...] = ("src/a",),
) -> WorkNode:
    return WorkNode(
        package_id=package_id,
        objective="test node",
        base_pin=EXPECTED_BASE_MAIN,
        dependencies=(),
        mutation_surface=MutationSurface(
            surface_id=surface,
            paths=paths,
            semantic=semantic,
        ),
        execution_host_class=ExecutionHostClass.IN_PROCESS,
        agent_capabilities_required=(AgentCapability.IMPLEMENT,),
        acceptance_criteria=("PASS",),
        iv_requirements=IvRequirements(certification_required=True),
        state=state,
    )


def _codex_profile(**overrides: Any) -> AgentProfile:
    body: dict[str, Any] = {
        "profile_id": "codex-impl",
        "agent_id": "codex-impl",
        "adapter": "codex",
        "capabilities": ["IMPLEMENT"],
        "permission_mode": "acceptEdits",
    }
    body.update(overrides)
    return AgentProfile.model_validate(body)


def _request(workspace: Path, profile: AgentProfile) -> AdapterRequest:
    return AdapterRequest(
        program_id="p",
        task_id="t",
        attempt_id="a1",
        attempt_number=1,
        idempotency_key="k",
        instruction="do the thing",
        workspace=workspace,
        profile=profile,
        session_id=None,
        resume_session_id=None,
        timeout_seconds=60,
        evidence_dir=workspace / "evidence",
    )

ZERO_PIN = "0" * 40
ZERO_DIGEST = "0" * 64


def _envelope(task_id: str, worker_id: str = "fixture-worker-01") -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id,
        objective=f"fixture task {task_id}",
        capabilities_required=("IMPLEMENT",),
        candidate_head="a" * 40,
        candidate_tree="b" * 40,
        allowed_paths=(f"{task_id}.txt",),
        acceptance=(
            AcceptanceCheck(
                check_id=f"{task_id}-out",
                kind=AcceptanceKind.FILE_EXISTS,
                description=f"{task_id}.txt exists",
                path=f"{task_id}.txt",
            ),
        ),
        budgets=TaskBudgets(),
        checkpoint_policy=CheckpointPolicy(steps=()),
        fallback_task_ids=(),
        replay_class=ReplayClass.IDEMPOTENT_MUTATION,
        approved_by="fixture-operator",
        approval_reference="tests/unit/test_program_adv927_p1_remediation.py",
        profile_ref="impl",
        worker_id=worker_id,
        program_id="fixture-program",
    )


def _grant_projected_lease(root: Path, *, task_id: str, agent_id: str) -> None:
    lease = AgentLease(
        lease_id=f"{task_id}-lease",
        agent_id=agent_id,
        package_id=task_id,
        branch="fixture-branch",
        worktree=str(root),
        base_pin=ZERO_PIN,
        authorized_paths=(f"{task_id}.txt",),
        capabilities=(AgentCapability.IMPLEMENT,),
        start_state=NodeState.READY,
        expected_output="fixture output",
        expiry_or_terminal_condition="TERMINAL",
        active=True,
        sequence=1,
    )
    project_grant(root, lease, live_main=ZERO_PIN)


def _block(
    root: Path,
    envelope: TaskEnvelope,
    *,
    lease_root: Path | None,
    worker_id: str = "fixture-worker-01",
) -> Any:
    return handle_blocked_task(
        root,
        envelope=envelope,
        kind=DecisionKind.PERMISSION,
        subject="WRITE_OUTSIDE_ALLOWED_PATHS",
        question="May this task write outside its allowed paths?",
        requested_action="Widen the program's mutation_paths, or decline.",
        worker_id=worker_id,
        session_id="session.1",
        evidence=("attempted path: outside/allowed",),
        lease_root=lease_root,
    )


def _persist_attempt(
    root: Path,
    *,
    task_id: str,
    pid: int | None,
    identity: str | None,
    confidence: ExecutionConfidence | None = ExecutionConfidence.CONFIRMED,
) -> None:
    attempt_id = f"{task_id}.attempt.1"
    persist_state(
        root,
        ProgramStateRecord(
            program_id="fixture-program",
            program_digest=ZERO_DIGEST,
            base_pin=ZERO_PIN,
            tasks={
                task_id: TaskRecord(
                    task_id=task_id,
                    state=NodeState.REMEDIATING,
                    last_attempt_id=attempt_id,
                )
            },
            attempts={
                attempt_id: AttemptRecord(
                    attempt_id=attempt_id,
                    task_id=task_id,
                    attempt_number=1,
                    idempotency_key=f"{task_id}-key",
                    profile_id="impl",
                    agent_id="fixture-worker-01",
                    adapter="local-command",
                    profile_digest=ZERO_DIGEST,
                    base_pin=ZERO_PIN,
                    process_pid=pid,
                    process_start_identity=identity,
                    confidence=confidence,
                )
            },
        ),
    )


# ------------------------------------------------------------------ P1-1


def test_p1_1_production_lease_root_releases_when_no_attempt(tmp_path: Path) -> None:
    """Resident always passes lease_root=state_dir; no PID must not preserve."""
    root = tmp_path / "state"
    root.mkdir()
    envelope = _envelope("blocked-task")
    persist_envelope(root, envelope)
    projection = state_dir(root)
    _grant_projected_lease(projection, task_id="blocked-task", agent_id="fixture-worker-01")
    assert [row.package_id for row in active_rows(load_projection(projection))] == [
        "blocked-task"
    ]

    outcome = _block(root, envelope, lease_root=projection)

    assert outcome.lease_released is True, outcome.lease_release_detail
    assert active_rows(load_projection(projection)) == ()


def test_p1_1_live_reused_pid_without_matching_identity_releases(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    envelope = _envelope("blocked-task")
    persist_envelope(root, envelope)
    projection = state_dir(root)
    _grant_projected_lease(projection, task_id="blocked-task", agent_id="fixture-worker-01")
    _persist_attempt(
        root,
        task_id="blocked-task",
        pid=os.getpid(),
        identity="linux:stale-or-reused-stranger",
    )

    outcome = _block(root, envelope, lease_root=projection)

    assert outcome.lease_released is True, outcome.lease_release_detail
    assert active_rows(load_projection(projection)) == ()


def test_p1_1_confirmed_live_owned_worker_preserves_lease(tmp_path: Path) -> None:
    root = tmp_path / "state"
    root.mkdir()
    envelope = _envelope("blocked-task")
    persist_envelope(root, envelope)
    projection = state_dir(root)
    _grant_projected_lease(projection, task_id="blocked-task", agent_id="fixture-worker-01")
    pid = os.getpid()
    _persist_attempt(
        root,
        task_id="blocked-task",
        pid=pid,
        identity=process_start_identity(pid),
    )

    outcome = _block(root, envelope, lease_root=projection)

    assert outcome.lease_released is False
    assert "lease preserved" in outcome.lease_release_detail
    assert [row.package_id for row in active_rows(load_projection(projection))] == [
        "blocked-task"
    ]


# ------------------------------------------------------------------ P1-2


def _git(workspace: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=str(workspace),
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _workspace(tmp_path: Path) -> Path:
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


def test_p1_2_successor_supervisor_rehydrates_then_releases(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    payload = {
        "schema_version": 1,
        "program": {
            "program_id": "p1-2-program",
            "objective": "successor lease release",
            "approved_by": "fixture-owner",
            "approval_reference": "tests/unit/test_program_adv927_p1_remediation.py",
            "workspace_root": str(workspace),
            "base_pin": _head(workspace),
            "tasks": [
                {
                    "task_id": "only",
                    "title": "only",
                    "instruction": "write only.txt",
                    "profile_ref": "implementer",
                    "mutation_paths": ["only.txt"],
                    "surface_id": "surface-only",
                    "surface_semantic": "ONLY",
                    "capabilities_required": ["IMPLEMENT"],
                    "acceptance": [
                        {
                            "check_id": "only-out",
                            "kind": "FILE_EXISTS",
                            "description": "only.txt exists",
                            "path": "only.txt",
                        }
                    ],
                }
            ],
            "limits": {"max_cycles": 4, "idle_sleep_seconds": 0.0},
        },
        "profiles": {
            "implementer": {
                "agent_id": "fixture-implementer",
                "adapter": "local-command",
                "credential": "NOT_APPLICABLE",
                "capabilities": ["IMPLEMENT"],
                "adapter_options": {
                    "argv": [sys.executable, "-c", "print('fixture')"],
                },
            }
        },
    }
    program_path = tmp_path / "program.json"
    program_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    loaded = load_program(program_path)
    first = ProgramSupervisor(
        loaded, state_root=tmp_path / "state", sleeper=lambda _seconds: None
    )
    first.load_or_init_state()
    task = first.program.tasks[0]
    lease = AgentLease(
        lease_id="only-lease",
        agent_id="fixture-implementer",
        package_id=task.task_id,
        branch="fixture-branch",
        worktree=str(first.workspace),
        base_pin=first.program.base_pin,
        authorized_paths=task.mutation_paths,
        capabilities=(AgentCapability.IMPLEMENT,),
        start_state=NodeState.READY,
        expected_output="fixture",
        expiry_or_terminal_condition="TERMINAL",
        active=True,
        sequence=1,
    )
    project_grant(state_dir(first.root), lease, live_main=first.program.base_pin)
    assert [row.package_id for row in active_rows(load_projection(state_dir(first.root)))] == [
        "only"
    ]

    successor = ProgramSupervisor(
        loaded, state_root=tmp_path / "state", sleeper=lambda _seconds: None
    )
    assert successor._leases == {}
    successor._release_lease(successor.load_or_init_state(), "only")
    assert active_rows(load_projection(state_dir(successor.root))) == ()


# ------------------------------------------------------------------ P1-3


def test_p1_3_prefix_overlapping_mutation_paths_conflict() -> None:
    left = _node(
        "PKG-A",
        state=NodeState.LEASED,
        surface="alpha",
        semantic="SEM_ALPHA",
        paths=("src",),
    )
    right = _node(
        "PKG-B",
        state=NodeState.READY,
        surface="beta",
        semantic="SEM_BETA",
        paths=("src/child.txt",),
    )
    assert surfaces_overlap(left, right)
    assert would_overlap((left,), right)


def test_p1_3_sibling_prefix_is_not_containment() -> None:
    left = _node(
        "PKG-A",
        state=NodeState.LEASED,
        surface="exp",
        semantic="SEM_EXP",
        paths=("src/exp",),
    )
    right = _node(
        "PKG-B",
        state=NodeState.ACTIVE,
        surface="exporter",
        semantic="SEM_EXPORTER",
        paths=("src/exporter",),
    )
    assert not surfaces_overlap(left, right)
    assert not would_overlap((left,), right)


# ------------------------------------------------------------------ P1-4


def test_p1_4_codex_add_dir_rejects_workspace_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "secret-outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("do-not-leak\n", encoding="utf-8")
    (workspace / "extra").symlink_to(outside)
    profile = _codex_profile(
        workspace={"restricted": True, "additional_dirs": ["extra"]}
    )
    adapter = CodexAdapter(INSTALLED_STAND_IN)
    with pytest.raises(ContainmentError):
        adapter.build_argv(_request(workspace, profile))


def test_p1_4_claude_add_dir_rejects_workspace_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "secret-outside"
    outside.mkdir()
    (workspace / "extra").symlink_to(outside)
    profile = AgentProfile.model_validate(
        {
            "profile_id": "claude-impl",
            "agent_id": "claude-impl",
            "adapter": "claude-code",
            "capabilities": ["IMPLEMENT"],
            "workspace": {"restricted": True, "additional_dirs": ["extra"]},
        }
    )
    adapter = ClaudeCodeAdapter(INSTALLED_STAND_IN)
    with pytest.raises(ContainmentError):
        adapter.build_argv(_request(workspace, profile))


def test_p1_4_codex_add_dir_keeps_a_real_child_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    extra = workspace / "extra"
    extra.mkdir(parents=True)
    profile = _codex_profile(
        workspace={"restricted": True, "additional_dirs": ["extra"]}
    )
    argv = CodexAdapter(INSTALLED_STAND_IN).build_argv(_request(workspace, profile))
    assert argv[argv.index("--add-dir") + 1] == str(extra.resolve())
    assert str(tmp_path / "secret-outside") not in argv
