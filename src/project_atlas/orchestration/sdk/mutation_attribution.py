"""Runtime-aware mutation path attribution (D-116).

LOCAL workers prove deltas from the governed local worktree.
CLOUD workers prove deltas from remote Git pushed by the Cloud run.
LOCAL repository state must never be accepted as proof of a CLOUD mutation.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, Protocol

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.models import (
    CANONICAL_REPO_URL,
    PACKAGE_ID,
    STATE_DIR_RELATIVE,
    AgentRuntime,
    SdkRuntimeError,
)
from project_atlas.orchestration.sdk.security_gates import collect_actual_changed_paths

ATTRIBUTION_STORE_NAME: Final[str] = "run-mutation-attribution.json"
AGENT_REMOTE_HIGH_WATER_NAME: Final[str] = "agent-remote-high-water.json"
FINDING_ID: Final[str] = "ORCH-SDK-CLOUD-PATH-ATTRIBUTION-001"

_REPO_HOST_PATH = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com[/:](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?/?$",
    re.IGNORECASE,
)


class RunGitInfo(BaseModel):
    """Terminal Run.git snapshot from Cursor SDK. Evidence only."""

    model_config = ConfigDict(extra="forbid")

    repo_url: str | None = None
    branches: tuple[str, ...] = ()


class RunMutationBaseline(BaseModel):
    """Durable per-run remote attribution state. Not authority."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_id: str
    runtime: AgentRuntime
    repository: str = CANONICAL_REPO_URL
    base_main: str
    remote_branch: str | None = None
    remote_pre_head: str | None = None
    remote_post_head: str | None = None
    dag_generation: int = Field(ge=0, le=1_000_000)
    lease_id: str | None = None
    package_id: str = PACKAGE_ID


class MutationAttributionProvider(Protocol):
    """Trust boundary: each execution backend must attribute its own mutations."""

    def collect_changed_paths(
        self,
        *,
        root: Path,
        attribution: RunMutationBaseline,
        terminal_git: RunGitInfo | None,
        local_pre_head: str | None,
    ) -> list[str] | None: ...


