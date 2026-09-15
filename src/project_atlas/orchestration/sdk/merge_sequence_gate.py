"""Fail-closed dependent-merge gate — parent post-merge seal before child merge.

D-138: PR436 must not merge until PR435 post-merge CI is TERMINAL_PASS and the
durable seal is recorded and bound to exact Git identity.
"""

from __future__ import annotations

import json
import time
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from project_atlas.orchestration.sdk.ci_observer import CiJobObservation, CiObservation, CiStatus
from project_atlas.orchestration.sdk.models import STATE_DIR_RELATIVE, SdkRuntimeError

PACKAGE_ID: Final[Literal["AS-ORCH-MERGE-SEQUENCE-GATE-001"]] = (
    "AS-ORCH-MERGE-SEQUENCE-GATE-001"
)
SEAL_FILENAME: Final[str] = "parent-post-merge-seal.json"
DISPATCH_LOG_FILENAME: Final[str] = "dependent-merge-dispatch-log.jsonl"
GATE_STATE_FILENAME: Final[str] = "dependent-merge-gate-state.json"

# Parent package observers that mint post-merge seals for stacked child merges.
_STACKED_MERGE_BY_PACKAGE: Final[dict[str, tuple[int, int]]] = {
    "AS-ORCH-SELF-WAKE-RESIDENT-DRIVER-001": (435, 436),
}

# Non-terminal CI / seal states that must deny dependent merge (fail closed).
_BLOCKING_CI: Final[frozenset[CiStatus]] = frozenset(
    {"PENDING", "UNKNOWN", "CANCELLED", "STALE_SUPERSEDED"}
)


class PrerequisiteSealState(StrEnum):
    """Evaluation of a parent post-merge prerequisite."""

    TERMINAL_PASS = "TERMINAL_PASS"
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    UNKNOWN = "UNKNOWN"
    MISSING = "MISSING"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    STALE = "STALE"
    PARTIAL = "PARTIAL"
    TERMINAL_FAIL = "TERMINAL_FAIL"


_TERMINAL_PASS_ONLY: Final[frozenset[PrerequisiteSealState]] = frozenset(
    {PrerequisiteSealState.TERMINAL_PASS}
)


class ParentPostMergeSeal(BaseModel):
    """Durable parent post-merge seal bound to exact Git identity."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    package_id: Literal["AS-ORCH-MERGE-SEQUENCE-GATE-001"] = PACKAGE_ID
    parent_pr_number: int = Field(ge=1)
    child_pr_number: int = Field(ge=1)
    parent_merge_commit: str = Field(min_length=40, max_length=40)
    parent_post_merge_main_sha: str = Field(min_length=40, max_length=40)
    parent_post_merge_tree: str = Field(min_length=40, max_length=40)
    ci_run_id: str = Field(min_length=1)
    ci_conclusion: Literal["success"] = "success"
    seal_generation: int = Field(ge=0)
    sealed_at: float
    merge_authorized: Literal[False] = False


class DependentMergeDecision(BaseModel):
    """Machine-readable dependent merge gate outcome."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reason: str
    prerequisite_state: PrerequisiteSealState
    parent_merged: bool
    parent_seal_pass: bool
    seal_sha_match: bool
    target_moved: bool
    child_merge_authorized: bool
    merge_authorized: Literal[False] = False


class MergeDispatchRecord(BaseModel):
    """Proof that child dispatch occurred after durable parent seal."""

    model_config = ConfigDict(extra="forbid")

    child_pr_number: int = Field(ge=1)
    parent_seal_generation: int = Field(ge=0)
    parent_sealed_at: float
    dispatched_at: float
    merge_authorized: Literal[False] = False


def seal_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / SEAL_FILENAME


def dispatch_log_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / DISPATCH_LOG_FILENAME


def gate_state_path(root: Path) -> Path:
    return root / STATE_DIR_RELATIVE / GATE_STATE_FILENAME


