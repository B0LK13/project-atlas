"""AS-RESULT-TO-REVIEW-HANDOFF-001 boundary tests. Zero model calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from tests.unit.test_taskcontract_preparation import _binding, _contract

from project_atlas.orchestration.taskcontract.result_review import (
    CandidateIdentity,
    CandidateKind,
    ChangeEntry,
    ChangeKind,
    EvidenceCoverageStatus,
    ExecutionBinding,
    WorkerClaim,
    build_evidence_coverage,
    build_result_review_package,
    compare_result_packages,
    export_is_idempotent,
    path_in_mutation_scope,
    snapshot_digest_from_bytes,
)
from project_atlas.orchestration.taskcontract.validate import validate_contract


def _exec(
    *,
    head: str | None = None,
    tree: str | None = None,
    content_digest: str | None = None,
    acceptance_version: str = "acc-v1",
    outcomes: list[dict[str, Any]] | None = None,
    checks: list[dict[str, Any]] | None = None,
    artifacts: dict[str, str] | None = None,
    direct_repair: dict[str, Any] | None = None,
) -> ExecutionBinding:
    if content_digest:
        candidate = CandidateIdentity(
            kind=CandidateKind.CONTENT_SNAPSHOT,
            content_digest=content_digest,
            note="fixture snapshot",
        )
    else:
        candidate = CandidateIdentity(
            kind=CandidateKind.GIT_COMMIT,
            base_pin="0" * 40,
            head=head or "a" * 40,
            tree=tree or "b" * 40,
        )
    return ExecutionBinding(
        program_id="prog-1",
        task_id="TASK-1",
        attempt_ids=("prog-1.TASK-1.run.1.deadbeef",),
        acceptance_version=acceptance_version,
        acceptance_outcomes=tuple(outcomes or ()),
        checks_run=tuple(checks or ()),
        artifact_digests=dict(artifacts or {}),
        candidate=candidate,
        direct_repair=direct_repair,
        historical_attempt_preserved=True,
    )


def test_complete_result_yields_reproducible_package(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    outcomes = [{"check_id": "behaviour", "passed": True}]
    checks = [{"check_id": "behaviour", "passed": True}]
    snap = snapshot_digest_from_bytes(b"fixture-bytes")
    execution = _exec(
        content_digest=snap,
        outcomes=outcomes,
        checks=checks,
    )
    changes = [
        ChangeEntry(path=next(iter(contract.mutation_paths)), kind=ChangeKind.MODIFIED)
    ]
    first = build_result_review_package(
        contract,
        binding,
        report,
        execution=execution,
        changes=changes,
        package_out_hint=str(tmp_path / "pkg.json"),
    )
    second = build_result_review_package(
        contract,
        binding,
        report,
        execution=execution,
        changes=changes,
        package_out_hint=str(tmp_path / "pkg.json"),
    )
    assert first["schema"] == "atlas.taskcontract.review/1"
    assert "result_handoff" in first
    assert first["result_handoff"]["package_id"] == "AS-RESULT-TO-REVIEW-HANDOFF-001"
    assert export_is_idempotent(first, second)
    assert first["result_handoff"]["merge_authorized"] is False
    assert first["result_handoff"]["self_approval"] is False
    assert first["result_handoff"]["inspection"]["package_generation_executed_tests"] is False


def test_exit_zero_wrong_artifact_stays_visible_reject(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    execution = _exec(
        content_digest=snapshot_digest_from_bytes(b"wrong"),
        outcomes=[{"check_id": "behaviour", "passed": False}],
        checks=[{"check_id": "behaviour", "passed": False}],
    )
    package = build_result_review_package(contract, binding, report, execution=execution)
    cov = package["result_handoff"]["evidence_coverage"]
    behaviour = next(r for r in cov if "behaviour" in r["check_ids"])
    assert behaviour["coverage"] == EvidenceCoverageStatus.CHECK_FAILED.value
    # Package may be complete while product quality is not evaluated here.
    assert package["result_handoff"]["package_completeness"] == "COMPLETE"
    assert package["result_handoff"]["product_quality_verdict"] == "NOT_EVALUATED_HERE"


def test_evidence_from_other_candidate_is_flagged(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    execution = _exec(
        content_digest="a" * 64,
        outcomes=[{"check_id": "behaviour", "passed": True}],
        checks=[{"check_id": "behaviour", "passed": True}],
        artifacts={"_candidate_digest": "b" * 64},
    )
    package = build_result_review_package(contract, binding, report, execution=execution)
    assert all(
        row["coverage"] == EvidenceCoverageStatus.EVIDENCE_OTHER_CANDIDATE.value
        for row in package["result_handoff"]["evidence_coverage"]
        if row["verification"] == "AUTOMATED"
    )


def test_direct_repair_does_not_overwrite_historical_attempt(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    execution = _exec(
        content_digest="c" * 64,
        outcomes=[{"check_id": "behaviour", "passed": True}],
        checks=[{"check_id": "behaviour", "passed": True}],
        direct_repair={"note": "operator patched after attempt", "paths": ["x"]},
    )
    package = build_result_review_package(contract, binding, report, execution=execution)
    ex = package["result_handoff"]["execution"]
    assert ex["attempt_ids"] == ["prog-1.TASK-1.run.1.deadbeef"]
    assert ex["direct_repair"]["note"] == "operator patched after attempt"
    assert ex["historical_attempt_preserved"] is True


def test_untracked_and_out_of_scope_visible(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    changes = [
        ChangeEntry(path="secret-outside.txt", kind=ChangeKind.UNTRACKED),
        ChangeEntry(
            path="tests/test_something.py",
            kind=ChangeKind.MODIFIED,
            executable_bit_changed=True,
        ),
    ]
    package = build_result_review_package(
        contract, binding, report, changes=changes, execution=_exec(content_digest="d" * 64)
    )
    unexpected = package["result_handoff"]["mutation_scope"]["unexpected_or_attention"]
    paths = {row["path"] for row in unexpected}
    assert "secret-outside.txt" in paths
    assert "tests/test_something.py" in paths


def test_missing_checks_not_shown_as_passed(tmp_path: Path) -> None:
    contract, _, _workspace = _contract(tmp_path)
    rows = build_evidence_coverage(contract, acceptance_outcomes=(), checks_run=())
    auto = [r for r in rows if r["verification"] == "AUTOMATED"]
    assert auto
    assert all(r["coverage"] == EvidenceCoverageStatus.CHECK_NOT_RUN.value for r in auto)
    assert EvidenceCoverageStatus.PROVEN.value not in {r["coverage"] for r in auto}


def test_changed_acceptance_version_recognizable(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    before = build_result_review_package(
        contract,
        binding,
        report,
        execution=_exec(content_digest="e" * 64, acceptance_version="acc-v1"),
        package_version=1,
    )
    after = build_result_review_package(
        contract,
        binding,
        report,
        execution=_exec(content_digest="e" * 64, acceptance_version="acc-v2"),
        previous_package=before,
        package_version=2,
    )
    diff = compare_result_packages(before, after)
    assert diff["acceptance_version_changed"] is True
    assert diff["prior_approval_carried"] is False
    assert after["result_handoff"]["previous_package_digest"] == before["result_handoff"][
        "package_digest"
    ]


def test_repeat_export_no_duplicate_handoff(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    kwargs: dict[str, Any] = {
        "execution": _exec(content_digest="f" * 64),
        "package_version": 1,
    }
    a = build_result_review_package(contract, binding, report, **kwargs)
    b = build_result_review_package(contract, binding, report, **kwargs)
    assert a["result_handoff"]["package_digest"] == b["result_handoff"]["package_digest"]
    assert a["result_handoff"]["idempotency"]["repeat_export_creates_new_attempt"] is False


def test_uncommitted_described_as_snapshot_not_git_tree() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc:
        CandidateIdentity(
            kind=CandidateKind.CONTENT_SNAPSHOT,
            content_digest="1" * 64,
            tree="2" * 40,
        )
    assert "CANDIDATE_TREE_CLAIM_FORBIDDEN" in str(exc.value) or "git tree" in str(exc.value)
    ok = CandidateIdentity(
        kind=CandidateKind.CONTENT_SNAPSHOT,
        patch_digest="3" * 64,
        note="working tree patch",
    )
    assert ok.tree is None


def test_package_generation_does_not_execute_supplied_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)

    def boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("subprocess must not run during package generation")

    monkeypatch.setattr("subprocess.run", boom)
    monkeypatch.setattr("subprocess.Popen", boom)
    package = build_result_review_package(
        contract,
        binding,
        report,
        execution=_exec(content_digest="7" * 64),
        targeted_tests=("tests/unit/test_result_to_review_handoff_001.py",),
    )
    cmds = package["result_handoff"]["inspection"]["commands"]
    assert any(c["purpose"] == "repeat_targeted_check" for c in cmds)
    assert package["result_handoff"]["inspection"]["package_generation_executed_tests"] is False


def test_worker_claims_remain_labeled(tmp_path: Path) -> None:
    contract, _, workspace = _contract(tmp_path)
    binding = _binding(tmp_path, workspace)
    report = validate_contract(contract, binding=binding)
    package = build_result_review_package(
        contract,
        binding,
        report,
        execution=_exec(content_digest="8" * 64),
        worker_claims=[
            WorkerClaim(claim_id="w1", text="All requirements satisfied.", attempt_id="a1")
        ],
    )
    claims = package["result_handoff"]["worker_claims"]
    assert claims[0]["status"] == "CLAIM"
    assert claims[0]["supported_by_evidence"] is False
    overview = package["result_handoff"]["reviewer_overview"]["worker_claims_labeled"][0]
    assert overview.startswith("[CLAIM]")


def test_path_in_scope_helper() -> None:
    assert path_in_mutation_scope("src/a.py", ("src/",))
    assert path_in_mutation_scope("src/a.py", ("src/a.py",))
    assert not path_in_mutation_scope("other/a.py", ("src/",))
