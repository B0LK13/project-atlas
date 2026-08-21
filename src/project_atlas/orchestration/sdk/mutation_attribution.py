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
# Sentinel: prior remote post known undetermined — mint must not fall back to base_main.
REMOTE_HIGH_WATER_UNDETERMINED: Final[str] = "__REMOTE_HIGH_WATER_UNDETERMINED__"

# Exact host/path identity only. Never use search()/suffix match — foreign hosts that
# embed "github.com/..." as a path segment must not collide with canonical.
_REPO_HOST_PATH = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com[/:](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?/?$",
    re.IGNORECASE,
)
_OWNER_REPO_ONLY = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$",
)


class RunGitInfo(BaseModel):
    """Terminal Run.git snapshot from Cursor SDK. Evidence only.

    ``head_sha`` is optional run-scoped post evidence when the SDK surfaces it.
    Prefer it over branch-tip ``ls-remote`` (ORCH-SDK-CLOUD-POST-HEAD-BRANCH-TIP-TOCTOU-001).
    """

    model_config = ConfigDict(extra="forbid")

    repo_url: str | None = None
    branches: tuple[str, ...] = ()
    head_sha: str | None = None


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
    """Normalize repo URLs to a comparable identity.

    Accepts only:
    - canonical GitHub host forms (``github.com/owner/repo`` with optional scheme)
    - bare ``owner/repo`` (no foreign host labels)

    Rejects foreign hosts (gitlab/evil/etc.) and suffix tricks such as
    ``evil.com/github.com/B0LK13/project-atlas`` that previously matched via
    ``re.search``.
    """
    if raw is None:
        return None
    text = raw.strip().replace("\\", "/")
    if not text:
        return None
    # git@github.com:owner/repo
    if text.casefold().startswith("git@"):
        _, remainder = text.split("@", 1)
        text = remainder.replace(":", "/", 1)
    for prefix in ("https://", "http://", "ssh://", "git://"):
        if text.casefold().startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.strip("/")
    match = _REPO_HOST_PATH.fullmatch(text)
    if match is not None:
        owner = match.group("owner")
        repo = match.group("repo")
        return f"https://github.com/{owner}/{repo}".casefold()
    # Bare owner/repo only — reject anything with an extra host/path segment.
    bare = _OWNER_REPO_ONLY.fullmatch(text)
    if bare is not None and "." not in bare.group("owner"):
        owner = bare.group("owner")
        repo = bare.group("repo")
        return f"https://github.com/{owner}/{repo}".casefold()
    # Foreign or malformed: return a stable non-canonical identity when a host
    # is present so callers raise "foreign repository"; otherwise None.
    parts = [p for p in text.split("/") if p]
    if len(parts) >= 3 and "." in parts[0]:
        host, owner, repo = parts[0], parts[1], parts[2].removesuffix(".git")
        return f"https://{host}/{owner}/{repo}".casefold()
    if len(parts) == 2 and "." in parts[0]:
        # host/repo without owner — not a valid GitHub identity
        return text.rstrip("/").casefold()
    return None


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


def mark_agent_remote_high_water_undetermined(root: Path, agent_id: str) -> None:
    """Record that prior remote post is undetermined (disconnect / failed enforce).

    ORCH-SDK-CLOUD-DISCONNECT-HW-GAP-001: subsequent mint must not silently
    re-baseline to base_main.
    """
    persist_agent_remote_high_water(root, agent_id, REMOTE_HIGH_WATER_UNDETERMINED)


def agent_remote_high_water_is_undetermined(value: str | None) -> bool:
    return value == REMOTE_HIGH_WATER_UNDETERMINED


def _agent_has_incomplete_cloud_baseline(root: Path, agent_id: str) -> bool:
    """True when a prior CLOUD baseline for this agent never recorded post_head."""
    path = attribution_store_path(root)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    if not isinstance(data, dict):
        return True
    for row in data.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("agent_id") or "") != agent_id:
            continue
        if str(row.get("runtime") or "") != AgentRuntime.CLOUD.value:
            continue
        post = row.get("remote_post_head")
        if post is None or (isinstance(post, str) and len(post.strip()) < 7):
            return True
    return False


