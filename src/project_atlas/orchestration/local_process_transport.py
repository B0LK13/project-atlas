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
import stat
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
        """Validate AND normalize -- IV finding (PR #661 review): the
        original validator called ``_safe_relative_path()`` only to
        check safety and then discarded its normalized return value,
        storing the caller's raw, un-normalized entry instead. A
        directory-prefix entry spelled ``./src/`` or ``src\\`` (Windows
        backslash) passed validation but would never equal the POSIX-
        normalized, ``./``-stripped git paths ``_matches_scope()``
        compares it against -- silently disabling enforcement for a
        mis-specified but otherwise reasonable-looking pattern."""
        normalized: list[str] = []
        for entry in value:
            is_dir_prefix = entry.endswith("/") or entry.endswith("\\")
            trimmed = entry[:-1] if is_dir_prefix else entry
            safe = _safe_relative_path(trimmed or ".", field_name="scope path")
            normalized.append(f"{safe}/" if is_dir_prefix else safe)
        return tuple(normalized)

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


def _require_clean_worktree(repo_root: Path) -> None:
    """Fail closed unless the repository has no uncommitted changes right
    before the task starts.

    IV finding (PR #661 review, ``chatgpt-codex-connector`` P1 + Copilot):
    the original "before minus after" set-difference approach fails open
    against a worktree that is already dirty: a path present (dirty) in
    both the "before" and "after" snapshots is filtered out by the
    subtraction even if its actual *content* changed during the run --
    "modify an already-modified forbidden file further" or "stage and
    commit an already-dirty change" both leave the path's *membership* in
    the dirty-set unchanged while its content moves. Requiring a clean
    starting point removes the ambiguity entirely: with nothing dirty to
    begin with, any post-run difference from the fixed baseline is
    unambiguously attributable to the task, with no subtraction needed at
    all (see ``run_local_task``).
    """
    status = _run_git(["status", "--porcelain"], cwd=repo_root)
    if status:
        raise LocalExecutionError(
            "repository has uncommitted changes before the task started -- "
            "refusing to run without a clean, unambiguous baseline to "
            f"measure authority against (dirty paths: {status[:10]!r})",
            code="WORKTREE_NOT_CLEAN",
        )


