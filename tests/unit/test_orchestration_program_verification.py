"""Model-free contract tests for the verification-only program route."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from project_atlas.orchestration.program.acceptance import AcceptanceResult
from project_atlas.orchestration.program.adapters.codex import validate_output_schema
from project_atlas.orchestration.program.loader import load_program
from project_atlas.orchestration.program.models import AcceptanceCheck
from project_atlas.orchestration.program.store import load_state
from project_atlas.orchestration.program.supervisor import ProgramSupervisor
from project_atlas.orchestration.program.verification import (
    REVIEW_ENGINE_ID,
    ReviewProposal,
    ReviewRecord,
    ReviewVerdict,
    VerificationSubject,
    publish_review_record,
    read_review_record,
    validate_subject,
)


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "subject"
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
    (root / "result.txt").write_text("candidate\n", encoding="utf-8")
    subprocess.run(["git", "add", "result.txt"], cwd=root, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "subject"], cwd=root, check=True)
    return root


def _subject(tmp_path: Path, *, attempt_id: str = "attempt-1") -> VerificationSubject:
    workspace = _workspace(tmp_path)
    state_root = tmp_path / "subject-state"
    state_dir = state_root / ".atlas" / "orchestration" / "program"
    state_dir.mkdir(parents=True)
    state = {
        "attempts": {
            attempt_id: {
                "attempt_id": attempt_id,
                "task_id": "subject-task",
                "phase": "TERMINAL",
                "acceptance_passed": False,
            }
        }
    }
    (state_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    check = AcceptanceCheck(
        check_id="result", kind="FILE_EXISTS", description="result exists", path="result.txt"
    )
    criteria = (check.model_dump(mode="json"),)
    criteria_digest = hashlib.sha256(
        json.dumps(criteria, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=workspace, text=True
    ).strip()
    return VerificationSubject(
        subject_program_id="subject-program",
        subject_task_id="subject-task",
        subject_attempt_id=attempt_id,
        candidate_head=head,
        candidate_tree=tree,
        subject_workspace=str(workspace),
        subject_state_root=str(state_root),
        acceptance=criteria,
        criteria_digest=criteria_digest,
        subject_profile_digest="a" * 64,
        evidence=(),
    )


def test_terminal_subject_with_open_predecessor_is_validated_read_only(tmp_path: Path) -> None:
    subject = _subject(tmp_path)

    snapshot = validate_subject(subject)

    assert snapshot.subject_attempt_id == "attempt-1"
    assert snapshot.subject_acceptance_passed is False
    assert (Path(subject.subject_workspace) / "result.txt").read_text() == "candidate\n"


def test_subject_binding_rejects_nonterminal_or_wrong_candidate(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    state_path = (
        Path(subject.subject_state_root) / ".atlas" / "orchestration" / "program" / "state.json"
    )
    state = json.loads(state_path.read_text())
    state["attempts"]["attempt-1"]["phase"] = "ACTIVE"
    state_path.write_text(json.dumps(state))

    with pytest.raises(ValueError, match="terminal"):
        validate_subject(subject)


def test_review_publication_is_idempotent_and_readable(tmp_path: Path) -> None:
    subject = _subject(tmp_path)
    proposal = ReviewProposal(
        review_engine_id=REVIEW_ENGINE_ID,
        review_engine_version="atlas-verification-route-v1",
        subject_attempt_id=subject.subject_attempt_id,
        verdict=ReviewVerdict.PASS,
        rationale="all bound criteria observed",
    )
    record = ReviewRecord.create(
        program_id="review-program",
        task_id="review-task",
        subject=subject,
        reviewer_agent_id="reviewer-1",
        verifier_attempt_id="review-attempt-1",
        proposal=proposal,
        acceptance=AcceptanceResult(passed=True, checks=()),
    )

    first = publish_review_record(tmp_path / "review-state", record)
    second = publish_review_record(tmp_path / "review-state", record)

    assert first.created is True
    assert second.created is False
    assert read_review_record(tmp_path / "review-state", record.review_id) == record


def test_review_proposal_binding_is_explicit() -> None:
    with pytest.raises(ValueError):
        ReviewProposal(
            review_engine_id=REVIEW_ENGINE_ID,
            review_engine_version="atlas-verification-route-v1",
            subject_attempt_id="different-attempt",
            verdict=ReviewVerdict.PASS,
            rationale="not bound",
        ).bind_to("attempt-1")


def test_verification_program_dispatches_review_without_mutating_subject(tmp_path: Path) -> None:
    subject = _subject(tmp_path / "subject-fixture")
    review_workspace = tmp_path / "review-workspace"
    review_workspace.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=review_workspace, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"], cwd=review_workspace, check=True
    )
    subprocess.run(["git", "config", "user.name", "test"], cwd=review_workspace, check=True)
    (review_workspace / "README.md").write_text("review\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=review_workspace, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "review"], cwd=review_workspace, check=True)
    worker = tmp_path / "reviewer.py"
    worker.write_text(
        "import json, time\n"
        "time.sleep(0.2)\n"
        "print(json.dumps({\n"
        "  'review_engine_id': 'atlas-verification-route',\n"
        "  'review_engine_version': 'atlas-verification-route-v1',\n"
        "  'subject_attempt_id': 'attempt-1',\n"
        "  'verdict': 'PASS',\n"
        "  'rationale': 'bound checks pass'\n"
        "}))\n",
        encoding="utf-8",
    )

    def profile(agent_id: str) -> dict[str, object]:
        return {
            "agent_id": agent_id,
            "adapter": "local-command",
            "credential": "NOT_APPLICABLE",
            "capabilities": ["VERIFY"],
            "allowed_mutation_prefixes": [],
            "limits": {"max_attempts": 1, "max_seconds": 30},
            "adapter_options": {"argv": [sys.executable, str(worker)]},
        }

    task = {
        "task_id": "review-task",
        "title": "review frozen subject",
        "task_kind": "VERIFY_SUBJECT",
        "instruction": "review the frozen subject",
        "profile_ref": "anchor",
        "verifier_profile_ref": "verifier",
        "review_engine_version": "atlas-verification-route-v1",
        "review_subject": subject.model_dump(mode="json"),
        "mutation_paths": [],
        "surface_id": "review-surface",
        "surface_semantic": "REVIEW",
        "capabilities_required": ["VERIFY"],
        "acceptance": [
            {
                "check_id": "review-workspace",
                "kind": "FILE_EXISTS",
                "description": "review workspace exists",
                "path": "README.md",
            }
        ],
    }
    program = tmp_path / "review-program.json"
    program.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "program": {
                    "program_id": "verification-program",
                    "objective": "review one frozen subject",
                    "approved_by": "owner",
                    "approval_reference": "ATLAS-VERIFICATION-ROUTE-IMPLEMENT-001",
                    "workspace_root": str(review_workspace),
                    "base_pin": subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], cwd=review_workspace, text=True
                    ).strip(),
                    "tasks": [task],
                    "limits": {
                        "max_task_launches": 1,
                        "max_attempts_per_task": 1,
                        "max_program_seconds": 120,
                        "max_cycles": 10,
                        "idle_sleep_seconds": 0,
                    },
                },
                "profile_defaults": {"adapter": "local-command", "credential": "NOT_APPLICABLE"},
                "profiles": {
                    "anchor": profile("subject-anchor"),
                    "verifier": profile("independent-reviewer"),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    loaded = load_program(program)
    report = ProgramSupervisor(
        loaded, state_root=tmp_path / "review-state", sleeper=lambda _: None
    ).start()

    assert report.complete is True, report.notifications
    assert any(
        mode.value == "VERIFY" for cycle in report.cycles for _task, mode in cycle.dispatched
    )
    state = load_state(tmp_path / "review-state")
    assert state is not None
    assert state.tasks["review-task"].state.value == "CERTIFIED"
    assert list(
        (tmp_path / "review-state" / ".atlas" / "orchestration" / "program" / "reviews").glob(
            "*.json"
        )
    )
    assert (
        json.loads(
            (
                Path(subject.subject_state_root)
                / ".atlas"
                / "orchestration"
                / "program"
                / "state.json"
            ).read_text()
        )["attempts"]["attempt-1"]["acceptance_passed"]
        is False
    )


def test_codex_schema_preflight_rejects_original_missing_type_and_accepts_repair() -> None:
    original = {
        "type": "object",
        "properties": {"review_engine_id": {"const": "atlas-verification-route"}},
        "required": ["review_engine_id"],
        "additionalProperties": False,
    }
    with pytest.raises(ValueError, match="type"):
        validate_output_schema(original)

    repaired = {
        "type": "object",
        "properties": {
            "review_engine_id": {
                "type": "string",
                "const": "atlas-verification-route",
            }
        },
        "required": ["review_engine_id"],
        "additionalProperties": False,
    }
    assert validate_output_schema(repaired) is None


@pytest.mark.parametrize(
    "schema",
    [
        {
            "type": "object",
            "properties": {"x": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        {"type": "object", "properties": {"x": {"type": "string"}}},
        {
            "type": "object",
            "properties": {
                "x": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"y": {"type": "string"}},
                        "required": ["y"],
                    },
                }
            },
            "required": ["x"],
            "additionalProperties": False,
        },
    ],
)
def test_codex_schema_preflight_rejects_required_or_nested_contract_gaps(
    schema: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        validate_output_schema(schema)