def _mapping_or_attr(obj: Any, *names: str) -> Any:
    """Read an explicit field from a typed object or mapping. No recursion."""
    if obj is None:
        return None
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


def _locate_terminal_git_object(source: Any) -> Any | None:
    """Bounded D-119 shapes only: source.git | source.run.git | dict forms."""
    if source is None:
        return None
    git_obj = _mapping_or_attr(source, "git")
    if git_obj is not None:
        return git_obj
    run_obj = _mapping_or_attr(source, "run")
    if run_obj is not None:
        return _mapping_or_attr(run_obj, "git")
    return None


def _read_repo_url_from_git_object(git_obj: Any) -> str | None:
    """Explicit git.* fields only (plus observed branch-entry repo_url on git)."""
    repo = _mapping_or_attr(git_obj, "repo_url", "repoUrl")
    if repo is not None:
        return str(repo)
    nested = _mapping_or_attr(git_obj, "repo", "repository")
    if nested is not None:
        nested_url = _mapping_or_attr(nested, "url", "repo_url", "repoUrl")
        if nested_url is not None:
            return str(nested_url)
    # Authentic cursor_sdk: repo_url may live on git.branches[] entries.
    branches_raw = _mapping_or_attr(git_obj, "branches")
    if isinstance(branches_raw, (list, tuple)):
        for item in branches_raw:
            if isinstance(item, str):
                continue
            item_repo = _mapping_or_attr(item, "repo_url", "repoUrl", "url")
            if item_repo is not None:
                return str(item_repo)
    return None


def _read_head_sha_from_git_object(git_obj: Any) -> str | None:
    head_sha = _mapping_or_attr(
        git_obj, "head_sha", "headSha", "commit_sha", "commitSha", "sha"
    )
    branches_raw = _mapping_or_attr(git_obj, "branches")
    if head_sha is None and isinstance(branches_raw, (list, tuple)):
        for item in branches_raw:
            if isinstance(item, str):
                continue
            head_sha = _mapping_or_attr(
                item, "head_sha", "headSha", "commit_sha", "commitSha", "sha"
            )
            if head_sha is not None:
                break
    if head_sha is None:
        return None
    text = str(head_sha).strip()
    return text if len(text) >= 7 else None


def _read_branches_from_git_object(git_obj: Any) -> tuple[str, ...]:
    branches_raw = _mapping_or_attr(git_obj, "branches")
    branches: list[str] = []
    if isinstance(branches_raw, (list, tuple)):
        for item in branches_raw:
            if isinstance(item, str):
                name = item.strip()
            else:
                name = str(
                    _mapping_or_attr(item, "name", "branch") or ""
                ).strip()
            if name:
                branches.append(name)
    return tuple(branches)


def extract_terminal_run_git(source: Any) -> RunGitInfo | None:
    """D-119 bounded adapter: locate Run.git then read explicit fields only.

    Allowed traversal: ``source.git``, ``source.run.git``, and dict equivalents.
    No arbitrary recursive walk / substring search / prose parsing.
    """
    git_obj = _locate_terminal_git_object(source)
    if git_obj is None:
        return None
    return RunGitInfo(
        repo_url=_read_repo_url_from_git_object(git_obj),
        branches=_read_branches_from_git_object(git_obj),
        head_sha=_read_head_sha_from_git_object(git_obj),
    )


def extract_run_git(result: Any) -> RunGitInfo | None:
    """Compatibility alias for :func:`extract_terminal_run_git`."""
    return extract_terminal_run_git(result)


