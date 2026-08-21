"""D-106: CursorSDKExecutionBackend allowed-paths + resume lineage."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from project_atlas.orchestration.sdk.backend import CursorSDKExecutionBackend
from project_atlas.orchestration.sdk.lease_registry import persist_durable_lease
from project_atlas.orchestration.sdk.models import (
    CANONICAL_REPO_URL,
    PACKAGE_ID,
    AgentRecord,
    AgentRole,
    AgentRuntime,
    AgentState,
    RunRecord,
    RunStatus,
    ScheduleRequest,
    SdkRuntimeError,
    _utc_now,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.role_pool import AgentRolePool
from project_atlas.orchestration.sdk.security_gates import (
    CANONICAL_BRANCH,
    GovernorLease,
    WorkerBackend,
    mint_creation_sequence,
)

PIN = "7e797468a2eca37c959920912b1fa264df4be638"
LEASE_ID = "lease-d106-sdk-test-97"


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=True,
    )


def _backend(root: Path) -> CursorSDKExecutionBackend:
    agents = CloudAgentRegistry(root)
    runs = RunRegistry(root)
    return CursorSDKExecutionBackend(
        root=root,
        agents_reg=agents,
        runs_reg=runs,
        pool=AgentRolePool(agents),
    )


def _seed_repo(root: Path) -> str:
    _git(root, "init")
    _git(root, "config", "user.email", "d106@invalid.local")
    _git(root, "config", "user.name", "D106")
    allowed = root / "src" / "project_atlas" / "orchestration" / "sdk"
    allowed.mkdir(parents=True)
    (allowed / "ok.py").write_text("ok\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "seed")
    return _git(root, "rev-parse", "HEAD").stdout.strip()


def _lease(root: Path, *, head: str) -> GovernorLease:
    lease = GovernorLease(
        lease_id=LEASE_ID,
        package_id=PACKAGE_ID,
        role=AgentRole.REMEDIATOR,
        dag_generation=97,
        allowed_paths=(
            "src/project_atlas/orchestration/sdk",
            "tests/unit",
            "scripts",
        ),
        worktree=str(root),
        candidate_head=head,
        candidate_tree="0" * 40,
        mutation_authorized=True,
        branch=CANONICAL_BRANCH,
    )
    persist_durable_lease(root, lease)
    return lease


def _run(root: Path, *, head: str, run_id: str = "run-d106-sdk-0001") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        agent_id="agent-d106test0001",
        cycle_id="C-D106",
        package_id=PACKAGE_ID,
        lease_id=LEASE_ID,
        role=AgentRole.REMEDIATOR,
        prompt_digest="a" * 64,
        idempotency_key="atlas-remediator-d106",
        status=RunStatus.FINISHED,
        started_at=_utc_now(),
        completed_at=_utc_now(),
        candidate_head=head,
        candidate_tree="0" * 40,
        node_id="REMEDIATE-D106",
        dag_generation=97,
        attempt=1,
    )


def test_sdk_backend_resume_rejects_cross_worktree(tmp_path: Path) -> None:
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    backend = _backend(tmp_path)
    backend.agents_reg.upsert(
        AgentRecord(
            agent_id="agent-d106test0001",
            runtime=AgentRuntime.LOCAL,
            role=AgentRole.REMEDIATOR,
            package_id=PACKAGE_ID,
            base_main=PIN,
            branch=CANONICAL_BRANCH,
            created_at=_utc_now(),
            state=AgentState.IDLE,
            worker_backend=WorkerBackend.CURSOR_SDK.value,
            workspace=str(foreign.resolve()),
            repository=CANONICAL_REPO_URL,
            creation_generation=97,
            creation_sequence=mint_creation_sequence(tmp_path, "agent-d106test0001"),
        )
    )
    with pytest.raises(SdkRuntimeError, match=r"cross-worktree"):
        asyncio.run(backend.resume_agent("agent-d106test0001"))


def test_sdk_backend_resume_rejects_missing_lineage(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    backend.agents_reg.upsert(
        AgentRecord(
            agent_id="agent-d106test0002",
            runtime=AgentRuntime.LOCAL,
            role=AgentRole.REMEDIATOR,
            package_id=PACKAGE_ID,
            base_main=PIN,
            branch=CANONICAL_BRANCH,
            created_at=_utc_now(),
            state=AgentState.IDLE,
        )
    )
    with pytest.raises(SdkRuntimeError, match=r"missing lineage"):
        asyncio.run(backend.resume_agent("agent-d106test0002"))


def test_sdk_backend_wait_run_rejects_committed_escape(tmp_path: Path) -> None:
    seed = _seed_repo(tmp_path)
    _lease(tmp_path, head=seed)
    _git(tmp_path, "add", ".atlas")
    _git(tmp_path, "commit", "-m", "lease")
    pre_head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    escape = tmp_path / "docs" / "secrets.txt"
    escape.parent.mkdir(parents=True)
    escape.write_text("leaked\n", encoding="utf-8")
    _git(tmp_path, "add", "docs/secrets.txt")
    _git(tmp_path, "commit", "-m", "hide via commit")
    backend = _backend(tmp_path)
    backend._pre_heads["run-d106-sdk-0001"] = pre_head
    with pytest.raises(SdkRuntimeError, match=r"REJECTED_SCOPE_ESCAPE"):
        backend._enforce_run_paths(_run(tmp_path, head=pre_head))


def test_sdk_backend_wait_run_allows_in_scope_delta(tmp_path: Path) -> None:
    seed = _seed_repo(tmp_path)
    _lease(tmp_path, head=seed)
    _git(tmp_path, "add", ".atlas")
    _git(tmp_path, "commit", "-m", "lease")
    pre_head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    allowed = tmp_path / "src" / "project_atlas" / "orchestration" / "sdk" / "ok.py"
    allowed.write_text("ok\nfixed\n", encoding="utf-8")
    _git(tmp_path, "add", "src/project_atlas/orchestration/sdk/ok.py")
    _git(tmp_path, "commit", "-m", "in scope")
    backend = _backend(tmp_path)
    backend._pre_heads["run-d106-sdk-0001"] = pre_head
    backend._enforce_run_paths(_run(tmp_path, head=pre_head))


def test_sdk_backend_create_binds_and_persists_lineage(tmp_path: Path) -> None:
    """create_and_send path: bind_worker_lineage + AgentRecord lineage fields."""
    backend = _backend(tmp_path)
    request = ScheduleRequest(
        package_id=PACKAGE_ID,
        role=AgentRole.REMEDIATOR,
        prompt="remediate",
        base_main=PIN,
        branch=CANONICAL_BRANCH,
        cycle_id="C-D106",
        node_id="REMEDIATE-D106",
        dag_generation=97,
        attempt=1,
        candidate_head=PIN,
        candidate_tree="0" * 40,
        lease_id=LEASE_ID,
        runtime=AgentRuntime.LOCAL,
    )
    lineage = backend._bind_lineage(
        agent_id="agent-d106create01",
        request=request,
        creation_sequence=mint_creation_sequence(tmp_path, "agent-d106create01"),
    )
    record = AgentRecord(
        agent_id="agent-d106create01",
        runtime=AgentRuntime.LOCAL,
        role=request.role,
        package_id=request.package_id,
        base_main=request.base_main,
        branch=request.branch,
        created_at=_utc_now(),
        state=AgentState.BUSY,
        worker_backend=WorkerBackend.CURSOR_SDK.value,
        workspace=lineage.workspace,
        repository=lineage.repository,
        creation_generation=lineage.creation_generation,
        creation_sequence=lineage.creation_sequence,
        lineage_id=f"lin-agent-d106create01-{lineage.creation_generation}",
    )
    backend.agents_reg.upsert(record)
    stored = backend.agents_reg.get("agent-d106create01")
    assert stored is not None
    assert stored.workspace == str(tmp_path.resolve())
    assert stored.repository == CANONICAL_REPO_URL
    assert stored.creation_generation == 97
    assert stored.creation_sequence == lineage.creation_sequence
    assert stored.worker_backend == WorkerBackend.CURSOR_SDK.value
    stored_lineage = backend._lineage_from_stored(stored)
    backend._bind_lineage(
        agent_id="agent-d106create01",
        request=request,
        expected=stored_lineage,
    )