def _git_changed_paths(repo_root: Path, *, baseline_sha: str) -> frozenset[str]:
    """Every path with a real difference from the FIXED ``baseline_sha``
    -- tracked modifications/deletions/renames plus new untracked files
    -- repo-relative, POSIX-normalized. This is the *only* git-based
    source of truth this module consults for "what changed"; it never
    reads what the launched process itself reported. Called exactly once,
    after the run, against a worktree ``_require_clean_worktree()``
    already verified was clean beforehand -- no "before" snapshot or
    subtraction is needed (see that function's docstring for why a
    before/after set-difference approach was itself the bypass).

    IV finding (PR #661 review, self-commit bypass): diffing against the
    live ``HEAD`` ref instead of a fixed baseline SHA meant a launched
    process that ran ``git commit`` on its own changes -- an entirely
    ordinary thing for a coding-agent-style task to do -- made ``HEAD``
    itself advance along with the change, so the measurement's own
    baseline moved too and the committed change never appeared as a
    delta. ``git diff <fixed-sha>`` (no second ref) compares that
    unmoving commit's tree against the *current working tree*, regardless
    of where ``HEAD`` points by the time this runs -- a committed change
    still shows up as a difference from the pre-run baseline, closing
    that bypass.

    This function alone only sees the *current working tree*, so it does
    NOT by itself catch a process that commits on a throwaway branch (or
    stash) and then returns the original branch and working tree to
    their pre-run state -- see ``_new_commit_changed_paths()``, called
    alongside this one in ``run_local_task()`` (paired with an existence
    snapshot of every ref TIP from ``_all_ref_tips()``), which closes
    that class of evasion by diffing baseline against every ref that
    changed or newly appeared (not just the current branch), not only
    the live working tree.

    ``git ls-files --others --exclude-standard`` deliberately excludes
    gitignored paths (the normal, desired behavior for "what would a
    human `git status` show"), which is why this alone is not sufficient
    for ``forbidden_paths`` enforcement -- see
    ``_forbidden_path_content_snapshot()``, which checks declared
    forbidden paths directly against the filesystem, independent of git
    tracking/ignore status entirely -- nor, by itself, for
    ``authorized_paths`` enforcement -- see ``_ignored_untracked_paths()``,
    called alongside this one in ``run_local_task()``, which additionally
    catches a *new* gitignored path created anywhere, closing the same
    blind spot for the "did this task stay within its authorized scope"
    check, not only the forbidden-path check.

    IV finding (PR #661 review, round 5): this function's own untracked-
    file listing has exactly the same NTFS-junction exposure
    ``_ignored_untracked_paths()`` was fixed for in round 4 -- ``git
    ls-files`` transparently follows a junction regardless of
    ``--exclude-standard``, so a junction under ``authorized_paths``'s
    scope (tracked-adjacent, not gitignored) still leaked every file
    inside its external target individually instead of collapsing to the
    junction's own path. The round-4 fix was applied only to the sibling
    function; confirmed by hosted CI failing on exactly this. Every path
    is now collapsed through ``_collapse_reparse_point_descendants()``
    here too.
    """
    tracked = _run_git(["diff", "--name-only", baseline_sha], cwd=repo_root)
    untracked = _run_git(["ls-files", "--others", "--exclude-standard"], cwd=repo_root)
    return _collapse_reparse_point_descendants(frozenset((*tracked, *untracked)), repo_root)


