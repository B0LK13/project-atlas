"""AS-2.2-EVAL-001 — hidden-holdout isolation regression guards.

W2 finding HIDDEN_HOLDOUT_ISOLATION=FAIL forward fix. These tests fail closed if
a future change reintroduces a committed plaintext holdout answer key, a durable
receipt that reconstructs holdout answers, or holdout leakage on the un-armed
scoring path.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from project_atlas.eval_substrate import (
    EVAL_HOLDOUT_EXPECTED_PATH_ENV,
    EVAL_SCORING_CAPABILITY_ENV,
    load_cases,
    scoring_capability_granted,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Basename patterns that must never appear as a committed plaintext answer map.
_EXPECTED_MAP_RE = re.compile(r"(eval.*expected|holdout.*expected).*\.json$", re.IGNORECASE)


def _git_tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def test_no_committed_plaintext_holdout_expected_map() -> None:
    """glob **/*eval*expected*.json (and holdout variant) finds nothing tracked."""
    tracked = _git_tracked_files(REPO_ROOT)
    leaks = [rel for rel in tracked if _EXPECTED_MAP_RE.search(Path(rel).name)]
    assert leaks == [], f"committed holdout expected map(s) leaked: {leaks}"


def test_no_committed_receipt_reconstructs_holdout_answers() -> None:
    """No tracked JSON persists per-row holdout predicted_norm/matched/expected."""
    offenders: list[str] = []
    for rel in _git_tracked_files(REPO_ROOT):
        if not rel.endswith(".json"):
            continue
        path = REPO_ROOT / rel
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        results = data.get("results")
        if not isinstance(results, list):
            continue
        for row in results:
            if not isinstance(row, dict) or row.get("visibility") != "holdout":
                continue
            if any(k in row for k in ("predicted_norm", "matched", "expected_norm")):
                offenders.append(rel)
                break
    assert offenders == [], f"receipt(s) reconstruct holdout answers: {offenders}"


def test_scoring_without_capability_exposes_non_hidden_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_cases('scoring') without capability yields the non-hidden view only."""
    monkeypatch.delenv(EVAL_SCORING_CAPABILITY_ENV, raising=False)
    monkeypatch.delenv(EVAL_HOLDOUT_EXPECTED_PATH_ENV, raising=False)
    assert not scoring_capability_granted()
    cases = load_cases(REPO_ROOT, "scoring")
    ids = {c["case_id"] for c in cases}
    # public + retired-holdout regression cases; never a live hidden holdout.
    assert ids == {"EV-PUB-001", "EV-PUB-002", "EV-REG-001", "EV-REG-002"}
    assert not any(str(cid).startswith("EV-HOLD-") for cid in ids)
