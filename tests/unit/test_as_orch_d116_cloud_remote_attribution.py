"""D-116 ADV matrix: CLOUD remote path attribution (no local fallback)."""

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
from project_atlas.orchestration.sdk.mutation_attribution import (
    CloudRemoteGitAttributionProvider,
    load_agent_remote_high_water,
    load_run_mutation_baseline,
    mint_cloud_run_baseline,
    normalize_repo_identity,
    persist_agent_remote_high_water,
)
from project_atlas.orchestration.sdk.registries import CloudAgentRegistry, RunRegistry
from project_atlas.orchestration.sdk.role_pool import AgentRolePool
from project_atlas.orchestration.sdk.security_gates import (
    CANONICAL_BRANCH,
    GovernorLease,
    WorkerBackend,
    persist_run_pre_head,
)

PIN = "7e797468a2eca37c959920912b1fa264df4be638"
H1 = "1111111111111111111111111111111111111111"
H2 = "2222222222222222222222222222222222222222"
H3 = "3333333333333333333333333333333333333333"
LEASE_ID = "lease-d116-sdk-test-01"
AGENT = "bc-d116cloudagent0001"
BRANCH = CANONICAL_BRANCH


def _backend(root: Path) -> CursorSDKExecutionBackend:
    return CursorSDKExecutionBackend(
        root=root,
        agents_reg=CloudAgentRegistry(root),
        runs_reg=RunRegistry(root),
        pool=AgentRolePool(CloudAgentRegistry(root)),
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
            branch=BRANCH,
        ),
    )


def _agent(root: Path) -> AgentRecord:
    return AgentRecord(
        agent_id=AGENT,
        runtime=AgentRuntime.CLOUD,
        role=AgentRole.REMEDIATOR,
        package_id=PACKAGE_ID,
        base_main=PIN,
        branch=BRANCH,
        created_at=_utc_now(),
        state=AgentState.BUSY,
        worker_backend=WorkerBackend.CURSOR_SDK.value,
        workspace=str(root.resolve()),
        repository=CANONICAL_REPO_URL,
        creation_generation=116,
        creation_sequence=1,
    )


def _run(run_id: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        agent_id=AGENT,
        cycle_id="C-D116",
        package_id=PACKAGE_ID,
        lease_id=LEASE_ID,
        role=AgentRole.REMEDIATOR,
        prompt_digest="a" * 64,
        idempotency_key=f"idemp-{run_id}",
        status=RunStatus.RUNNING,
        started_at=_utc_now(),
        candidate_head=PIN,
        candidate_tree="0" * 40,
        node_id="REMEDIATE-D116",
        dag_generation=116,
    )


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


def _provider(
    *,
    heads: dict[str, str],
    diffs: dict[tuple[str, str], list[str]],
) -> CloudRemoteGitAttributionProvider:
    def resolve_head(repository: str, branch: str) -> str | None:
        del repository
        return heads.get(branch)

    def resolve_diff(repository: str, pre: str, post: str) -> list[str] | None:
        del repository
        return diffs.get((pre, post))

    return CloudRemoteGitAttributionProvider(
        resolve_remote_head=resolve_head,
        resolve_remote_diff=resolve_diff,
    )


def test_normalize_repo_identity_strips_scheme() -> None:
    assert normalize_repo_identity("github.com/B0LK13/project-atlas") == normalize_repo_identity(
        CANONICAL_REPO_URL
    )


def test_cloud_attr_iv_allowed_remote_mutation(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-iv",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    backend.register_cloud_attribution_provider(
        _provider(
            heads={BRANCH: H1},
            diffs={(PIN, H1): ["src/project_atlas/orchestration/sdk/backend.py"]},
        )
    )
    backend.runs_reg.upsert(_run("run-iv"))
    backend._handles["run:run-iv"] = _GitWaitHandle(
        repo="github.com/B0LK13/project-atlas", branches=[BRANCH]
    )
    updated = asyncio.run(backend.wait_run("run-iv", agent_id=AGENT))
    assert updated.status == RunStatus.FINISHED
    assert load_agent_remote_high_water(tmp_path, AGENT) == H1


