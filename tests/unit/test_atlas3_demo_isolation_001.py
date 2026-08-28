"""Atlas 3 must not rewrite certified demo / 2.x surfaces."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

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


class DemoIsolationGuardError(RuntimeError):
    """Fail-closed: the certified-surface freeze guard could not determine
    its comparison base. An inconclusive result must fail visibly, never
    be silently treated as "no changes" -- that would turn the guard into
    a no-op exactly when it matters most.
    """


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
    Raises if the fetch itself fails -- a comparison base that cannot be
    obtained must not be silently skipped.
    """
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return
    fetch = subprocess.run(
        ["git", "fetch", "--depth=1", "origin", sha],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if fetch.returncode != 0:
        raise DemoIsolationGuardError(
            f"could not fetch commit {sha} needed for the freeze-guard "
            f"comparison: {fetch.stderr.strip()}"
        )


def _resolve_diff_base(*, root: Path = ROOT, env: Mapping[str, str] | None = None) -> str:
    """Return the exact commit SHA the freeze guard must diff HEAD
    against, and guarantee it is fetched/resolvable in ``root``'s local
    object database before returning.

    Prefers the authoritative GitHub ``pull_request`` event base SHA, then
    the ``push`` event's pre-push SHA, when running in either context
    (both work correctly under any checkout depth, including the hosted
    CI default of a single-commit shallow fetch). Falls back to
    ``origin/main`` for local/full-clone use, but fails closed (raises)
    if that ref cannot be resolved either, rather than letting the caller
    silently treat an unresolvable base as "nothing changed".
    """
    pr_shas = _event_pull_request_shas(env=env)
    if pr_shas is not None:
        base_sha, _head_sha = pr_shas
        _ensure_commit_fetched(base_sha, root=root)
        return base_sha
    push_before = _event_push_before_sha(env=env)
    if push_before is not None:
        _ensure_commit_fetched(push_before, root=root)
        return push_before
    resolve = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if resolve.returncode != 0:
        raise DemoIsolationGuardError(
            "not running in a GitHub Actions pull_request or push context "
            "and origin/main is not resolvable locally -- cannot determine "
            "the freeze-guard comparison base (this must fail, not pass)"
        )
    return "origin/main"


def _changed_paths(*, root: Path = ROOT, env: Mapping[str, str] | None = None) -> set[str]:
    """Return every path changed relative to the resolved diff base, plus
    any uncommitted worktree/staged changes. Fails closed (raises via
    ``_resolve_diff_base``) if the comparison base cannot be determined --
    never silently returns an empty/inconclusive result as if nothing
    changed.
    """
    base = _resolve_diff_base(root=root, env=env)
    # Direct two-endpoint diff, not three-dot merge-base diff: when `base`
    # is an exact PR-event SHA, computing a merge-base can fail outright
    # under a shallow/disconnected fetch (no shared history graph) even
    # though both endpoints are individually resolvable. A direct diff
    # needs only the two commits' trees, not their ancestry, and is exactly
    # correct here since `base` is already the PR's real base commit, not
    # a possibly-since-moved branch tip.
    committed = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    worktree = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    staged = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    names = "\n".join([committed.stdout, worktree.stdout, staged.stdout])
    return {line.strip() for line in names.splitlines() if line.strip()}


def test_certified_surfaces_unmodified() -> None:
    changed = _changed_paths()
    violated = sorted(path for path in DENY if path in changed)
    assert violated == []


def test_cli_mutation_is_additive_only() -> None:
    if "src/project_atlas/cli.py" not in _changed_paths():
        return
    base = _resolve_diff_base()
    diff = subprocess.run(
        ["git", "diff", base, "--", "src/project_atlas/cli.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    text = diff.stdout
    assert "register_atlas3_parsers" in text
    assert "dispatch_atlas3" in text
    lines = text.splitlines()
    added = [line for line in lines if line.startswith("+") and not line.startswith("+++")]
    removed = [line for line in lines if line.startswith("-") and not line.startswith("---")]
    assert removed == []
    assert any("register_atlas3_parsers" in line for line in added)
    source = (ROOT / "src" / "project_atlas" / "cli.py").read_text(encoding="utf-8")
    for command in ("connect", "ask2", "kdiff", "brief", "capture"):
        assert f'"{command}"' in source or f"'{command}'" in source


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


def test_freeze_guard_fails_closed_when_origin_main_unresolvable_outside_ci(
    tmp_path: Path,
) -> None:
    """Property 6c: outside any pull_request event context, an
    unresolvable ``origin/main`` (e.g. a bare fixture repo with no remote
    configured at all) must raise, never be silently treated as zero
    changes."""
    repo = _init_fixture_repo(tmp_path)
    env: dict[str, str] = {}

    try:
        _changed_paths(root=repo, env=env)
    except DemoIsolationGuardError:
        return
    raise AssertionError("expected DemoIsolationGuardError, guard did not fail closed")


def test_freeze_guard_local_full_clone_behavior_preserved() -> None:
    """Property 7: outside a pull_request event context, against the real
    project-atlas checkout (which does have ``origin/main``), resolution
    must still work exactly as it did before this fix -- this is the
    existing local-development path and must not regress."""
    resolve = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if resolve.returncode != 0:
        return  # no origin/main available in this environment either; nothing to assert
    base = _resolve_diff_base(root=ROOT, env={})
    assert base == "origin/main"


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
