"""Lightweight exact-head CI observer. No LLM run. No secrets."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CANONICAL_PR = 429
CANONICAL_REPO = "B0LK13/project-atlas"

CiStatus = Literal[
    "PENDING",
    "PASS",
    "FAIL",
    "UNKNOWN",
    "CANCELLED",
    "STALE_SUPERSEDED",
]


class CiObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    head_sha: str
    run_id: str | None = None
    status: CiStatus
    conclusion: str | None = None
    observer: Literal["SDK_SUPERVISOR"] = "SDK_SUPERVISOR"
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


class PrHeadRef(BaseModel):
    """Live pull-request head. Not a certification."""

    model_config = ConfigDict(extra="forbid")

    pr_number: int = Field(ge=1)
    head_sha: str
    tree_sha: str | None = None


def classify_exact_head_status(
    *,
    raw_status: str,
    conclusion: str | None,
) -> CiStatus:
    """Classify one exact-head Actions run. Cancelled is not FAIL."""
    status_l = raw_status.lower()
    conclusion_l = (conclusion or "").lower() or None
    if status_l in {"queued", "in_progress", "waiting", "pending"}:
        return "PENDING"
    if conclusion_l == "success":
        return "PASS"
    if conclusion_l == "cancelled":
        return "CANCELLED"
    if conclusion_l in {"failure", "timed_out", "startup_failure"}:
        return "FAIL"
    return "UNKNOWN"


def classify_against_live_head(
    *,
    exact: CiObservation,
    live_head: str | None,
) -> CiObservation:
    """Case C/D: cancelled or any observation for a superseded head is stale."""
    if live_head and live_head != exact.head_sha:
        return exact.model_copy(
            update={"status": "STALE_SUPERSEDED"}
        )
    return exact


def observe_exact_head_ci(
    *,
    head_sha: str,
    repo: str = CANONICAL_REPO,
    gh_bin: str = "gh",
) -> CiObservation:
    """Read GitHub Actions for one commit. Bounded, no polling inside this call."""
    if len(head_sha) != 40 or any(ch not in "0123456789abcdef" for ch in head_sha):
        return CiObservation(head_sha=head_sha, status="UNKNOWN")
    try:
        proc = subprocess.run(
            [
                gh_bin,
                "run",
                "list",
                "--repo",
                repo,
                "--commit",
                head_sha,
                "--limit",
                "1",
                "--json",
                "databaseId,status,conclusion,headSha",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return CiObservation(head_sha=head_sha, status="UNKNOWN")
    if proc.returncode != 0:
        return CiObservation(head_sha=head_sha, status="UNKNOWN")
    try:
        rows = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return CiObservation(head_sha=head_sha, status="UNKNOWN")
    if not isinstance(rows, list) or not rows:
        return CiObservation(head_sha=head_sha, status="PENDING")
    row = rows[0]
    if not isinstance(row, dict):
        return CiObservation(head_sha=head_sha, status="UNKNOWN")
    run_id = str(row.get("databaseId") or "") or None
    raw_status = str(row.get("status") or "").lower()
    conclusion = str(row.get("conclusion") or "") or None
    status = classify_exact_head_status(raw_status=raw_status, conclusion=conclusion)
    return CiObservation(
        head_sha=head_sha, run_id=run_id, status=status, conclusion=conclusion
    )


def refresh_pr_head(
    *,
    pr_number: int = CANONICAL_PR,
    repo: str = CANONICAL_REPO,
    gh_bin: str = "gh",
) -> PrHeadRef | None:
    """Read the live PR head. Does not mutate. Returns None if gh is unavailable."""
    try:
        proc = subprocess.run(
            [
                gh_bin,
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repo,
                "--json",
                "headRefOid",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    head = str(payload.get("headRefOid") or "")
    if len(head) != 40:
        return None
    tree: str | None = None
    try:
        tree_proc = subprocess.run(
            [
                gh_bin,
                "api",
                f"repos/{repo}/commits/{head}",
                "--jq",
                ".commit.tree.sha",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        candidate = (tree_proc.stdout or "").strip()
        if tree_proc.returncode == 0 and len(candidate) == 40:
            tree = candidate
    except (OSError, subprocess.TimeoutExpired):
        tree = None
    return PrHeadRef(pr_number=pr_number, head_sha=head, tree_sha=tree)


def persist_observation(root: Path, observation: CiObservation) -> Path:
    target = root / ".atlas" / "orchestration" / "sdk-runtime" / "ci-observer.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(observation.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
