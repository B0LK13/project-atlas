"""ULT-01b-1 — execution observation: scripted-runner unit tests + proof v2 linkage."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from atlas_contracts.execution_identity import seal_execution_identity
from atlas_contracts.observation_receipt import seal_observation_receipt
from project_atlas.atlas3.contracts import Atlas3Error
from project_atlas.atlas3.proof import PROOF_STAGES, evaluate_proof, evaluate_proof_v2
from project_atlas.execution_observation import (
    ARCH_NORMALIZATION,
    DECLARED_TOOLCHAIN,
    CommandResult,
    EnvironmentObservation,
    ObservationError,
    ToolchainObservation,
    build_child_env,
    load_stored_receipt,
    observe_environment,
    observe_execution,
    observe_git,
    observe_toolchain,
    receipt_locator,
    resolve_executable,
    store_observation_receipt,
)
from project_atlas.execution_observation.git import _normalize_remote
from project_atlas.execution_observation.host import observe_observer_version

HEAD = "a" * 40
HTREE = "b" * 40
BASE = "1" * 40
BTREE = "2" * 40
GIT = Path("/usr/bin/git")
ENV = EnvironmentObservation("OBSERVED", "Linux", "x86_64", "3.12.14", "x86_64", None)
TOOLS = ToolchainObservation("OBSERVED", (("git", "2.53.0"),), ("git",), (), None)


class ScriptedRunner:
    """Answers git argv by matching the sub-command; records every call."""

    def __init__(self, root: Path, **overrides: Any) -> None:
        self.root = root
        self.calls: list[list[str]] = []
        self.answers: dict[str, Any] = {
            "--version": "git version 2.53.0\n",
            "--is-inside-work-tree": "true\n",
            "--show-toplevel": f"{root}\n",
            "--is-shallow-repository": "false\n",
            "status": "",
            "HEAD^{commit}": f"{HEAD}\n",
            "HEAD^{tree}": f"{HTREE}\n",
            "origin/main^{commit}": f"{BASE}\n",
            "origin/main^{tree}": f"{BTREE}\n",
            "get-url": "https://github.com/B0LK13/project-atlas.git\n",
        }
        self.answers.update(overrides)

    def run(self, argv: Sequence[str], *, cwd: Path, timeout: float) -> CommandResult:
        self.calls.append(list(argv))
        assert argv[0] == str(GIT) and argv[1] == "-C" and cwd == self.root
        assert 0 < timeout <= 60
        for key, answer in self.answers.items():
            if key in argv:
                if isinstance(answer, CommandResult):
                    return answer
                if isinstance(answer, Exception):
                    raise answer
                return CommandResult(returncode=0, stdout=str(answer))
        return CommandResult(returncode=128, stdout="")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    return root.resolve()


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    (v / "projects" / "harbor-api").mkdir(parents=True)
    return v


def observe(repo: Path, runner: ScriptedRunner | None = None, **kw: Any) -> Any:
    return observe_execution(
        repo,
        project_id="harbor-api",
        runner=runner or ScriptedRunner(repo),
        git_executable=GIT,
        environment=kw.pop("environment", ENV),
        toolchain=kw.pop("toolchain", TOOLS),
        observer_version=kw.pop("observer_version", ("2.0.0", "OBSERVED")),
        **kw,
    )


# ------------------------------------------------------------------ runner


def test_child_env_is_constructed_not_inherited() -> None:
    env = build_child_env(
        {
            "PATH": "/usr/bin",
            "HOME": "/h",
            "GIT_DIR": "/elsewhere/.git",
            "GIT_WORK_TREE": "/elsewhere",
            "GIT_CONFIG_GLOBAL": "/x",
            "AWS_SECRET_ACCESS_KEY": "nope",
            "TEMP": "/t",
            "BAD": "a\x00b",
        }
    )
    assert env["PATH"] == "/usr/bin" and env["HOME"] == "/h" and env["TEMP"] == "/t"
    assert not any(
        key.startswith("GIT_") and key not in ("GIT_TERMINAL_PROMPT", "GIT_OPTIONAL_LOCKS")
        for key in env
    )
    assert "AWS_SECRET_ACCESS_KEY" not in env and "BAD" not in env
    assert env["LC_ALL"] == "C" and env["GIT_TERMINAL_PROMPT"] == "0"


def test_resolve_executable_refuses_wrappers_on_windows_and_bad_names(tmp_path: Path) -> None:
    exe = tmp_path / "git.exe"
    exe.write_bytes(b"MZ")
    cmd = tmp_path / "git.cmd"
    cmd.write_text("@echo off\n")
    assert resolve_executable("git", which=lambda _n: str(exe), os_name="nt") == exe.resolve()
    with pytest.raises(ObservationError) as excinfo:
        resolve_executable("git", which=lambda _n: str(cmd), os_name="nt")
    assert excinfo.value.code == "GIT_EXECUTABLE_WRAPPER_REFUSED"
    assert resolve_executable("git", which=lambda _n: str(cmd), os_name="posix") == cmd.resolve()
    with pytest.raises(ObservationError) as excinfo:
        resolve_executable("git", which=lambda _n: None)
    assert excinfo.value.code == "GIT_EXECUTABLE_UNAVAILABLE"
    for bad in ("../git", "git/x", "-git", ""):
        with pytest.raises(ObservationError) as excinfo:
            resolve_executable(bad, which=lambda _n: str(exe))
        assert excinfo.value.code == "EXECUTABLE_NAME_INVALID"
    with pytest.raises(ObservationError) as excinfo:
        resolve_executable("git", which=lambda _n: str(tmp_path))
    assert excinfo.value.code == "GIT_EXECUTABLE_UNAVAILABLE"


# ------------------------------------------------------------------ git


def test_git_observation_happy_path_records_methods_not_urls(repo: Path) -> None:
    runner = ScriptedRunner(repo)
    obs = observe_git(repo, runner=runner, git=GIT)
    assert (obs.repository, obs.base_head, obs.base_tree) == (
        "github.com/b0lk13/project-atlas",
        BASE,
        BTREE,
    )
    assert (obs.candidate_head, obs.candidate_tree, obs.git_version) == (HEAD, HTREE, "2.53.0")
    assert obs.shallow is False and obs.worktree_clean is True
    assert obs.base_ref == "origin/main" and obs.remote_name == "origin"
    assert all("://" not in ref and "@" not in ref for ref in obs.method_refs)
    argv_flat = [part for call in runner.calls for part in call]
    assert "--end-of-options" in argv_flat and "--no-optional-locks" in argv_flat
    assert not any(part.startswith("--force") for part in argv_flat)


def test_dirty_worktree_refuses_before_any_pin_is_read(repo: Path) -> None:
    runner = ScriptedRunner(repo, status=" M a.txt\n")
    with pytest.raises(ObservationError) as excinfo:
        observe_git(repo, runner=runner, git=GIT)
    assert excinfo.value.code == "WORKTREE_NOT_CLEAN"
    assert not any("rev-parse" in call and "--verify" in call for call in runner.calls)


@pytest.mark.parametrize(
    "answer",
    ["abc1234\n", HEAD.upper() + "\n", "f" * 64 + "\n", "HEAD is at aaaa\n", "\n"],
)
def test_non_canonical_pins_are_refused(repo: Path, answer: str) -> None:
    with pytest.raises(ObservationError) as excinfo:
        observe_git(repo, runner=ScriptedRunner(repo, **{"HEAD^{commit}": answer}), git=GIT)
    assert excinfo.value.code == "PIN_INVALID"


def test_missing_base_ref_is_a_distinct_refusal_and_override_is_recorded(repo: Path) -> None:
    runner = ScriptedRunner(repo, **{"origin/main^{commit}": CommandResult(128, "")})
    with pytest.raises(ObservationError) as excinfo:
        observe_git(repo, runner=runner, git=GIT)
    assert excinfo.value.code == "BASE_REF_UNOBSERVABLE"
    runner = ScriptedRunner(
        repo, **{"upstream/dev^{commit}": f"{BASE}\n", "upstream/dev^{tree}": f"{BTREE}\n"}
    )
    obs = observe_git(repo, runner=runner, git=GIT, base_ref="upstream/dev")
    assert obs.base_ref == "upstream/dev" and obs.remote_name == "upstream"
    for bad in ("-x", "a..b", "a b", "x" * 129, "ref\n"):
        with pytest.raises(ObservationError) as excinfo:
            observe_git(repo, runner=ScriptedRunner(repo), git=GIT, base_ref=bad)
        assert excinfo.value.code == "BASE_REF_INVALID"


def test_timeouts_and_failures_are_coded_not_raised_raw(repo: Path) -> None:
    runner = ScriptedRunner(repo, **{"--version": CommandResult(-1, "", timed_out=True)})
    with pytest.raises(ObservationError) as excinfo:
        observe_git(repo, runner=runner, git=GIT)
    assert excinfo.value.code == "GIT_OBSERVATION_TIMEOUT"
    runner = ScriptedRunner(repo, **{"--is-inside-work-tree": "false\n"})
    with pytest.raises(ObservationError) as excinfo:
        observe_git(repo, runner=runner, git=GIT)
    assert excinfo.value.code == "GIT_UNOBSERVABLE"
    runner = ScriptedRunner(repo, **{"--show-toplevel": f"{repo.parent}\n"})
    with pytest.raises(ObservationError) as excinfo:
        observe_git(repo, runner=runner, git=GIT)
    assert excinfo.value.code == "GIT_ROOT_MISMATCH"
    runner = ScriptedRunner(repo, **{"--is-shallow-repository": "maybe\n"})
    with pytest.raises(ObservationError) as excinfo:
        observe_git(repo, runner=runner, git=GIT)
    assert excinfo.value.code == "GIT_UNOBSERVABLE"
    obs = observe_git(
        repo, runner=ScriptedRunner(repo, **{"--is-shallow-repository": "true\n"}), git=GIT
    )
    assert obs.shallow is True


def test_unparsable_git_version_is_absent_not_fatal(repo: Path) -> None:
    obs = observe_git(
        repo, runner=ScriptedRunner(repo, **{"--version": "git version weird build\n"}), git=GIT
    )
    assert obs.git_version is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/B0LK13/project-atlas.git", "github.com/b0lk13/project-atlas"),
        ("git@github.com:B0LK13/project-atlas.git", "github.com/b0lk13/project-atlas"),
        ("ssh://git@github.com/B0LK13/project-atlas.git", "github.com/b0lk13/project-atlas"),
        ("https://github.com/b0lk13/project-atlas/", "github.com/b0lk13/project-atlas"),
    ],
)
def test_remote_urls_normalize_to_a_schemeless_identity(url: str, expected: str) -> None:
    assert _normalize_remote(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://x-access-token:ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@github.com/b0lk13/project-atlas.git",
        "https://token@github.com/b0lk13/project-atlas.git",
        "https://user:pass@github.com/b0lk13/project-atlas",
        "ssh://deploy@github.com/b0lk13/project-atlas.git",
        "",
        "https://github.com/../x",
        "file:///tmp/x\n",
    ],
)
def test_remote_urls_with_userinfo_or_junk_are_refused_without_echo(url: str) -> None:
    with pytest.raises(ObservationError) as excinfo:
        _normalize_remote(url)
    assert excinfo.value.code == "REPO_IDENTITY_UNVERIFIABLE"
    assert "github.com" not in str(excinfo.value) and "ghp_" not in str(excinfo.value)


def test_secret_shaped_remote_url_never_reaches_an_error_or_a_receipt(repo: Path) -> None:
    secret_url = "https://AKIAIOSFODNN7EXAMPLE@github.com/b0lk13/project-atlas.git\n"
    runner = ScriptedRunner(repo, **{"get-url": secret_url})
    with pytest.raises(ObservationError) as excinfo:
        observe(repo, runner)
    assert excinfo.value.code == "REPO_IDENTITY_UNVERIFIABLE"
    assert "AKIA" not in str(excinfo.value)


# ------------------------------------------------------------------ host


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "x86_64", ("Linux", "x86_64")),
        ("Windows", "AMD64", ("Windows", "x86_64")),
        ("Darwin", "arm64", ("Darwin", "aarch64")),
        ("Linux", "aarch64", ("Linux", "aarch64")),
    ],
)
def test_environment_normalizes_to_the_canonical_vocabulary(
    system: str, machine: str, expected: tuple[str, str]
) -> None:
    env = observe_environment(
        system=lambda: system, machine=lambda: machine, version_info=(3, 12, 14)
    )
    assert env.status == "OBSERVED" and (env.os, env.arch, env.python) == (*expected, "3.12.14")
    assert env.arch_raw == machine


@pytest.mark.parametrize(
    ("system", "machine", "reason"),
    [
        ("Linux", "riscv64", "ARCH_UNMAPPED"),
        ("Plan9", "x86_64", "OS_UNMAPPED"),
        ("Linux", "", "ARCH_UNMAPPED"),
    ],
)
def test_unmapped_environment_stays_unknown_not_guessed(
    system: str, machine: str, reason: str
) -> None:
    env = observe_environment(
        system=lambda: system, machine=lambda: machine, version_info=(3, 12, 1)
    )
    assert env.status == "UNKNOWN" and env.reason == reason
    assert env.os is None and env.arch is None and env.python is None


def test_environment_platform_failure_is_unknown() -> None:
    def boom() -> str:
        raise RuntimeError("no platform")

    env = observe_environment(system=boom, machine=lambda: "x86_64")
    assert env.status == "UNKNOWN" and env.reason == "PLATFORM_UNOBSERVABLE"


def test_arch_table_covers_the_owner_vocabulary_and_nothing_secret() -> None:
    assert {ARCH_NORMALIZATION[k] for k in ("amd64", "x86_64", "arm64", "aarch64")} == {
        "x86_64",
        "aarch64",
    }
    assert sorted(DECLARED_TOOLCHAIN) == list(DECLARED_TOOLCHAIN)
    assert "git" in DECLARED_TOOLCHAIN and "project-atlas" in DECLARED_TOOLCHAIN


def test_toolchain_uses_metadata_only_and_records_absence() -> None:
    versions = {"pydantic": "2.13.5", "ruff": "0.16.6", "weird": "1 .0"}

    def version_of(name: str) -> str | None:
        return versions.get(name)

    tools = observe_toolchain(
        declared=("ruff", "pydantic", "pytest", "git", "weird"),
        version_of=version_of,
        git_version="2.53.0",
    )
    assert tools.status == "OBSERVED"
    assert tools.tools == (("git", "2.53.0"), ("pydantic", "2.13.5"), ("ruff", "0.16.6"))
    assert tools.absent == ("pytest", "weird")
    assert tools.declared == ("git", "pydantic", "pytest", "ruff", "weird")


def test_toolchain_without_any_observable_tool_is_unknown_and_never_consults_dunder_version() -> (
    None
):
    def failing(name: str) -> str | None:
        raise RuntimeError("metadata unavailable")

    tools = observe_toolchain(declared=("pydantic",), version_of=failing, git_version=None)
    assert tools.status == "UNKNOWN" and tools.reason == "TOOLCHAIN_UNOBSERVABLE"
    import pydantic

    assert hasattr(pydantic, "__version__")  # the attribute exists and was not used
    assert observe_observer_version(version_of=failing) == ("UNKNOWN", "UNKNOWN")
    assert observe_observer_version(version_of=lambda _n: "2.0.0") == ("2.0.0", "OBSERVED")


# ------------------------------------------------------------------ compose / seal


def test_observation_seals_identity_and_receipt_through_the_canonical_paths(repo: Path) -> None:
    out = observe(repo)
    assert out.identity.bindings() == {
        "object_bound": True,
        "environment_bound": True,
        "toolchain_bound": True,
        "agent_bound": False,
        "context_bound": False,
        "capabilities_bound": False,
    }
    assert out.receipt.identity_digest == out.identity.identity_digest
    assert out.receipt.identity == out.identity
    assert out.receipt.observed.source.status == "OBSERVED"
    assert out.receipt.observed.agent.status == "UNKNOWN"
    assert out.receipt.observed_is_current is False
    record = json.dumps(out.receipt.to_record())
    assert "B0LK13" not in record and "https://" not in record and str(repo) not in record
    assert "/usr/bin/git" not in record
    assert out.receipt.observed.source.git_executable_path_digest is not None


def test_observation_is_deterministic_across_calls(repo: Path) -> None:
    a = observe(repo)
    b = observe(repo)
    assert a.identity.identity_digest == b.identity.identity_digest
    assert a.receipt.content_hash == b.receipt.content_hash
    assert a.receipt.to_record() == b.receipt.to_record()


def test_unknown_environment_and_toolchain_seal_honestly(repo: Path) -> None:
    out = observe(
        repo,
        environment=EnvironmentObservation("UNKNOWN", None, None, None, "riscv64", "ARCH_UNMAPPED"),
        toolchain=ToolchainObservation("UNKNOWN", (), ("git",), ("git",), "TOOLCHAIN_UNOBSERVABLE"),
        observer_version=("UNKNOWN", "UNKNOWN"),
    )
    assert out.identity.environment.status == "UNKNOWN"
    assert out.identity.toolchain.status == "UNKNOWN"
    assert out.receipt.observed.environment.reason == "ARCH_UNMAPPED"
    assert out.receipt.observed.environment.arch_raw == "riscv64"
    assert out.receipt.observed.toolchain.reason == "TOOLCHAIN_UNOBSERVABLE"
    assert out.receipt.observer.version == "UNKNOWN"


def test_secret_shaped_project_id_never_reaches_a_receipt(repo: Path) -> None:
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(
            repo,
            project_id="AKIAIOSFODNN7EXAMPLE",
            runner=ScriptedRunner(repo),
            git_executable=GIT,
            environment=ENV,
            toolchain=TOOLS,
            observer_version=("2.0.0", "OBSERVED"),
        )
    assert excinfo.value.code == "OBSERVATION_SECRET_FORBIDDEN"
    assert "AKIA" not in str(excinfo.value)


def test_unsafe_project_id_is_refused_before_observation(repo: Path) -> None:
    runner = ScriptedRunner(repo)
    with pytest.raises(ObservationError) as excinfo:
        observe_execution(repo, project_id="../x", runner=runner, git_executable=GIT)
    assert excinfo.value.code == "UNSAFE_PROJECT_ID" and runner.calls == []


# ------------------------------------------------------------------ store


def test_store_writes_content_addressed_receipt_and_loads_it_back(repo: Path, vault: Path) -> None:
    out = observe(repo)
    path = store_observation_receipt(vault, out.receipt)
    assert path == (vault / receipt_locator("harbor-api", out.identity.identity_digest)).resolve()
    text = path.read_text(encoding="utf-8")
    assert text.isascii() and "\r" not in text
    assert load_stored_receipt(vault, "harbor-api", out.identity.identity_digest) == out.receipt
    assert load_stored_receipt(vault, "harbor-api", "f" * 64) is None
    # same receipt again: idempotent, not a collision
    assert store_observation_receipt(vault, out.receipt) == path


def test_store_refuses_symlinked_components_and_foreign_digests(repo: Path, vault: Path) -> None:
    out = observe(repo)
    base = vault / "generated" / "ops" / "atlas3"
    (base / "observation").mkdir(parents=True)
    outside = vault.parent / "outside"
    outside.mkdir()
    try:
        (base / "observation" / "v1").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    with pytest.raises(ObservationError) as excinfo:
        store_observation_receipt(vault, out.receipt)
    assert excinfo.value.code == "OBSERVATION_LOCATOR_UNSAFE"
    assert list(outside.iterdir()) == []
    (base / "observation" / "v1").unlink()
    target = vault / receipt_locator("harbor-api", out.identity.identity_digest)
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"identity_digest": "f" * 64}), encoding="utf-8")
    with pytest.raises(ObservationError) as excinfo:
        store_observation_receipt(vault, out.receipt)
    assert excinfo.value.code == "OBSERVATION_LOCATOR_COLLISION"
    assert json.loads(target.read_text(encoding="utf-8")) == {"identity_digest": "f" * 64}
    with pytest.raises((ObservationError, ValueError)):
        load_stored_receipt(vault, "harbor-api", out.identity.identity_digest)


def test_store_requires_a_known_project(repo: Path, tmp_path: Path) -> None:
    out = observe(repo)
    empty = tmp_path / "empty-vault"
    empty.mkdir()
    with pytest.raises(Atlas3Error) as excinfo:
        store_observation_receipt(empty, out.receipt)
    assert excinfo.value.code == "UNKNOWN_PROJECT"


# ------------------------------------------------------------------ proof v2 linkage


def _chain(ident: Any) -> list[dict[str, Any]]:
    from atlas_contracts.attestation import seal_evidence_attestation

    stage_type = {
        "TASK": "TASK_RECORD",
        "IMPLEMENTATION": "IMPLEMENTATION_RECORD",
        "TESTS": "TEST_RESULT",
        "CI": "CI_RESULT",
        "INDEPENDENT_VERIFICATION": "VERIFICATION_RESULT",
        "ADV": "ADVERSARIAL_RESULT",
        "INTEGRATION": "INTEGRATION_RESULT",
        "POST_MERGE": "POST_MERGE_RESULT",
    }
    out = []
    for stage in PROOF_STAGES:
        independent = stage in {"INDEPENDENT_VERIFICATION", "ADV"}
        out.append(
            seal_evidence_attestation(
                {
                    "project_id": "harbor-api",
                    "execution_identity_digest": ident.identity_digest,
                    "stage": stage,
                    "evidence_type": stage_type[stage],
                    "producer": {
                        "kind": "human" if independent else "tool",
                        "name": "v" if independent else "pytest",
                        "version": "1",
                        "independent_of_implementer": independent,
                    },
                    "object": {"head": HEAD, "tree": HTREE},
                    "result": {"status": "PASS", "summary": {"passed": 1}},
                    "dependencies": ["DEP_HEAD", "DEP_TREE"],
                }
            ).to_record()
        )
    return out


def test_proof_v2_links_a_verified_receipt_and_stays_false_without_one(
    repo: Path, vault: Path
) -> None:
    out = observe(repo)
    plain = evaluate_proof_v2(
        vault,
        "P",
        project_id="harbor-api",
        identity=out.identity,
        attestations=_chain(out.identity),
    )
    assert plain["live_observation_wired"] is False and plain["observation_id"] is None
    linked = evaluate_proof_v2(
        vault,
        "L",
        project_id="harbor-api",
        identity=out.identity.to_record(),
        attestations=_chain(out.identity),
        observation_receipt=out.receipt.to_record(),
    )
    assert linked["live_observation_wired"] is True
    assert linked["observation_id"] == out.receipt.observation_id
    assert linked["observed_is_current"] is False
    assert linked["chain_status"] == "PROVEN"
    assert linked["merge_authorization"] == "NOT_GRANTED"


def test_proof_v2_refuses_a_receipt_for_another_identity_or_tampered(
    repo: Path, vault: Path
) -> None:
    out = observe(repo)
    other_record = out.identity.body()
    other_record["environment"] = {"status": "UNKNOWN", "os": None, "arch": None, "python": None}
    other = seal_execution_identity(other_record)
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault,
            "X",
            project_id="harbor-api",
            identity=other,
            attestations=[],
            observation_receipt=out.receipt,
        )
    assert excinfo.value.code == "OBSERVATION_IDENTITY_MISMATCH"
    tampered = out.receipt.to_record()
    tampered["observed"]["source"]["shallow"] = True
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault,
            "X",
            project_id="harbor-api",
            identity=out.identity,
            attestations=[],
            observation_receipt=tampered,
        )
    assert excinfo.value.code == "RECEIPT_HASH_MISMATCH"
    with pytest.raises(Atlas3Error) as excinfo:
        evaluate_proof_v2(
            vault,
            "X",
            project_id="harbor-api",
            identity=out.identity,
            attestations=[],
            observation_receipt="junk",
        )
    assert excinfo.value.code == "OBSERVATION_RECEIPT_MALFORMED"
    smuggled = out.receipt.to_record()
    smuggled["merge_authorization"] = "GRANTED"
    with pytest.raises(Atlas3Error):
        evaluate_proof_v2(
            vault,
            "X",
            project_id="harbor-api",
            identity=out.identity,
            attestations=[],
            observation_receipt=smuggled,
        )
    assert not (vault / "generated" / "ops" / "atlas3" / "proof" / "v2" / "X").exists()


def test_receipt_cannot_make_a_stage_present(repo: Path, vault: Path) -> None:
    out = observe(repo)
    report = evaluate_proof_v2(
        vault,
        "E",
        project_id="harbor-api",
        identity=out.identity,
        attestations=[],
        observation_receipt=out.receipt,
    )
    assert report["chain_status"] == "UNKNOWN" and report["present_count"] == 0
    assert report["live_observation_wired"] is True


def test_proof_v1_is_untouched_by_the_linkage(vault: Path) -> None:
    report = evaluate_proof(vault, "V1", project_id="harbor-api")
    assert report["schema"] == "atlas3.agent-proof.v1" and "live_observation_wired" not in report


# ------------------------------------------------------------------ boundaries


def test_observer_reads_no_clock_and_atlas3_stays_subprocess_free() -> None:
    root = Path(__file__).parents[2] / "src" / "project_atlas"
    clock = re.compile(r"datetime\.now|time\.time\(|utcnow|time\.monotonic")
    for path in (root / "execution_observation").glob("*.py"):
        assert not clock.search(path.read_text(encoding="utf-8")), path.name
    for path in (root / "atlas3").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import subprocess" not in text and "from subprocess" not in text, path.name
    contract = Path(__file__).parents[2] / "src" / "atlas_contracts" / "observation_receipt.py"
    assert "datetime" not in contract.read_text(encoding="utf-8")


def test_receipt_helper_seal_mode_does_not_bypass_identity_verification(repo: Path) -> None:
    out = observe(repo)
    body = out.receipt.body()
    body["identity"]["identity_digest"] = "0" * 64
    body["identity"]["run_id"] = "run-" + "0" * 16
    with pytest.raises(Exception) as excinfo:
        seal_observation_receipt(body)
    assert "IDENTITY_DIGEST_MISMATCH" in str(excinfo.value)