def test_cloud_attr_escape_rejects_before_terminal(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-escape",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    backend.register_cloud_attribution_provider(
        _provider(heads={BRANCH: H1}, diffs={(PIN, H1): ["docs/evil.md"]})
    )
    backend.runs_reg.upsert(_run("run-escape"))
    backend._handles["run:run-escape"] = _GitWaitHandle(
        repo=CANONICAL_REPO_URL, branches=[BRANCH]
    )
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-escape", agent_id=AGENT))
    assert exc.value.code == "REJECTED_SCOPE_ESCAPE"
    stored = backend.runs_reg.get("run-escape")
    assert stored is not None
    assert stored.status == RunStatus.RUNNING


def test_cloud_attr_local_decoy_ignored(tmp_path: Path) -> None:
    """Local allowed decoy must not mask a forbidden remote Cloud mutation."""
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-decoy",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    # Local decoy: only allowed paths dirty in worktree.
    allowed = tmp_path / "src" / "project_atlas" / "orchestration" / "sdk"
    allowed.mkdir(parents=True)
    (allowed / "ok.py").write_text("ok\n", encoding="utf-8")
    persist_run_pre_head(tmp_path, "run-decoy", PIN)
    backend.register_cloud_attribution_provider(
        _provider(heads={BRANCH: H1}, diffs={(PIN, H1): ["docs/evil.md"]})
    )
    backend.runs_reg.upsert(_run("run-decoy"))
    backend._handles["run:run-decoy"] = _GitWaitHandle(
        repo=CANONICAL_REPO_URL, branches=[BRANCH]
    )
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-decoy", agent_id=AGENT))
    assert exc.value.code == "REJECTED_SCOPE_ESCAPE"


def test_cloud_attr_followup_chains_baselines(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-1",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    backend.register_cloud_attribution_provider(
        _provider(
            heads={BRANCH: H1},
            diffs={(PIN, H1): ["src/project_atlas/orchestration/sdk/a.py"]},
        )
    )
    backend.runs_reg.upsert(_run("run-1"))
    backend._handles["run:run-1"] = _GitWaitHandle(
        repo=CANONICAL_REPO_URL, branches=[BRANCH]
    )
    asyncio.run(backend.wait_run("run-1", agent_id=AGENT))
    assert load_agent_remote_high_water(tmp_path, AGENT) == H1

    b2 = mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-2",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    assert b2.remote_pre_head == H1
    seen: dict[str, object] = {}

    def resolve_diff(repository: str, pre: str, post: str) -> list[str] | None:
        del repository
        seen["pre"] = pre
        seen["post"] = post
        return ["src/project_atlas/orchestration/sdk/b.py"]

    backend.register_cloud_attribution_provider(
        CloudRemoteGitAttributionProvider(
            resolve_remote_head=lambda _r, _b: H2,
            resolve_remote_diff=resolve_diff,
        )
    )
    backend.runs_reg.upsert(_run("run-2"))
    backend._handles["run:run-2"] = _GitWaitHandle(
        repo=CANONICAL_REPO_URL, branches=[BRANCH]
    )
    asyncio.run(backend.wait_run("run-2", agent_id=AGENT))
    assert seen["pre"] == H1
    assert seen["post"] == H2
    assert load_agent_remote_high_water(tmp_path, AGENT) == H2


def test_cloud_attr_restart_recovers_baseline(tmp_path: Path) -> None:
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-restart",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    loaded = load_run_mutation_baseline(tmp_path, "run-restart")
    assert loaded is not None
    assert loaded.remote_pre_head == PIN
    persist_agent_remote_high_water(tmp_path, AGENT, H1)
    again = mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-restart-2",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    assert again.remote_pre_head == H1


