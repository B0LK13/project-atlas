"""Live git observation for the execution identity (ULT-01b-1).

Observes, in this order, and refuses at the first failure without writing
anything:

1. ``git --version`` (the tool that will be trusted for everything below);
2. the root is inside a work tree and **is** its top level (a subdirectory
   would describe the wrong object);
3. shallow-ness (recorded, not refused);
4. ``git status --porcelain`` must be empty — a candidate pair observed on a
   dirty tree would name an object that did not run
   (``DIRTY_WORKTREE != VALID_CANDIDATE_OBSERVATION``);
5. ``HEAD``, ``HEAD^{tree}``, ``<base_ref>``, ``<base_ref>^{tree}`` — each a
   40-hex lowercase pin, validated with the existing ``require_full_pin``;
6. the remote URL, normalized with the existing
   ``normalize_repository_identity`` — the raw URL is never persisted, logged
   or placed in an error, because it may embed a credential.

Configuration chooses *what* to observe (``base_ref``, ``remote_name``) and
is recorded in the receipt as configuration; it never supplies a value.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from atlas_contracts.observation_receipt import GIT_REF_PATTERN, REMOTE_NAME_PATTERN
from project_atlas.execution_observation.runner import (
    DEFAULT_TIMEOUT_SECONDS,
    CommandRunner,
    ObservationError,
)
from project_atlas.orchestration.autonomy.trust import (
    TrustError,
    normalize_repository_identity,
    require_full_pin,
)

DEFAULT_BASE_REF: Final[str] = "origin/main"
DEFAULT_REMOTE_NAME: Final[str] = "origin"
_REF_RE: Final[re.Pattern[str]] = re.compile(GIT_REF_PATTERN)
_REMOTE_RE: Final[re.Pattern[str]] = re.compile(REMOTE_NAME_PATTERN)
_VERSION_RE: Final[re.Pattern[str]] = re.compile(
    r"^git version (\d+(?:\.\d+)+(?:[.\-][A-Za-z0-9.\-]+)?)$"
)
_BOOL: Final[dict[str, bool]] = {"true": True, "false": False}


@dataclass(frozen=True)
class GitObservation:
    repository: str
    base_ref: str
    remote_name: str
    base_head: str
    base_tree: str
    candidate_head: str
    candidate_tree: str
    git_version: str | None
    shallow: bool
    worktree_clean: bool
    executable_path_digest: str
    method_refs: tuple[str, ...]


def validate_base_ref(base_ref: str) -> str:
    if not isinstance(base_ref, str) or not _REF_RE.fullmatch(base_ref) or ".." in base_ref:
        raise ObservationError("BASE_REF_INVALID", "base ref must be a plain git ref name")
    return base_ref


def validate_remote_name(remote_name: str) -> str:
    if not isinstance(remote_name, str) or not _REMOTE_RE.fullmatch(remote_name):
        raise ObservationError("REMOTE_NAME_INVALID", "remote name must be an identifier")
    return remote_name


def derive_remote_name(base_ref: str, remote_name: str | None) -> str:
    if remote_name is not None:
        return validate_remote_name(remote_name)
    head, sep, _ = base_ref.partition("/")
    return validate_remote_name(head) if sep else DEFAULT_REMOTE_NAME


class _Git:
    def __init__(self, runner: CommandRunner, git: Path, root: Path, timeout: float) -> None:
        self._runner = runner
        self._git = str(git)
        self._root = root
        self._timeout = timeout
        self.method_refs: list[str] = []

    def run(self, args: Sequence[str], *, ref: str, code: str) -> str:
        self.method_refs.append(ref)
        result = self._runner.run(
            [self._git, "-C", str(self._root), *args], cwd=self._root, timeout=self._timeout
        )
        if result.timed_out:
            raise ObservationError("GIT_OBSERVATION_TIMEOUT", f"{ref}: timed out")
        if result.returncode != 0:
            raise ObservationError(code, f"{ref}: git exited {result.returncode}")
        return result.stdout.strip()

    def pin(self, spec: str, *, ref: str) -> str:
        out = self.run(
            ["rev-parse", "--verify", "--end-of-options", spec],
            ref=ref,
            code="GIT_PIN_UNOBSERVABLE",
        )
        try:
            return require_full_pin(out, ref)
        except TrustError as exc:
            raise ObservationError(
                "PIN_INVALID", f"{ref}: not a 40-char lowercase git SHA"
            ) from exc


def _resolve_root(repo_root: Path | str) -> Path:
    try:
        root = Path(repo_root).expanduser().resolve(strict=True)
    except OSError as exc:
        raise ObservationError("GIT_UNOBSERVABLE", "repository root does not exist") from exc
    if not root.is_dir() or not (root / ".git").exists():
        raise ObservationError("GIT_UNOBSERVABLE", "repository root is not a git work tree")
    return root


def _normalize_remote(raw_url: str) -> str:
    """Normalize without ever echoing the raw URL. Only the bare ``git@`` user is tolerated."""
    url = raw_url.strip()
    if not url or "\n" in url or "\x00" in url:
        raise ObservationError("REPO_IDENTITY_UNVERIFIABLE", "remote url unobservable")
    if "@" in url:
        # scp form git@host:owner/name is handled by the shared normalizer;
        # ssh://git@host/owner/name loses its bare user here; any other
        # userinfo (a token, a user:password) is refused outright.
        scheme, sep, rest = url.partition("://")
        body = rest if sep else url
        user, at, tail = body.partition("@")
        if not at or user != "git" or "@" in tail:
            raise ObservationError(
                "REPO_IDENTITY_UNVERIFIABLE", "remote url carries userinfo; refusing to record it"
            )
        if sep:
            url = f"{scheme}://{tail}"
    try:
        return normalize_repository_identity(url)
    except TrustError as exc:
        raise ObservationError(
            "REPO_IDENTITY_UNVERIFIABLE", "remote url did not normalize to a repository identity"
        ) from exc


def observe_git(
    repo_root: Path | str,
    *,
    runner: CommandRunner,
    git: Path,
    base_ref: str = DEFAULT_BASE_REF,
    remote_name: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> GitObservation:
    base = validate_base_ref(base_ref)
    remote = derive_remote_name(base, remote_name)
    root = _resolve_root(repo_root)
    g = _Git(runner, git, root, timeout)

    version_out = g.run(["--version"], ref="git --version", code="GIT_UNOBSERVABLE")
    match = _VERSION_RE.match(version_out)
    git_version = match.group(1) if match else None

    inside = g.run(
        ["rev-parse", "--is-inside-work-tree"],
        ref="git rev-parse --is-inside-work-tree",
        code="GIT_UNOBSERVABLE",
    )
    if inside != "true":
        raise ObservationError("GIT_UNOBSERVABLE", "root is not inside a git work tree")
    toplevel = g.run(
        ["rev-parse", "--show-toplevel"],
        ref="git rev-parse --show-toplevel",
        code="GIT_UNOBSERVABLE",
    )
    try:
        if Path(toplevel).resolve(strict=True) != root:
            raise ObservationError("GIT_ROOT_MISMATCH", "root is not the work tree top level")
    except OSError as exc:
        raise ObservationError("GIT_ROOT_MISMATCH", "work tree top level unresolvable") from exc

    shallow_out = g.run(
        ["rev-parse", "--is-shallow-repository"],
        ref="git rev-parse --is-shallow-repository",
        code="GIT_UNOBSERVABLE",
    )
    if shallow_out not in _BOOL:
        raise ObservationError("GIT_UNOBSERVABLE", "shallow state unobservable")
    shallow = _BOOL[shallow_out]

    status = g.run(
        ["--no-optional-locks", "status", "--porcelain", "--untracked-files=all"],
        ref="git status --porcelain --untracked-files=all",
        code="GIT_UNOBSERVABLE",
    )
    if status:
        raise ObservationError(
            "WORKTREE_NOT_CLEAN", "worktree has uncommitted or untracked changes; no candidate"
        )

    candidate_head = g.pin("HEAD^{commit}", ref="git rev-parse HEAD^{commit}")
    candidate_tree = g.pin("HEAD^{tree}", ref="git rev-parse HEAD^{tree}")
    try:
        base_head = g.pin(f"{base}^{{commit}}", ref=f"git rev-parse {base}^{{commit}}")
        base_tree = g.pin(f"{base}^{{tree}}", ref=f"git rev-parse {base}^{{tree}}")
    except ObservationError as exc:
        if exc.code == "GIT_PIN_UNOBSERVABLE":
            raise ObservationError(
                "BASE_REF_UNOBSERVABLE", "base ref is not resolvable in this repository"
            ) from exc
        raise

    remote_url = g.run(
        ["remote", "get-url", remote],
        ref=f"git remote get-url {remote}",
        code="REPO_IDENTITY_UNVERIFIABLE",
    )
    repository = _normalize_remote(remote_url)

    return GitObservation(
        repository=repository,
        base_ref=base,
        remote_name=remote,
        base_head=base_head,
        base_tree=base_tree,
        candidate_head=candidate_head,
        candidate_tree=candidate_tree,
        git_version=git_version,
        shallow=shallow,
        worktree_clean=True,
        executable_path_digest=hashlib.sha256(str(git).encode("utf-8")).hexdigest(),
        method_refs=tuple(g.method_refs),
    )


__all__ = [
    "DEFAULT_BASE_REF",
    "DEFAULT_REMOTE_NAME",
    "GitObservation",
    "derive_remote_name",
    "observe_git",
    "validate_base_ref",
    "validate_remote_name",
]