def classify_ci_prerequisite(obs: CiObservation | None) -> PrerequisiteSealState:
    """Map CI observation to prerequisite seal state. Fail closed."""
    if obs is None:
        return PrerequisiteSealState.MISSING
    status = obs.status
    if status == "PASS":
        required = [j for j in obs.jobs if j.required]
        if not required:
            # Run-level PASS without job detail — treat as PARTIAL (deny).
            if (obs.run_status or "").lower() in {"in_progress", "queued", "waiting"}:
                return PrerequisiteSealState.RUNNING
            return PrerequisiteSealState.PARTIAL
        incomplete = [
            j
            for j in required
            if j.job_status.lower() != "completed"
            or (j.job_conclusion or "").lower() != "success"
        ]
        if incomplete:
            if any(
                j.job_status.lower() in {"queued", "in_progress", "waiting", "pending"}
                for j in incomplete
            ):
                return PrerequisiteSealState.RUNNING
            if any((j.job_conclusion or "").lower() == "cancelled" for j in incomplete):
                return PrerequisiteSealState.CANCELLED
            if any(
                (j.job_conclusion or "").lower() in {"timed_out", "failure"}
                for j in incomplete
            ):
                return PrerequisiteSealState.TERMINAL_FAIL
            return PrerequisiteSealState.PARTIAL
        return PrerequisiteSealState.TERMINAL_PASS
    if status == "PENDING":
        return PrerequisiteSealState.PENDING
    if status == "CANCELLED":
        return PrerequisiteSealState.CANCELLED
    if status == "STALE_SUPERSEDED":
        return PrerequisiteSealState.STALE
    if status == "FAIL":
        return PrerequisiteSealState.TERMINAL_FAIL
    return PrerequisiteSealState.UNKNOWN


def seal_from_ci_observation(
    *,
    obs: CiObservation,
    parent_pr_number: int,
    child_pr_number: int,
    parent_merge_commit: str,
    parent_post_merge_main_sha: str,
    parent_post_merge_tree: str,
    seal_generation: int,
    sealed_at: float | None = None,
) -> ParentPostMergeSeal | None:
    """Mint durable seal only when prerequisite is TERMINAL_PASS."""
    if classify_ci_prerequisite(obs) is not PrerequisiteSealState.TERMINAL_PASS:
        return None
    if obs.run_id is None:
        return None
    if (obs.conclusion or obs.run_conclusion or "").lower() != "success":
        return None
    return ParentPostMergeSeal(
        parent_pr_number=parent_pr_number,
        child_pr_number=child_pr_number,
        parent_merge_commit=parent_merge_commit,
        parent_post_merge_main_sha=parent_post_merge_main_sha,
        parent_post_merge_tree=parent_post_merge_tree,
        ci_run_id=obs.run_id,
        seal_generation=seal_generation,
        sealed_at=sealed_at if sealed_at is not None else time.time(),
    )


