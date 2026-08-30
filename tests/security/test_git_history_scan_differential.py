"""Differential proof: the redesigned historical-leak scanner (Cluster C,
D-CODEX-ATLAS-OWNER-FRONTIER-RESOLUTION-CI-CONDITIONAL-INTEGRATION-AND-DAG-
CONTINUATION §5) detects every violation the original exhaustive
``git grep <token> <every revision>`` / ``git log -p -S <id>`` implementation
detects, across synthetic histories covering every required adversarial
position, PLUS a real violation class the original implementation provably
MISSES (a ``-S`` pickaxe blind spot: editing an existing case file's
``expected`` field without changing the case-id string's occurrence count
leaves the commit invisible to ``-S <case_id>``).

These synthetic repos are tiny, so the original algorithm's cost stays
affordable here even though it becomes pathological against the real
Project Atlas history (see the PR's runtime evidence) -- exactly the
"generated matrix of small synthetic Git histories where the old exhaustive
implementation remains affordable" the redesign directive calls for.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.security.git_history_scan import find_leaked_holdout_evidence

# Extends (not replaces) the real process environment -- Cursor automated
# review of PR #651 found that a bare identity-only dict silently drops
# PATH (and, on Windows, SYSTEMROOT) for the child `git` process. This
# happened to still work on this session's Linux/WSL host only because of
# execvpe's POSIX default-PATH fallback when PATH is entirely absent from
# `env` -- a coincidence of this one host, not a portable guarantee, and
# specifically NOT something Windows subprocess/git.exe can be relied on to
# tolerate (this repo's own CI matrix includes `windows-latest`).
#
# Spreading the full os.environ also forwards HOME (and therefore the
# host's global/system gitconfig) and, if set, GIT_DIR/GIT_WORK_TREE/
# GIT_INDEX_FILE. Independently confirmed on this host: with a bare
# `**os.environ` spread and no isolation, `git config --get
# commit.gpgsign` inside a freshly `git init`-ed scratch repo returns
# "true" -- inherited straight from this account's real global gitconfig.
# Every synthetic commit here has therefore been silently GPG-signing with
# this account's real key; it only ever appeared to work because this host
# happens to have a usable default signing key configured. On a host
# without one (any ordinary CI runner, most fresh dev machines) every
# commit in this file would fail with a GPG signing error. GIT_DIR/
# GIT_WORK_TREE/GIT_INDEX_FILE are not currently set on this host, but if
# ever set by an invoking process (e.g. a git hook), they would redirect
# init/add/commit at the WRONG repository (the real developer checkout)
# instead of the intended `tmp_path` scratch repo -- a correctness/safety
# risk, not just a portability one. Found by Cursor's automated review;
# independently reproduced (the gpgsign leak above) before accepting.
_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
}
for _git_override in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
    _ENV.pop(_git_override, None)

_LEAK_JSON = json.dumps({"case_id": "EV-HOLD-999", "expected": "the-secret-answer"})
_CLEAN_JSON = json.dumps({"case_id": "EV-HOLD-999", "query": "q"})
_NESTED_LEAK_JSON = json.dumps(
    {"case_id": "EV-HOLD-999", "scoring": {"expected": "the-secret-answer"}}
)
_CASE_ID_KEYED_RECORD_JSON = json.dumps({"EV-HOLD-999": {"expected": "the-secret-answer"}})
_EXPECTED_MAP_KEYED_BY_CASE_ID_JSON = json.dumps(
    {"expected": {"EV-HOLD-999": "the-secret-answer"}}
)
_CASE_IDS = ("EV-HOLD-999",)


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, env=_ENV
    )


def _build_repo(root: Path, commits: list[dict[str, str | None]]) -> Path:
    """Each dict maps repo-relative path -> content (``None`` deletes it);
    one commit per dict, applied in order."""
    root.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], root)
    for i, ops in enumerate(commits):
        for rel, content in ops.items():
            path = root / rel
            if content is None:
                path.unlink()
                _git(["rm", "-q", rel], root)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                _git(["add", rel], root)
        _git(["commit", "-q", "-m", f"c{i}", "--allow-empty"], root)
    return root


def _old_algorithm_answer_leak(repo: Path, case_ids: tuple[str, ...]) -> bool:
    """Faithful port of the ORIGINAL test_adv_git_history_access "expected"
    -leak check, for differential comparison only."""
    for case_id in case_ids:
        log = _git(
            ["log", "--all", "-p", "-S", case_id, "--", "fixtures/eval"], repo
        )
        for line in log.stdout.splitlines():
            if line.startswith("+") and '"expected"' in line:
                return True
    return False


@pytest.mark.parametrize(
    "name, commits, expect_leak",
    [
        ("clean_no_violation", [{"fixtures/eval/f.json": _CLEAN_JSON}], False),
        (
            "violation_at_current_head",
            [
                {"fixtures/eval/f.json": _CLEAN_JSON},
                {"fixtures/eval/f.json": _LEAK_JSON},
            ],
            True,
        ),
        ("violation_at_first_commit", [{"fixtures/eval/f.json": _LEAK_JSON}], True),
        (
            "violation_at_middle_commit",
            [
                {"fixtures/eval/f.json": _CLEAN_JSON},
                {"fixtures/eval/f.json": _LEAK_JSON},
                {"fixtures/eval/f.json": _CLEAN_JSON},
            ],
            True,
        ),
        (
            "violation_then_renamed_path",
            [
                {"fixtures/eval/old.json": _LEAK_JSON},
                {"fixtures/eval/old.json": None, "fixtures/eval/new.json": _LEAK_JSON},
            ],
            True,
        ),
        (
            "violation_then_deleted_path",
            [{"fixtures/eval/f.json": _LEAK_JSON}, {"fixtures/eval/f.json": None}],
            True,
        ),
        (
            "violation_deleted_then_recreated_clean",
            [
                {"fixtures/eval/f.json": _LEAK_JSON},
                {"fixtures/eval/f.json": None},
                {"fixtures/eval/f.json": _CLEAN_JSON},
            ],
            True,
        ),
        (
            "same_content_different_pathname",
            [
                {"docs/notes.json": _LEAK_JSON},
                {"fixtures/eval/f.json": _LEAK_JSON},
            ],
            True,
        ),
        (
            "violation_split_across_sibling_dicts",
            [{"fixtures/eval/f.json": _NESTED_LEAK_JSON}],
            True,
        ),
    ],
)
def test_new_scanner_matches_ground_truth(
    tmp_path: Path, name: str, commits: list[dict[str, str | None]], expect_leak: bool
) -> None:
    repo = _build_repo(tmp_path / name, commits)
    _secret_hits, answer_hits = find_leaked_holdout_evidence(
        repo, secret_tokens=(), holdout_case_ids=_CASE_IDS
    )
    assert bool(answer_hits) == expect_leak


def test_new_scanner_rejects_false_positive_from_source_code_discussion(
    tmp_path: Path,
) -> None:
    """A test file that legitimately asserts on both the case id and the
    field name "expected" together must NOT be flagged -- confirmed real
    false-positive class this redesign fixes (see module docstring)."""
    repo = _build_repo(
        tmp_path / "fp_guard",
        [
            {
                "tests/test_thing.py": (
                    'def test_x():\n'
                    '    assert hold["expected"] == scoring_capability["EV-HOLD-999"]\n'
                )
            }
        ],
    )
    _secret_hits, answer_hits = find_leaked_holdout_evidence(
        repo, secret_tokens=(), holdout_case_ids=_CASE_IDS
    )
    assert answer_hits == ()


def test_new_scanner_detects_secret_amid_many_irrelevant_commits(tmp_path: Path) -> None:
    repo = tmp_path / "many_commits"
    commits: list[dict[str, str | None]] = [{"README.md": f"noise {i}"} for i in range(30)]
    commits.insert(15, {"leaked.txt": "token-abc123-should-never-appear"})
    commits.append({"leaked.txt": None})
    _build_repo(repo, commits)
    secret_hits, _answer_hits = find_leaked_holdout_evidence(
        repo, secret_tokens=("token-abc123-should-never-appear",), holdout_case_ids=()
    )
    assert secret_hits


def test_old_algorithm_is_proven_to_miss_same_occurrence_count_edits(
    tmp_path: Path,
) -> None:
    """Documents WHY the redesign is a strict strengthening, not merely a
    speedup: -S pickaxe flags a commit only when the NUMBER of occurrences
    of the pickaxe string changes between parent and child. Editing an
    existing case file's "expected" field while the case_id string's own
    occurrence count stays the same (still exactly one "EV-HOLD-999" before
    and after) is invisible to `git log -S <case_id>` -- confirmed here
    against the OLD algorithm directly. This is not a synthetic edge case
    invented to make the new design look good; it is the realistic shape of
    a real mistake (editing a case file to add its answer) that the old
    design would silently fail to catch.
    """
    repo = _build_repo(
        tmp_path / "old_blind_spot",
        [
            {"fixtures/eval/f.json": _CLEAN_JSON},
            {"fixtures/eval/f.json": _LEAK_JSON},
        ],
    )
    assert _old_algorithm_answer_leak(repo, _CASE_IDS) is False  # old: false negative
    _secret_hits, answer_hits = find_leaked_holdout_evidence(
        repo, secret_tokens=(), holdout_case_ids=_CASE_IDS
    )
    assert bool(answer_hits) is True  # new: correctly catches it


def test_new_scanner_catches_case_id_and_expected_split_across_sibling_dicts(
    tmp_path: Path,
) -> None:
    """PR #651 round-1 independent verification: REJECTED. Pins the found
    defect as a permanent regression test.

    An earlier version of `_structural_answer_key_leaks` required the
    holdout case id and the `"expected"` field to be in the SAME dict
    record. Adversarial IV constructed
    `{"case_id": "EV-HOLD-999", "scoring": {"expected": "leak"}}` -- a real,
    ordinary way to structure a scored-case record (grading metadata nested
    under a sibling key) -- and proved the same-dict-only check silently
    missed it, while the OLD (pre-redesign) algorithm's ADDED-line substring
    check caught it (the whole object lands on one diff line). The fix
    widened detection to same-DOCUMENT co-occurrence (case id anywhere in
    the parsed JSON value, `"expected"` key anywhere in the same value),
    which this test pins.
    """
    repo = _build_repo(
        tmp_path / "sibling_dict_leak", [{"fixtures/eval/f.json": _NESTED_LEAK_JSON}]
    )
    _secret_hits, answer_hits = find_leaked_holdout_evidence(
        repo, secret_tokens=(), holdout_case_ids=_CASE_IDS
    )
    assert bool(answer_hits) is True


@pytest.mark.parametrize(
    "name, leak_json",
    [
        ("case_id_keyed_record", _CASE_ID_KEYED_RECORD_JSON),
        ("expected_map_keyed_by_case_id", _EXPECTED_MAP_KEYED_BY_CASE_ID_JSON),
    ],
)
def test_new_scanner_catches_case_id_used_as_json_object_key(
    tmp_path: Path, name: str, leak_json: str
) -> None:
    """Found post-round-2-IV via Cursor's automated review of PR #651, and
    independently reproduced against the unfixed code before accepting the
    fix (an unfixed run against `_CASE_ID_KEYED_RECORD_JSON` returned no
    hit -- confirmed real, not overstated).

    `_json_contains_string` originally walked only dict VALUES, so a
    holdout case id appearing solely as a JSON object KEY was invisible
    even when the same document carried an `"expected"` field. This is not
    a contrived shape: it is the exact structure of this repository's own
    operator expected-answer map (`test_as_2_2_eval_broker_adversarial.py`'s
    `broker` fixture builds `{cid: token for cid in meta}` -- case ids as
    keys). Pins both the direct form (`{case_id: {"expected": ...}}`) and
    the sibling form (`{"expected": {case_id: ...}}`).
    """
    repo = _build_repo(tmp_path / name, [{"fixtures/eval/f.json": leak_json}])
    _secret_hits, answer_hits = find_leaked_holdout_evidence(
        repo, secret_tokens=(), holdout_case_ids=_CASE_IDS
    )
    assert bool(answer_hits) is True