def bind_terminal_git_repository(
    terminal_git: RunGitInfo,
    *,
    attribution: RunMutationBaseline,
) -> RunGitInfo:
    """Apply trusted launch binding vs terminal SDK echo (D-119).

    - ``REPO_URL_PRESENT_AND_FOREIGN`` → fail closed
    - ``REPO_URL_ABSENT`` + valid canonical launch baseline → supply from baseline
    - ``REPO_URL_ABSENT`` without valid baseline → fail closed
    """
    canon = canonical_repo_identity()
    base_id = normalize_repo_identity(attribution.repository)
    if terminal_git.repo_url is not None:
        echo_id = normalize_repo_identity(terminal_git.repo_url)
        if (
            echo_id is None
            or canon is None
            or echo_id != canon
            or base_id != canon
            or echo_id != base_id
        ):
            raise SdkRuntimeError(
                "foreign repository in terminal Run.git",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        return terminal_git
    # Omitted repo_url: launch baseline may supply ONLY under strict binding.
    if attribution.runtime != AgentRuntime.CLOUD:
        raise SdkRuntimeError(
            "terminal Run.git missing repository",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    if attribution.package_id != PACKAGE_ID:
        raise SdkRuntimeError(
            "launch baseline package_id mismatch",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    if base_id != canon:
        raise SdkRuntimeError(
            "launch baseline repository is not canonical Atlas",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    if not attribution.remote_pre_head or len(attribution.remote_pre_head) < 7:
        raise SdkRuntimeError(
            "launch baseline remote_pre_head invalid",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    if not attribution.run_id or not attribution.agent_id:
        raise SdkRuntimeError(
            "launch baseline missing run/agent binding",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    return terminal_git.model_copy(update={"repo_url": attribution.repository})


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
        # D-119: bind trusted launch repository when Run.git omits repo_url;
        # foreign present echo always fails closed.
        bound_git = bind_terminal_git_repository(
            terminal_git, attribution=attribution
        )
        branch = select_canonical_remote_branch(
            bound_git, expected_branch=attribution.remote_branch
        )
        if (
            attribution.remote_branch
            and branch != attribution.remote_branch
        ):
            raise SdkRuntimeError(
                "cloud branch changed unexpectedly vs lineage",
                code="REMOTE_ATTRIBUTION_UNDETERMINED",
            )
        # Prefer run-scoped SHA when SDK provides it (closes branch-tip TOCTOU
        # for that run). Current cursor_sdk RunGitInfo has no SHA field — tip
        # resolution remains a documented residual hazard covered by regression
        # tests that prove SHA preference when present.
        post: str | None = None
        if bound_git.head_sha and len(bound_git.head_sha) >= 7:
            post = bound_git.head_sha.strip()
        else:
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
        local_impl = local_provider or LocalWorktreeAttributionProvider()
        baseline = attribution or RunMutationBaseline(
            run_id="local",
            agent_id="local",
            runtime=AgentRuntime.LOCAL,
            base_main=local_pre_head or "0" * 40,
            dag_generation=0,
        )
        return local_impl.collect_changed_paths(
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
        cloud_impl = cloud_provider or CloudRemoteGitAttributionProvider()
        return cloud_impl.collect_changed_paths(
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
    """First Cloud run baselines at base_main; follow-ups chain prior post head.

    ORCH-SDK-CLOUD-DISCONNECT-HW-GAP-001: refuse silent re-baseline to base_main
    when prior remote high-water is undetermined or a prior CLOUD baseline never
    recorded remote_post_head.
    """
    prior = load_agent_remote_high_water(root, agent_id)
    if agent_remote_high_water_is_undetermined(prior):
        raise SdkRuntimeError(
            "prior CLOUD remote high-water undetermined; refuse silent rebase to base_main",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
    if prior is None and _agent_has_incomplete_cloud_baseline(root, agent_id):
        raise SdkRuntimeError(
            "incomplete prior CLOUD remote post; refuse silent rebase to base_main",
            code="REMOTE_ATTRIBUTION_UNDETERMINED",
        )
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
