"""Verification-only review subjects and durable, idempotent receipts.

This module is deliberately separate from ordinary coding-successor state.
It binds a read-only review to a frozen terminal attempt and gives the
supervisor a small publication primitive. A verifier proposal is evidence;
the supervisor combines it with the existing acceptance evaluator before it
publishes a verdict.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from project_atlas.orchestration.program.acceptance import AcceptanceResult
from project_atlas.orchestration.program.models import AcceptanceCheck, ProgramError
from project_atlas.orchestration.program.store import _write_atomic

REVIEW_ENGINE_ID: Final[str] = "atlas-verification-route"
REVIEW_ENGINE_VERSION: Final[str] = "atlas-verification-route-v1"
_SHA_RE = r"^[0-9a-f]{40,64}$"


class ReviewVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class ReviewEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(min_length=64, max_length=64)

    @field_validator("sha256")
    @classmethod
    def _sha(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("evidence digest must be lowercase sha256 hex")
        return value


class VerificationSubject(BaseModel):
    """The immutable subject a verification task is allowed to inspect."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_program_id: str = Field(min_length=1, max_length=128)
    subject_task_id: str = Field(min_length=1, max_length=128)
    subject_attempt_id: str = Field(min_length=1, max_length=256)
    candidate_head: str = Field(min_length=40, max_length=40)
    candidate_tree: str = Field(min_length=40, max_length=64)
    subject_workspace: str = Field(min_length=1, max_length=4096)
    subject_state_root: str = Field(min_length=1, max_length=4096)
    acceptance: tuple[dict[str, Any], ...] = Field(min_length=1, max_length=32)
    criteria_digest: str = Field(min_length=64, max_length=64)
    subject_profile_digest: str = Field(min_length=64, max_length=64)
    evidence: tuple[ReviewEvidence, ...] = Field(default_factory=tuple, max_length=64)

    @field_validator("candidate_head", "candidate_tree")
    @classmethod
    def _git_sha(cls, value: str) -> str:
        if not __import__("re").fullmatch(_SHA_RE, value):
            raise ValueError("candidate identity must be a lowercase git digest")
        return value

    @field_validator("criteria_digest", "subject_profile_digest")
    @classmethod
    def _sha256(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("digest must be lowercase sha256 hex")
        return value


class ReviewProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_engine_id: str = Field(min_length=1, max_length=128)
    review_engine_version: str = Field(min_length=1, max_length=128)
    subject_attempt_id: str = Field(min_length=1, max_length=256)
    verdict: ReviewVerdict
    rationale: str = Field(min_length=1, max_length=8192)

    def bind_to(
        self, attempt_id: str, engine_version: str = REVIEW_ENGINE_VERSION
    ) -> ReviewProposal:
        if self.subject_attempt_id != attempt_id:
            raise ValueError("review proposal is bound to another subject attempt")
        if self.review_engine_id != REVIEW_ENGINE_ID:
            raise ValueError("review proposal names an unsupported review engine")
        if self.review_engine_version != engine_version:
            raise ValueError("review proposal names another review engine version")
        return self


class ReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str = Field(min_length=64, max_length=64)
    program_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=128)
    subject: VerificationSubject
    review_engine_id: str
    review_engine_version: str
    reviewer_agent_id: str
    verifier_attempt_id: str
    verdict: ReviewVerdict
    rationale: str = Field(min_length=1, max_length=8192)
    acceptance: dict[str, Any]
    proposal_sha256: str = Field(min_length=64, max_length=64)
    evidence_paths: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    published_at: str

    @classmethod
    def create(
        cls,
        *,
        program_id: str,
        task_id: str,
        subject: VerificationSubject,
        reviewer_agent_id: str,
        verifier_attempt_id: str,
        proposal: ReviewProposal,
        acceptance: AcceptanceResult,
        evidence_paths: tuple[str, ...] = (),
    ) -> ReviewRecord:
        proposal.bind_to(subject.subject_attempt_id, REVIEW_ENGINE_VERSION)
        payload = {
            "program_id": program_id,
            "task_id": task_id,
            "subject": subject.model_dump(mode="json"),
            "review_engine_id": REVIEW_ENGINE_ID,
            "review_engine_version": REVIEW_ENGINE_VERSION,
            "reviewer_agent_id": reviewer_agent_id,
            "verifier_attempt_id": verifier_attempt_id,
            "proposal": proposal.model_dump(mode="json"),
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        proposal_digest = hashlib.sha256(
            json.dumps(
                proposal.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        return cls(
            review_id=digest,
            program_id=program_id,
            task_id=task_id,
            subject=subject,
            review_engine_id=REVIEW_ENGINE_ID,
            review_engine_version=REVIEW_ENGINE_VERSION,
            reviewer_agent_id=reviewer_agent_id,
            verifier_attempt_id=verifier_attempt_id,
            verdict=proposal.verdict,
            rationale=proposal.rationale,
            acceptance=acceptance.to_public_dict(),
            proposal_sha256=proposal_digest,
            evidence_paths=evidence_paths,
            published_at=datetime.now(UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
        )


class ReviewPublication(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record: ReviewRecord
    created: bool


class SubjectSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_attempt_id: str
    subject_acceptance_passed: bool | None


def _review_dir(root: Path) -> Path:
    return root / "reviews"


def _record_path(root: Path, review_id: str) -> Path:
    return _review_dir(root) / f"{review_id}.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _subject_tree(workspace: Path) -> str:
    """Hash the complete current candidate through an isolated git index."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="atlas-review-index-") as temp:
        index = Path(temp) / "index"
        env = {"GIT_INDEX_FILE": str(index)}
        base = subprocess.run(
            ["git", "read-tree", "HEAD"],
            cwd=workspace,
            env={**__import__("os").environ, **env},
            capture_output=True,
        )
        if base.returncode != 0:
            raise ValueError("subject workspace is not a usable git worktree")
        added = subprocess.run(
            ["git", "add", "-A", "--"],
            cwd=workspace,
            env={**__import__("os").environ, **env},
            capture_output=True,
        )
        if added.returncode != 0:
            raise ValueError("subject worktree could not be snapshotted")
        tree = subprocess.run(
            ["git", "write-tree"],
            cwd=workspace,
            env={**__import__("os").environ, **env},
            capture_output=True,
            text=True,
        )
        if tree.returncode != 0:
            raise ValueError("subject worktree tree could not be read")
        return tree.stdout.strip()


def validate_subject(subject: VerificationSubject) -> SubjectSnapshot:
    """Validate frozen subject identity without changing any subject bytes."""
    workspace = Path(subject.subject_workspace).resolve()
    state_root = Path(subject.subject_state_root).resolve()
    state_path = state_root / ".atlas" / "orchestration" / "program" / "state.json"
    if not workspace.is_dir() or not state_path.is_file():
        raise ValueError("subject workspace or state is unavailable")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    attempt = state.get("attempts", {}).get(subject.subject_attempt_id)
    if not isinstance(attempt, dict) or attempt.get("task_id") != subject.subject_task_id:
        raise ValueError("subject attempt is not present in its bound state")
    if attempt.get("phase") != "TERMINAL":
        raise ValueError("subject attempt is not terminal")
    if attempt.get("acceptance_passed") is not False:
        raise ValueError("subject attempt is not the expected acceptance=false result")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    if head != subject.candidate_head:
        raise ValueError("subject HEAD does not match the frozen candidate")
    if _subject_tree(workspace) != subject.candidate_tree:
        raise ValueError("subject TREE does not match the frozen candidate")
    checks = tuple(AcceptanceCheck.model_validate(item) for item in subject.acceptance)
    criteria = [check.model_dump(mode="json") for check in checks]
    digest = hashlib.sha256(
        json.dumps(criteria, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != subject.criteria_digest:
        raise ValueError("subject acceptance criteria digest does not match")
    for evidence in subject.evidence:
        path = Path(evidence.path).resolve()
        if not path.is_file() or _sha256(path) != evidence.sha256:
            raise ValueError(f"subject evidence is stale or unreadable: {evidence.path}")
    return SubjectSnapshot(
        subject_attempt_id=subject.subject_attempt_id,
        subject_acceptance_passed=attempt.get("acceptance_passed"),
    )


def publish_review_record(root: Path, record: ReviewRecord) -> ReviewPublication:
    """Atomically publish one review, returning the existing equal record."""
    path = _record_path(root, record.review_id)
    payload = record.model_dump(mode="json")
    if path.is_file():
        existing = ReviewRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if existing != record:
            raise ProgramError(
                f"review id {record.review_id} is already bound to different content",
                code="REVIEW_ID_CONFLICT",
            )
        return ReviewPublication(record=existing, created=False)
    _write_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    readback = ReviewRecord.model_validate_json(path.read_text(encoding="utf-8"))
    if readback != record:
        raise ProgramError("review receipt readback differs", code="REVIEW_READBACK_MISMATCH")
    return ReviewPublication(record=readback, created=True)


def read_review_record(root: Path, review_id: str) -> ReviewRecord:
    path = _record_path(root, review_id)
    return ReviewRecord.model_validate_json(path.read_text(encoding="utf-8"))