def _ignored_untracked_paths(repo_root: Path) -> frozenset[str]:
    """Every currently-existing untracked path, INCLUDING gitignored ones
    -- unlike ``_git_changed_paths()``'s own untracked listing, which
    passes ``--exclude-standard`` specifically to mirror ordinary ``git
    status`` output. Used only for a before/after SET-difference (see
    ``run_local_task``) to detect a newly-created ignored path.

    IV finding (PR #661 review, round 3): the ``OUTSIDE_AUTHORIZED_SCOPE``
    half of enforcement relied solely on ``_git_changed_paths()``, which
    excludes gitignored paths entirely -- a task that created a brand-new
    gitignored file *outside every declared* ``authorized_paths``/
    ``forbidden_paths`` entry (e.g. an ad hoc ``.log`` or cache file
    sitting at the repo root, gitignored by a wildcard rule that was
    never meant to hide anything security-relevant) was completely
    invisible to enforcement -- ``authority_clean=True`` with the file
    left on disk.

    A before/after SET-difference is safe here specifically because this
    only tracks pure path *existence*, never content: a path present in
    both snapshots is unambiguously "already existed, not new" -- there
    is no membership-vs-content subtlety to exploit the way there was for
    git's own dirty-status tracking (which is exactly why
    ``_require_clean_worktree()`` requires a clean start for the
    git-tracked side, but a set-difference remains sound here). This
    mirrors ``_forbidden_path_content_snapshot()``'s bounded, filesystem-
    direct approach rather than trying to force ``_git_changed_paths()``
    itself to somehow cover both cases.

    Residual, disclosed limitation (same class as the ``git reset --hard``
    case): a gitignored path that already existed unchanged before the
    task ran, then has its *content* modified during the run, is not
    caught by this existence-only set-difference unless it also falls
    under a declared ``forbidden_paths`` entry (which IS content-hashed,
    not just existence-checked) -- closing that fully in general would
    require content-hashing every gitignored path in the repository on
    every run (e.g. an entire ``.venv``/``node_modules`` tree), which is
    not a proportionate cost for this module's stated design.

    IV finding (PR #661 review, round 4): ``git ls-files --others``
    transparently follows an NTFS junction on Windows -- unlike a
    symlink, git has no special handling for a junction at all, so it
    silently enumerates whatever the junction's external target
    contains as though those files were untracked content of this repo
    (e.g. a task creating ``secrets/junction_out`` pointed at an
    unrelated external directory makes every file in that external
    directory show up here as ``secrets/junction_out/<name>``). Left
    unhandled, this both re-exposes a milder version of the round-3
    resource-exhaustion risk (enumerating, though not reading, an
    arbitrarily large external tree) and misleadingly attributes
    pre-existing external files to the task as though it had created
    them. Every path is collapsed to its nearest reparse-point ancestor
    (``_collapse_reparse_point_descendants()``) before returning -- the
    junction/symlink entity itself is still a real, reported new path
    (created during the run), but nothing "inside" it is ever walked or
    listed.
    """
    result = subprocess.run(
        ["git", "ls-files", "--others"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    raw_paths = frozenset(
        line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()
    )
    return _collapse_reparse_point_descendants(raw_paths, repo_root)


def _collapse_reparse_point_descendants(paths: frozenset[str], repo_root: Path) -> frozenset[str]:
    """Replace any path that lies *underneath* a reparse-point directory
    (a symlink or, on Windows, an NTFS junction) with that directory's
    own path instead -- so a caller never sees, and this module never
    stats/reads, anything git happened to enumerate by transparently
    walking through the reparse point itself. A directory's reparse
    status is checked at most once per distinct ancestor path (cached),
    not once per file beneath it."""
    reparse_cache: dict[str, bool] = {}
    collapsed: set[str] = set()
    for rel in paths:
        parts = rel.split("/")
        prefix_parts: list[str] = []
        current = repo_root
        replacement: str | None = None
        for part in parts[:-1]:
            prefix_parts.append(part)
            current = current / part
            prefix = "/".join(prefix_parts)
            is_reparse = reparse_cache.get(prefix)
            if is_reparse is None:
                is_reparse = _is_reparse_point(current)
                reparse_cache[prefix] = is_reparse
            if is_reparse:
                replacement = prefix
                break
        collapsed.add(replacement if replacement is not None else rel)
    return frozenset(collapsed)


def _all_ref_tips(repo_root: Path) -> frozenset[str]:
    """Every ref's current tip commit SHA right now -- every branch,
    every tag, and ``refs/stash`` if it exists (``git for-each-ref`` with
    no pattern lists everything under ``refs/``, ``refs/stash`` included).
    A pure existence snapshot, taken before and after the run and
    compared by set difference in ``run_local_task``: only a ref whose
    tip is genuinely new (or changed) is passed on to
    ``_new_commit_changed_paths()``, which then walks *that ref's own*
    bounded history segment back to baseline -- never every ref's full
    reachable history (``--all``), which is what caused the round-4
    false-positive bug this pairing exists to avoid."""
    try:
        result = subprocess.run(
            ["git", "for-each-ref", "--format=%(objectname)"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.CalledProcessError:
        return frozenset()
    return frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())


def _is_root_commit(repo_root: Path, commit_sha: str) -> bool:
    """True if ``commit_sha`` has no parent of its own -- e.g. the
    synthetic "untracked files" commit ``git stash push -u`` creates."""
    result = subprocess.run(
        ["git", "rev-list", "--parents", "-n", "1", commit_sha],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Output is "<sha> [parent1] [parent2] ..." on one line -- exactly
    # one token (the commit itself) means no parents.
    return len(result.stdout.split()) <= 1


def _new_commit_changed_paths(
    repo_root: Path, *, baseline_sha: str, new_tips: frozenset[str]
) -> frozenset[str]:
    """Every path changed relative to the fixed ``baseline_sha``, as seen
    from any of ``new_tips``.

    IV finding (PR #661 review, round 3): ``_git_changed_paths()`` alone
    only sees the current working tree, so a launched process that
    commits its own forbidden-path change on a throwaway branch (``git
    checkout -b tmp && ... && git commit ... && git checkout -``) or as a
    stash entry (``git stash push``), then returns the original branch
    and working tree to their exact pre-run state, left nothing for a
    working-tree diff to see -- even though the change survives as a
    real, ref-reachable commit object (visible to a human via ``git
    branch -a`` or ``git stash list``).

    IV finding (PR #661 review, round 4 -- this function's own
    correctness bug, not a security bypass but the opposite): the
    round-3 predecessor of this function queried ``git rev-list --all
    --not <baseline_sha>`` in a single post-run call. That lists every
    commit reachable from any ref that is simply not an ANCESTOR of
    baseline -- which includes every commit that already existed on any
    other branch/tag/remote-tracking ref *before the task ever ran* (an
    ordinary thing for almost any real, multi-branch clone to have), not
    only commits newly created *during* the run. Demonstrated to produce
    thousands of spurious violations against a completely inert task run
    against this repository's own real clone. Fixed (round 4) by taking
    an existence-only before/after snapshot of ref TIPS (``_all_ref_tips()``)
    instead, and walking only THIS ref's own new history segment
    (``git rev-list <tip> --not <baseline_sha>`` -- bounded to this one
    ref, never ``--all``'s repo-wide walk) rather than every commit
    reachable from anywhere.

    IV finding (PR #661 review, round 5 -- the round-4 fix was itself
    still incomplete in the opposite direction): an early round-5 attempt
    diffed only each new tip directly against baseline (one diff per
    ref, no segment walk at all) reasoning that a tree diff between two
    commits already reflects the tip's full accumulated state. That
    reasoning is wrong for exactly the shape ``git stash push -u``
    produces: the stash entry's own tip tree reflects only *tracked*-file
    modifications -- the untracked files live solely on a third,
    PARENTLESS parent commit, never merged into the tip's own tree at
    all. Diffing tip-vs-baseline directly therefore silently missed the
    untracked-file content entirely (the opposite failure from round 4:
    under-detection instead of a false-positive explosion). Root commits
    are now handled specially: for each commit in the (bounded, per-ref)
    history segment between baseline and a new tip, a ROOT commit (no
    parent -- ``_is_root_commit()``) has every file in its own tree
    listed directly (``git ls-tree``, never diffed against baseline's
    unrelated full tree, which is what caused round 4's explosion); a
    normal, non-root commit is diffed against baseline as before.

    Does NOT catch a commit made unreachable from every ref before the
    process exits (``git reset --hard <baseline>`` after committing, or
    an explicit ``git branch -D``/``git stash drop``) -- a ref-less,
    orphaned commit object requires reflog/dangling-object forensics to
    find, which is a materially harder, more deliberate evasion than an
    ordinary ``checkout -b``/``stash push`` and remains this module's one
    disclosed residual limitation.
    """
    changed: set[str] = set()
    for tip_sha in new_tips:
        try:
            result = subprocess.run(
                ["git", "rev-list", tip_sha, "--not", baseline_sha],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.CalledProcessError:
            continue
        segment = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        for commit_sha in segment:
            if _is_root_commit(repo_root, commit_sha):
                changed.update(
                    _run_git(["ls-tree", "-r", "--name-only", commit_sha], cwd=repo_root)
                )
            else:
                changed.update(
                    _run_git(["diff", "--name-only", baseline_sha, commit_sha], cwd=repo_root)
                )
    return frozenset(changed)


#: A forbidden-path file larger than this is hashed only up to the cap
#: (plus its total size, folded into the digest) -- IV finding (PR #661
#: review, round 3): reading an entire file with no size bound gave a
#: task a way to make this module's own post-run audit step -- which
#: runs synchronously, in-process, after the child's own timeout has
#: already elapsed -- read/hash an arbitrarily large or slow target
#: (see the symlink note below), a resource-exhaustion risk against the
#: orchestrator itself, not against the sandboxed task.
_MAX_FORBIDDEN_PATH_HASH_BYTES = 8 * 1024 * 1024


def _forbidden_path_content_snapshot(
    repo_root: Path, forbidden_paths: tuple[str, ...]
) -> dict[str, str]:
    """Content digest of every file reachable under each declared
    ``forbidden_paths`` entry, read directly from the filesystem --
    entirely independent of git's tracking or ``.gitignore`` status.

    IV finding (PR #661 review, ``chatgpt-codex-connector`` P1): ``git
    ls-files --others --exclude-standard`` deliberately omits gitignored
    paths, so a task that creates or modifies a gitignored, credential-
    shaped file (e.g. ``.env``) inside a declared forbidden path was
    invisible to the git-based scan and returned a clean authority
    verdict. Checking the declared forbidden paths directly against the
    filesystem closes this regardless of whether git would ever track or
    ignore them.

    IV finding (PR #661 review, round 3): a symlink planted under a
    declared forbidden directory could previously point *outside the
    repository entirely* and would be transparently dereferenced by
    ``read_bytes()`` -- correct for detection (the symlink's target
    content changing was still caught), but it meant a task could make
    this audit step read an arbitrary external path with no bound. A
    symlinked *directory* is a further version of the same risk:
    ``Path.rglob()`` follows symlinked directories by default, which
    could walk this audit step into an arbitrarily large or slow
    external tree. Neither a symlinked file nor a symlinked directory is
    ever dereferenced here (``os.walk(..., followlinks=False)`` plus
    explicitly pruning any reparse-point directory out of ``dirnames``
    before the next iteration -- see ``_is_reparse_point()``) -- each is
    fingerprinted by its own link-target text instead, so creating,
    removing, or repointing a symlink under a forbidden path is still
    always a detected change, without this audit step ever opening
    whatever it points to.

    IV finding (PR #661 review, round 4): on Windows, an NTFS junction
    (``mklink /J``, fully unprivileged -- unlike a true Windows symlink,
    no admin rights or Developer Mode required) is a reparse point that
    ``Path.is_symlink()`` does NOT recognize, so ``os.walk(...,
    followlinks=False)`` still descended into one -- reopening exactly
    the external-content resource-exhaustion risk the round-3 fix was
    meant to close, via an ordinary, unprivileged operation. Detection
    now uses ``_is_reparse_point()`` (checks the Windows-only
    ``FILE_ATTRIBUTE_REPARSE_POINT`` bit in addition to
    ``is_symlink()``), which recognizes junctions too.
    """
    snapshot: dict[str, str] = {}
    for entry in forbidden_paths:
        is_dir_prefix = entry.endswith("/")
        base = (repo_root / entry.rstrip("/")).resolve()
        if not base.is_relative_to(repo_root):
            continue  # scope-path validator already rejects traversal; defensive only
        if is_dir_prefix:
            if base.is_dir() and not _is_reparse_point(base):
                for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
                    dirnames.sort()
                    reparse_names = [
                        name for name in dirnames if _is_reparse_point(Path(dirpath) / name)
                    ]
                    for name in reparse_names:
                        _snapshot_symlink(Path(dirpath) / name, repo_root, snapshot)
                    # Prune every reparse-point directory (symlink or
                    # junction) out of dirnames so os.walk never descends
                    # into it on a later iteration -- followlinks=False
                    # alone only stops true symlinks, not junctions.
                    dirnames[:] = [name for name in dirnames if name not in reparse_names]
                    for name in sorted(filenames):
                        _snapshot_leaf(Path(dirpath) / name, repo_root, snapshot)
        elif _is_reparse_point(base):
            _snapshot_symlink(base, repo_root, snapshot)
        elif base.is_file():
            _snapshot_leaf(base, repo_root, snapshot)
    return snapshot


def _is_reparse_point(path: Path) -> bool:
    """True for a POSIX symlink OR a Windows reparse point (NTFS
    junction/mount point included) -- see
    ``_forbidden_path_content_snapshot()``'s round-4 docstring note for
    why ``is_symlink()`` alone is not sufficient on Windows."""
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:
        # getattr(), not direct attribute access: `st_file_attributes` is
        # a Windows-only os.stat_result field, present only conditionally
        # in typeshed's stub across the platforms this repo's CI matrix
        # runs mypy on (ubuntu-latest and windows-latest both run this
        # module's own type check) -- getattr() sidesteps a mypy
        # attr-defined/unused-ignore mismatch between them entirely,
        # while remaining correct at runtime on every platform (the
        # os.name check above already short-circuits before this on
        # POSIX regardless).
        attributes = getattr(path.lstat(), "st_file_attributes", None)
    except OSError:
        return False
    if attributes is None:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _snapshot_symlink(link_path: Path, repo_root: Path, snapshot: dict[str, str]) -> None:
    rel = link_path.relative_to(repo_root).as_posix()
    try:
        target = os.readlink(link_path)
    except OSError:
        target = "<unreadable>"
    snapshot[rel] = f"SYMLINK:{digest_bytes(target.encode('utf-8', 'surrogateescape'))}"


def _snapshot_leaf(file_path: Path, repo_root: Path, snapshot: dict[str, str]) -> None:
    if _is_reparse_point(file_path):
        _snapshot_symlink(file_path, repo_root, snapshot)
        return
    if not file_path.is_file():
        return
    rel = file_path.relative_to(repo_root).as_posix()
    try:
        size = file_path.stat().st_size
        with file_path.open("rb") as handle:
            head = handle.read(_MAX_FORBIDDEN_PATH_HASH_BYTES)
    except OSError:
        snapshot[rel] = "UNREADABLE"
        return
    snapshot[rel] = digest_bytes(head) + f":{size}"


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
    forbidden_before: dict[str, str],
    forbidden_after: dict[str, str],
) -> tuple[AuthorityViolation, ...]:
    violations: dict[str, AuthorityViolation] = {}
    for path in sorted(changed_paths):
        if _matches_scope(path, forbidden_paths):
            violations[path] = AuthorityViolation(path=path, reason="FORBIDDEN_PATH")
            continue
        if authorized_paths and not _matches_scope(path, authorized_paths):
            violations[path] = AuthorityViolation(path=path, reason="OUTSIDE_AUTHORIZED_SCOPE")
    # Filesystem-direct forbidden-path check (independent of git tracking/
    # ignore status -- see _forbidden_path_content_snapshot's docstring):
    # any path added, removed, or content-changed under a declared
    # forbidden_paths entry, whether or not git would ever see it.
    for path in sorted(set(forbidden_before) | set(forbidden_after)):
        if forbidden_before.get(path) != forbidden_after.get(path):
            violations[path] = AuthorityViolation(path=path, reason="FORBIDDEN_PATH")
    return tuple(violations[path] for path in sorted(violations))


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
    forwarded unless a project's own config explicitly names it.

    IV finding (PR #661 review, Copilot): on Windows, environment
    variable names are conventionally case-insensitive (``os.environ``
    itself performs case-insensitive lookups there), but the actual
    casing an ambient variable is *reported* under when iterating
    ``os.environ.items()`` is not guaranteed to match the allowlist's own
    casing (a real, commonly-seen example: ``Path`` rather than ``PATH``)
    -- an exact-string ``in allowed`` membership check could silently
    drop an intended allowlist entry and break the child process's basic
    ability to start. Matching is case-folded on ``nt`` (mirrors
    ``agent_transport.resolve_windows_comspec()``'s own ``SystemRoot``/
    ``SYSTEMROOT`` dual-casing check, generalized to every allowlisted
    name); POSIX platforms keep exact-case matching, since environment
    variable names are genuinely case-sensitive there and folding case
    could incorrectly conflate two distinct real variables."""
    if os.name == "nt":
        allowed_folded = {name.casefold() for name in allowlist}
        env: dict[str, str] = {
            name: value for name, value in os.environ.items() if name.casefold() in allowed_folded
        }
        for name, value in overrides:
            if name.casefold() in allowed_folded:
                env[name] = value
        return env
    allowed = set(allowlist)
    env = {name: value for name, value in os.environ.items() if name in allowed}
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
    never an implicit default-on. Also refuses to run
    (``LocalExecutionError`` / ``WORKTREE_NOT_CLEAN``) if the repository
    already has uncommitted changes before the task starts -- see
    ``_require_clean_worktree()`` for why an ambiguous starting point is
    never silently tolerated. A malformed/missing/non-executable
    ``argv[0]`` fails the same way any other transport failure does
    (``TransportError`` from ``SubprocessProcessRunner``, propagated
    unchanged -- never swallowed into a false "nothing happened").

    Authority enforcement is independent of the process's own report:
    ``changed_paths``/``violations``/``authority_clean`` are derived
    entirely from real filesystem/git state measured before and after the
    run, regardless of ``exit_code`` or anything on stdout/stderr. A
    process that exits 0 and claims success while having touched a
    forbidden path -- including a gitignored one, and including one it
    then committed or re-dirtied on top of -- is still flagged.
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

    _require_clean_worktree(resolved_root)
    # A FIXED commit SHA, captured once before the run and never
    # re-resolved afterward -- the git-based measurement below diffs
    # against this same unmoving baseline even if the launched process
    # itself advances HEAD (e.g. by running `git commit`); see
    # _git_changed_paths's own docstring for the bypass this closes.
    baseline_sha = _current_head_sha(resolved_root)
    # Filesystem-direct snapshot of declared forbidden paths, independent
    # of git tracking/ignore status entirely -- see
    # _forbidden_path_content_snapshot's docstring for the gitignored-file
    # bypass this closes.
    forbidden_before = _forbidden_path_content_snapshot(resolved_root, envelope.forbidden_paths)
    # Existence snapshot of every ignored path (see
    # _ignored_untracked_paths's docstring for the authorized_paths-side
    # gitignored-file bypass this closes).
    ignored_before = _ignored_untracked_paths(resolved_root)
    # Existence snapshot of every ref TIP (see _new_commit_changed_paths's
    # docstring: round-4 walked every reachable commit and diffed each
    # individually, which broke on `git stash -u`'s synthetic orphan
    # parent; round-5 diffs only ref tips, which is both correct and
    # simpler).
    tips_before = _all_ref_tips(resolved_root)

    request = ProcessRunRequest(
        argv=envelope.argv,
        cwd=resolved_cwd,
        timeout_seconds=config.timeout_seconds,
        env=env,
        stdin=None,
    )
    active_runner: ProcessRunner = runner if runner is not None else SubprocessProcessRunner()
    outcome: ProcessRunOutcome = active_runner.run(request)

    new_ignored_paths = _ignored_untracked_paths(resolved_root) - ignored_before
    new_tips = _all_ref_tips(resolved_root) - tips_before
    new_paths = (
        _git_changed_paths(resolved_root, baseline_sha=baseline_sha)
        | _new_commit_changed_paths(resolved_root, baseline_sha=baseline_sha, new_tips=new_tips)
        | new_ignored_paths
    )
    forbidden_after = _forbidden_path_content_snapshot(resolved_root, envelope.forbidden_paths)
    violations = _enforce_authority(
        new_paths,
        authorized_paths=envelope.authorized_paths,
        forbidden_paths=envelope.forbidden_paths,
        forbidden_before=forbidden_before,
        forbidden_after=forbidden_after,
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