def normalize_repo_identity(raw: str | None) -> str | None:
    """Normalize GitHub repo URLs/paths for identity comparison."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    match = _REPO_HOST_PATH.search(text.replace("\\", "/"))
    if match is None:
        # Accept owner/repo already-normalized forms.
        parts = text.strip("/").split("/")
        if len(parts) >= 2 and "github.com" not in text.casefold():
            owner, repo = parts[-2], parts[-1]
            repo = repo.removesuffix(".git")
            return f"https://github.com/{owner}/{repo}".casefold()
        return text.rstrip("/").casefold()
    owner = match.group("owner")
    repo = match.group("repo")
    return f"https://github.com/{owner}/{repo}".casefold()


def canonical_repo_identity() -> str:
    return normalize_repo_identity(CANONICAL_REPO_URL) or CANONICAL_REPO_URL.casefold()


def attribution_store_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / ATTRIBUTION_STORE_NAME


def agent_remote_high_water_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / AGENT_REMOTE_HIGH_WATER_NAME


def persist_run_mutation_baseline(root: Path, baseline: RunMutationBaseline) -> None:
    path = attribution_store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError) as exc:
            raise SdkRuntimeError(
                "corrupt run mutation attribution store",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            ) from exc
    data[baseline.run_id] = baseline.model_dump(mode="json")
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def load_run_mutation_baseline(root: Path, run_id: str) -> RunMutationBaseline | None:
    path = attribution_store_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SdkRuntimeError(
            "corrupt run mutation attribution store",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        ) from exc
    if not isinstance(data, dict):
        raise SdkRuntimeError(
            "corrupt run mutation attribution store",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    row = data.get(run_id)
    if row is None:
        return None
    try:
        return RunMutationBaseline.model_validate(row)
    except ValueError as exc:
        raise SdkRuntimeError(
            "corrupt run mutation attribution row",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        ) from exc


def load_agent_remote_high_water(root: Path, agent_id: str) -> str | None:
    path = agent_remote_high_water_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SdkRuntimeError(
            "corrupt agent remote high-water store",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        ) from exc
    if not isinstance(data, dict):
        raise SdkRuntimeError(
            "corrupt agent remote high-water store",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    value = data.get(agent_id)
    if value is None:
        return None
    text = str(value).strip()
    return text if len(text) >= 7 else None


def persist_agent_remote_high_water(root: Path, agent_id: str, sha: str) -> None:
    path = agent_remote_high_water_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError) as exc:
            raise SdkRuntimeError(
                "corrupt agent remote high-water store",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            ) from exc
    data[agent_id] = sha
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def extract_run_git(result: Any) -> RunGitInfo | None:
    """Pull Run.git / git.branches[] from a Cursor run result object."""
    git_obj = getattr(result, "git", None)
    if git_obj is None and isinstance(result, dict):
        git_obj = result.get("git")
    if git_obj is None:
        return None
    repo = getattr(git_obj, "repo_url", None) or getattr(git_obj, "repoUrl", None)
    if repo is None and isinstance(git_obj, dict):
        repo = git_obj.get("repo_url") or git_obj.get("repoUrl") or git_obj.get("url")
    branches_raw = getattr(git_obj, "branches", None)
    if branches_raw is None and isinstance(git_obj, dict):
        branches_raw = git_obj.get("branches")
    branches: list[str] = []
    if isinstance(branches_raw, (list, tuple)):
        for item in branches_raw:
            if isinstance(item, str):
                name = item.strip()
            else:
                name = str(
                    getattr(item, "name", None)
                    or getattr(item, "branch", None)
                    or (item.get("name") if isinstance(item, dict) else "")
                    or ""
                ).strip()
            if name:
                branches.append(name)
    return RunGitInfo(
        repo_url=str(repo) if repo is not None else None,
        branches=tuple(branches),
    )


def select_canonical_remote_branch(
    terminal_git: RunGitInfo,
    *,
    expected_branch: str | None,
) -> str:
    """Fail closed unless exactly one canonical Atlas branch can be bound."""
    repo_id = normalize_repo_identity(terminal_git.repo_url)
    if repo_id is None:
        raise SdkRuntimeError(
            "terminal Run.git missing repository",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    if repo_id != canonical_repo_identity():
        raise SdkRuntimeError(
            "foreign repository in terminal Run.git",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    branches = [b for b in terminal_git.branches if b.strip()]
    if not branches:
        raise SdkRuntimeError(
            "terminal Run.git missing branches",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    if len(branches) > 1:
        raise SdkRuntimeError(
            "ambiguous Atlas branches in Run.git",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    branch = branches[0]
    if expected_branch and branch != expected_branch:
        raise SdkRuntimeError(
            "cloud branch changed unexpectedly vs lineage",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    return branch


def default_resolve_remote_head(repository: str, branch: str) -> str | None:
    """Resolve remote branch HEAD via git ls-remote. None => undetermined."""
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "ls-remote", repository, f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    for line in (completed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].strip():
            sha = parts[0].strip()
            if len(sha) >= 7:
                return sha
    return None


def default_resolve_remote_diff(
    repository: str, pre_head: str, post_head: str, *, work_root: Path
) -> list[str] | None:
    """Fetch remote SHAs into object DB and diff names. Never uses worktree content."""
    import subprocess

    try:
        fetched = subprocess.run(
            ["git", "fetch", "--no-tags", "--depth=0", repository, pre_head, post_head],
            cwd=str(work_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        # Shallow/depth flags vary; retry without depth.
        try:
            fetched = subprocess.run(
                ["git", "fetch", "--no-tags", repository, pre_head, post_head],
                cwd=str(work_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
    if fetched.returncode != 0:
        # Objects may already exist locally from a prior fetch.
        pass
    try:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", pre_head, post_head],
            cwd=str(work_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if ancestor.returncode != 0:
        raise SdkRuntimeError(
            "remote terminal head is not a descendant of baseline",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    try:
        diff = subprocess.run(
            ["git", "diff", "--name-only", "--find-renames", pre_head, post_head],
            cwd=str(work_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if diff.returncode != 0:
        return None
    paths = sorted(
        {line.strip().strip('"') for line in (diff.stdout or "").splitlines() if line.strip()}
    )
    return paths


class LocalWorktreeAttributionProvider:
    def collect_changed_paths(
        self,
        *,
        root: Path,
        attribution: RunMutationBaseline,
        terminal_git: RunGitInfo | None,
        local_pre_head: str | None,
    ) -> list[str] | None:
        del attribution, terminal_git
        return collect_actual_changed_paths(root, pre_head=local_pre_head)


class CloudRemoteGitAttributionProvider:
    def __init__(
        self,
        *,
        resolve_remote_head: Callable[[str, str], str | None] | None = None,
        resolve_remote_diff: Callable[[str, str, str], list[str] | None] | None = None,
    ) -> None:
        self._resolve_head = resolve_remote_head or default_resolve_remote_head
        self._resolve_diff = resolve_remote_diff

    def collect_changed_paths(
        self,
        *,
        root: Path,
        attribution: RunMutationBaseline,
        terminal_git: RunGitInfo | None,
        local_pre_head: str | None,
    ) -> list[str] | None:
        # Explicitly ignore local worktree state for CLOUD attribution.
        del local_pre_head
        if terminal_git is None:
            raise SdkRuntimeError(
                "terminal Run.git absent for CLOUD mutating run",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        if not attribution.remote_pre_head or len(attribution.remote_pre_head) < 7:
            raise SdkRuntimeError(
                "missing CLOUD remote baseline",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        branch = select_canonical_remote_branch(
            terminal_git, expected_branch=attribution.remote_branch
        )
        if (
            attribution.remote_branch
            and branch != attribution.remote_branch
        ):
            raise SdkRuntimeError(
                "cloud branch changed unexpectedly vs lineage",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        post = self._resolve_head(attribution.repository, branch)
        if post is None or len(post) < 7:
            raise SdkRuntimeError(
                "remote terminal HEAD cannot be resolved",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        if self._resolve_diff is not None:
            paths = self._resolve_diff(
                attribution.repository, attribution.remote_pre_head, post
            )
        else:
            paths = default_resolve_remote_diff(
                attribution.repository,
                attribution.remote_pre_head,
                post,
                work_root=root,
            )
        if paths is None:
            raise SdkRuntimeError(
                "remote changed-path diff undetermined",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        # Persist terminal head onto the mutable baseline copy for caller.
        attribution.remote_branch = branch
        attribution.remote_post_head = post
        return paths


def collect_run_changed_paths(
    root: Path,
    *,
    runtime: AgentRuntime,
    attribution: RunMutationBaseline | None,
    terminal_git: RunGitInfo | None,
    local_pre_head: str | None,
    cloud_provider: CloudRemoteGitAttributionProvider | None = None,
    local_provider: LocalWorktreeAttributionProvider | None = None,
) -> list[str] | None:
    """Dispatch attribution by runtime. CLOUD never falls back to local root."""
    if runtime == AgentRuntime.LOCAL:
        provider = local_provider or LocalWorktreeAttributionProvider()
        baseline = attribution or RunMutationBaseline(
            run_id="local",
            agent_id="local",
            runtime=AgentRuntime.LOCAL,
            base_main=local_pre_head or "0" * 40,
            dag_generation=0,
        )
        return provider.collect_changed_paths(
            root=root,
            attribution=baseline,
            terminal_git=terminal_git,
            local_pre_head=local_pre_head,
        )
    if runtime == AgentRuntime.CLOUD:
        if attribution is None:
            raise SdkRuntimeError(
                "missing CLOUD run mutation baseline",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        if attribution.runtime != AgentRuntime.CLOUD:
            raise SdkRuntimeError(
                "attribution runtime mismatch",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        provider = cloud_provider or CloudRemoteGitAttributionProvider()
        return provider.collect_changed_paths(
            root=root,
            attribution=attribution,
            terminal_git=terminal_git,
            local_pre_head=None,
        )
    raise SdkRuntimeError(
        f"unsupported attribution runtime {runtime}",
        code="REMOTE_ATTRIBUTION_UNDETERMINED",
    )


def mint_cloud_run_baseline(
    *,
    root: Path,
    run_id: str,
    agent_id: str,
    base_main: str,
    branch: str | None,
    dag_generation: int,
    lease_id: str | None,
    package_id: str = PACKAGE_ID,
    repository: str = CANONICAL_REPO_URL,
) -> RunMutationBaseline:
    """First Cloud run baselines at base_main; follow-ups chain prior post head."""
    prior = load_agent_remote_high_water(root, agent_id)
    remote_pre = prior if prior else base_main
    if not remote_pre or len(remote_pre) < 7:
        raise SdkRuntimeError(
            "invalid CLOUD remote baseline",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    baseline = RunMutationBaseline(
        run_id=run_id,
        agent_id=agent_id,
        runtime=AgentRuntime.CLOUD,
        repository=repository,
        base_main=base_main,
        remote_branch=branch,
        remote_pre_head=remote_pre,
        remote_post_head=None,
        dag_generation=dag_generation,
        lease_id=lease_id,
        package_id=package_id,
    )
    persist_run_mutation_baseline(root, baseline)
    return baseline
