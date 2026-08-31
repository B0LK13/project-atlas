"""AS-ORCH-LOCAL-PROC-001: provider-neutral local process execution backend.

DISABLED BY DEFAULT. Launches an explicitly configured local command --
this module implies nothing about Cursor, OpenAI, Anthropic, network
access, or API billing. It merely runs a fixed argv vector as a local
child process and independently measures what that process actually
touched.

Reuses ``agent_transport.py``'s ``ProcessRunRequest`` / ``ProcessRunOutcome``
/ ``ProcessRunner`` / ``SubprocessProcessRunner`` -- already argv-vector-only
(``shell=False``, never a shell string), timeout-enforcing, and bounded-
capture -- rather than re-implementing process launch. This module adds
what that transport layer deliberately does not: a disabled-by-default
config, an immutable per-task envelope, a minimum-necessary env allowlist,
and independent post-execution authority enforcement via ``git`` state
inspection.

Independent post-execution authority enforcement (the security property
this module exists for): what a launched process actually changed on disk
is measured by diffing the repository's own git state before and after
the run -- never by trusting the process's exit code or anything it wrote
to stdout/stderr. That measured change set is then checked against an
explicit ``authorized_paths`` allowlist and ``forbidden_paths`` denylist
carried on the task envelope itself, never inferred or guessed.

SPEND_OR_NETWORK_SIDE_EFFECT = NO -- this module never makes an HTTP
request, never reads a cloud API key, and never references Cursor,
OpenAI, or Anthropic by name anywhere in its logic. The only network
access a task could ever perform is whatever the operator-configured
argv itself does, entirely outside this module's control -- the same is
true of any local process launcher; this module's job is to constrain
*how* that argv is launched and *what is authorized to change*, not to
sandbox arbitrary code execution.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.agent_transport import (
    ProcessRunner,
    ProcessRunOutcome,
    ProcessRunRequest,
    SubprocessProcessRunner,
    digest_bytes,
)

PACKAGE_ID: Final[str] = "AS-ORCH-LOCAL-PROC-001"

#: A conservative, explicitly non-secret set of purely operational
#: environment variables most local interpreters/tools need merely to
#: start up (locate shared libraries, a temp dir, the current user's
#: profile). None of these carry credentials. This is the executor
#: config's *default* -- a project may narrow it (down to ``()``, the
#: most conservative setting) or widen it, but nothing outside this
#: explicit, reviewable list -- and certainly nothing that merely
#: *looks* like a secret to some heuristic -- is ever forwarded by
#: default. "Minimum necessary", not "zero", because a default of
#: literally no environment at all silently breaks most real
#: interpreters on most platforms in a way that looks like this module
#: is broken rather than like the operator made a deliberate choice.
DEFAULT_ENV_ALLOWLIST: Final[tuple[str, ...]] = (
    "PATH",
    "SystemRoot",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "PYTHONIOENCODING",
)

_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_MAX_ARGV_LENGTH = 64
_MAX_PATH_ENTRIES = 256
_MAX_ENV_ENTRIES = 64


class LocalExecutionError(ValueError):
    """A local-process task could not be run at all (never a partial or
    ambiguous outcome -- either a real ``LocalExecutionResult`` comes
    back, or this is raised before any process is started)."""

    code: str = "LOCAL_EXECUTION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class LocalExecutionDisabledError(LocalExecutionError):
    code = "LOCAL_EXECUTION_DISABLED"


#: IV finding (PR #661 review): the original check only looked for a
#: leading POSIX ``/`` -- a Windows drive-letter (``C:/...``,
#: ``C:\...``) or UNC (``\\host\share``) absolute path was not rejected
#: at construction time. It was still blocked one layer later
#: (``_resolve_cwd()``'s ``is_relative_to(resolved_root)`` check, before
#: any process starts -- no actual launch bypass existed), but input
#: validation should reject an absolute path at the envelope boundary
#: itself, not rely solely on that downstream defense-in-depth.
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _safe_relative_path(value: str, *, field_name: str) -> str:
    posix = value.replace("\\", "/")
    if posix.startswith("./"):
        posix = posix[2:]
    if (
        not posix
        or posix.startswith("/")
        or posix.startswith("//")
        or _WINDOWS_DRIVE_RE.match(value)
        or ".." in posix.split("/")
    ):
        raise ValueError(f"{field_name} must be a safe relative path, got {value!r}")
    return posix


class LocalProcessExecutorConfig(BaseModel):
    """Explicit, operator-authored configuration for the local-process
    backend. ``enabled`` defaults to ``False`` -- the backend refuses to
    run anything at all until a project/operator explicitly opts in
    (D-CODEX-ATLAS-SUPERVISED-AUTONOMY-PREREQUISITES-AND-RETRY: "DISABLED
    BY DEFAULT")."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool = False
    env_allowlist: tuple[str, ...] = Field(
        default=DEFAULT_ENV_ALLOWLIST, max_length=_MAX_ENV_ENTRIES
    )
    timeout_seconds: int = Field(default=600, ge=1, le=86_400)

    @field_validator("env_allowlist")
    @classmethod
    def _validate_env_allowlist(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for name in value:
            if not _ENV_NAME_RE.fullmatch(name):
                raise ValueError(f"invalid env allowlist entry: {name!r}")
        return tuple(dict.fromkeys(value))


class LocalTaskEnvelope(BaseModel):
    """Immutable description of exactly ONE local-process task
    (``frozen=True``: constructing a new envelope is the only way to
    change anything about it -- there is no in-place mutation path).
    Every fact the executor consults comes from here, never from ambient
    process state and never from anything the launched process itself
    later reports about what it did.

    ``argv`` is a trusted vector, never shell text: element 0 is the
    executable, everything after is passed to it literally. No element
    of ``argv`` is ever interpreted by a shell (mirrors
    ``agent_transport.SubprocessProcessRunner``'s own ``shell=False``
    invariant one layer up); a task's own title/prose can never choose
    or influence the executable or its arguments merely by containing
    shell metacharacters -- the caller must construct ``argv`` itself
    from trusted configuration, exactly as ``agent_transport.py``'s
    Cursor launch-plan resolver already requires for its own executable
    identity.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str = Field(min_length=1, max_length=128)
    argv: tuple[str, ...] = Field(min_length=1, max_length=_MAX_ARGV_LENGTH)
    cwd: str = Field(default=".", min_length=1, max_length=4096)
    authorized_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=_MAX_PATH_ENTRIES)
    forbidden_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=_MAX_PATH_ENTRIES)
    env_overrides: tuple[tuple[str, str], ...] = Field(
        default_factory=tuple, max_length=_MAX_ENV_ENTRIES
    )

    @field_validator("cwd")
    @classmethod
    def _validate_cwd(cls, value: str) -> str:
        if value == ".":
            return value
        return _safe_relative_path(value, field_name="cwd")

    @field_validator("authorized_paths", "forbidden_paths")
    @classmethod
    def _validate_scope_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for entry in value:
            trimmed = entry[:-1] if entry.endswith("/") else entry
            _safe_relative_path(trimmed or ".", field_name="scope path")
        return value

    @field_validator("env_overrides")
    @classmethod
    def _validate_env_override_names(
        cls, value: tuple[tuple[str, str], ...]
    ) -> tuple[tuple[str, str], ...]:
        for name, _ in value:
            if not _ENV_NAME_RE.fullmatch(name):
                raise ValueError(f"invalid env override name: {name!r}")
        return value


class AuthorityViolation(BaseModel):
    """One path the launched process changed that its own task envelope
    did not authorize. Never a claim the process was malicious -- only
    that its actual effect exceeded its declared scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    reason: Literal["FORBIDDEN_PATH", "OUTSIDE_AUTHORIZED_SCOPE"]


class LocalExecutionResult(BaseModel):
    """Terminal facts about one completed local-process task. Exit 0 is
    not task success (mirrors ``agent_transport.ProcessRunOutcome``'s own
    documented stance) and ``authority_clean`` is not merit -- it only
    means the independently-measured change set matched what was
    declared authorized."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_id: str
    exit_code: int
    timed_out: bool
    duration_ms: int
    stdout_digest: str
    stderr_digest: str
    changed_paths: tuple[str, ...]
    violations: tuple[AuthorityViolation, ...]
    authority_clean: bool
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


def _run_git(args: list[str], *, cwd: Path) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _current_head_sha(repo_root: Path) -> str:
    result = _run_git(["rev-parse", "HEAD"], cwd=repo_root)
    if not result:
        raise LocalExecutionError(
            "could not resolve HEAD before running the task -- refusing to run "
            "without a fixed baseline to measure authority against",
            code="GIT_BASELINE_UNRESOLVABLE",
        )
    return result[0]


def _git_changed_paths(repo_root: Path, *, baseline_sha: str) -> frozenset[str]:
    """Every path with a real difference from the FIXED ``baseline_sha``
    -- tracked modifications/deletions/renames plus new untracked files
    -- repo-relative, POSIX-normalized. This is the *only* source of
    truth this module consults for "what changed"; it never reads what
    the launched process itself reported.

    IV finding (PR #661 review, self-commit bypass): diffing against the
    live ``HEAD`` ref instead of a fixed baseline SHA meant a launched
    process that ran ``git commit`` on its own changes -- an entirely
    ordinary thing for a coding-agent-style task to do -- made ``HEAD``
    itself advance along with the change, so the "after" measurement's
    baseline moved too and the committed change never appeared as a
    delta. ``git diff <fixed-sha>`` (no second ref) compares that
    unmoving commit's tree against the *current working tree*, regardless
    of where ``HEAD`` points by the time this runs -- a committed change
    still shows up as a difference from the pre-run baseline, closing
    that bypass. (A process that commits and then discards its own commit
    via ``git reset --hard <baseline>`` before exiting can still erase
    its tracks from this working-tree-vs-baseline comparison, same as it
    could erase them from a live-``HEAD`` comparison or from disk
    directly -- that residual gap is a git-history-forensics problem, not
    something a single before/after working-tree diff can close, and is
    out of scope for this module's stated design.)
    """
    tracked = _run_git(["diff", "--name-only", baseline_sha], cwd=repo_root)
    untracked = _run_git(["ls-files", "--others", "--exclude-standard"], cwd=repo_root)
    return frozenset((*tracked, *untracked))


def _matches_scope(path: str, patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/"):
            prefix = pattern.rstrip("/")
            if path == prefix or path.startswith(pattern):
                return True
        elif path == pattern:
            return True
    return False


def _enforce_authority(
    changed_paths: frozenset[str],
    *,
    authorized_paths: tuple[str, ...],
    forbidden_paths: tuple[str, ...],
) -> tuple[AuthorityViolation, ...]:
    violations: list[AuthorityViolation] = []
    for path in sorted(changed_paths):
        if _matches_scope(path, forbidden_paths):
            violations.append(AuthorityViolation(path=path, reason="FORBIDDEN_PATH"))
            continue
        if authorized_paths and not _matches_scope(path, authorized_paths):
            violations.append(AuthorityViolation(path=path, reason="OUTSIDE_AUTHORIZED_SCOPE"))
    return tuple(violations)


def _build_env(
    *, allowlist: tuple[str, ...], overrides: tuple[tuple[str, str], ...]
) -> dict[str, str]:
    """Minimum-necessary environment: start from nothing (never
    ``os.environ`` wholesale -- see ``agent_transport.sanitize_inherited_
    env``'s own docstring for why ambient inheritance is the wrong
    default for an externally-configured local command), then copy
    across only the ambient values for names the executor config's own
    ``env_allowlist`` names, plus any per-task ``env_overrides`` -- also
    restricted to allowlisted names, so a task envelope can never smuggle
    a non-allowlisted variable in on its own authority. Nothing here
    inspects a name for "looks like a secret"; the allowlist is the only
    authority. An ambient ``ANTHROPIC_API_KEY``/``OPENAI_API_KEY``/
    ``CURSOR_API_KEY`` (or any other credential-shaped variable) is never
    forwarded unless a project's own config explicitly names it."""
    allowed = set(allowlist)
    env: dict[str, str] = {
        name: value for name, value in os.environ.items() if name in allowed
    }
    for name, value in overrides:
        if name in allowed:
            env[name] = value
    return env


def _resolve_cwd(project_root: Path, relative_cwd: str) -> Path:
    resolved_root = project_root.expanduser().resolve()
    target = (resolved_root / relative_cwd).resolve() if relative_cwd != "." else resolved_root
    if not (target == resolved_root or target.is_relative_to(resolved_root)):
        raise LocalExecutionError(
            f"envelope cwd {relative_cwd!r} resolves outside project_root", code="CWD_UNSAFE"
        )
    return target


def run_local_task(
    envelope: LocalTaskEnvelope,
    config: LocalProcessExecutorConfig,
    *,
    project_root: Path,
    runner: ProcessRunner | None = None,
) -> LocalExecutionResult:
    """Run exactly one ``LocalTaskEnvelope`` as a local child process and
    return its terminal facts, including an independent authority-
    enforcement verdict.

    Fail-closed: refuses to run at all (``LocalExecutionDisabledError``)
    unless ``config.enabled`` is ``True`` -- never a silent no-op success,
    never an implicit default-on. A malformed/missing/non-executable
    ``argv[0]`` fails the same way any other transport failure does
    (``TransportError`` from ``SubprocessProcessRunner``, propagated
    unchanged -- never swallowed into a false "nothing happened").

    Authority enforcement is independent of the process's own report:
    ``changed_paths``/``violations``/``authority_clean`` are derived
    entirely from git state measured before and after the run, regardless
    of ``exit_code`` or anything on stdout/stderr. A process that exits 0
    and claims success while having touched a forbidden path is still
    flagged.
    """
    if not config.enabled:
        raise LocalExecutionDisabledError(
            "local process execution is disabled (config.enabled=False) -- "
            "no process was started",
            code="LOCAL_EXECUTION_DISABLED",
        )
    resolved_root = project_root.expanduser().resolve()
    resolved_cwd = _resolve_cwd(resolved_root, envelope.cwd)
    env = _build_env(allowlist=config.env_allowlist, overrides=envelope.env_overrides)

    # A FIXED commit SHA, captured once before the run and never
    # re-resolved afterward. Both the "before" and "after" measurements
    # below diff against this same unmoving baseline -- if the launched
    # process itself advances HEAD (e.g. by running `git commit`), the
    # comparison point does not move with it (see _git_changed_paths's
    # own docstring for the bypass this specifically closes).
    baseline_sha = _current_head_sha(resolved_root)
    before = _git_changed_paths(resolved_root, baseline_sha=baseline_sha)
    request = ProcessRunRequest(
        argv=envelope.argv,
        cwd=resolved_cwd,
        timeout_seconds=config.timeout_seconds,
        env=env,
        stdin=None,
    )
    active_runner: ProcessRunner = runner if runner is not None else SubprocessProcessRunner()
    outcome: ProcessRunOutcome = active_runner.run(request)
    after = _git_changed_paths(resolved_root, baseline_sha=baseline_sha)

    new_paths = after - before
    violations = _enforce_authority(
        new_paths,
        authorized_paths=envelope.authorized_paths,
        forbidden_paths=envelope.forbidden_paths,
    )
    return LocalExecutionResult(
        work_id=envelope.work_id,
        exit_code=outcome.exit_code,
        timed_out=outcome.timed_out,
        duration_ms=outcome.duration_ms,
        stdout_digest=digest_bytes(outcome.stdout),
        stderr_digest=digest_bytes(outcome.stderr),
        changed_paths=tuple(sorted(new_paths)),
        violations=violations,
        authority_clean=not violations,
    )


__all__ = [
    "DEFAULT_ENV_ALLOWLIST",
    "PACKAGE_ID",
    "AuthorityViolation",
    "LocalExecutionDisabledError",
    "LocalExecutionError",
    "LocalExecutionResult",
    "LocalProcessExecutorConfig",
    "LocalTaskEnvelope",
    "run_local_task",
]