def persist_parent_seal(root: Path, seal: ParentPostMergeSeal) -> Path:
    target = seal_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(seal.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def load_parent_seal(root: Path) -> ParentPostMergeSeal | None:
    target = seal_path(root)
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SdkRuntimeError("parent seal corrupt", code="SEAL_CORRUPT") from exc
    return ParentPostMergeSeal.model_validate(payload)


def seal_matches_live(
    seal: ParentPostMergeSeal,
    *,
    live_main_sha: str,
    live_tree_sha: str,
    parent_merge_commit: str,
) -> bool:
    """Exact-object binding — stale seals for wrong SHAs are rejected."""
    return (
        seal.parent_post_merge_main_sha == live_main_sha
        and seal.parent_post_merge_tree == live_tree_sha
        and seal.parent_merge_commit == parent_merge_commit
    )


def evaluate_dependent_merge_allowed(
    *,
    parent_merged: bool,
    parent_seal: ParentPostMergeSeal | None,
    ci_observation: CiObservation | None,
    live_main_sha: str,
    live_tree_sha: str,
    parent_merge_commit: str,
    child_merge_authorized: bool,
) -> DependentMergeDecision:
    """Fail-closed gate: child merge only after parent seal TERMINAL_PASS."""
    prereq = classify_ci_prerequisite(ci_observation)
    seal_pass = False
    seal_sha_match = False
    target_moved = False

    if parent_seal is not None:
        seal_sha_match = seal_matches_live(
            parent_seal,
            live_main_sha=live_main_sha,
            live_tree_sha=live_tree_sha,
            parent_merge_commit=parent_merge_commit,
        )
        if not seal_sha_match:
            target_moved = True
        seal_pass = seal_sha_match and parent_seal.ci_conclusion == "success"

    # Durable seal is authoritative once written; live CI must not regress below.
    if parent_seal is None:
        effective = prereq
    elif not seal_pass:
        effective = PrerequisiteSealState.STALE
    elif prereq not in _TERMINAL_PASS_ONLY:
        # Seal exists but live CI degraded — deny (fail closed).
        effective = (
            prereq
            if prereq != PrerequisiteSealState.TERMINAL_PASS
            else PrerequisiteSealState.STALE
        )
    else:
        effective = PrerequisiteSealState.TERMINAL_PASS

    allowed = (
        parent_merged
        and child_merge_authorized
        and effective is PrerequisiteSealState.TERMINAL_PASS
        and seal_pass
        and parent_seal is not None
    )

    if not parent_merged:
        reason = "PARENT_NOT_MERGED"
    elif not child_merge_authorized:
        reason = "CHILD_MERGE_NOT_AUTHORIZED"
    elif parent_seal is None:
        reason = "PARENT_SEAL_NOT_DURABLY_RECORDED"
    elif not seal_sha_match:
        reason = "SEAL_SHA_MISMATCH_TARGET_MOVED"
    elif effective is not PrerequisiteSealState.TERMINAL_PASS:
        reason = f"PREREQUISITE_{effective.value}"
    else:
        reason = "DEPENDENT_MERGE_ALLOWED"

    return DependentMergeDecision(
        allowed=allowed,
        reason=reason,
        prerequisite_state=effective,
        parent_merged=parent_merged,
        parent_seal_pass=seal_pass,
        seal_sha_match=seal_sha_match,
        target_moved=target_moved,
        child_merge_authorized=child_merge_authorized,
    )


def record_child_merge_dispatch(
    root: Path,
    *,
    child_pr_number: int,
    parent_seal: ParentPostMergeSeal,
    dispatched_at: float | None = None,
) -> MergeDispatchRecord:
    """Append dispatch record; proves CHILD_MERGE_DISPATCH_TIME > PARENT_SEAL_TIME."""
    when = dispatched_at if dispatched_at is not None else time.time()
    if when <= parent_seal.sealed_at:
        raise SdkRuntimeError(
            "child dispatch before parent seal durable pass",
            code="DISPATCH_ORDER_VIOLATION",
        )
    record = MergeDispatchRecord(
        child_pr_number=child_pr_number,
        parent_seal_generation=parent_seal.seal_generation,
        parent_sealed_at=parent_seal.sealed_at,
        dispatched_at=when,
    )
    log = dispatch_log_path(root)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.model_dump(mode="json"), sort_keys=True) + "\n")
    return record


def on_ci_terminal_pass_for_stacked_merge(
    root: Path,
    *,
    package_id: str,
    ci_observation: CiObservation,
    parent_merge_commit: str,
    parent_post_merge_main_sha: str,
    parent_post_merge_tree: str,
    seal_generation: int = 1,
) -> ParentPostMergeSeal | None:
    """Mint durable parent seal when stacked parent post-merge CI is TERMINAL_PASS."""
    pair = _STACKED_MERGE_BY_PACKAGE.get(package_id)
    if pair is None:
        return None
    parent_pr, child_pr = pair
    seal = seal_from_ci_observation(
        obs=ci_observation,
        parent_pr_number=parent_pr,
        child_pr_number=child_pr,
        parent_merge_commit=parent_merge_commit,
        parent_post_merge_main_sha=parent_post_merge_main_sha,
        parent_post_merge_tree=parent_post_merge_tree,
        seal_generation=seal_generation,
    )
    if seal is None:
        return None
    persist_parent_seal(root, seal)
    return seal


