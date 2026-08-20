"""Lightweight exact-head CI observer. No LLM run. No secrets."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CiObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    head_sha: str
    run_id: str | None = None
    status: Literal["PENDING", "PASS", "FAIL", "UNKNOWN"]
    conclusion: str | None = None
    observer: Literal["SDK_SUPERVISOR"] = "SDK_SUPERVISOR"
    merge_authorized: Literal[False] = False
    execution_authorized: Literal[False] = False


def observe_exact_head_ci(
    *,
    head_sha: str,
    repo: str = "B0LK13/project-atlas",
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
    if raw_status in {"queued", "in_progress", "waiting", "pending"}:
        status: Literal["PENDING", "PASS", "FAIL", "UNKNOWN"] = "PENDING"
    elif conclusion == "success":
        status = "PASS"
    elif conclusion in {"failure", "timed_out", "cancelled", "startup_failure"}:
        status = "FAIL"
    else:
        status = "UNKNOWN"
    return CiObservation(
        head_sha=head_sha, run_id=run_id, status=status, conclusion=conclusion
    )


def persist_observation(root: Path, observation: CiObservation) -> Path:
    target = root / ".atlas" / "orchestration" / "sdk-runtime" / "ci-observer.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(observation.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
