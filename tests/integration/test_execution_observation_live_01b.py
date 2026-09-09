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


def _git(*args: str, cwd: Path) -> str:
    assert GIT is not None
    done = subprocess.run(
        [GIT, *args], cwd=str(cwd), env=_ENV, capture_output=True, text=True, timeout=60, check=True
    )
    return done.stdout.strip()


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
