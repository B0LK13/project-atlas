"""Atlas 3 must not rewrite certified demo / 2.x surfaces."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Every git subprocess call in this module is bounded. A hung git process
# (most plausibly the network-dependent fetch, e.g. a credential prompt
# that never resolves, or an unusual server-side negotiation) must fail
# loudly within a bounded time, never silently consume an entire hosted
# CI job's runtime -- discovered the hard way when an untimed `git fetch`
# call left a real hosted CI run "in_progress" for over an hour.
_LOCAL_GIT_TIMEOUT_SECONDS = 30
_NETWORK_GIT_TIMEOUT_SECONDS = 60

DENY = (
    "src/project_atlas/chatgpt_bridge.py",
    "src/project_atlas/chatgpt_capture.py",
    "src/project_atlas/knowledge_compiler.py",
    "src/project_atlas/api_server.py",
    "src/project_atlas/authz.py",
    "src/project_atlas/discovery.py",
    "src/project_atlas/ingestion.py",
    "src/project_atlas/compat_anchor.py",
    "src/project_atlas/conflict_projections.py",
    "src/project_atlas/reality_gap.py",
    "src/project_atlas/bitemporal.py",
    "src/project_atlas/conversation_capture.py",
)

# Owner-approved narrow exceptions to the freeze above (SS9.1 of
# docs/atlas-3/ARCHITECTURE.md). This is NOT a path allowlist: each entry
# is pinned to the *exact*, reviewed content of one file by sha256. Any
# further edit -- even one byte, even by the same PR -- changes the hash
# and the guard fires again for that path. An exception never widens to
# cover a different path, a different diff, or a later PR; there is no
# generic "this file is now unfrozen" mechanism here, only ever a specific
# reviewed byte sequence for a specific, named, owner-approved reason.
#
# Do not add an entry here without an explicit owner grant recorded in
# WORKLOG.md; do not extend an existing entry's scope beyond its recorded
# reason; do not use this mechanism to work around a failing guard on an
# unreviewed change.
_OWNER_APPROVED_EXCEPTIONS: tuple[dict[str, str], ...] = (
    {
        "exception_id": "DOGFOOD-001",
        "owner_approved": "YES",
        "reason": "authentic first-run P1 source-safety remediation (PR #656)",
        "path": "src/project_atlas/ingestion.py",
        "allowed_sha256": (
            "e8d779a8ab2fe0b4327ae9cf8cae115f2a793eb96eb35e8b0024b6ee085168ef"
        ),
    },
    {
        "exception_id": "R-READY-LINUX-RESIDUALS-20260905-DISCOVERY",
        "owner_approved": "YES",
        "reason": (
            "owner grant R_READY (supersedes the discovery.py pin of "
            "OG-ATLAS-LINUX-FILESYSTEM-20260905): verified residuals R1 "
            "canonical-equivalence collision, R2 unreadable metadata "
            "boundary, R3 silent loss of inaccessible discovery scope, plus "
            "the post-verification remediation (unmeasurable-path skip now "
            "observable; ordering key made total for NFR-001 determinism), and "
            "owner grant R_READY-2 residual R4 (a real document in the "
            "reserved agent-event routing scope reached neither inventory "
            "and produced no diagnostic), including R4-D (a real document, or a "
            "whole subtree behind a directory symlink, escaping the source "
            "root was excluded without any diagnostic), and owner grant "
            "R_READY-5 residual R5 (an unreadable scope under the agent-event "
            "inbox aborted the entire discovery run), and owner grant "
            "OG-ATLAS-DISCOVERY-M1M2-20260906 (directive "
            "D-UBUNTU-AUTONOMOUS-PR683-INTEGRATE-AND-SUCCESSOR-EXECUTION) "
            "residual M1 (five main-walk OSError guards caught every errno, "
            "so an injected EIO was skipped with exit 0 or recorded as an "
            "'unreadable' source; every guard now filters through the "
            "module's stated inaccessible-scope errno contract) and residual "
            "M2 (the event inventory followed symbolic links on the chain to "
            "a package while the walk did not, so an aliased scope was "
            "inventoried twice or silently not at all; links are now refused "
            "on physical identity, reported, and a linked event directory is "
            "recorded as an invalid row), plus the IV remediation (ENAMETOOLONG "
            "joins the inaccessible-scope set: a tree grown past PATH_MAX is "
            "one unaddressable path, not a fault) and the review remediation "
            "(the event-scope chain is tested before any probe that would "
            "follow it, so an escaping link is refused without a metadata "
            "probe through it and a dangling or file-targeted scope link is "
            "named rather than dropped as 'no scope')"
        ),
        "path": "src/project_atlas/discovery.py",
        "allowed_sha256": (
            "471a56af7fcb45220f7c18b5b96efeb32acf7460489c2e9e7525eeec0a429f35"
        ),
    },
    {
        "exception_id": "OG-ATLAS-LINUX-FILESYSTEM-20260905-INGESTION",
        "owner_approved": "YES",
        "reason": (
            "owner grant OG-ATLAS-LINUX-FILESYSTEM-20260905: excluded records "
            "are no longer pre-resolved at the manifest boundary, and a "
            "symlinked authorized root now names its physical path"
        ),
        "path": "src/project_atlas/ingestion.py",
        "allowed_sha256": (
            "6911a99d2c5127a45f29d55888fb2398270749dcfd6c49da3d0626a106d74159"
        ),
    },
)


def _owner_approved_exception_permits(
    path: str, *, root: Path, exceptions: tuple[dict[str, str], ...] = _OWNER_APPROVED_EXCEPTIONS
) -> bool:
    """True only if an owner-approved exception names `path` AND the file's
    *current* content at `root` matches that exception's pinned, exact
    reviewed sha256. Anything else -- a different path, a missing file, a
    hash mismatch from ANY further edit -- returns False, and the caller
    treats `path` as a real, unexcepted violation."""
    target = root / path
    if not target.is_file():
        return False
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return any(
        exc.get("path") == path
        and exc.get("owner_approved") == "YES"
        and digest == exc.get("allowed_sha256")
        for exc in exceptions
    )


class DemoIsolationGuardError(RuntimeError):
    """Fail-closed: the certified-surface freeze guard could not determine
    its comparison base. An inconclusive result must fail visibly, never
    be silently treated as "no changes" -- that would turn the guard into
    a no-op exactly when it matters most.
    """


class DemoIsolationGuardNotApplicable(Exception):
    """Distinct from ``DemoIsolationGuardError``: there is no comparison
    base to even attempt (no CI pull_request/push event context, and no
    git remote configured at all -- e.g. a source archive, vendored
    copy, or a checkout with remotes deliberately stripped). This is not
    a failure to enforce something real; there is nothing to enforce
    here. Callers should skip, not fail and not silently pass.
    """


def _has_any_remote(*, root: Path) -> bool:
    result = subprocess.run(
        ["git", "remote"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def _event_pull_request_shas(
    *, env: Mapping[str, str] | None = None
) -> tuple[str, str] | None:
    """Read the authoritative base/head commit SHAs for this PR directly
    from the GitHub Actions ``pull_request`` event payload.

    This is independent of local checkout depth or which refs happen to
    be fetched -- it comes from GitHub's own event metadata (the API's
    view of the PR), not from resolving a branch name like ``origin/main``
    against whatever the local clone happens to contain. Returns ``None``
    only when we are demonstrably not running in a GitHub Actions
    ``pull_request`` context (i.e. ``GITHUB_EVENT_NAME`` is unset or is
    something else, such as a local run or a ``push`` trigger) -- in that
    case the caller falls back to local/full-clone behavior. If
    ``GITHUB_EVENT_NAME=pull_request`` but the payload cannot actually be
    read, this raises rather than returning ``None``, so a broken/missing
    event file cannot be silently treated the same as "not in CI".
    """
    env = os.environ if env is None else env
    if env.get("GITHUB_EVENT_NAME") != "pull_request":
        return None
    event_path = env.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise DemoIsolationGuardError(
            "GITHUB_EVENT_NAME=pull_request but GITHUB_EVENT_PATH is unset "
            "-- cannot determine the PR's actual base/head commits"
        )
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        base_sha = payload["pull_request"]["base"]["sha"]
        head_sha = payload["pull_request"]["head"]["sha"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DemoIsolationGuardError(
            f"could not read pull_request base/head sha from "
            f"GITHUB_EVENT_PATH ({event_path}): {exc}"
        ) from exc
    if (
        not isinstance(base_sha, str)
        or not isinstance(head_sha, str)
        or not base_sha
        or not head_sha
    ):
        raise DemoIsolationGuardError(
            "pull_request base/head sha missing or malformed in event payload"
        )
    return base_sha, head_sha


def _event_push_before_sha(*, env: Mapping[str, str] | None = None) -> str | None:
    """Read the authoritative pre-push commit SHA (``before``) directly
    from the GitHub Actions ``push`` event payload.

    This repository's own ``ci.yml`` triggers the same ``quality`` job
    (which runs this guard) on both ``pull_request`` and ``push:
    branches: [main]``. The ``pull_request`` case is covered by
    ``_event_pull_request_shas``; this covers the other real hosted-CI
    trigger this guard actually runs under, so a shallow-clone push run
    cannot silently no-op the same way the original ``pull_request``-only
    fix would have left it. Returns ``None`` only when demonstrably not
    running in a GitHub Actions ``push`` context. Raises, rather than
    returning ``None``, if that context is claimed but the payload cannot
    actually be read -- same fail-closed contract as the PR-event reader.
    """
    env = os.environ if env is None else env
    if env.get("GITHUB_EVENT_NAME") != "push":
        return None
    event_path = env.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise DemoIsolationGuardError(
            "GITHUB_EVENT_NAME=push but GITHUB_EVENT_PATH is unset -- "
            "cannot determine the pre-push commit"
        )
    try:
        payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        before_sha = payload["before"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise DemoIsolationGuardError(
            f"could not read push 'before' sha from GITHUB_EVENT_PATH "
            f"({event_path}): {exc}"
        ) from exc
    if not isinstance(before_sha, str) or not before_sha:
        raise DemoIsolationGuardError("push 'before' sha missing or malformed in event payload")
    # GitHub uses an all-zero SHA for `before` on a branch's first-ever
    # push (nothing to diff against). Treat that the same as "not
    # resolvable" -- fail closed rather than attempt to fetch/diff a
    # sentinel that was never a real commit.
    if before_sha == "0" * 40:
        raise DemoIsolationGuardError(
            "push event 'before' sha is the all-zero first-push sentinel "
            "-- no real prior commit exists to diff against"
        )
    return before_sha


def _ensure_commit_fetched(sha: str, *, root: Path) -> None:
    """Make ``sha`` resolvable in the local object database, fetching it
    directly by SHA if a shallow checkout did not already include it.
    Raises if the fetch itself fails, is refused, or does not complete
    within a bounded time -- a comparison base that cannot be obtained
    must not be silently skipped, and must never be allowed to hang the
    calling process indefinitely.
    """
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    if probe.returncode == 0:
        return
    try:
        fetch = subprocess.run(
            ["git", "fetch", "--depth=1", "origin", sha],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=_NETWORK_GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise DemoIsolationGuardError(
            f"fetching commit {sha} for the freeze-guard comparison did "
            f"not complete within {_NETWORK_GIT_TIMEOUT_SECONDS}s -- "
            "treating as a fetch failure rather than hanging"
        ) from exc
    if fetch.returncode != 0:
        raise DemoIsolationGuardError(
            f"could not fetch commit {sha} needed for the freeze-guard "
            f"comparison: {fetch.stderr.strip()}"
        )


def _resolve_diff_base_and_mode(
    *, root: Path = ROOT, env: Mapping[str, str] | None = None
) -> tuple[str, bool]:
    """Return ``(sha, exact)`` -- the commit SHA the freeze guard must diff
    HEAD against, and whether that SHA is an *exact* changeset endpoint
    (``True``: a GitHub event's own base/before SHA, safe to diff directly
    against) or a *floating local fallback* (``False``: ``origin/main``
    resolved outside any CI event context, which can independently advance
    out from under a local branch and must be diffed via its merge-base
    with HEAD instead, or an unrelated upstream change to a DENY-listed
    path would false-positive as though the local branch itself made it).

    Prefers the authoritative GitHub ``pull_request`` event base SHA, then
    the ``push`` event's pre-push SHA (both exact, both correct under any
    checkout depth including the hosted CI default of a single-commit
    shallow fetch). Falls back to ``origin/main`` for local/full-clone use,
    but only when a git remote is actually configured at all -- raises
    ``DemoIsolationGuardNotApplicable`` (not ``DemoIsolationGuardError``)
    when neither a recognized CI event context nor any remote exists,
    since a source archive, vendored copy, or a checkout with remotes
    deliberately stripped was never a context this guard could
    meaningfully enforce against; callers should skip in that case, not
    fail closed. When a remote *is* configured but ``origin/main``
    specifically cannot be resolved, that is a genuine failure and still
    raises ``DemoIsolationGuardError`` -- never silently treat an
    unresolvable base as "nothing changed".
    """
    pr_shas = _event_pull_request_shas(env=env)
    if pr_shas is not None:
        base_sha, _head_sha = pr_shas
        _ensure_commit_fetched(base_sha, root=root)
        return base_sha, True
    push_before = _event_push_before_sha(env=env)
    if push_before is not None:
        _ensure_commit_fetched(push_before, root=root)
        return push_before, True
    if not _has_any_remote(root=root):
        raise DemoIsolationGuardNotApplicable(
            "not running in a GitHub Actions pull_request or push context, "
            "and no git remote is configured at all -- nothing to compare "
            "against (e.g. a source archive or vendored checkout); the "
            "freeze guard does not apply here"
        )
    resolve = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    if resolve.returncode != 0:
        raise DemoIsolationGuardError(
            "a git remote is configured but origin/main is not resolvable "
            "locally, and no pull_request/push CI event context is present "
            "-- cannot determine the freeze-guard comparison base (this "
            "must fail, not pass)"
        )
    return resolve.stdout.strip(), False


def _resolve_diff_base(*, root: Path = ROOT, env: Mapping[str, str] | None = None) -> str:
    """Return just the resolved comparison SHA (see
    ``_resolve_diff_base_and_mode`` for the full contract, including the
    exact-vs-floating-fallback distinction that ``_changed_paths`` needs
    and this wrapper deliberately discards for callers that only want the
    commit itself, e.g. ``test_cli_mutation_is_additive_only``'s own
    direct diff against ``cli.py``)."""
    sha, _exact = _resolve_diff_base_and_mode(root=root, env=env)
    return sha


def _changed_paths(*, root: Path = ROOT, env: Mapping[str, str] | None = None) -> set[str]:
    """Return every path changed relative to the resolved diff base, plus
    any uncommitted worktree/staged changes. Fails closed (raises via
    ``_resolve_diff_base_and_mode``) if the comparison base cannot be
    determined -- never silently returns an empty/inconclusive result as
    if nothing changed.
    """
    base, exact = _resolve_diff_base_and_mode(root=root, env=env)
    if exact:
        # Direct two-endpoint diff, not three-dot merge-base diff: `base`
        # is an exact PR/push-event SHA, and computing a merge-base can
        # fail outright under a shallow/disconnected fetch (no shared
        # history graph) even though both endpoints are individually
        # resolvable. A direct diff needs only the two commits' trees, not
        # their ancestry, and is exactly correct here since `base` is
        # already the changeset's real prior commit, not a possibly-
        # since-moved branch tip.
        diff_base = base
    else:
        # `base` is the floating local-fallback `origin/main`, resolved
        # outside any CI event context (full clone required -- property 7
        # -- so a merge-base computation is safe and expected to succeed
        # here, unlike in the shallow exact-SHA case above). A direct diff
        # against the live `origin/main` tip would false-positive on any
        # DENY-listed path main has independently advanced since this
        # branch last rebased/merged, flagging it as though the local
        # branch itself touched it. Diffing against the merge-base instead
        # (equivalent to a three-dot diff) isolates exactly the local
        # branch's own changes, which is what this guard is actually
        # supposed to enforce.
        merge_base = subprocess.run(
            ["git", "merge-base", base, "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
        )
        if merge_base.returncode != 0:
            raise DemoIsolationGuardError(
                f"could not compute a merge-base between {base} and HEAD "
                f"for the local-fallback freeze-guard comparison: "
                f"{merge_base.stderr.strip()}"
            )
        diff_base = merge_base.stdout.strip()
    committed = subprocess.run(
        ["git", "diff", "--name-only", diff_base, "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    worktree = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    staged = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    names = "\n".join([committed.stdout, worktree.stdout, staged.stdout])
    return {line.strip() for line in names.splitlines() if line.strip()}


def test_certified_surfaces_unmodified() -> None:
    try:
        changed = _changed_paths()
    except DemoIsolationGuardNotApplicable as exc:
        pytest.skip(str(exc))
    violated = sorted(
        path
        for path in DENY
        if path in changed and not _owner_approved_exception_permits(path, root=ROOT)
    )
    assert violated == []


#: Owner-approved exceptions to the *Atlas-3 hook* requirement below, pinned
#: the same way `_OWNER_APPROVED_EXCEPTIONS` is: to one exact reviewed
#: sha256 of `cli.py`, never to the path in general. The guard's purpose is
#: to stop the Atlas 3 lane rewriting certified 2.x CLI surfaces, and it
#: expresses that by demanding the diff be the two additive Atlas-3
#: registration hooks. A change that is genuinely not an Atlas 3 change --
#: and must not touch that seam -- cannot satisfy that shape, so it needs an
#: explicit owner grant rather than a weakened guard.
#:
#: What an entry here waives is ONLY the "diff must be the Atlas-3 hooks"
#: assertions. Additive-only and command-integrity stay enforced for every
#: change, excepted or not.
_CLI_ADDITIVE_EXCEPTIONS: tuple[dict[str, str], ...] = (
    {
        "exception_id": "OG-ATLAS-CLI-LOGFORMAT-BOOTSTRAP-20260906",
        "owner_approved": "YES",
        "reason": (
            "owner grant OG-ATLAS-CLI-LOGFORMAT-BOOTSTRAP-20260906: an "
            "explicitly requested --log-format must govern every record the "
            "process emits. Modules configure logging with the console "
            "default at import, so applying the flag only after load_config "
            "left that bootstrap record in console format and a "
            "JSON-consuming deployment received an unparseable stream. The "
            "diff is one guarded configure_logging call after parse_args; no "
            "Atlas-3 seam change, no command added, renamed or removed"
        ),
        "path": "src/project_atlas/cli.py",
        "allowed_sha256": (
            "752eb7f346814d1064faf7502f6fc55f4e47bc738c5bda24f5396bf63bfa8550"
        ),
    },
)


#: Commands whose registration must survive every cli.py diff, waived or not.
_CERTIFIED_COMMANDS = ("connect", "ask2", "kdiff", "brief", "capture")


def _cli_guard_violations(
    *, diff_text: str, cli_source: str, atlas3_hooks_waived: bool
) -> list[str]:
    """The guard's decision, as a pure function of its inputs.

    Extracted so the waiver can be proven narrow by *running* the guard
    against synthetic candidate diffs, rather than by reading its source and
    asserting the arrangement looks right. A waiver that silently stopped
    blocking a command deletion would pass a source-shape assertion and fail
    the mutation cases below.

    Returns the violations found; empty means the diff is permitted.
    """
    violations: list[str] = []
    lines = diff_text.splitlines()
    added = [line for line in lines if line.startswith("+") and not line.startswith("+++")]
    removed = [line for line in lines if line.startswith("-") and not line.startswith("---")]

    # Never waivable: a certified CLI surface may only grow.
    if removed:
        violations.append("deletion-from-certified-cli-surface")

    # Waivable by an owner grant pinned to exact reviewed bytes: the demand
    # that the diff *be* the two additive Atlas-3 registration hooks. A change
    # that is deliberately not an Atlas 3 change cannot satisfy that shape.
    if not atlas3_hooks_waived:
        if "register_atlas3_parsers" not in diff_text:
            violations.append("missing-atlas3-register-hook")
        if "dispatch_atlas3" not in diff_text:
            violations.append("missing-atlas3-dispatch-hook")
        if not any("register_atlas3_parsers" in line for line in added):
            violations.append("no-added-atlas3-registration")

    # Never waivable: every certified command must still be registered.
    for command in _CERTIFIED_COMMANDS:
        if f'"{command}"' not in cli_source and f"'{command}'" not in cli_source:
            violations.append(f"certified-command-missing:{command}")
    return violations


def test_cli_mutation_is_additive_only() -> None:
    try:
        already_changed = _changed_paths()
    except DemoIsolationGuardNotApplicable as exc:
        pytest.skip(str(exc))
    if "src/project_atlas/cli.py" not in already_changed:
        return
    atlas3_hooks_waived = _owner_approved_exception_permits(
        "src/project_atlas/cli.py", root=ROOT, exceptions=_CLI_ADDITIVE_EXCEPTIONS
    )
    base = _resolve_diff_base()
    diff = subprocess.run(
        ["git", "diff", base, "--", "src/project_atlas/cli.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    violations = _cli_guard_violations(
        diff_text=diff.stdout,
        cli_source=(ROOT / "src" / "project_atlas" / "cli.py").read_text(encoding="utf-8"),
        atlas3_hooks_waived=atlas3_hooks_waived,
    )
    assert violations == []


# ---------------------------------------------------------------------------
# Owner-approved exceptions must be narrow: pinned to one exact reviewed
# byte sequence, never a path allowlist, never transferable to another
# path or another diff. These use a throwaway `_owner_approved_exception_permits`
# call with a synthetic exceptions tuple (never the real
# `_OWNER_APPROVED_EXCEPTIONS`), so they stay valid regardless of what
# `ingestion.py` legitimately contains after DOGFOOD-001 lands or after
# `FULL_LIVE_DEMO_READY` eventually lifts the freeze entirely.
# ---------------------------------------------------------------------------


def test_exception_permits_only_the_exact_pinned_content(tmp_path: Path) -> None:
    target = tmp_path / "src" / "project_atlas" / "ingestion.py"
    target.parent.mkdir(parents=True)
    approved_content = b"# approved DOGFOOD-001 content\n"
    target.write_bytes(approved_content)
    exceptions = (
        {
            "exception_id": "DOGFOOD-001",
            "owner_approved": "YES",
            "reason": "test fixture",
            "path": "src/project_atlas/ingestion.py",
            "allowed_sha256": hashlib.sha256(approved_content).hexdigest(),
        },
    )

    assert _owner_approved_exception_permits(
        "src/project_atlas/ingestion.py", root=tmp_path, exceptions=exceptions
    )


def test_exception_does_not_survive_any_further_edit(tmp_path: Path) -> None:
    """A future PR touching ingestion.py must not automatically inherit
    DOGFOOD-001 permission -- not even by one byte."""
    target = tmp_path / "src" / "project_atlas" / "ingestion.py"
    target.parent.mkdir(parents=True)
    approved_content = b"# approved DOGFOOD-001 content\n"
    exceptions = (
        {
            "exception_id": "DOGFOOD-001",
            "owner_approved": "YES",
            "reason": "test fixture",
            "path": "src/project_atlas/ingestion.py",
            "allowed_sha256": hashlib.sha256(approved_content).hexdigest(),
        },
    )
    target.write_bytes(approved_content + b"# one more unreviewed line\n")

    assert not _owner_approved_exception_permits(
        "src/project_atlas/ingestion.py", root=tmp_path, exceptions=exceptions
    )


def test_exception_does_not_cover_a_different_deny_listed_path(tmp_path: Path) -> None:
    """An exception for ingestion.py must not blanket-permit any other
    DENY-listed surface, even an untouched, byte-identical one."""
    approved_content = b"# approved DOGFOOD-001 content\n"
    ingestion = tmp_path / "src" / "project_atlas" / "ingestion.py"
    ingestion.parent.mkdir(parents=True)
    ingestion.write_bytes(approved_content)
    other = tmp_path / "src" / "project_atlas" / "discovery.py"
    other.write_bytes(approved_content)  # byte-identical content, different path
    exceptions = (
        {
            "exception_id": "DOGFOOD-001",
            "owner_approved": "YES",
            "reason": "test fixture",
            "path": "src/project_atlas/ingestion.py",
            "allowed_sha256": hashlib.sha256(approved_content).hexdigest(),
        },
    )

    assert _owner_approved_exception_permits(
        "src/project_atlas/ingestion.py", root=tmp_path, exceptions=exceptions
    )
    assert not _owner_approved_exception_permits(
        "src/project_atlas/discovery.py", root=tmp_path, exceptions=exceptions
    )


def test_exception_without_owner_approval_flag_permits_nothing(tmp_path: Path) -> None:
    """A registry entry missing the explicit owner_approved=YES marker must
    never be treated as a live exception -- guards against a future entry
    being added with the grant recorded elsewhere (or not at all)."""
    approved_content = b"# content\n"
    target = tmp_path / "src" / "project_atlas" / "ingestion.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(approved_content)
    exceptions = (
        {
            "exception_id": "UNAPPROVED",
            "reason": "no owner sign-off recorded",
            "path": "src/project_atlas/ingestion.py",
            "allowed_sha256": hashlib.sha256(approved_content).hexdigest(),
        },
    )

    assert not _owner_approved_exception_permits(
        "src/project_atlas/ingestion.py", root=tmp_path, exceptions=exceptions
    )


def test_real_dogfood_001_exception_is_currently_live_or_absent_honestly() -> None:
    """Sanity check against the real registry and the real checkout: either
    the pinned hash matches the file currently on disk (the exception is
    live), or it doesn't (the exception is inert and the guard is fully
    load-bearing for ingestion.py again) -- never an exception mechanically
    incapable of ever matching anything (e.g. an empty/placeholder hash)."""
    assert len(_OWNER_APPROVED_EXCEPTIONS) >= 1
    for exc in _OWNER_APPROVED_EXCEPTIONS:
        assert exc["owner_approved"] == "YES"
        assert exc["exception_id"]
        assert exc["reason"]
        assert exc["path"] in DENY, "an exception must name a real DENY-listed path"
        assert len(exc["allowed_sha256"]) == 64
        int(exc["allowed_sha256"], 16)  # must be real hex, not a placeholder


def test_end_to_end_exception_gate_via_pr_event_shas(tmp_path: Path) -> None:
    """Exercises the real `_changed_paths` + exception-gate combination
    (mirroring `test_certified_surfaces_unmodified`'s own logic) against a
    synthetic PR event, on a throwaway repo -- never the real checkout."""
    repo = _init_fixture_repo(tmp_path)
    base_sha = _run_git(["rev-parse", "HEAD"], cwd=repo).strip()
    ingestion = repo / "src" / "project_atlas" / "ingestion.py"
    ingestion.parent.mkdir(parents=True)
    approved_content = b"# reviewed DOGFOOD-001-shaped change\n"
    ingestion.write_bytes(approved_content)
    _run_git(["add", "-A"], cwd=repo)
    _run_git(["commit", "-q", "-m", "dogfood-001-shaped change"], cwd=repo)
    head_sha = _run_git(["rev-parse", "HEAD"], cwd=repo).strip()
    event_path = _write_event_payload(tmp_path, base_sha=base_sha, head_sha=head_sha)
    env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_path)}
    exceptions = (
        {
            "exception_id": "DOGFOOD-001",
            "owner_approved": "YES",
            "reason": "test fixture",
            "path": "src/project_atlas/ingestion.py",
            "allowed_sha256": hashlib.sha256(approved_content).hexdigest(),
        },
    )

    changed = _changed_paths(root=repo, env=env)
    assert "src/project_atlas/ingestion.py" in changed

    # With the matching exception: not a violation.
    violated_with_exception = sorted(
        path
        for path in DENY
        if path in changed
        and not _owner_approved_exception_permits(path, root=repo, exceptions=exceptions)
    )
    assert violated_with_exception == []

    # With no exception at all: a real, unexcepted violation.
    violated_without_exception = sorted(
        path
        for path in DENY
        if path in changed and not _owner_approved_exception_permits(path, root=repo, exceptions=())
    )
    assert violated_without_exception == ["src/project_atlas/ingestion.py"]

    # Same content, but the exception is pinned to different bytes (as if
    # someone edited the file after review, or copied the exception onto a
    # different unreviewed change): a real, unexcepted violation again.
    stale_exceptions = (
        {**exceptions[0], "allowed_sha256": hashlib.sha256(b"different content\n").hexdigest()},
    )
    violated_with_stale_exception = sorted(
        path
        for path in DENY
        if path in changed
        and not _owner_approved_exception_permits(path, root=repo, exceptions=stale_exceptions)
    )
    assert violated_with_stale_exception == ["src/project_atlas/ingestion.py"]


# ---------------------------------------------------------------------------
# Regression coverage for the freeze guard itself (ORCHAUT/D-041-style
# self-verification: the guard's own hosted-CI blind spot was found and
# fixed 2026-08-28 -- see WORKLOG "Freeze-guard hosted-CI blind spot").
# These build a real, throwaway git repository per test rather than
# mutating the actual project-atlas checkout.
# ---------------------------------------------------------------------------


def _run_git(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "freeze-guard-test",
            "GIT_AUTHOR_EMAIL": "freeze-guard-test@example.invalid",
            "GIT_COMMITTER_NAME": "freeze-guard-test",
            "GIT_COMMITTER_EMAIL": "freeze-guard-test@example.invalid",
        },
    )
    return result.stdout


def _init_fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _run_git(["init", "-q", "-b", "main"], cwd=repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=repo)
    _run_git(["commit", "-q", "-m", "base"], cwd=repo)
    return repo


def _write_event_payload(tmp_path: Path, *, base_sha: str, head_sha: str) -> Path:
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps({"pull_request": {"base": {"sha": base_sha}, "head": {"sha": head_sha}}}),
        encoding="utf-8",
    )
    return event_path


def test_freeze_guard_detects_frozen_path_via_pr_event_shas(tmp_path: Path) -> None:
    """Property 2/3: the guard must evaluate the actual PR changeset (via
    the GitHub event payload, not a possibly-unresolvable branch name) and
    must fail when a DENY-listed path is touched."""
    repo = _init_fixture_repo(tmp_path)
    base_sha = _run_git(["rev-parse", "HEAD"], cwd=repo).strip()
    frozen = repo / "src" / "project_atlas" / "api_server.py"
    frozen.parent.mkdir(parents=True)
    frozen.write_text("# touched\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=repo)
    _run_git(["commit", "-q", "-m", "touch frozen surface"], cwd=repo)
    head_sha = _run_git(["rev-parse", "HEAD"], cwd=repo).strip()
    event_path = _write_event_payload(tmp_path, base_sha=base_sha, head_sha=head_sha)
    env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_path)}

    changed = _changed_paths(root=repo, env=env)

    assert "src/project_atlas/api_server.py" in changed


def test_freeze_guard_allows_non_frozen_path_via_pr_event_shas(tmp_path: Path) -> None:
    """Property 4: a change that never touches a DENY-listed path must not
    false-positive as a violation."""
    repo = _init_fixture_repo(tmp_path)
    base_sha = _run_git(["rev-parse", "HEAD"], cwd=repo).strip()
    allowed = repo / "src" / "project_atlas" / "totally_unrelated_module.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text("# fine\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=repo)
    _run_git(["commit", "-q", "-m", "touch allowed surface"], cwd=repo)
    head_sha = _run_git(["rev-parse", "HEAD"], cwd=repo).strip()
    event_path = _write_event_payload(tmp_path, base_sha=base_sha, head_sha=head_sha)
    env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_path)}

    changed = _changed_paths(root=repo, env=env)
    violated = sorted(path for path in DENY if path in changed)

    assert "src/project_atlas/totally_unrelated_module.py" in changed
    assert violated == []


def test_freeze_guard_survives_shallow_single_commit_checkout(tmp_path: Path) -> None:
    """Property 5: a shallow, single-commit checkout (mirroring hosted
    CI's default ``fetch-depth: 1``) must not silently turn the guard
    into a no-op. Simulated by cloning only the head commit with
    ``--depth=1`` into a fresh directory that never had the base commit
    at all -- exactly the condition that made the original guard
    silently pass regardless of what changed."""
    source_repo = _init_fixture_repo(tmp_path)
    base_sha = _run_git(["rev-parse", "HEAD"], cwd=source_repo).strip()
    frozen = source_repo / "src" / "project_atlas" / "authz.py"
    frozen.parent.mkdir(parents=True)
    frozen.write_text("# touched\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=source_repo)
    _run_git(["commit", "-q", "-m", "touch frozen surface"], cwd=source_repo)
    head_sha = _run_git(["rev-parse", "HEAD"], cwd=source_repo).strip()

    shallow = tmp_path / "shallow-checkout"
    _run_git(
        # --no-local is required: git optimizes same-machine clones by
        # hardlinking the full object store regardless of --depth unless
        # explicitly told not to, which would silently defeat this exact
        # fixture (it must produce a genuinely shallow clone, matching
        # actions/checkout's real network-transport behavior).
        [
            "clone",
            "-q",
            "--no-local",
            "--depth=1",
            "--branch",
            "main",
            str(source_repo),
            str(shallow),
        ],
        cwd=tmp_path,
    )
    # Confirm the shallow clone genuinely does not have the base commit --
    # this is the precondition that defeated the original implementation.
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{base_sha}^{{commit}}"],
        cwd=shallow,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    assert probe.returncode != 0, "fixture setup error: base commit unexpectedly present"

    event_path = _write_event_payload(tmp_path, base_sha=base_sha, head_sha=head_sha)
    env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_path)}

    changed = _changed_paths(root=shallow, env=env)
    violated = sorted(path for path in DENY if path in changed)

    assert violated == ["src/project_atlas/authz.py"]


def test_freeze_guard_fails_closed_on_missing_event_path(tmp_path: Path) -> None:
    """Property 6a: claiming pull_request context without a readable event
    payload must raise, never silently pass."""
    repo = _init_fixture_repo(tmp_path)
    env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": ""}

    try:
        _changed_paths(root=repo, env=env)
    except DemoIsolationGuardError:
        return
    raise AssertionError("expected DemoIsolationGuardError, guard did not fail closed")


def test_freeze_guard_fails_closed_on_malformed_event_payload(tmp_path: Path) -> None:
    """Property 6b: an unreadable/malformed event payload must raise."""
    repo = _init_fixture_repo(tmp_path)
    bad_event = tmp_path / "bad-event.json"
    bad_event.write_text("{not valid json", encoding="utf-8")
    env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(bad_event)}

    try:
        _changed_paths(root=repo, env=env)
    except DemoIsolationGuardError:
        return
    raise AssertionError("expected DemoIsolationGuardError, guard did not fail closed")


def test_freeze_guard_not_applicable_with_no_remote_at_all(tmp_path: Path) -> None:
    """Property 6c, corrected per review (P2): outside any CI event
    context, a checkout with NO git remote configured at all (a source
    archive, vendored copy, or remotes deliberately stripped) has nothing
    to compare against -- this must raise the distinct
    ``DemoIsolationGuardNotApplicable``, not the fail-closed
    ``DemoIsolationGuardError``. Callers (the actual tests) turn this into
    a skip, not a suite-wide failure. Regression coverage for the original
    over-broad fail-closed behavior, which made the entire unit suite
    fail when run from an environment with remotes stripped."""
    repo = _init_fixture_repo(tmp_path)
    assert _has_any_remote(root=repo) is False, "fixture setup error: unexpected remote present"
    env: dict[str, str] = {}

    try:
        _changed_paths(root=repo, env=env)
    except DemoIsolationGuardNotApplicable:
        return
    except DemoIsolationGuardError:
        raise AssertionError(
            "expected DemoIsolationGuardNotApplicable (no remote at all -- "
            "nothing to enforce), got the fail-closed DemoIsolationGuardError instead"
        ) from None
    raise AssertionError("expected DemoIsolationGuardNotApplicable, guard did not skip")


def test_freeze_guard_fails_closed_when_remote_exists_but_origin_main_unresolvable(
    tmp_path: Path,
) -> None:
    """The genuine fail-closed case, distinct from the above: a remote
    IS configured (so this is not a "nothing to enforce" situation), but
    ``origin/main`` specifically cannot be resolved -- this must still
    raise the fail-closed ``DemoIsolationGuardError``."""
    repo = _init_fixture_repo(tmp_path)
    other_remote = tmp_path / "unrelated-remote"
    other_remote.mkdir()
    _run_git(["init", "-q", "--bare"], cwd=other_remote)
    _run_git(["remote", "add", "origin", str(other_remote)], cwd=repo)
    assert _has_any_remote(root=repo) is True
    env: dict[str, str] = {}

    try:
        _changed_paths(root=repo, env=env)
    except DemoIsolationGuardNotApplicable:
        raise AssertionError(
            "expected the fail-closed DemoIsolationGuardError (a remote is "
            "configured), got DemoIsolationGuardNotApplicable instead"
        ) from None
    except DemoIsolationGuardError:
        return
    raise AssertionError("expected DemoIsolationGuardError, guard did not fail closed")


def test_freeze_guard_local_full_clone_behavior_preserved() -> None:
    """Property 7: outside a pull_request event context, against the real
    project-atlas checkout (which does have ``origin/main``), resolution
    must still work -- this is the existing local-development path and
    must not regress. The fix now resolves to the concrete SHA rather
    than the floating ref name (correcting the "exact commit SHA"
    docstring/contract accuracy raised in review), so this checks that
    the returned value is genuinely that commit, not the literal string
    "origin/main"."""
    resolve = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    if resolve.returncode != 0:
        return  # no origin/main available in this environment either; nothing to assert
    expected_sha = resolve.stdout.strip()
    base = _resolve_diff_base(root=ROOT, env={})
    assert base == expected_sha
    assert base != "origin/main"


# ---------------------------------------------------------------------------
# Extension: the repository's ci.yml also runs this same guard on `push:
# branches: [main]`, not only `pull_request`. An independent re-verifier
# of the pull_request-only fix (above) correctly found that trigger was
# still silently unprotected under the same shallow-clone mechanism --
# `origin/main` still resolves (fail-open, not fail-closed) but is
# degenerate (== HEAD) under fetch-depth: 1, so nothing is ever detected
# on a push run. Closing that gap here, same established scope.
# ---------------------------------------------------------------------------


def _write_push_event_payload(tmp_path: Path, *, before_sha: str) -> Path:
    event_path = tmp_path / "push-event.json"
    event_path.write_text(json.dumps({"before": before_sha}), encoding="utf-8")
    return event_path


def test_freeze_guard_detects_frozen_path_via_push_event_before_sha(tmp_path: Path) -> None:
    """The push-event equivalent of the pull_request detection test: a
    shallow single-commit clone (matching ci.yml's push-triggered quality
    job) must still detect a DENY-listed change via the event's `before`
    SHA."""
    source_repo = _init_fixture_repo(tmp_path)
    before_sha = _run_git(["rev-parse", "HEAD"], cwd=source_repo).strip()
    frozen = source_repo / "src" / "project_atlas" / "discovery.py"
    frozen.parent.mkdir(parents=True)
    frozen.write_text("# touched\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=source_repo)
    _run_git(["commit", "-q", "-m", "touch frozen surface"], cwd=source_repo)

    shallow = tmp_path / "shallow-push-checkout"
    _run_git(
        [
            "clone",
            "-q",
            "--no-local",
            "--depth=1",
            "--branch",
            "main",
            str(source_repo),
            str(shallow),
        ],
        cwd=tmp_path,
    )
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{before_sha}^{{commit}}"],
        cwd=shallow,
        check=False,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    assert probe.returncode != 0, "fixture setup error: base commit unexpectedly present"

    event_path = _write_push_event_payload(tmp_path, before_sha=before_sha)
    env = {"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": str(event_path)}

    changed = _changed_paths(root=shallow, env=env)
    violated = sorted(path for path in DENY if path in changed)

    assert violated == ["src/project_atlas/discovery.py"]


def test_freeze_guard_push_event_no_false_positive_on_allowed_path(tmp_path: Path) -> None:
    repo = _init_fixture_repo(tmp_path)
    before_sha = _run_git(["rev-parse", "HEAD"], cwd=repo).strip()
    allowed = repo / "src" / "project_atlas" / "totally_unrelated_module.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text("# fine\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=repo)
    _run_git(["commit", "-q", "-m", "touch allowed surface"], cwd=repo)
    event_path = _write_push_event_payload(tmp_path, before_sha=before_sha)
    env = {"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": str(event_path)}

    changed = _changed_paths(root=repo, env=env)
    violated = sorted(path for path in DENY if path in changed)

    assert "src/project_atlas/totally_unrelated_module.py" in changed
    assert violated == []


def test_freeze_guard_push_event_fails_closed_on_missing_event_path(tmp_path: Path) -> None:
    repo = _init_fixture_repo(tmp_path)
    env = {"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": ""}

    try:
        _changed_paths(root=repo, env=env)
    except DemoIsolationGuardError:
        return
    raise AssertionError("expected DemoIsolationGuardError, guard did not fail closed")


def test_freeze_guard_push_event_fails_closed_on_malformed_payload(tmp_path: Path) -> None:
    repo = _init_fixture_repo(tmp_path)
    bad_event = tmp_path / "bad-push-event.json"
    bad_event.write_text("not json at all", encoding="utf-8")
    env = {"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": str(bad_event)}

    try:
        _changed_paths(root=repo, env=env)
    except DemoIsolationGuardError:
        return
    raise AssertionError("expected DemoIsolationGuardError, guard did not fail closed")


def test_freeze_guard_push_event_fails_closed_on_first_push_sentinel(tmp_path: Path) -> None:
    """GitHub uses an all-zero SHA for `before` on a branch's very first
    push. There is no real prior commit to diff against; this must fail
    closed, not silently resolve to something wrong."""
    repo = _init_fixture_repo(tmp_path)
    event_path = _write_push_event_payload(tmp_path, before_sha="0" * 40)
    env = {"GITHUB_EVENT_NAME": "push", "GITHUB_EVENT_PATH": str(event_path)}

    try:
        _changed_paths(root=repo, env=env)
    except DemoIsolationGuardError:
        return
    raise AssertionError("expected DemoIsolationGuardError, guard did not fail closed")


# ---------------------------------------------------------------------------
# Round-4 fixes. An independent re-verifier of round 3 (bound to exact head
# 99ce6fbf3329273425025643bc5963cd805b2005) reproduced a real, pre-existing
# P2 in the local/full-clone fallback path (property 7): because
# `_changed_paths` diffed directly against the live `origin/main` tip
# rather than its merge-base with HEAD, a local branch that is behind
# `origin/main` would false-positive on any DENY-listed path main had
# independently advanced since -- flagging it as though the local branch
# itself had touched it. This matches a stale Copilot review comment on
# this PR's round-1 head that the earlier three-dot-to-direct-diff switch
# had not accounted for. Fixed by computing an explicit merge-base for
# this one fallback path (safe here: full clone, not the shallow
# exact-SHA CI-event case the original direct-diff switch was protecting).
# ---------------------------------------------------------------------------


def test_freeze_guard_local_fallback_no_false_positive_on_diverged_main(
    tmp_path: Path,
) -> None:
    """The local/full-clone fallback (no CI event context) must diff HEAD
    against its merge-base with origin/main, not origin/main's live tip --
    otherwise an unrelated DENY-listed change that main picked up AFTER
    this branch diverged reads as a violation the local branch never
    committed.

    Fetches/clones directly against a plain working-tree "seed" repo
    (git supports both against a non-bare local path) rather than
    round-tripping through a separate bare "origin" repo with two
    `git push`es -- push's pack-generation/transfer overhead was the
    single largest contributor to this test's wall time on the
    already-tight hosted Windows CI lane; this fixture is behaviorally
    identical (a real, separate `origin` remote a real `git fetch`
    populates) but meaningfully cheaper.
    """
    seed = _init_fixture_repo(tmp_path)

    clone = tmp_path / "diverged-clone"
    _run_git(["clone", "-q", "--no-local", str(seed), str(clone)], cwd=tmp_path)

    # The local branch makes its own, allowed-only change and diverges.
    local_change = clone / "src" / "project_atlas" / "totally_unrelated_module.py"
    local_change.parent.mkdir(parents=True)
    local_change.write_text("# local branch's own change\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=clone)
    _run_git(["commit", "-q", "-m", "local branch change"], cwd=clone)

    # Meanwhile origin/main independently advances with a DENY-listed
    # change the local branch never saw and never touched.
    frozen = seed / "src" / "project_atlas" / "authz.py"
    frozen.parent.mkdir(parents=True)
    frozen.write_text("# unrelated upstream change\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=seed)
    _run_git(["commit", "-q", "-m", "upstream touches frozen surface"], cwd=seed)
    _run_git(["fetch", "-q", "origin"], cwd=clone)

    # Precondition: the naive direct diff WOULD flag the frozen path here.
    naive = subprocess.run(
        ["git", "diff", "--name-only", "origin/main", "HEAD"],
        cwd=clone,
        check=True,
        capture_output=True,
        text=True,
        timeout=_LOCAL_GIT_TIMEOUT_SECONDS,
    )
    assert "src/project_atlas/authz.py" in naive.stdout, (
        "fixture setup error: expected the direct-diff false positive "
        "precondition to hold before asserting the fix avoids it"
    )

    changed = _changed_paths(root=clone, env={})
    violated = sorted(path for path in DENY if path in changed)

    assert violated == [], (
        "local-fallback diff must isolate the local branch's own changes "
        f"via merge-base, not flag upstream-only advancement: {violated}"
    )
    assert "src/project_atlas/totally_unrelated_module.py" in changed


# ---------------------------------------------------------------------------
# The incident this timeout responds to: a real hosted CI run for this PR
# left three quality jobs "in_progress" for over an hour (well past
# ci.yml's own 20-minute job timeout) because the network `git fetch` this
# guard added had no bound of its own. GitHub's job-level timeout only
# fires once a job has actually started consuming its allotted wall
# clock; it does not help if a single subprocess call inside that job can
# block forever. Proven directly here with a fake, deliberately-hanging
# `git` on PATH -- not just trusted because `subprocess.run(timeout=...)`
# is a standard library feature.
# ---------------------------------------------------------------------------


def test_fetch_timeout_is_actually_enforced_not_just_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Directly proves the incident this fix responds to cannot recur: a
    `git fetch` that never returns must be converted to
    DemoIsolationGuardError, not left to hang the calling process (and, in
    real hosted CI, the whole job) indefinitely.

    A real subprocess hang is deliberately NOT simulated here: on Windows,
    `subprocess.run(["git", ...])` with `shell=False` resolves the
    executable via a restricted, .exe-only search (Windows' own
    documented CreateProcess behavior for a NULL application name) and
    will not pick up a `.cmd`/`.bat` shim placed on PATH, so an
    orchestrated "fake hanging git" fixture would silently invoke the
    real git instead and prove nothing (or worse, flake). `subprocess.
    run(timeout=...)` reliably raising `TimeoutExpired` on an actual
    timeout is standard-library behavior, not this guard's own logic to
    prove; what this guard's own code needs proving is that a real
    `TimeoutExpired` -- however it arises -- is caught on the fetch call
    specifically and converted into the documented, fail-closed
    `DemoIsolationGuardError`, rather than propagating as a raw traceback
    or (worse) being swallowed. That is exercised directly here by making
    the fetch call itself raise a real `subprocess.TimeoutExpired`, while
    every other subprocess call (including `_ensure_commit_fetched`'s own
    preceding `cat-file -e` probe) still runs for real, so the "probe
    reports absent, falls through to fetch" path is genuinely exercised.
    """
    import time

    repo = _init_fixture_repo(tmp_path)
    real_run = subprocess.run

    def _fake_run(
        cmd: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "fetch":
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
        return real_run(
            cmd, cwd=cwd, check=check, capture_output=capture_output, text=text, timeout=timeout
        )

    monkeypatch.setattr(
        "tests.unit.test_atlas3_demo_isolation_001.subprocess.run",
        _fake_run,
    )
    monkeypatch.setattr(
        "tests.unit.test_atlas3_demo_isolation_001._NETWORK_GIT_TIMEOUT_SECONDS",
        2,
        raising=True,
    )

    started = time.monotonic()
    with pytest.raises(DemoIsolationGuardError, match="did not complete within"):
        _ensure_commit_fetched("0" * 40, root=repo)
    elapsed = time.monotonic() - started

    assert elapsed < 10, (
        f"fetch-timeout conversion took {elapsed:.1f}s -- should be "
        "near-instant since the timeout itself is simulated, not waited out"
    )


# --- the waiver, proven by running the guard, not by reading it ------------
#
# Source inspection cannot show that a waiver still blocks what it must. Each
# case below feeds a synthetic candidate diff through the guard's own decision
# function with the waiver ACTIVE, and asserts the outcome.

_LOGFORMAT_DELTA = """diff --git a/src/project_atlas/cli.py b/src/project_atlas/cli.py
--- a/src/project_atlas/cli.py
+++ b/src/project_atlas/cli.py
@@ -3125,6 +3125,8 @@ def main(argv: Sequence[str] | None = None) -> int:
     args = parser.parse_args(argv)
+    if args.log_format is not None:
+        configure_logging(log_format=args.log_format)
     try:
"""

_INTACT_SOURCE = " ".join(f'"{command}"' for command in _CERTIFIED_COMMANDS)


def test_waiver_permits_only_the_authorized_bootstrap_delta() -> None:
    """A: the authorized change passes with the waiver active."""
    assert (
        _cli_guard_violations(
            diff_text=_LOGFORMAT_DELTA,
            cli_source=_INTACT_SOURCE,
            atlas3_hooks_waived=True,
        )
        == []
    )


def test_waiver_still_blocks_a_certified_command_deletion() -> None:
    """B: removing a certified command registration must fail even when waived."""
    diff = _LOGFORMAT_DELTA + '-    connect_parser = subparsers.add_parser("connect")\n'
    source = " ".join(
        f'"{command}"' for command in _CERTIFIED_COMMANDS if command != "connect"
    )
    violations = _cli_guard_violations(
        diff_text=diff, cli_source=source, atlas3_hooks_waived=True
    )
    assert "deletion-from-certified-cli-surface" in violations
    assert "certified-command-missing:connect" in violations


def test_waiver_still_blocks_an_atlas3_seam_deletion() -> None:
    """C: removing the Atlas-3 seam call must fail even when waived."""
    diff = _LOGFORMAT_DELTA + "-    register_atlas3_parsers(subparsers)\n"
    violations = _cli_guard_violations(
        diff_text=diff, cli_source=_INTACT_SOURCE, atlas3_hooks_waived=True
    )
    assert "deletion-from-certified-cli-surface" in violations


def test_waiver_does_not_bless_an_unauthorized_addition_by_itself() -> None:
    """D/E/F: containment for additions is the sha256 pin, not the diff shape.

    The guard cannot tell an authorized added line from an unauthorized one,
    and it does not try to. What stops an unauthorized addition is that any
    other cli.py bytes fail the pin, so the waiver is simply not active --
    proven here and in the pin tests below.
    """
    direct_registration = _LOGFORMAT_DELTA + '+    subparsers.add_parser("atlas3-secret")\n'
    # With the waiver active (i.e. bytes matching the reviewed candidate) this
    # shape is permitted...
    assert (
        _cli_guard_violations(
            diff_text=direct_registration,
            cli_source=_INTACT_SOURCE,
            atlas3_hooks_waived=True,
        )
        == []
    )
    # ...which is exactly why the waiver must never be active for bytes other
    # than the reviewed ones. Without it, the Atlas-3 hook requirement returns.
    unwaived = _cli_guard_violations(
        diff_text=direct_registration,
        cli_source=_INTACT_SOURCE,
        atlas3_hooks_waived=False,
    )
    assert "missing-atlas3-register-hook" in unwaived
    assert "missing-atlas3-dispatch-hook" in unwaived


def test_unwaived_authorized_delta_is_blocked() -> None:
    """The waiver is load-bearing: without it, this exact change cannot land."""
    violations = _cli_guard_violations(
        diff_text=_LOGFORMAT_DELTA,
        cli_source=_INTACT_SOURCE,
        atlas3_hooks_waived=False,
    )
    assert "missing-atlas3-register-hook" in violations
    assert "no-added-atlas3-registration" in violations


def test_cli_exception_does_not_survive_any_further_edit(tmp_path: Path) -> None:
    """G: one more byte in cli.py and the Atlas-3 hook requirement returns."""
    approved = b"import sys\n"
    (tmp_path / "src" / "project_atlas").mkdir(parents=True)
    target = tmp_path / "src" / "project_atlas" / "cli.py"
    target.write_bytes(approved)
    exceptions = (
        {
            "exception_id": "OG-ATLAS-CLI-LOGFORMAT-BOOTSTRAP-20260906",
            "owner_approved": "YES",
            "reason": "test",
            "path": "src/project_atlas/cli.py",
            "allowed_sha256": hashlib.sha256(approved).hexdigest(),
        },
    )
    assert _owner_approved_exception_permits(
        "src/project_atlas/cli.py", root=tmp_path, exceptions=exceptions
    )
    target.write_bytes(approved + b"# one more byte\n")
    assert not _owner_approved_exception_permits(
        "src/project_atlas/cli.py", root=tmp_path, exceptions=exceptions
    )


def test_cli_exception_does_not_cover_a_deny_listed_path(tmp_path: Path) -> None:
    """The CLI waiver must not leak into the frozen runtime surfaces."""
    approved = b"import sys\n"
    (tmp_path / "src" / "project_atlas").mkdir(parents=True)
    for name in ("cli.py", "discovery.py"):
        (tmp_path / "src" / "project_atlas" / name).write_bytes(approved)
    exceptions = (
        {
            "exception_id": "OG-ATLAS-CLI-LOGFORMAT-BOOTSTRAP-20260906",
            "owner_approved": "YES",
            "reason": "test",
            "path": "src/project_atlas/cli.py",
            "allowed_sha256": hashlib.sha256(approved).hexdigest(),
        },
    )
    assert not _owner_approved_exception_permits(
        "src/project_atlas/discovery.py", root=tmp_path, exceptions=exceptions
    )


def test_real_cli_exception_is_live_or_inert_honestly() -> None:
    """Every live CLI waiver names cli.py, is owner-approved, and is real hex."""
    for exc in _CLI_ADDITIVE_EXCEPTIONS:
        assert exc["owner_approved"] == "YES"
        assert exc["exception_id"]
        assert exc["reason"]
        assert exc["path"] == "src/project_atlas/cli.py"
        assert len(exc["allowed_sha256"]) == 64
        int(exc["allowed_sha256"], 16)
