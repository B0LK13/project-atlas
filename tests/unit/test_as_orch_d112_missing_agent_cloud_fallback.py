"""D-112 remediator proofs: missing agent cannot default CLOUD-shaped runs to LOCAL.

Writer-local only. Not independent certification.
Finding: ORCH-SDK-CLOUD-MUTATING-ATTRIBUTION-001.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from project_atlas.orchestration.sdk.backend import CursorSDKExecutionBackend
from project_atlas.orchestration.sdk.lease_registry import persist_durable_lease
from project_atlas.orchestration.sdk.models import (
    CANONICAL_REPO_URL,
    PACKAGE_ID,
    AgentRole,
    RunRecord,
    RunStatus,
    SdkRuntimeError,
    _utc_now,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.role_pool import AgentRolePool
from project_atlas.orchestration.sdk.security_gates import (
    CANONICAL_BRANCH,
    GovernorLease,
    persist_run_pre_head,
)

PIN = "7e797468a2eca37c959920912b1fa264df4be638"
LEASE_ID = "lease-d112-missing-agent-01"
CLOUD_AGENT = "bc-d112missingagent01"
LOCAL_AGENT = "agent-d112missinglocal01"


class _GitWaitHandle:
    def __init__(self, *, repo: str, branches: list[str]) -> None:
        self._repo = repo
        self._branches = branches

    async def wait(self) -> SimpleNamespace:
        return SimpleNamespace(
            status="finished",
            result="ok",
            usage=None,
            git=SimpleNamespace(repo_url=self._repo, branches=list(self._branches)),
        )


class _WaitHandle:
    async def wait(self) -> SimpleNamespace:
        return SimpleNamespace(status="finished", result="ok", usage=None)


def _backend(root: Path) -> CursorSDKExecutionBackend:
    agents = CloudAgentRegistry(root)
    return CursorSDKExecutionBackend(
        root=root,
        agents_reg=agents,
        runs_reg=RunRegistry(root),
        pool=AgentRolePool(agents),
    )


def _lease(root: Path) -> None:
    persist_durable_lease(
        root,
        GovernorLease(
            lease_id=LEASE_ID,
            package_id=PACKAGE_ID,
            role=AgentRole.REMEDIATOR,
            dag_generation=116,
            allowed_paths=(
                "src/project_atlas/orchestration/sdk",
                "tests/unit",
                "scripts",
            ),
            worktree=str(root),
            candidate_head=PIN,
            candidate_tree="0" * 40,
            mutation_authorized=True,
            branch=CANONICAL_BRANCH,
        ),
    )


def _run(run_id: str, agent_id: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        agent_id=agent_id,
        cycle_id="C-D112",
        package_id=PACKAGE_ID,
        lease_id=LEASE_ID,
        role=AgentRole.REMEDIATOR,
        prompt_digest="a" * 64,
        idempotency_key=f"idemp-{run_id}",
        status=RunStatus.RUNNING,
        started_at=_utc_now(),
        candidate_head=PIN,
        candidate_tree="0" * 40,
        node_id="REMEDIATE-D112",
        dag_generation=116,
    )


def test_missing_agent_with_run_git_fail_closed(tmp_path: Path) -> None:
    _lease(tmp_path)
    persist_run_pre_head(tmp_path, "run-missing-git", PIN)
    backend = _backend(tmp_path)
    backend.runs_reg.upsert(_run("run-missing-git", CLOUD_AGENT))
    backend._handles["run:run-missing-git"] = _GitWaitHandle(
        repo=CANONICAL_REPO_URL, branches=[CANONICAL_BRANCH]
    )
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-missing-git", agent_id=CLOUD_AGENT))
    assert exc.value.code == "REMOTE_ATTRIBUTION_UNDETERMINED"
    stored = backend.runs_reg.get("run-missing-git")
    assert stored is not None
    assert stored.status == RunStatus.RUNNING
    assert stored.run_id in {row.run_id for row in backend.runs_reg.nonterminal()}


def test_missing_agent_bc_identity_without_git_fail_closed(tmp_path: Path) -> None:
    _lease(tmp_path)
    persist_run_pre_head(tmp_path, "run-missing-bc", PIN)
    backend = _backend(tmp_path)
    backend.runs_reg.upsert(_run("run-missing-bc", CLOUD_AGENT))
    backend._handles["run:run-missing-bc"] = _WaitHandle()
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-missing-bc", agent_id=CLOUD_AGENT))
    assert exc.value.code == "REMOTE_ATTRIBUTION_UNDETERMINED"
    stored = backend.runs_reg.get("run-missing-bc")
    assert stored is not None
    assert stored.status == RunStatus.RUNNING


def test_missing_agent_local_identity_without_git_still_local(tmp_path: Path) -> None:
    import subprocess

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=str(tmp_path), capture_output=True, text=True, check=True
        )
        return completed.stdout.strip()

    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    git("config", "user.email", "d112@invalid.local")
    git("config", "user.name", "D112")
    allowed = tmp_path / "src" / "project_atlas" / "orchestration" / "sdk"
    allowed.mkdir(parents=True)
    (allowed / "ok.py").write_text("ok\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "seed")
    pre = git("rev-parse", "HEAD")
    _lease(tmp_path)
    persist_run_pre_head(tmp_path, "run-missing-local", pre)
    backend = _backend(tmp_path)
    backend.runs_reg.upsert(_run("run-missing-local", LOCAL_AGENT))
    backend._handles["run:run-missing-local"] = _WaitHandle()
    backend._pre_heads["run-missing-local"] = pre
    updated = asyncio.run(backend.wait_run("run-missing-local", agent_id=LOCAL_AGENT))
    assert updated.status == RunStatus.FINISHED