def refresh_dependent_merge_gate_state(
    root: Path,
    *,
    child_pr_number: int = 436,
    child_merge_authorized: bool = False,
    parent_merged: bool = True,
    parent_merge_commit: str = "",
    live_main_sha: str = "",
    live_tree_sha: str = "",
    ci_observation: CiObservation | None = None,
) -> DependentMergeDecision:
    """Evaluate and persist gate state for the canonical stacked child PR."""
    parent_seal = load_parent_seal(root)
    if not parent_merge_commit and parent_seal is not None:
        parent_merge_commit = parent_seal.parent_merge_commit
    if not live_main_sha and parent_seal is not None:
        live_main_sha = parent_seal.parent_post_merge_main_sha
    if not live_tree_sha and parent_seal is not None:
        live_tree_sha = parent_seal.parent_post_merge_tree
    decision = evaluate_dependent_merge_allowed(
        parent_merged=parent_merged,
        parent_seal=parent_seal,
        ci_observation=ci_observation,
        live_main_sha=live_main_sha,
        live_tree_sha=live_tree_sha,
        parent_merge_commit=parent_merge_commit,
        child_merge_authorized=child_merge_authorized,
    )
    target = gate_state_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = decision.model_dump(mode="json")
    payload["child_pr_number"] = child_pr_number
    payload["refreshed_at"] = time.time()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return decision


def guard_dependent_merge_dispatch(
    root: Path,
    *,
    child_pr_number: int,
    child_merge_authorized: bool,
    live_main_sha: str,
    live_tree_sha: str,
    parent_merge_commit: str,
    parent_merged: bool,
    ci_observation: CiObservation | None = None,
) -> DependentMergeDecision:
    """Mandatory chokepoint before any dependent merge dispatch. Fail closed."""
    decision = evaluate_dependent_merge_allowed(
        parent_merged=parent_merged,
        parent_seal=load_parent_seal(root),
        ci_observation=ci_observation,
        live_main_sha=live_main_sha,
        live_tree_sha=live_tree_sha,
        parent_merge_commit=parent_merge_commit,
        child_merge_authorized=child_merge_authorized,
    )
    if not decision.allowed:
        raise SdkRuntimeError(
            f"dependent merge blocked: {decision.reason}",
            code="DEPENDENT_MERGE_GATE_DENIED",
        )
    parent_seal = load_parent_seal(root)
    if parent_seal is None:
        raise SdkRuntimeError("parent seal missing after allow", code="SEAL_MISSING")
    record_child_merge_dispatch(root, child_pr_number=child_pr_number, parent_seal=parent_seal)
    return decision


def simulate_d137_violation() -> DependentMergeDecision:
    """Deterministic replay of D-137: ubuntu PASS, Windows RUNNING → child denied."""
    obs = CiObservation(
        head_sha="8a38498c5f95181aa66e2a99bc507824fd8a8e60",
        run_id="32563926641",
        status="PASS",
        conclusion=None,
        run_status="in_progress",
        run_conclusion=None,
        jobs=(
            _job("97009630940", "quality (ubuntu-latest, 3.12, full)", "completed", "success"),
            _job("97009630918", "quality (ubuntu-latest, 3.13, compat)", "completed", "success"),
            _job("97009630992", "control-plane", "completed", "success"),
            _job("97009630877", "quality (windows-latest, 3.12, windows)", "in_progress", None),
        ),
    )
    return evaluate_dependent_merge_allowed(
        parent_merged=True,
        parent_seal=None,
        ci_observation=obs,
        live_main_sha="bd8faa8f97df454943181d19f1e14ee826900a20",
        live_tree_sha="49643ac38f3bf0037c0dc78aeef877ecc7e23821",
        parent_merge_commit="8a38498c5f95181aa66e2a99bc507824fd8a8e60",
        child_merge_authorized=True,
    )


def _job(
    job_id: str,
    name: str,
    status: str,
    conclusion: str | None,
) -> CiJobObservation:
    return CiJobObservation(
        job_id=job_id,
        job_name=name,
        job_status=status,
        job_conclusion=conclusion,
        required=True,
    )
