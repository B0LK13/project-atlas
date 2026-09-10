"""AS-RESULT-TO-REVIEW-HANDOFF-001 — extend taskcontract review for result handoff.

Leading package remains ``atlas.taskcontract.review/1`` (``render_review_package``).
This module adds an additive ``result_handoff`` section so a reviewer can bind
execution evidence to the same review identity without a parallel package format.

  PACKAGE_COMPLETE != PRODUCT_QUALITY
  WORKER_CLAIM != EVIDENCE
  WORKING_TREE_CHANGE != COMMIT
  REVIEW_PACKAGE != APPROVAL / MERGE AUTHORIZATION
  PRIOR_APPROVAL != CURRENT_APPROVAL

Package generation never executes acceptance argv, never runs arbitrary tests,
and never grants merge or self-approval.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from project_atlas.orchestration.taskcontract.models import (
    DeploymentBinding,
    TaskContract,
    TaskContractError,
    VerificationMode,
)
from project_atlas.orchestration.taskcontract.render import render_review_package

PACKAGE_ID: Final[Literal["AS-RESULT-TO-REVIEW-HANDOFF-001"]] = (
    "AS-RESULT-TO-REVIEW-HANDOFF-001"
)
EXTENSION_KEY: Final[str] = "result_handoff"
SCHEMA_REVIEW: Final[str] = "atlas.taskcontract.review/1"
TRUTH_BOUNDARY: Final[str] = (
    "PACKAGE_COMPLETE != PRODUCT_QUALITY / "
    "WORKER_CLAIM != EVIDENCE / "
    "WORKING_TREE_CHANGE != COMMIT / "
    "REVIEW_PACKAGE != APPROVAL / "
    "PRIOR_APPROVAL != CURRENT_APPROVAL"
)


class EvidenceCoverageStatus(StrEnum):
    PROVEN = "PROVEN"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    CHECK_FAILED = "CHECK_FAILED"
    CHECK_NOT_RUN = "CHECK_NOT_RUN"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    EVIDENCE_OTHER_CANDIDATE = "EVIDENCE_OTHER_CANDIDATE"


class CandidateKind(StrEnum):
    GIT_COMMIT = "GIT_COMMIT"
    CONTENT_SNAPSHOT = "CONTENT_SNAPSHOT"


class ChangeKind(StrEnum):
    MODIFIED = "MODIFIED"
    ADDED = "ADDED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    UNTRACKED = "UNTRACKED"
    MODE_OR_SYMLINK = "MODE_OR_SYMLINK"


class CandidateIdentity(BaseModel):
    """What the review is of. Never invents a git tree for an uncommitted result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: CandidateKind
    base_pin: str | None = Field(default=None, min_length=40, max_length=40)
    head: str | None = Field(default=None, min_length=40, max_length=40)
    tree: str | None = Field(default=None, min_length=40, max_length=40)
    #: Present when kind is CONTENT_SNAPSHOT (uncommitted / patch).
    patch_digest: str | None = Field(default=None, min_length=64, max_length=64)
    content_digest: str | None = Field(default=None, min_length=64, max_length=64)
    note: str = Field(default="", max_length=512)

    @model_validator(mode="after")
    def _coherent(self) -> CandidateIdentity:
        if self.kind is CandidateKind.GIT_COMMIT and (not self.head or not self.tree):
            raise TaskContractError(
                "GIT_COMMIT candidate requires head and tree",
                code="CANDIDATE_IDENTITY_INCOMPLETE",
            )
        if self.kind is CandidateKind.CONTENT_SNAPSHOT:
            if not self.patch_digest and not self.content_digest:
                raise TaskContractError(
                    "CONTENT_SNAPSHOT requires patch_digest and/or content_digest; "
                    "do not claim a git tree that does not exist",
                    code="CANDIDATE_SNAPSHOT_REQUIRED",
                )
            if self.tree is not None:
                raise TaskContractError(
                    "CONTENT_SNAPSHOT must not claim a git tree identity",
                    code="CANDIDATE_TREE_CLAIM_FORBIDDEN",
                )
        return self


class ChangeEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1, max_length=512)
    kind: ChangeKind
    from_path: str | None = Field(default=None, max_length=512)
    executable_bit_changed: bool = False
    symlink_changed: bool = False
    in_allowed_mutation_scope: bool = False
    touches_acceptance_or_tests: bool = False

    @field_validator("path", "from_path")
    @classmethod
    def _path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip().replace("\\", "/")
        if text.startswith("/") or ".." in text.split("/"):
            raise TaskContractError(
                f"change path {value!r} must be safe relative",
                code="CHANGE_PATH_UNSAFE",
            )
        return text


class WorkerClaim(BaseModel):
    """Worker-reported text. Remains CLAIM until supporting evidence exists."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=8192)
    attempt_id: str | None = Field(default=None, max_length=256)
    status: Literal["CLAIM"] = "CLAIM"
    supported_by_evidence: bool = False


class OpenFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1, max_length=1024)
    owner: str = Field(default="", max_length=256)
    status: Literal["OPEN", "RESOLVED", "NEW"] = "OPEN"


class ExecutionBinding(BaseModel):
    """Program/task/attempt identities and acceptance outcomes (read-only facts)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    program_id: str | None = Field(default=None, max_length=128)
    task_id: str | None = Field(default=None, max_length=128)
    attempt_ids: tuple[str, ...] = Field(default_factory=tuple, max_length=64)
    acceptance_version: str | None = Field(default=None, max_length=128)
    acceptance_outcomes: tuple[dict[str, Any], ...] = Field(
        default_factory=tuple, max_length=64
    )
    checks_run: tuple[dict[str, Any], ...] = Field(default_factory=tuple, max_length=64)
    artifact_digests: dict[str, str] = Field(default_factory=dict, max_length=64)
    candidate: CandidateIdentity
    #: Direct repair after the worker attempt — distinct from worker result.
    direct_repair: dict[str, Any] | None = None
    historical_attempt_preserved: bool = True


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def package_digest(package: dict[str, Any]) -> str:
    """Stable identity of a review package body (excludes write-path metadata)."""
    body = {
        k: v
        for k, v in package.items()
        if k not in {"written", "export_path", "exported_at"}
    }
    # Digest excludes itself if present.
    body.pop("package_digest", None)
    if EXTENSION_KEY in body and isinstance(body[EXTENSION_KEY], dict):
        rh = dict(body[EXTENSION_KEY])
        rh.pop("package_digest", None)
        body[EXTENSION_KEY] = rh
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def snapshot_digest_from_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def path_in_mutation_scope(path: str, mutation_paths: tuple[str, ...]) -> bool:
    """Path is under an allowed prefix. In-scope ≠ content correctness."""
    norm = path.strip().replace("\\", "/")
    for allowed in mutation_paths:
        a = allowed.strip().replace("\\", "/")
        if norm == a or norm.startswith(a.rstrip("/") + "/"):
            return True
    return False