def test_cloud_attr_foreign_repo_fail_closed(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-foreign",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    backend.register_cloud_attribution_provider(
        _provider(
            heads={BRANCH: H1},
            diffs={(PIN, H1): ["src/project_atlas/orchestration/sdk/x.py"]},
        )
    )
    backend.runs_reg.upsert(_run("run-foreign"))
    backend._handles["run:run-foreign"] = _GitWaitHandle(
        repo="https://github.com/evil/other", branches=[BRANCH]
    )
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-foreign", agent_id=AGENT))
    assert exc.value.code == "REMOTE_ATTRIBUTION_UNDETERMINED"


def test_cloud_attr_ambiguous_branch_fail_closed(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-ambig",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    backend.register_cloud_attribution_provider(
        _provider(heads={BRANCH: H1}, diffs={(PIN, H1): []})
    )
    backend.runs_reg.upsert(_run("run-ambig"))
    backend._handles["run:run-ambig"] = _GitWaitHandle(
        repo=CANONICAL_REPO_URL, branches=[BRANCH, "feat/other-atlas-branch"]
    )
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-ambig", agent_id=AGENT))
    assert exc.value.code == "REMOTE_ATTRIBUTION_UNDETERMINED"


def test_cloud_attr_divergence_fail_closed(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-div",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )

    def resolve_diff(repository: str, pre: str, post: str) -> list[str] | None:
        del repository, pre, post
        raise SdkRuntimeError(
            "remote terminal head is not a descendant of baseline",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )

    backend.register_cloud_attribution_provider(
        CloudRemoteGitAttributionProvider(
            resolve_remote_head=lambda _r, _b: H3,
            resolve_remote_diff=resolve_diff,
        )
    )
    backend.runs_reg.upsert(_run("run-div"))
    backend._handles["run:run-div"] = _GitWaitHandle(
        repo=CANONICAL_REPO_URL, branches=[BRANCH]
    )
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-div", agent_id=AGENT))
    assert exc.value.code == "REMOTE_ATTRIBUTION_UNDETERMINED"


def test_cloud_attr_rename_delete_included(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-rename",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    backend.register_cloud_attribution_provider(
        _provider(
            heads={BRANCH: H1},
            diffs={
                (PIN, H1): [
                    "src/project_atlas/orchestration/sdk/old.py",
                    "src/project_atlas/orchestration/sdk/new.py",
                ]
            },
        )
    )
    backend.runs_reg.upsert(_run("run-rename"))
    backend._handles["run:run-rename"] = _GitWaitHandle(
        repo=CANONICAL_REPO_URL, branches=[BRANCH]
    )
    updated = asyncio.run(backend.wait_run("run-rename", agent_id=AGENT))
    assert updated.status == RunStatus.FINISHED


def test_cloud_attr_missing_git_fail_closed(tmp_path: Path) -> None:
    backend = _backend(tmp_path)
    _lease(tmp_path)
    backend.agents_reg.upsert(_agent(tmp_path))
    mint_cloud_run_baseline(
        root=tmp_path,
        run_id="run-nogit",
        agent_id=AGENT,
        base_main=PIN,
        branch=BRANCH,
        dag_generation=116,
        lease_id=LEASE_ID,
    )
    backend.register_cloud_attribution_provider(
        _provider(heads={BRANCH: H1}, diffs={(PIN, H1): []})
    )
    backend.runs_reg.upsert(_run("run-nogit"))

    class _NoGit:
        async def wait(self) -> SimpleNamespace:
            return SimpleNamespace(status="finished", result="ok", usage=None)

    backend._handles["run:run-nogit"] = _NoGit()
    with pytest.raises(SdkRuntimeError) as exc:
        asyncio.run(backend.wait_run("run-nogit", agent_id=AGENT))
    assert exc.value.code == "REMOTE_ATTRIBUTION_UNDETERMINED"
