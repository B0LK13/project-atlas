"""Regressions for hardened A1 acceptance (t003d false-positive closed).

PRE_EXISTING_DIRT != SUCCESS
EMPTY_OUTPUT != SCOPED_DIFF
ACCEPTANCE != INDEPENDENT_VERIFICATION
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from project_atlas.orchestration.program.acceptance import evaluate_check
from project_atlas.orchestration.program.models import AcceptanceCheck, ProgramTask
from project_atlas.orchestration.program.profiles import AgentProfile
from project_atlas.orchestration.program.semantic_acceptance import (
    BaselineManifest,
    capture_baseline_manifest,
    evaluate_semantic_acceptance,
)


def _profile() -> AgentProfile:
    return AgentProfile.model_validate(
        {
            "profile_id": "test-local",
            "description": "test",
            "agent_id": "tester",
            "adapter": "local-command",
            "capabilities": ["IMPLEMENT"],
            "allowed_mutation_prefixes": [],
            "credential": "NOT_APPLICABLE",
            "adapter_options": {"argv": ["/bin/true"]},
        }
    )


def _git_init(workspace: Path) -> None:
    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t003e@example.com"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "t003e"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )
    (workspace / "README").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )


def _task(allowlist: tuple[str, ...]) -> ProgramTask:
    return ProgramTask(
        task_id="prime-a1",
        title="A1",
        instruction="implement kernel readiness",
        profile_ref="prime-worker",
        mutation_paths=allowlist,
        surface_id="surface-prime-kernel-a1-slice-002",
        surface_semantic="PRIME_A1_KERNEL_READINESS",
        requires_independent_verification=True,
        verifier_profile_ref="reviewer",
        acceptance=(
            AcceptanceCheck(
                check_id="candidate-changed",
                kind="GIT_TREE_CHANGED",
                description="scoped change",
                path=allowlist[0],
            ),
        ),
    )


PROD = "src/project_atlas/orchestration/program/control.py"
TESTS = "tests/unit/test_orchestration_program_control.py"
ALLOW = (PROD, TESTS)


def _seed_allowlist(workspace: Path) -> None:
    for relative in ALLOW:
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# baseline {relative}\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "allowlist seed"],
        cwd=workspace,
        check=True,
        capture_output=True,
    )


def test_git_tree_changed_ignores_preexisting_out_of_scope_dirt(tmp_path: Path) -> None:
    """Only pre-existing dirt → FAIL when path is scoped (t003d shape)."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _git_init(workspace)
    _seed_allowlist(workspace)
    # Pre-existing dirt outside allowlist — exactly t003d porcelain shape.
    (workspace / "docs").mkdir()
    (workspace / "docs" / "LEDGER.md").write_text("dirty\n", encoding="utf-8")
    (workspace / ".prime-config").mkdir()
    (workspace / ".prime-config" / "x").write_text("y\n", encoding="utf-8")
    check = AcceptanceCheck(
        check_id="candidate-changed",
        kind="GIT_TREE_CHANGED",
        description="scoped",
        path=PROD,
    )
    result = evaluate_check(check, workspace=workspace, profile=_profile())
    assert result.passed is False
    assert "in scope" in result.detail


