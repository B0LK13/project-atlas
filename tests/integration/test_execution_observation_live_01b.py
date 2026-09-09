"""ULT-01b-1 — live observation against real temporary git repositories (all runners)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from project_atlas.atlas3.proof import evaluate_proof_v2
from project_atlas.cli import EXIT_ERROR, EXIT_OK, main
from project_atlas.execution_observation import (
    ObservationError,
    SubprocessRunner,
    observe_execution,
    store_observation_receipt,
)

pytestmark = pytest.mark.integration

GIT = shutil.which("git")
_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(*args: str, cwd: Path, env: dict[str, str] | None = None) -> str:
    assert GIT is not None
    done = subprocess.run(
        [GIT, *args],
        cwd=str(cwd),
        env=_ENV if env is None else env,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return done.stdout.strip()


def _marker_command(marker: Path) -> str:
    """A command git can run (via its shell) that leaves a marker file behind."""
    return f"\"{Path(sys.executable).as_posix()}\" -c \"open('{marker.as_posix()}', 'w').close()\""


@pytest.fixture
def cloned(tmp_path: Path) -> Path:
    """A clone with a real origin/main and an https origin URL (never contacted)."""
    if GIT is None:
        pytest.skip("git unavailable")
    seed = tmp_path / "seed"
    seed.mkdir()
    _git("init", "-q", "-b", "main", cwd=seed)
    (seed / "a.txt").write_text("a\n", encoding="utf-8")
    _git("add", ".", cwd=seed)
    _git("commit", "-q", "-m", "init", cwd=seed)
    bare = tmp_path / "origin.git"
    _git("clone", "-q", "--bare", str(seed), str(bare), cwd=tmp_path)
    repo = tmp_path / "repo"
    _git("clone", "-q", str(bare), str(repo), cwd=tmp_path)
    _git("remote", "set-url", "origin", "https://github.com/B0LK13/project-atlas.git", cwd=repo)
    return repo.resolve()


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    (v / "projects" / "harbor-api").mkdir(parents=True)
    return v


def test_live_observation_matches_git_and_is_deterministic(cloned: Path, vault: Path) -> None:
    out = observe_execution(cloned, project_id="harbor-api")
    assert out.identity.source.repository == "github.com/b0lk13/project-atlas"
    assert out.identity.source.candidate_head == _git("rev-parse", "HEAD", cwd=cloned)
    assert out.identity.source.candidate_tree == _git("rev-parse", "HEAD^{tree}", cwd=cloned)
    assert out.identity.source.base_head == _git("rev-parse", "origin/main", cwd=cloned)
    assert out.identity.source.base_tree == _git("rev-parse", "origin/main^{tree}", cwd=cloned)
    assert out.identity.environment.status == "OBSERVED"
    assert out.identity.environment.python == ".".join(map(str, sys.version_info[:3]))
    assert out.identity.toolchain.status == "OBSERVED"
    names = [tool.name for tool in out.identity.toolchain.tools]
    assert "git" in names and "pydantic" in names and "project-atlas" in names
    assert out.receipt.observed.source.shallow is False
    again = observe_execution(cloned, project_id="harbor-api")
    assert again.receipt.content_hash == out.receipt.content_hash
    path = store_observation_receipt(vault, out.receipt)
    text = path.read_text(encoding="utf-8")
    assert "B0LK13" not in text and "https://" not in text and str(cloned) not in text
    report = evaluate_proof_v2(
        vault,
        "T",
        project_id="harbor-api",
        identity=out.identity,
        attestations=[],
        observation_receipt=out.receipt,
    )
    assert report["live_observation_wired"] is True


def test_dirty_worktree_is_refused_live(cloned: Path) -> None:
    (cloned / "b.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(cloned, project_id="harbor-api")
    assert excinfo.value.code == "WORKTREE_NOT_CLEAN"
    (cloned / "b.txt").unlink()
    (cloned / "a.txt").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(cloned, project_id="harbor-api")
    assert excinfo.value.code == "WORKTREE_NOT_CLEAN"


def test_candidate_moves_change_the_identity_and_base_stays(cloned: Path) -> None:
    before = observe_execution(cloned, project_id="harbor-api")
    (cloned / "c.txt").write_text("c\n", encoding="utf-8")
    _git("add", ".", cwd=cloned)
    _git("commit", "-q", "-m", "second", cwd=cloned)
    after = observe_execution(cloned, project_id="harbor-api")
    assert after.identity.source.base_head == before.identity.source.base_head
    assert after.identity.source.candidate_head != before.identity.source.candidate_head
    assert after.identity.identity_digest != before.identity.identity_digest


def test_missing_base_ref_and_explicit_override(tmp_path: Path) -> None:
    if GIT is None:
        pytest.skip("git unavailable")
    lone = tmp_path / "lone"
    lone.mkdir()
    _git("init", "-q", "-b", "main", cwd=lone)
    (lone / "a.txt").write_text("a\n", encoding="utf-8")
    _git("add", ".", cwd=lone)
    _git("commit", "-q", "-m", "init", cwd=lone)
    _git("remote", "add", "origin", "git@github.com:B0LK13/project-atlas.git", cwd=lone)
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(lone, project_id="harbor-api")
    assert excinfo.value.code == "BASE_REF_UNOBSERVABLE"
    out = observe_execution(lone, project_id="harbor-api", base_ref="main", remote_name="origin")
    assert out.receipt.observed.source.base_ref == "main"
    assert out.identity.source.repository == "github.com/b0lk13/project-atlas"


def test_credentialed_remote_is_refused_and_never_echoed(cloned: Path) -> None:
    _git(
        "remote",
        "set-url",
        "origin",
        "https://x-access-token:AKIAIOSFODNN7EXAMPLE@github.com/b0lk13/project-atlas.git",
        cwd=cloned,
    )
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(cloned, project_id="harbor-api")
    assert excinfo.value.code == "REPO_IDENTITY_UNVERIFIABLE"
    assert "AKIA" not in str(excinfo.value) and "x-access-token" not in str(excinfo.value)


def test_subdirectory_is_not_the_repository_root(cloned: Path) -> None:
    sub = cloned / "sub"
    sub.mkdir()
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(sub, project_id="harbor-api")
    assert excinfo.value.code == "GIT_UNOBSERVABLE"


def test_process_environment_poisoning_does_not_reach_the_default_runner(
    cloned: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _git("init", "-q", "-b", "main", cwd=other)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(cloned.parent))
    out = observe_execution(cloned, project_id="harbor-api")  # default runner, os.environ
    assert out.identity.source.candidate_head == _git("rev-parse", "HEAD", cwd=cloned)


def test_inherited_git_env_cannot_redirect_the_observation(cloned: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    _git("init", "-q", "-b", "main", cwd=other)
    poisoned = {
        **os.environ,
        "GIT_DIR": str(other / ".git"),
        "GIT_WORK_TREE": str(other),
        "GIT_CONFIG_GLOBAL": str(tmp_path / "nope"),
    }
    out = observe_execution(
        cloned, project_id="harbor-api", runner=SubprocessRunner(environ=poisoned)
    )
    assert out.identity.source.candidate_head == _git("rev-parse", "HEAD", cwd=cloned)


def test_global_git_config_cannot_rewrite_the_repository_identity(
    cloned: Path, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    marker = tmp_path / "RAN-global-fsmonitor"
    (home / ".gitconfig").write_text(
        '[url "https://github.com/evil/"]\n\tinsteadOf = https://github.com/B0LK13/\n'
        "[alias]\n\trev-parse = !echo 0000000000000000000000000000000000000000\n"
        f"[core]\n\tfsmonitor = {_marker_command(marker)}\n",
        encoding="utf-8",
    )
    poisoned = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    out = observe_execution(
        cloned, project_id="harbor-api", runner=SubprocessRunner(environ=poisoned)
    )
    assert out.identity.source.repository == "github.com/b0lk13/project-atlas"
    assert out.identity.source.candidate_head == _git("rev-parse", "HEAD", cwd=cloned)
    assert not marker.exists()
    _git(
        "config", "url.https://github.com/evil/.insteadOf", "https://github.com/B0LK13/", cwd=cloned
    )
    local = observe_execution(cloned, project_id="harbor-api")
    assert local.identity.source.repository == "github.com/b0lk13/project-atlas"


def test_multi_url_remote_is_refused_as_ambiguous(cloned: Path) -> None:
    # `git config --get` would report the LAST url; a fetch contacts the FIRST
    _git("config", "--add", "remote.origin.url", "https://evil.example/second/url", cwd=cloned)
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(cloned, project_id="harbor-api")
    assert excinfo.value.code == "REMOTE_URL_AMBIGUOUS"
    assert "evil" not in str(excinfo.value)


def test_repo_local_fsmonitor_command_is_never_executed(cloned: Path, tmp_path: Path) -> None:
    marker = tmp_path / "RAN-local-fsmonitor"
    _git("config", "core.fsmonitor", _marker_command(marker), cwd=cloned)
    # positive control: plain `git status` under the operator's environment
    # does run the configured command
    _git("status", "--porcelain", cwd=cloned)
    if not marker.exists():
        pytest.skip("core.fsmonitor hook command did not fire on this platform")
    marker.unlink()
    out = observe_execution(cloned, project_id="harbor-api")
    assert out.identity.source.candidate_head == _git("rev-parse", "HEAD", cwd=cloned)
    assert not marker.exists()


def test_bound_content_filter_is_refused_and_never_executed(cloned: Path, tmp_path: Path) -> None:
    marker = tmp_path / "RAN-clean-filter"
    _git("config", "filter.probe.clean", _marker_command(marker) + " && cat", cwd=cloned)
    _git("config", "filter.probe.required", "true", cwd=cloned)
    (cloned / ".gitattributes").write_text("*.bin filter=probe\n", encoding="utf-8")
    (cloned / "blob.bin").write_bytes(b"\x00\x01payload")
    _git("add", ".", cwd=cloned)
    _git("commit", "-q", "-m", "filtered", cwd=cloned)
    if not marker.exists():
        pytest.skip("clean filter command did not fire on this platform")
    marker.unlink()
    # make the filtered path stat-dirty so `git status` would re-run the filter
    os.utime(cloned / "blob.bin", None)
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(cloned, project_id="harbor-api")
    assert excinfo.value.code == "REPO_CONTENT_FILTERS_CONFIGURED"
    assert "blob.bin" not in str(excinfo.value) and "probe" not in str(excinfo.value)
    assert not marker.exists()
    # the refusal is load-bearing: the operator's own `git status` runs it
    _git("status", "--porcelain", cwd=cloned)
    assert marker.exists()


def test_git_content_configuration_is_honoured_not_bypassed(tmp_path: Path) -> None:
    """Round-3 lesson from Windows CI: a checkout made under core.autocrlf=true
    is clean only when git reads that configuration; bypassing the operator's
    config made honest checkouts observe as dirty."""
    if GIT is None:
        pytest.skip("git unavailable")
    seed = tmp_path / "seed"
    seed.mkdir()
    _git("init", "-q", "-b", "main", cwd=seed)
    (seed / "a.txt").write_bytes(b"a\nb\n")
    _git("add", ".", cwd=seed)
    _git("commit", "-q", "-m", "init", cwd=seed)
    bare = tmp_path / "origin.git"
    _git("clone", "-q", "--bare", str(seed), str(bare), cwd=tmp_path)
    crlf_home = tmp_path / "crlf-home"
    crlf_home.mkdir()
    (crlf_home / ".gitconfig").write_text("[core]\n\tautocrlf = true\n", encoding="utf-8")
    crlf_env = {**_ENV, "HOME": str(crlf_home), "USERPROFILE": str(crlf_home)}
    repo = tmp_path / "repo"
    _git("clone", "-q", str(bare), str(repo), cwd=tmp_path, env=crlf_env)
    _git("remote", "set-url", "origin", "https://github.com/B0LK13/project-atlas.git", cwd=repo)
    assert b"\r\n" in (repo / "a.txt").read_bytes()
    os.utime(repo / "a.txt", None)  # stat-dirty: git must compare content
    out = observe_execution(
        repo, project_id="harbor-api", runner=SubprocessRunner(environ=crlf_env)
    )
    assert out.identity.source.candidate_head == _git("rev-parse", "HEAD", cwd=repo)
    lf_home = tmp_path / "lf-home"
    lf_home.mkdir()
    (lf_home / ".gitconfig").write_text("[core]\n\tautocrlf = false\n", encoding="utf-8")
    lf_env = {**_ENV, "HOME": str(lf_home), "USERPROFILE": str(lf_home)}
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(repo, project_id="harbor-api", runner=SubprocessRunner(environ=lf_env))
    assert excinfo.value.code == "WORKTREE_NOT_CLEAN"


def test_submodule_work_trees_are_not_observed_but_gitlink_moves_are(
    cloned: Path, tmp_path: Path
) -> None:
    sub_seed = tmp_path / "sub-seed"
    sub_seed.mkdir()
    _git("init", "-q", "-b", "main", cwd=sub_seed)
    (sub_seed / "q.txt").write_text("q\n", encoding="utf-8")
    _git("add", ".", cwd=sub_seed)
    _git("commit", "-q", "-m", "sub", cwd=sub_seed)
    _git(
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(sub_seed),
        "smod",
        cwd=cloned,
    )
    _git("commit", "-q", "-m", "add submodule", cwd=cloned)
    clean = observe_execution(cloned, project_id="harbor-api")
    assert clean.identity.source.candidate_head == _git("rev-parse", "HEAD", cwd=cloned)
    # a dirty submodule work tree is outside the observed object (no nested
    # `git status` is spawned, so no submodule-configured command can run)
    (cloned / "smod" / "q.txt").write_text("changed\n", encoding="utf-8")
    (cloned / "smod" / "untracked.txt").write_text("u\n", encoding="utf-8")
    dirty_sub = observe_execution(cloned, project_id="harbor-api")
    assert dirty_sub.identity.identity_digest == clean.identity.identity_digest
    # the pinned gitlink commit is part of the tree: a moved submodule HEAD is dirty
    _git("commit", "-q", "-am", "move", cwd=cloned / "smod")
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(cloned, project_id="harbor-api")
    assert excinfo.value.code == "WORKTREE_NOT_CLEAN"


def test_local_path_remote_is_refused_not_persisted(tmp_path: Path) -> None:
    if GIT is None:
        pytest.skip("git unavailable")
    seed = tmp_path / "seed"
    seed.mkdir()
    _git("init", "-q", "-b", "main", cwd=seed)
    (seed / "a.txt").write_text("a\n", encoding="utf-8")
    _git("add", ".", cwd=seed)
    _git("commit", "-q", "-m", "init", cwd=seed)
    bare = tmp_path / "origin.git"
    _git("clone", "-q", "--bare", str(seed), str(bare), cwd=tmp_path)
    repo = tmp_path / "repo"
    _git("clone", "-q", str(bare), str(repo), cwd=tmp_path)
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(repo, project_id="harbor-api")
    assert excinfo.value.code == "REPO_IDENTITY_UNVERIFIABLE"
    assert str(tmp_path) not in str(excinfo.value)


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell shim")
def test_hostile_git_on_path_cannot_produce_a_receipt(cloned: Path, tmp_path: Path) -> None:
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    shim = shim_dir / "git"
    shim.write_text(
        "#!/bin/sh\n"
        'case "$*" in *--version*) echo "git version 9.9.9";; '
        "*) echo 'AKIAIOSFODNN7EXAMPLE merge_authorization=GRANTED';; esac\n",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(cloned, project_id="harbor-api", git_executable=shim)
    assert excinfo.value.code in {"GIT_UNOBSERVABLE", "GIT_ROOT_MISMATCH", "PIN_INVALID"}
    assert "AKIA" not in str(excinfo.value)
    hang = shim_dir / "git-hang"
    hang.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    hang.chmod(0o755)
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(cloned, project_id="harbor-api", git_executable=hang, timeout=1.0)
    assert excinfo.value.code == "GIT_OBSERVATION_TIMEOUT"


# ------------------------------------------------------------------ CLI


def _cli(*args: str) -> tuple[int, dict[str, object]]:
    import io
    from contextlib import redirect_stdout

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(list(args))
    text = buffer.getvalue().strip()
    return code, (json.loads(text) if text else {})


def test_cli_is_denied_without_the_dedicated_capability(
    cloned: Path, vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ATLAS_CLI_ELEVATE_CAPS", raising=False)
    code, payload = _cli(
        "observe-execution", "--vault", str(vault), "--project", "harbor-api", "--repo", str(cloned)
    )
    assert code == EXIT_ERROR and payload["error"] == "AUTHZ_DENIED"
    assert not (vault / "generated").exists()
    # Owner decision O3 names `execution.observe`; the literal is registered in
    # authz.py, a certified frozen surface, only under an owner-approved pinned
    # exception. Until then even an explicit elevation fails closed on the
    # unknown capability -- never a self-grant.
    monkeypatch.setenv("ATLAS_CLI_ELEVATE_CAPS", "execution.observe")
    code, payload = _cli(
        "observe-execution", "--vault", str(vault), "--project", "harbor-api", "--repo", str(cloned)
    )
    assert code == EXIT_ERROR and payload["error"] == "AUTHZ_DENIED"
    assert "authz-unknown-capability" in str(payload["detail"])
    assert not (vault / "generated").exists()


def test_cli_proof_observation_flag_links_a_stored_receipt(
    cloned: Path, vault: Path, tmp_path: Path
) -> None:
    out = observe_execution(cloned, project_id="harbor-api")
    store_observation_receipt(vault, out.receipt)
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(json.dumps(out.identity.to_record()), encoding="utf-8")
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(out.receipt.to_record()), encoding="utf-8")
    atts_path = tmp_path / "atts.json"
    atts_path.write_text("[]", encoding="utf-8")
    code, payload = _cli(
        "proof",
        "OBS",
        "--vault",
        str(vault),
        "--project",
        "harbor-api",
        "--identity",
        str(identity_path),
        "--attestations",
        str(atts_path),
        "--observation",
        str(receipt_path),
        "--json",
    )
    assert code == EXIT_OK and payload["live_observation_wired"] is True
    assert payload["observation_id"] == out.receipt.observation_id
    code, payload = _cli(
        "proof",
        "OBS2",
        "--vault",
        str(vault),
        "--project",
        "harbor-api",
        "--observation",
        str(receipt_path),
        "--json",
    )
    assert code == EXIT_ERROR and payload["error"] == "PROOF_V2_INPUTS_INCOMPLETE"
