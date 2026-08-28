"""D-112 writer proofs for SDK wait_run pre_head + creation_sequence.

Writer-local only. Not independent certification.
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
    AgentRecord,
    AgentRole,
    AgentRuntime,
    AgentState,
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
    WorkerBackend,
    mint_creation_sequence,
    persist_run_pre_head,
)

PIN = "7e797468a2eca37c959920912b1fa264df4be638"
LEASE_ID = "lease-d112-sdk-test-01"
AGENT = "agent-d112test0001"


class _WaitHandle:
    async def wait(self) -> SimpleNamespace:
        return SimpleNamespace(status="finished", result="ok", usage=None)


def _backend(root: Path) -> CursorSDKExecutionBackend:
    agents = CloudAgentRegistry(root)
    runs = RunRegistry(root)
    return CursorSDKExecutionBackend(
        root=root,
        agents_reg=agents,
        runs_reg=runs,
        pool=AgentRolePool(agents),
    )


def _lease(root: Path, *, head: str) -> None:
    persist_durable_lease(
        root,
        GovernorLease(
            lease_id=LEASE_ID,
            package_id=PACKAGE_ID,
            role=AgentRole.REMEDIATOR,
            dag_generation=112,
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
        ),
    )


def _run(run_id: str, head: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        agent_id=AGENT,
        cycle_id="C-D112",
        package_id=PACKAGE_ID,
        lease_id=LEASE_ID,
        role=AgentRole.REMEDIATOR,
        prompt_digest="a" * 64,
        idempotency_key=f"idemp-{run_id}",
        status=RunStatus.RUNNING,
        started_at=_utc_now(),
        candidate_head=head,
        candidate_tree="0" * 40,
        node_id="REMEDIATE-D112",
        dag_generation=112,
    )


def _agent(root: Path, **updates: object) -> AgentRecord:
    base: dict[str, object] = dict(
        agent_id=AGENT,
        runtime=AgentRuntime.LOCAL,
        role=AgentRole.REMEDIATOR,
        package_id=PACKAGE_ID,
        base_main=PIN,
        branch=CANONICAL_BRANCH,
        created_at=_utc_now(),
        state=AgentState.IDLE,
        worker_backend=WorkerBackend.CURSOR_SDK.value,
        workspace=str(root.resolve()),
        repository=CANONICAL_REPO_URL,
        creation_generation=112,
    )
    base.update(updates)
    return AgentRecord(**base)  # type: ignore[arg-type]


def test_wait_run_restart_hide_fail_closed(tmp_path: Path) -> None:
    """Missing pre_head + candidate_head=post must not accept a hidden escape."""
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
    _lease(tmp_path, head=pre)
    evil = tmp_path / "docs" / "evil.md"
    evil.parent.mkdir()
    evil.write_text("escaped\n", encoding="utf-8")
    git("add", "docs/evil.md")
    git("commit", "-m", "hide-via-candidate")
    post = git("rev-parse", "HEAD")
    backend = _backend(tmp_path)
    backend.runs_reg.upsert(_run("run-restart-hide", post))
    backend._handles["run:run-restart-hide"] = _WaitHandle()
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-restart-hide", agent_id=AGENT))
    assert exc.value.code == "DIFF_UNDETERMINED"


def test_wait_run_persisted_pre_head_rejects_escape(tmp_path: Path) -> None:
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
    _lease(tmp_path, head=pre)
    persist_run_pre_head(tmp_path, "run-persisted", pre)
    evil = tmp_path / "docs" / "evil.md"
    evil.parent.mkdir()
    evil.write_text("escaped\n", encoding="utf-8")
    git("add", "docs/evil.md")
    git("commit", "-m", "escape")
    backend = _backend(tmp_path)
    backend.runs_reg.upsert(_run("run-persisted", git("rev-parse", "HEAD")))
    backend._handles["run:run-persisted"] = _WaitHandle()
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-persisted", agent_id=AGENT))
    assert exc.value.code == "REJECTED_SCOPE_ESCAPE"
    # D-115: escape must not leave durable FINISHED outside nonterminal ingest.
    stored = backend.runs_reg.get("run-persisted")
    assert stored is not None
    assert stored.status == RunStatus.RUNNING


def test_wait_run_enforces_before_durable_terminal(tmp_path: Path) -> None:
    """REJECTED_SCOPE_ESCAPE must occur before mark_terminal persists FINISHED."""
    import subprocess

    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=str(tmp_path), capture_output=True, text=True, check=True
        )
        return completed.stdout.strip()

    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    git("config", "user.email", "d115@invalid.local")
    git("config", "user.name", "D115")
    allowed = tmp_path / "src" / "project_atlas" / "orchestration" / "sdk"
    allowed.mkdir(parents=True)
    (allowed / "ok.py").write_text("ok\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "seed")
    pre = git("rev-parse", "HEAD")
    _lease(tmp_path, head=pre)
    persist_run_pre_head(tmp_path, "run-order", pre)
    evil = tmp_path / "docs" / "evil.md"
    evil.parent.mkdir()
    evil.write_text("escaped\n", encoding="utf-8")
    git("add", "docs/evil.md")
    git("commit", "-m", "escape")
    backend = _backend(tmp_path)
    backend.runs_reg.upsert(_run("run-order", git("rev-parse", "HEAD")))
    backend._handles["run:run-order"] = _WaitHandle()
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-order", agent_id=AGENT))
    assert exc.value.code == "REJECTED_SCOPE_ESCAPE"
    stored = backend.runs_reg.get("run-order")
    assert stored is not None
    assert stored.status is RunStatus.RUNNING
    assert stored.run_id in {r.run_id for r in backend.runs_reg.nonterminal()}


def test_resume_missing_creation_sequence(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.resume_agent(AGENT))
    assert exc.value.code == "STALE_WORKER_LINEAGE"


def test_resume_rolled_back_creation_sequence(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    mint_creation_sequence(tmp_path, AGENT)
    mint_creation_sequence(tmp_path, AGENT)
    backend.agents_reg.upsert(_agent(tmp_path, creation_sequence=1))
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.resume_agent(AGENT))
    assert exc.value.code == "ROLLED_BACK_CREATION_SEQUENCE"