def test_empty_output_and_no_scoped_diff_fails(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _git_init(workspace)
    _seed_allowlist(workspace)
    (workspace / "docs").mkdir()
    (workspace / "docs" / "LEDGER.md").write_text("dirt\n", encoding="utf-8")
    profile = _profile()
    baseline = capture_baseline_manifest(
        workspace=workspace,
        profile=profile,
        attempt_id="t003d.prime-a1.run.1.1570964f",
        allowlist=ALLOW,
    )
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "t003d.prime-a1.run.1.1570964f.child-admission.jsonl").write_text(
        "", encoding="utf-8"
    )
    (evidence / "t003d.prime-a1.run.1.1570964f.prime-daemon.json").write_text(
        json.dumps({"child_registry": []}), encoding="utf-8"
    )
    (evidence / "t003d.prime-a1.run.1.1570964f.prime-daemon.jsonl").write_text(
        json.dumps(
            {
                "command": "get_session_stats",
                "data": {"toolCalls": 0, "assistantMessages": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sessions = workspace / ".prime-sessions"
    sessions.mkdir()
    (sessions / "t003d.prime-a1.run.1.1570964f.jsonl").write_text(
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [{"type": "text", "text": ""}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result = evaluate_semantic_acceptance(
        _task(ALLOW),
        workspace=workspace,
        profile=profile,
        baseline=baseline,
        evidence_root=evidence,
        attempt_id="t003d.prime-a1.run.1.1570964f",
        require_reviewer=True,
    )
    assert result.passed is False
    by_id = {c.check_id: c for c in result.checks}
    assert by_id["scoped-diff-vs-baseline"].passed is False
    assert by_id["worker-output-nonempty"].passed is False
    assert by_id["native-child-bound"].passed is False
    assert by_id["independent-reviewer"].passed is False
    assert "VERIFYING/BLOCKED" in by_id["independent-reviewer"].detail


def test_change_outside_allowlist_fails(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _git_init(workspace)
    _seed_allowlist(workspace)
    profile = _profile()
    baseline = capture_baseline_manifest(
        workspace=workspace, profile=profile, attempt_id="a1", allowlist=ALLOW
    )
    (workspace / "policy.json").write_text("{}\n", encoding="utf-8")
    result = evaluate_semantic_acceptance(
        _task(ALLOW),
        workspace=workspace,
        profile=profile,
        baseline=baseline,
        evidence_root=tmp_path / "evidence",
        attempt_id="a1",
        require_reviewer=False,
    )
    assert result.passed is False
    by_id = {c.check_id: c for c in result.checks}
    assert by_id["allowlist-only-mutations"].passed is False


def test_tests_without_production_change_fails(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _git_init(workspace)
    _seed_allowlist(workspace)
    profile = _profile()
    baseline = capture_baseline_manifest(
        workspace=workspace, profile=profile, attempt_id="a1", allowlist=ALLOW
    )
    (workspace / TESTS).write_text(
        "# updated tests only\n_kernel_readiness_status\nBLOCKED\nREADY\nUNKNOWN\n",
        encoding="utf-8",
    )
    result = evaluate_semantic_acceptance(
        _task(ALLOW),
        workspace=workspace,
        profile=profile,
        baseline=baseline,
        evidence_root=tmp_path / "evidence",
        attempt_id="a1",
        require_reviewer=False,
    )
    assert result.passed is False
    by_id = {c.check_id: c for c in result.checks}
    assert by_id["tests-without-production-change"].passed is False


def test_missing_native_child_fails(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _git_init(workspace)
    _seed_allowlist(workspace)
    profile = _profile()
    baseline = capture_baseline_manifest(
        workspace=workspace, profile=profile, attempt_id="a1", allowlist=ALLOW
    )
    (workspace / PROD).write_text(
        "def _kernel_readiness_status(diagnostic):\n"
        "    if diagnostic.get('status') == 'kernel_start_failure':\n"
        "        return 'BLOCKED'\n"
        "    if diagnostic.get('status') == 'tool_result_received' and not diagnostic.get('isError'):\n"
        "        return 'READY'\n"
        "    return 'UNKNOWN'\n"
        "kernel_readiness = _kernel_readiness_status\n",
        encoding="utf-8",
    )
    (workspace / TESTS).write_text(
        "def test_kernel_readiness():\n"
        "    assert _kernel_readiness_status\n"
        "    assert 'BLOCKED' and 'READY' and 'UNKNOWN'\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "a1.prime-daemon.json").write_text(
        json.dumps({"child_registry": []}), encoding="utf-8"
    )
    result = evaluate_semantic_acceptance(
        _task(ALLOW),
        workspace=workspace,
        profile=profile,
        baseline=baseline,
        evidence_root=evidence,
        attempt_id="a1",
        require_reviewer=False,
    )
    assert result.passed is False
    assert {c.check_id: c for c in result.checks}["native-child-bound"].passed is False


def test_missing_reviewer_never_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _git_init(workspace)
    _seed_allowlist(workspace)
    profile = _profile()
    baseline = BaselineManifest(
        attempt_id="a1",
        workspace=str(workspace),
        allowlist=ALLOW,
        path_sha256={p: "0" * 64 for p in ALLOW},
        pre_existing_porcelain=(),
        head_sha="deadbeef",
    )
    result = evaluate_semantic_acceptance(
        _task(ALLOW),
        workspace=workspace,
        profile=profile,
        baseline=baseline,
        evidence_root=tmp_path / "evidence",
        attempt_id="a1",
        reviewer_verdict=None,
        require_reviewer=True,
    )
    assert result.passed is False
    review = {c.check_id: c for c in result.checks}["independent-reviewer"]
    assert review.passed is False
    assert "VERIFYING/BLOCKED" in review.detail


def test_valid_scoped_patch_tests_child_reviewer_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    _git_init(workspace)
    _seed_allowlist(workspace)
    profile = _profile()
    baseline = capture_baseline_manifest(
        workspace=workspace, profile=profile, attempt_id="a1", allowlist=ALLOW
    )
    (workspace / PROD).write_text(
        "def _kernel_readiness_status(diagnostic):\n"
        "    status = (diagnostic or {}).get('status')\n"
        "    if status == 'kernel_start_failure':\n"
        "        return 'BLOCKED'\n"
        "    if status == 'tool_result_received' and not (diagnostic or {}).get('isError'):\n"
        "        return 'READY'\n"
        "    return 'UNKNOWN'\n\n"
        "# expose kernel_readiness on last_attempt\n",
        encoding="utf-8",
    )
    (workspace / TESTS).write_text(
        "from project_atlas.orchestration.program.control import _kernel_readiness_status\n\n"
        "def test_blocked():\n    assert _kernel_readiness_status({'status':'kernel_start_failure'}) == 'BLOCKED'\n"
        "def test_ready():\n    assert _kernel_readiness_status({'status':'tool_result_received','isError':False}) == 'READY'\n"
        "def test_unknown():\n    assert _kernel_readiness_status({}) == 'UNKNOWN'\n",
        encoding="utf-8",
    )
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "a1.prime-daemon.json").write_text(
        json.dumps(
            {
                "child_registry": [
                    {"id": "child-1", "message": "attributable ok", "artifact": "art-1"}
                ]
            }
        ),
        encoding="utf-8",
    )
    (evidence / "a1.prime-daemon.jsonl").write_text(
        json.dumps({"command": "get_session_stats", "data": {"toolCalls": 3, "assistantMessages": 2}})
        + "\n",
        encoding="utf-8",
    )
    result = evaluate_semantic_acceptance(
        _task(ALLOW),
        workspace=workspace,
        profile=profile,
        baseline=baseline,
        evidence_root=evidence,
        attempt_id="a1",
        reviewer_verdict="PASS",
        require_reviewer=True,
    )
    assert result.passed is True, [c.to_public_dict() for c in result.checks if not c.passed]


def test_preserved_t003d_result_is_rejected_by_hardened_evaluator() -> None:
    """Prove the saved t003d acceptance artifact would fail under hardening."""
    preserved = Path(
        "/tmp/a002/t3d/.atlas/orchestration/program/evidence/"
        "t003d.prime-a1.run.1.1570964f.acceptance.json"
    )
    if not preserved.is_file():
        pytest.skip("preserved t003d acceptance evidence not present")
    document = json.loads(preserved.read_text(encoding="utf-8"))
    assert document["acceptance"]["passed"] is True  # historical false positive

    workspace = Path("/tmp/atlas-prime-e2e-002-workspace")
    profile = _profile()
    # Reconstruct baseline as if captured before the empty run: current
    # allowlist hashes (control.py still unchanged) + recorded porcelain.
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    pre = tuple(line for line in (porcelain.stdout or "").splitlines() if line.strip())
    path_sha256 = {}
    for relative in ALLOW:
        raw = (workspace / relative).read_bytes()
        import hashlib

        path_sha256[relative] = hashlib.sha256(raw).hexdigest()
    baseline = BaselineManifest(
        attempt_id="t003d.prime-a1.run.1.1570964f",
        workspace=str(workspace),
        allowlist=ALLOW,
        path_sha256=path_sha256,
        pre_existing_porcelain=pre,
        head_sha="4f52f56ecdf6b38e15ced2b30d2098b6dbc8677a",
    )
    evidence = Path("/tmp/a002/t3d/.atlas/orchestration/program/evidence")
    # Scoped GIT_TREE_CHANGED alone must reject (path ignore fix).
    scoped = evaluate_check(
        AcceptanceCheck(
            check_id="candidate-changed",
            kind="GIT_TREE_CHANGED",
            description="scoped",
            path=PROD,
        ),
        workspace=workspace,
        profile=profile,
    )
    assert scoped.passed is False

    semantic = evaluate_semantic_acceptance(
        _task(ALLOW),
        workspace=workspace,
        profile=profile,
        baseline=baseline,
        evidence_root=evidence,
        attempt_id="t003d.prime-a1.run.1.1570964f",
        require_reviewer=True,
    )
    assert semantic.passed is False
    failed = [c.check_id for c in semantic.checks if not c.passed]
    assert "scoped-diff-vs-baseline" in failed
    assert "native-child-bound" in failed
    assert "independent-reviewer" in failed
