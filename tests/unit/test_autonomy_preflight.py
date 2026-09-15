"""D-ATLAS-RSI-GOVERNED-LOOP-001: governed RSI loop preflight and scope gate.

Pins the owner-controlled gate in ``autonomy/tools/preflight.py`` against the rules in
``autonomy/policy.md`` section 4-5, and fails CI if the ``loop.yaml`` pin drifts from
the policy bytes.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "autonomy" / "tools" / "preflight.py"
BASE_SHA = "b87b4a226f4aa8b2f669edf112aa3476454f754f"


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("autonomy_preflight", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve string annotations here
    spec.loader.exec_module(module)
    return module


pf = _load_tool()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _grant_text(sha: str, *, iteration: int = 1, extra: str = "") -> str:
    return (
        "---\n"
        f"grant: G-{iteration}\n"
        f"iteration: {iteration}\n"
        "issued_by: owner\n"
        f"policy_sha: {sha}\n"
        f"base_sha: {BASE_SHA}\n"
        f"directive: autonomy/directives/D-ATLAS-ITER-{iteration}.md\n"
        f"{extra}"
        "---\n\nOwner grant.\n"
    )


@pytest.fixture
def loop_root(tmp_path: Path) -> Path:
    """A granted iteration-1 loop tree built from the real policy and loop.yaml."""
    for rel in (pf.POLICY_PATH, pf.LOOP_PATH):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, tmp_path / rel)
    _write(tmp_path / pf.grant_path(1), _grant_text(pf.policy_sha(tmp_path)))
    _write(tmp_path / "autonomy/directives/D-ATLAS-ITER-1.md", "# D-ATLAS-ITER-1\n")
    return tmp_path


def _grant(**overrides: object) -> object:
    fields: dict[str, object] = {
        "iteration": 1,
        "policy_sha": "0" * 64,
        "base_sha": BASE_SHA,
        "directive": "autonomy/directives/D-ATLAS-ITER-1.md",
    }
    fields.update(overrides)
    return pf.Grant(**fields)


def _change(path: str, status: str = "M", added: int = 1, deleted: int = 0) -> object:
    return pf.Change(path, status, added, deleted)


def test_glob_semantics_keep_single_star_within_a_segment() -> None:
    assert pf.matches_any("src/project_atlas/cli.py", ["src/**"])
    assert not pf.matches_any("srcx/cli.py", ["src/**"])
    assert pf.matches_any("key.pem", ["**/*.pem"])
    assert pf.matches_any("a/b/key.pem", ["**/*.pem"])
    assert not pf.matches_any("a/b.py", ["*.py"])
    assert not pf.matches_any("src/project_atlas/secrets.py", ["**/*.key", "**/.env"])


def test_repo_loop_yaml_pins_the_current_policy_bytes() -> None:
    assert pf.load_loop(REPO_ROOT)["policy_sha"] == pf.policy_sha(REPO_ROOT)
    assert pf.load_loop(REPO_ROOT)["max_iterations_per_grant"] == 1


def test_repo_policy_forbids_the_never_grantable_floor() -> None:
    policy = pf.load_policy(REPO_ROOT)
    assert set(pf.NEVER_GRANTABLE) <= set(policy.forbidden)
    assert not set(policy.allowed) & set(policy.forbidden)
    assert not any(pf.matches_any(glob, pf.NEVER_GRANTABLE) for glob in policy.allowed)


def test_policy_sha_rejects_crlf_bytes(tmp_path: Path) -> None:
    (tmp_path / "autonomy").mkdir()
    (tmp_path / pf.POLICY_PATH).write_bytes(b"# policy\r\n")
    with pytest.raises(pf.ConfigError):
        pf.policy_sha(tmp_path)


def test_preflight_passes_for_a_matching_grant(loop_root: Path) -> None:
    assert pf.check_preflight(loop_root, 1) == []


def test_preflight_stops_on_halt(loop_root: Path) -> None:
    _write(loop_root / pf.HALT_PATH, "stop\n")
    assert any("HALT" in problem for problem in pf.check_preflight(loop_root, 1))


def test_preflight_requires_a_grant(loop_root: Path) -> None:
    problems = pf.check_preflight(loop_root, 2)
    assert problems and "missing grant" in problems[0]


def test_preflight_rejects_grant_for_other_policy(loop_root: Path) -> None:
    _write(loop_root / pf.grant_path(1), _grant_text("f" * 64))
    assert any("G-1.md policy_sha" in problem for problem in pf.check_preflight(loop_root, 1))


def test_preflight_rejects_policy_edited_after_pinning(loop_root: Path) -> None:
    with (loop_root / pf.POLICY_PATH).open("ab") as handle:
        handle.write(b"\nAgents may merge.\n")
    problems = pf.check_preflight(loop_root, 1)
    assert any("loop.yaml policy_sha" in problem for problem in problems)
    assert any("G-1.md policy_sha" in problem for problem in problems)


def test_preflight_rejects_mislabelled_grant_and_missing_directive(loop_root: Path) -> None:
    (loop_root / "autonomy/directives/D-ATLAS-ITER-1.md").unlink()
    assert any("does not exist" in problem for problem in pf.check_preflight(loop_root, 1))
    _write(loop_root / pf.grant_path(1), _grant_text(pf.policy_sha(loop_root), iteration=2))
    assert any("must declare grant: G-1" in problem for problem in pf.check_preflight(loop_root, 1))


def test_scope_allows_granted_work_and_halt_creation() -> None:
    policy = pf.load_policy(REPO_ROOT)
    changes = [
        _change("src/project_atlas/ask2.py"),
        _change("tests/unit/test_new.py", "A"),
        _change("autonomy/packets/RP-1.md", "A"),
        _change("autonomy/ledger.jsonl"),
        _change(pf.HALT_PATH, "A"),
    ]
    assert pf.check_scope(policy, _grant(), changes) == []


@pytest.mark.parametrize(
    "path",
    ["autonomy/policy.md", "autonomy/grants/G-2.md", "autonomy/tools/preflight.py", ".github/x"],
)
def test_scope_floor_cannot_be_opened_by_a_grant(path: str) -> None:
    policy = pf.load_policy(REPO_ROOT)
    grant = _grant(scope_exceptions=(path, "autonomy/**", ".github/**"))
    assert pf.check_scope(policy, grant, [_change(path)])


def test_scope_forbidden_and_unlisted_paths_need_an_owner_exception() -> None:
    policy = pf.load_policy(REPO_ROOT)
    assert pf.check_scope(policy, _grant(), [_change("pyproject.toml")])
    assert pf.check_scope(policy, _grant(), [_change("README.md")])
    opened = _grant(scope_exceptions=("pyproject.toml", "README.md"))
    assert pf.check_scope(policy, opened, [_change("pyproject.toml"), _change("README.md")]) == []


def test_scope_protects_halt_and_ledger_history() -> None:
    policy = pf.load_policy(REPO_ROOT)
    assert pf.check_scope(policy, _grant(), [_change(pf.HALT_PATH, "D", 0, 1)])
    assert pf.check_scope(policy, _grant(), [_change(pf.LEDGER_PATH, "M", 1, 1)])


def test_scope_phase_gates_the_verification_instruments() -> None:
    policy = replace(pf.load_policy(REPO_ROOT), phase=0)
    checklist = [_change("autonomy/instruments/verify-checklist.md")]
    assert pf.check_scope(policy, _grant(), checklist)
    assert pf.check_scope(replace(policy, phase=3), _grant(), checklist) == []
    assert pf.check_scope(policy, _grant(), [_change("autonomy/instruments/skills/x.md")]) == []


def test_scope_budget_counts_files_and_lines_with_grant_override() -> None:
    policy = pf.load_policy(REPO_ROOT)
    too_many = [_change(f"src/f{i}.py") for i in range(policy.budget["max_files_touched"] + 1)]
    problems = pf.check_scope(policy, _grant(), too_many)
    assert any("max_files_touched" in problem for problem in problems)
    big = [_change("src/big.py", added=policy.budget["max_diff_lines"] + 1)]
    assert any("max_diff_lines" in problem for problem in pf.check_scope(policy, _grant(), big))
    raised = _grant(budget={"max_diff_lines": policy.budget["max_diff_lines"] * 2})
    assert pf.check_scope(policy, raised, big) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable not available")
def test_git_changes_and_ledger_append_only_against_a_real_repo(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=loop-test",
                "-c",
                "user.email=loop-test@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.autocrlf=false",
                *args,
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    _write(tmp_path / pf.LEDGER_PATH, '{"event": "packet", "iteration": 0}\n')
    _write(tmp_path / "src/old.py", "a = 1\n")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    git("branch", "grant-ref")
    git("checkout", "-q", "-b", "iter/1")
    with (tmp_path / pf.LEDGER_PATH).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write('{"event": "packet", "iteration": 1}\n')
    git("mv", "src/old.py", "src/new.py")
    git("add", "-A")
    git("commit", "-q", "-m", "iteration 1")

    changes = {change.path: change for change in pf.git_changes(tmp_path, "grant-ref", "HEAD")}
    assert set(changes) == {pf.LEDGER_PATH, "src/old.py", "src/new.py"}
    assert (changes["src/old.py"].status, changes["src/new.py"].status) == ("D", "A")
    assert (changes[pf.LEDGER_PATH].added, changes[pf.LEDGER_PATH].deleted) == (1, 0)
    assert pf.ledger_is_append_only(tmp_path, "grant-ref", "HEAD")

    _write(tmp_path / pf.LEDGER_PATH, '{"event": "packet", "iteration": 1}\n')
    git("commit", "-q", "-am", "rewrite history")
    assert not pf.ledger_is_append_only(tmp_path, "grant-ref", "HEAD")