def classify_change_inventory(
    changes: tuple[ChangeEntry, ...] | list[ChangeEntry],
    *,
    mutation_paths: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Annotate each change with scope/acceptance-touch flags (no mutation)."""
    out: list[dict[str, Any]] = []
    for raw in changes:
        entry = raw if isinstance(raw, ChangeEntry) else ChangeEntry.model_validate(raw)
        touches = _touches_acceptance_or_tests(entry.path)
        if entry.from_path:
            touches = touches or _touches_acceptance_or_tests(entry.from_path)
        in_scope = path_in_mutation_scope(entry.path, mutation_paths)
        annotated = entry.model_copy(
            update={
                "in_allowed_mutation_scope": in_scope,
                "touches_acceptance_or_tests": touches,
            }
        )
        out.append(annotated.model_dump(mode="json"))
    return out


def _touches_acceptance_or_tests(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    name = lower.rsplit("/", 1)[-1]
    if "acceptance" in lower or name.startswith("test_") or "/tests/" in f"/{lower}":
        return True
    return name.endswith("_test.py") or name.endswith(".test.ts")


def build_evidence_coverage(
    contract: TaskContract,
    *,
    acceptance_outcomes: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
    checks_run: tuple[dict[str, Any], ...] | list[dict[str, Any]] = (),
    candidate_digest: str | None = None,
    evidence_candidate_digest: str | None = None,
) -> list[dict[str, Any]]:
    """Map each result requirement to coverage status. Missing checks ≠ passed."""
    outcomes_by_check: dict[str, dict[str, Any]] = {}
    for row in acceptance_outcomes:
        cid = str(row.get("check_id") or row.get("id") or "")
        if cid:
            outcomes_by_check[cid] = row
    run_ids = {
        str(row.get("check_id") or row.get("id") or "")
        for row in checks_run
        if row.get("check_id") or row.get("id")
    }
    other_candidate = (
        candidate_digest is not None
        and evidence_candidate_digest is not None
        and candidate_digest != evidence_candidate_digest
    )
    rows: list[dict[str, Any]] = []
    for req in contract.requirements:
        status: EvidenceCoverageStatus
        detail: str
        if other_candidate:
            status = EvidenceCoverageStatus.EVIDENCE_OTHER_CANDIDATE
            detail = (
                f"evidence candidate {evidence_candidate_digest} does not match "
                f"review candidate {candidate_digest}"
            )
        elif req.verification is VerificationMode.HUMAN_REVIEW:
            status = EvidenceCoverageStatus.MANUAL_REVIEW_REQUIRED
            detail = req.review_note or "human review required"
        elif req.verification is VerificationMode.NO_CHECK_AVAILABLE:
            status = EvidenceCoverageStatus.EVIDENCE_MISSING
            detail = "NO_CHECK_AVAILABLE — no machine check to pass"
        elif not req.check_ids:
            status = EvidenceCoverageStatus.EVIDENCE_MISSING
            detail = "AUTOMATED requirement lists no check_ids"
        else:
            statuses: list[EvidenceCoverageStatus] = []
            notes: list[str] = []
            for cid in req.check_ids:
                if cid not in run_ids and cid not in outcomes_by_check:
                    statuses.append(EvidenceCoverageStatus.CHECK_NOT_RUN)
                    notes.append(f"{cid}: not run")
                    continue
                outcome = outcomes_by_check.get(cid)
                if outcome is None:
                    statuses.append(EvidenceCoverageStatus.CHECK_NOT_RUN)
                    notes.append(f"{cid}: listed as run without outcome")
                    continue
                passed = outcome.get("passed")
                if passed is True:
                    statuses.append(EvidenceCoverageStatus.PROVEN)
                    notes.append(f"{cid}: passed")
                elif passed is False:
                    statuses.append(EvidenceCoverageStatus.CHECK_FAILED)
                    notes.append(f"{cid}: failed")
                else:
                    statuses.append(EvidenceCoverageStatus.EVIDENCE_MISSING)
                    notes.append(f"{cid}: outcome unknown")
            if EvidenceCoverageStatus.CHECK_FAILED in statuses:
                status = EvidenceCoverageStatus.CHECK_FAILED
            elif EvidenceCoverageStatus.CHECK_NOT_RUN in statuses:
                status = EvidenceCoverageStatus.CHECK_NOT_RUN
            elif EvidenceCoverageStatus.EVIDENCE_MISSING in statuses:
                status = EvidenceCoverageStatus.EVIDENCE_MISSING
            else:
                status = EvidenceCoverageStatus.PROVEN
            detail = "; ".join(notes)
        rows.append(
            {
                "requirement_id": req.requirement_id,
                "statement": req.statement,
                "verification": req.verification.value,
                "check_ids": list(req.check_ids),
                "coverage": status.value,
                "detail": detail,
            }
        )
    return rows


def build_reviewer_overview(
    contract: TaskContract,
    *,
    change_paths: list[str],
    coverage: list[dict[str, Any]],
    open_findings: list[dict[str, Any]],
    worker_claims: list[dict[str, Any]],
    validation_plan_ref: str | None,
) -> dict[str, Any]:
    """Compact structured overview. Does not invent motivation or test results."""
    attention = [
        row["requirement_id"]
        for row in coverage
        if row["coverage"]
        in {
            EvidenceCoverageStatus.MANUAL_REVIEW_REQUIRED.value,
            EvidenceCoverageStatus.CHECK_FAILED.value,
            EvidenceCoverageStatus.CHECK_NOT_RUN.value,
            EvidenceCoverageStatus.EVIDENCE_MISSING.value,
            EvidenceCoverageStatus.EVIDENCE_OTHER_CANDIDATE.value,
        }
    ]
    claim_lines = [
        f"[CLAIM] {c.get('claim_id')}: {str(c.get('text', ''))[:200]}"
        for c in worker_claims
        if c.get("status", "CLAIM") == "CLAIM"
    ]
    return {
        "problem_addressed": contract.objective,
        "observable_outcome": contract.observable_outcome,
        "what_changed_paths": list(change_paths),
        "how_checked": {
            "from_contract_acceptance": [c.check_id for c in contract.acceptance],
            "validation_plan_ref": validation_plan_ref,
            "coverage_summary": {
                status.value: sum(1 for r in coverage if r["coverage"] == status.value)
                for status in EvidenceCoverageStatus
            },
        },
        "needs_extra_attention": attention,
        "remaining_risks_or_unknowns": [
            f["summary"] for f in open_findings if f.get("status") == "OPEN"
        ]
        + (
            ["worker claims present without supporting evidence"]
            if any(not c.get("supported_by_evidence") for c in worker_claims)
            else []
        ),
        "where_to_look": {
            "diff_and_changes": "result_handoff.mutation_scope.changes",
            "tests_and_acceptance": "result_handoff.evidence_coverage",
            "execution_attempts": "result_handoff.execution.attempt_ids",
            "underlying_contract": "contract / contract_digest",
        },
        "worker_claims_labeled": claim_lines,
        "source": "TaskContract fields + supplied execution/change inventory (not filenames)",
    }


def build_inspection_commands(
    *,
    package_path: str | None,
    candidate: CandidateIdentity,
    bundle_path: str | None = None,
    targeted_tests: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Exact restore/diff/origin/recheck commands. Labels runtime expectations."""
    cmds: list[dict[str, Any]] = []
    if candidate.kind is CandidateKind.GIT_COMMIT and candidate.head:
        cmds.append(
            {
                "purpose": "restore_candidate",
                "command": f"git fetch --no-tags && git switch --detach {candidate.head}",
                "side_effects": "moves HEAD; does not modify remotes",
                "runtime": "git",
            }
        )
        cmds.append(
            {
                "purpose": "inspect_tree",
                "command": f"git rev-parse {candidate.head}^{{tree}}",
                "expected": candidate.tree,
                "side_effects": "none",
                "runtime": "git",
            }
        )
        if candidate.base_pin:
            cmds.append(
                {
                    "purpose": "inspect_diff",
                    "command": f"git diff --stat {candidate.base_pin}..{candidate.head}",
                    "side_effects": "none",
                    "runtime": "git",
                }
            )
    else:
        cmds.append(
            {
                "purpose": "restore_snapshot",
                "command": (
                    "Apply the recorded patch/content snapshot; "
                    f"verify digest patch={candidate.patch_digest} "
                    f"content={candidate.content_digest}"
                ),
                "side_effects": "workspace patch apply if operator chooses",
                "runtime": "operator",
                "note": "WORKING_TREE_CHANGE != COMMIT — no git tree claimed",
            }
        )
    if bundle_path:
        cmds.append(
            {
                "purpose": "restore_bundle",
                "command": f"git bundle verify {bundle_path} && git fetch {bundle_path}",
                "side_effects": "adds fetched refs locally",
                "runtime": "git",
            }
        )
    if package_path:
        cmds.append(
            {
                "purpose": "module_origin",
                "command": (
                    f"python -c \"import json; p=json.load(open({package_path!r})); "
                    f"print(p.get('contract_digest'), "
                    f"p.get('result_handoff',{{}}).get('package_digest'))\""
                ),
                "side_effects": "none",
                "runtime": "python3",
            }
        )
    for test in targeted_tests:
        cmds.append(
            {
                "purpose": "repeat_targeted_check",
                "command": f"python -m pytest {test} -q --tb=short",
                "side_effects": "runs tests; may write caches under .pytest_cache",
                "runtime": "python3+pytest",
                "dependencies": "editable install project-atlas[dev]",
                "platform": "linux (fixture paths may differ on Windows)",
                "note": "Listed for operator recheck; package generation did NOT run this",
            }
        )
    return {
        "commands": cmds,
        "package_generation_executed_tests": False,
        "credentials_included": False,
    }


def compare_result_packages(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Compare two review packages. Never auto-carries prior approval."""
    bh = before.get(EXTENSION_KEY) or {}
    ah = after.get(EXTENSION_KEY) or {}
    b_exec = bh.get("execution") or {}
    a_exec = ah.get("execution") or {}
    b_cand = (b_exec.get("candidate") or {}) if isinstance(b_exec, dict) else {}
    a_cand = (a_exec.get("candidate") or {}) if isinstance(a_exec, dict) else {}
    b_changes = {
        (c.get("path"), c.get("kind"))
        for c in ((bh.get("mutation_scope") or {}).get("changes") or [])
    }
    a_changes = {
        (c.get("path"), c.get("kind"))
        for c in ((ah.get("mutation_scope") or {}).get("changes") or [])
    }
    b_findings = {
        f.get("finding_id"): f
        for f in (bh.get("open_findings") or [])
        if isinstance(f, dict)
    }
    a_findings = {
        f.get("finding_id"): f
        for f in (ah.get("open_findings") or [])
        if isinstance(f, dict)
    }
    resolved = [
        fid
        for fid, f in b_findings.items()
        if fid in a_findings and a_findings[fid].get("status") == "RESOLVED"
    ]
    still_open = [
        fid
        for fid, f in a_findings.items()
        if f.get("status") == "OPEN"
    ]
    new_findings = [fid for fid in a_findings if fid not in b_findings]
    b_acc = b_exec.get("acceptance_version")
    a_acc = a_exec.get("acceptance_version")
    stale_evidence = []
    if b_cand.get("head") and a_cand.get("head") and b_cand.get("head") != a_cand.get("head"):
        stale_evidence.append("prior evidence bound to different candidate head")
    if b_cand.get("content_digest") and a_cand.get("content_digest") and (
        b_cand.get("content_digest") != a_cand.get("content_digest")
    ):
        stale_evidence.append("prior content_digest no longer matches")
    return {
        "schema": "atlas.taskcontract.review.compare/1",
        "package_id": PACKAGE_ID,
        "before_package_digest": bh.get("package_digest") or package_digest(before),
        "after_package_digest": ah.get("package_digest") or package_digest(after),
        "candidate_identity_changed": b_cand != a_cand,
        "candidate_before": b_cand,
        "candidate_after": a_cand,
        "files_added_or_changed": sorted(a_changes - b_changes),
        "files_removed_since_before": sorted(b_changes - a_changes),
        "acceptance_version_before": b_acc,
        "acceptance_version_after": a_acc,
        "acceptance_version_changed": b_acc != a_acc,
        "findings_resolved": resolved,
        "findings_still_open": still_open,
        "findings_new": new_findings,
        "checks_again_relevant": [
            row.get("requirement_id")
            for row in (ah.get("evidence_coverage") or [])
            if row.get("coverage")
            in {
                EvidenceCoverageStatus.CHECK_NOT_RUN.value,
                EvidenceCoverageStatus.CHECK_FAILED.value,
                EvidenceCoverageStatus.MANUAL_REVIEW_REQUIRED.value,
            }
        ],
        "stale_evidence_relative_to_after": stale_evidence,
        "prior_approval_carried": False,
        "prior_review_reference": {
            "package_digest": bh.get("package_digest"),
            "scope_note": (
                "Earlier review applies only to its own candidate identity and "
                "acceptance_version; it is not inherited"
            ),
        },
        "grants": "NOTHING. Comparison is informational; decisions stay with the owner procedure.",
    }


def load_execution_binding_from_state(
    state_path: Path,
    *,
    candidate: CandidateIdentity,
    acceptance_version: str | None = None,
    task_id: str | None = None,
) -> ExecutionBinding:
    """Read supervisor state.json without mutating it."""
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    attempts = raw.get("attempts") or {}
    if not isinstance(attempts, dict):
        attempts = {}
    selected = []
    outcomes: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    artifacts: dict[str, str] = {}
    for aid, attempt in sorted(attempts.items()):
        if task_id and attempt.get("task_id") != task_id:
            continue
        selected.append(aid)
        detail = attempt.get("acceptance_detail") or []
        if isinstance(detail, list):
            for row in detail:
                if isinstance(row, dict):
                    outcomes.append(dict(row))
                    cid = row.get("check_id")
                    if cid:
                        checks.append({"check_id": cid, "passed": row.get("passed")})
        for rel in attempt.get("evidence_paths") or []:
            artifacts[str(rel)] = "path-recorded-no-digest"
        claim = attempt.get("worker_reported")
        # claims collected by caller via worker_claims param
        _ = claim
    program_id = raw.get("program_id")
    if task_id is None and selected:
        task_id = attempts[selected[0]].get("task_id")
    return ExecutionBinding(
        program_id=program_id,
        task_id=task_id,
        attempt_ids=tuple(selected),
        acceptance_version=acceptance_version,
        acceptance_outcomes=tuple(outcomes),
        checks_run=tuple(checks),
        artifact_digests=artifacts,
        candidate=candidate,
        historical_attempt_preserved=True,
    )


def build_result_review_package(
    contract: TaskContract,
    binding: DeploymentBinding | None,
    validation_report: dict[str, Any],
    *,
    program: dict[str, Any] | None = None,
    execution: ExecutionBinding | None = None,
    changes: list[ChangeEntry] | list[dict[str, Any]] | None = None,
    open_findings: list[OpenFinding] | list[dict[str, Any]] | None = None,
    worker_claims: list[WorkerClaim] | list[dict[str, Any]] | None = None,
    validation_plan_ref: str | None = None,
    previous_package: dict[str, Any] | None = None,
    package_version: int = 1,
    targeted_tests: tuple[str, ...] = (),
    bundle_path: str | None = None,
    package_out_hint: str | None = None,
) -> dict[str, Any]:
    """Extend ``atlas.taskcontract.review/1`` with result_handoff (additive)."""
    base = render_review_package(contract, binding, validation_report, program=program)
    change_models: list[ChangeEntry] = []
    for item in changes or []:
        change_models.append(
            item if isinstance(item, ChangeEntry) else ChangeEntry.model_validate(item)
        )
    annotated = classify_change_inventory(
        change_models, mutation_paths=contract.mutation_paths
    )
    unexpected = [
        c
        for c in annotated
        if not c["in_allowed_mutation_scope"]
        or c["kind"] == ChangeKind.UNTRACKED.value
        or c["executable_bit_changed"]
        or c["symlink_changed"]
    ]
    findings = [
        f.model_dump(mode="json") if isinstance(f, OpenFinding) else dict(f)
        for f in (open_findings or [])
    ]
    claims = [
        c.model_dump(mode="json") if isinstance(c, WorkerClaim) else dict(c)
        for c in (worker_claims or [])
    ]
    for c in claims:
        c.setdefault("status", "CLAIM")
        c.setdefault("supported_by_evidence", False)

    cand_digest = None
    evidence_cand = None
    exec_dump = None
    if execution is not None:
        exec_dump = execution.model_dump(mode="json")
        cand = execution.candidate
        cand_digest = cand.head or cand.content_digest or cand.patch_digest
        # Evidence other-candidate detection: artifact marker if present.
        evidence_cand = (execution.artifact_digests or {}).get("_candidate_digest")

    coverage = build_evidence_coverage(
        contract,
        acceptance_outcomes=execution.acceptance_outcomes if execution else (),
        checks_run=execution.checks_run if execution else (),
        candidate_digest=cand_digest,
        evidence_candidate_digest=evidence_cand,
    )
    overview = build_reviewer_overview(
        contract,
        change_paths=[c["path"] for c in annotated],
        coverage=coverage,
        open_findings=findings,
        worker_claims=claims,
        validation_plan_ref=validation_plan_ref,
    )
    inspection: dict[str, Any]
    if execution is not None:
        inspection = build_inspection_commands(
            package_path=package_out_hint,
            candidate=execution.candidate,
            bundle_path=bundle_path,
            targeted_tests=targeted_tests,
        )
    else:
        inspection = {
            "commands": [
                {
                    "purpose": "incomplete_package",
                    "command": (
                        "Supply --state/--candidate before restore; execution "
                        "binding was not provided"
                    ),
                    "side_effects": "none",
                    "runtime": "operator",
                }
            ],
            "package_generation_executed_tests": False,
            "credentials_included": False,
        }
    prev_digest = None
    prev_version = None
    if previous_package is not None:
        prev_rh = previous_package.get(EXTENSION_KEY) or {}
        prev_digest = prev_rh.get("package_digest") or package_digest(previous_package)
        prev_version = prev_rh.get("package_version")

    handoff: dict[str, Any] = {
        "extension_of": SCHEMA_REVIEW,
        "package_id": PACKAGE_ID,
        "package_version": package_version,
        "previous_package_digest": prev_digest,
        "previous_package_version": prev_version,
        "truth_boundary": TRUTH_BOUNDARY,
        "execution": exec_dump,
        "mutation_scope": {
            "allowed_mutation_paths": list(contract.mutation_paths),
            "changes": annotated,
            "unexpected_or_attention": unexpected,
            "note": (
                "In-scope path does not prove content correctness. "
                "Unexpected changes are reported only — not auto-removed."
            ),
        },
        "evidence_coverage": coverage,
        "reviewer_overview": overview,
        "open_findings": findings,
        "worker_claims": claims,
        "validation_plan_ref": validation_plan_ref,
        "inspection": inspection,
        "idempotency": {
            "same_result_same_digest": True,
            "repeat_export_creates_new_attempt": False,
            "repeat_export_creates_review_decision": False,
        },
        "package_completeness": "COMPLETE" if execution is not None else "INCOMPLETE",
        "product_quality_verdict": "NOT_EVALUATED_HERE",
        "grants": (
            "NOTHING. This handoff prepares independent review; it does not "
            "approve this work or authorize merge."
        ),
        "independent_review": False,
        "merge_authorized": False,
        "self_approval": False,
    }
    base[EXTENSION_KEY] = handoff
    digest = package_digest(base)
    handoff["package_digest"] = digest
    base[EXTENSION_KEY] = handoff
    # Embed digest also at top for quick identity checks.
    base["result_handoff_package_digest"] = digest
    return base


def export_is_idempotent(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """True when two exports of the same result share package_digest."""
    a = (first.get(EXTENSION_KEY) or {}).get("package_digest") or package_digest(first)
    b = (second.get(EXTENSION_KEY) or {}).get("package_digest") or package_digest(second)
    return a == b


def render_overview_markdown(package: dict[str, Any]) -> str:
    """Human-readable overview. Untrusted claim text is fenced as CLAIM."""
    rh = package.get(EXTENSION_KEY) or {}
    ov = rh.get("reviewer_overview") or {}
    lines = [
        f"# Result review handoff (`{PACKAGE_ID}`)",
        "",
        f"- Package digest: `{rh.get('package_digest')}`",
        f"- Version: {rh.get('package_version')}",
        f"- Completeness: {rh.get('package_completeness')} "
        f"(product quality: {rh.get('product_quality_verdict')})",
        f"- Grants: {rh.get('grants')}",
        "",
        "## Problem addressed",
        str(ov.get("problem_addressed") or "(not supplied)"),
        "",
        "## Observable outcome",
        str(ov.get("observable_outcome") or "(not supplied)"),
        "",
        "## What changed (paths)",
    ]
    for path in ov.get("what_changed_paths") or []:
        lines.append(f"- `{path}`")
    if not ov.get("what_changed_paths"):
        lines.append("- (no change inventory supplied)")
    lines += ["", "## How checked", "```json", _canonical(ov.get("how_checked") or {}), "```"]
    lines += ["", "## Needs extra attention"]
    for item in ov.get("needs_extra_attention") or []:
        lines.append(f"- `{item}`")
    lines += ["", "## Remaining risks / unknowns"]
    for item in ov.get("remaining_risks_or_unknowns") or ["(none recorded)"]:
        lines.append(f"- {item}")
    lines += ["", "## Worker claims (not evidence)"]
    for claim in ov.get("worker_claims_labeled") or ["(none)"]:
        lines.append(f"- {claim}")
    lines += ["", "## Where to look", "```json", _canonical(ov.get("where_to_look") or {}), "```"]
    unexpected = (rh.get("mutation_scope") or {}).get("unexpected_or_attention") or []
    if unexpected:
        lines += ["", "## Unexpected / attention changes (not auto-fixed)"]
        for row in unexpected:
            lines.append(
                f"- `{row.get('path')}` kind={row.get('kind')} "
                f"in_scope={row.get('in_allowed_mutation_scope')}"
            )
    lines += ["", "## Inspection commands"]
    for cmd in (rh.get("inspection") or {}).get("commands") or []:
        lines.append(f"- **{cmd.get('purpose')}**: `{cmd.get('command')}`")
        lines.append(
            f"  _(runtime={cmd.get('runtime')}; side_effects={cmd.get('side_effects')})_"
        )
    lines.append("")
    return "\n".join(lines)
