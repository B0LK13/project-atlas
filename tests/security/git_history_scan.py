"""One-pass, blob-deduplicated historical content scanner.

Cluster C redesign (D-CODEX-ATLAS-OWNER-FRONTIER-RESOLUTION-CI-CONDITIONAL-
INTEGRATION-AND-DAG-CONTINUATION §4/§5/§13). Replaces the pathological
``for token in secrets: git grep <token> <every revision>`` pattern (cost
grows with ``len(secrets) * len(revisions)``, and ``git grep`` re-walks each
revision's tree even when most revisions share the same blob content) with a
single traversal that costs ``O(unique blobs ever reachable from any ref)``,
independent of how many revisions or needles are checked.

SECURITY_INVARIANT (formalized before any optimization, per directive §4):
    No needle -- a holdout secret answer value, or a holdout case id
    co-occurring with the literal JSON key ``"expected"`` -- has ever existed
    in any blob object reachable from any ref in this repository's history:
    at any commit, on any branch, under any path or filename, including a
    path that was later renamed, deleted, or recreated, and including
    identical content re-introduced under a different pathname.

THREAT_MODEL: an adversary (an optimizing agent, or an external contributor)
with full read access to the repository INCLUDING its complete commit
history (every ref reachable via ``git rev-list --all``; true dangling/
unreachable objects, which normal `git log`/`git grep`-based tooling also
cannot see, are out of scope for both the old and new implementation alike --
this redesign neither widens nor narrows that boundary).

Why a blob-level scan is not weaker than a revision-level scan: git blob
identity is content-addressed (SHA-1 of the blob's bytes). Every revision's
tree references blobs by that same content hash; a file that is unchanged
across 500 commits is ONE blob object, not 500 copies. ``git rev-list
--objects --all`` enumerates every object -- commit, tree, and blob --
reachable from any ref exactly once. Filtering to blobs and reading each
exactly once therefore visits the exact same universe of historical content
``git grep <pattern> <every revision>`` would visit, with the redundant
re-reads of unchanged content across revisions collapsed away. A path that
is renamed, deleted, or recreated with the same content is the same blob
object regardless of the path/filename used to reach it in any given
revision's tree -- so this approach detects those cases automatically,
without any path-based or rename-tracking logic, which is a STRICT
STRENGTHENING relative to the original ``git log -p -S <id> -- fixtures/eval``
check (that pickaxe search is path-scoped to a single pathspec and inspects
only the lines ADDED in each matching diff hunk, which is a real proof
technique with one known inherent limitation: ``-S`` matches on a net
occurrence-count delta between parent and child, so content added and
removed again within a single commit, or content that migrated outside the
pathspec, is not guaranteed to surface as an "added line" -- this module's
raw-blob-content check has no such limitation, since it inspects every
historical blob's actual bytes directly rather than a diff of them).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BATCH_CHECK_FORMAT = "%(objectname) %(objecttype)"
_EXPECTED_KEY_MARKER = '"expected"'
_ANSWER_KEY_FIELD = "expected"


@dataclass(frozen=True, slots=True)
class LeakedSecretHit:
    """A registered secret value was found in a historical blob."""

    secret_label: str
    blob_sha: str


@dataclass(frozen=True, slots=True)
class LeakedAnswerKeyHit:
    """A holdout case id co-occurs with an ``"expected"`` key in one blob --
    i.e. a blob that looks like a committed answer key for that case."""

    case_id: str
    blob_sha: str


def unique_historical_blob_shas(repo_root: Path) -> list[str]:
    """Every distinct blob object reachable from any ref, listed exactly once.

    ``git rev-list --objects --all`` performs one mark-and-sweep traversal of
    every ref's history; ``git cat-file --batch-check`` classifies each
    listed object in one streamed pass with no further tree walking.
    """
    rev_list = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    object_ids = "\n".join(
        line.split(" ", 1)[0] for line in rev_list.stdout.splitlines() if line.strip()
    )
    if not object_ids:
        return []
    batch_check = subprocess.run(
        ["git", "cat-file", f"--batch-check={_BATCH_CHECK_FORMAT}"],
        cwd=repo_root,
        input=object_ids,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        line.rsplit(" ", 1)[0]
        for line in batch_check.stdout.splitlines()
        if line.endswith(" blob")
    ]


def _iter_unique_historical_blobs(
    repo_root: Path, blob_shas: Sequence[str]
) -> Iterator[tuple[str, bytes]]:
    """Yield each unique blob's raw bytes exactly once, via one streamed
    ``git cat-file --batch`` process (no per-object process spawn)."""
    if not blob_shas:
        return
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=repo_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert proc.stdin is not None and proc.stdout is not None
    try:
        for sha in blob_shas:
            proc.stdin.write((sha + "\n").encode("ascii"))
            proc.stdin.flush()
            header = proc.stdout.readline().decode("ascii", errors="strict")
            parts = header.split()
            if len(parts) != 3 or parts[1] != "blob":
                raise RuntimeError(
                    f"unexpected `git cat-file --batch` header for {sha}: {header!r}"
                )
            size = int(parts[2])
            content = proc.stdout.read(size)
            proc.stdout.read(1)  # the trailing newline `--batch` appends per object
            yield sha, content
    finally:
        proc.stdin.close()
        proc.wait(timeout=120)


def _json_has_answer_key(obj: Any) -> bool:
    """True if any dict anywhere in a parsed JSON value carries an
    ``"expected"`` key, at ANY nesting depth -- not just the top-level
    record. IV finding (PR #651 round 1, REJECTED): restricting the match
    to "the SAME dict has both `case_id` and `expected`" produces a real
    false negative for a document like
    ``{"case_id": "EV-HOLD-999", "scoring": {"expected": "leak"}}`` -- the
    case id and the answer are in the same JSON DOCUMENT, just different,
    sibling/nested dicts, which is an entirely ordinary way to structure a
    scored-case record (grouping grading metadata under a nested key).
    Reproduced directly: the OLD algorithm's ADDED-line substring check DID
    catch this shape (the whole object lands on one diff line); the
    same-dict-only structural check did not. Checking document-wide instead
    of same-record closes that gap while keeping the JSON-parse gate that
    fixes the ORIGINAL false-positive class (Python source that merely
    discusses "expected" and a case id together never parses as JSON at
    all, so it's excluded before this function is even reached)."""
    if isinstance(obj, dict):
        if _ANSWER_KEY_FIELD in obj:
            return True
        return any(_json_has_answer_key(value) for value in obj.values())
    if isinstance(obj, list):
        return any(_json_has_answer_key(item) for item in obj)
    return False


def _json_contains_string(obj: Any, target: str) -> bool:
    """True if ``target`` appears as a string VALUE or object KEY anywhere
    in a parsed JSON value, at any nesting depth -- not restricted to a
    specific field name, for the same document-wide, err-toward-detection
    reasoning as `_json_has_answer_key`.

    Keys must be inspected, not just values: this repository's own operator
    expected-answer map (`test_as_2_2_eval_broker_adversarial.py`'s
    `broker` fixture: ``{cid: token for cid in meta}``) uses holdout case
    ids as dict KEYS, not values -- a values-only walk misses the exact
    on-disk shape this helper exists to catch. Found post-round-2-IV, via
    Cursor's automated review of PR #651 -- independently reproduced before
    accepting (an unfixed run against `{"EV-HOLD-999": {"expected": "..."}}`
    returned no hit) and re-verified after."""
    if isinstance(obj, dict):
        return any(
            _json_contains_string(key, target) or _json_contains_string(value, target)
            for key, value in obj.items()
        )
    if isinstance(obj, list):
        return any(_json_contains_string(item, target) for item in obj)
    return isinstance(obj, str) and obj == target


def _structural_answer_key_leaks(text: str, holdout_case_ids: Sequence[str]) -> set[str]:
    """Case ids whose committed record, in this blob, pairs a holdout case
    id with an ``"expected"`` answer ANYWHERE in the same parsed JSON
    document -- not requiring both in the same dict (see
    `_json_has_answer_key`'s docstring for why that stricter form was
    proven wrong). Parses the blob as JSON first (this repo's holdout cases
    are exclusively JSON; parsing rejects Python/Markdown/etc. source that
    merely *mentions* both substrings, which is what a naive same-blob
    substring check false-positived on: this file's own test source, in its
    own git history, both defines and checks for the strings
    "EV-HOLD-101"/"EV-HOLD-102" and "expected" -- discussing the property is
    not violating it)."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return set()
    if not _json_has_answer_key(parsed):
        return set()
    return {
        case_id
        for case_id in holdout_case_ids
        if case_id and _json_contains_string(parsed, case_id)
    }


# Known, accepted trade-off (round-2 IV of PR #651, CONFIRMED WITH MINOR
# NOTES): document-wide matching can false-positive on a RETIRED holdout
# case. This repo's established "retired holdout -> public regression case"
# workflow (D-ULTRA-RESUME-010 §8) produces files like
# fixtures/eval/regression/cases/EV-REG-00N-*.json carrying a
# `"retired_from": "EV-HOLD-00N"` cross-reference AND their own unrelated,
# now-public `"expected"` field in the same flat dict -- if a RETIRED id
# were ever passed into `holdout_case_ids` here, this would flag those
# files. It does not fire today: the live call site only scans currently-
# active holdout ids, never retired ones. Not a false negative (this
# function never gets less strict about missing a real leak), so it does
# not compromise the security property -- only ever pass CURRENTLY-ACTIVE
# holdout case ids to `find_leaked_holdout_evidence`, not retired ones.


def find_leaked_holdout_evidence(
    repo_root: Path,
    *,
    secret_tokens: Sequence[str] = (),
    holdout_case_ids: Sequence[str] = (),
) -> tuple[tuple[LeakedSecretHit, ...], tuple[LeakedAnswerKeyHit, ...]]:
    """Single traversal of every unique historical blob, checking BOTH
    security properties in one pass (no matter how many secrets/case ids):

    1. none of ``secret_tokens`` appears in any historical blob;
    2. no historical blob's parsed JSON document contains BOTH a
       ``holdout_case_ids`` entry AND an ``"expected"`` answer field,
       ANYWHERE in that document -- the signature of a committed answer key.
       Deliberately JSON-parse-gated rather than a raw substring/same-line
       check across the whole blob: adversarial differential testing against
       this repository's own real history (see the PR evidence doc) found
       that BOTH a same-blob and a same-line substring heuristic
       false-positive on ordinary Python test source that legitimately
       discusses/asserts on the case id and the ``"expected"`` field name
       together (e.g. `hold["expected"] == scoring_capability["EV-HOLD-101"]`)
       without ever containing a real leaked value -- gating on successful
       JSON parse excludes that source entirely (Python source never parses
       as JSON). Document-wide rather than same-dict-only: an EARLIER,
       stricter version of this check required the case id and the
       ``"expected"`` field in the SAME dict record, and independent
       adversarial verification (round 1 IV, REJECTED) proved that version
       has a real false negative -- `{"case_id": "X", "scoring": {"expected":
       "leak"}}` splits the two fields across sibling dicts, an entirely
       ordinary way to structure a scored-case record, and was silently
       missed. Checking document-wide (see `_json_has_answer_key` /
       `_json_contains_string`) closes that gap while keeping the
       false-positive fix, at the cost of being slightly more permissive
       than strictly necessary -- an intentional, security-first trade-off
       (a false positive costs a human a few minutes of triage; a false
       negative costs a leaked evaluation answer).

    Returns ``(secret_hits, answer_key_hits)`` -- both empty on a clean repo.
    """
    blob_shas = unique_historical_blob_shas(repo_root)
    secret_hits: list[LeakedSecretHit] = []
    answer_key_hits: list[LeakedAnswerKeyHit] = []
    for sha, raw in _iter_unique_historical_blobs(repo_root, blob_shas):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("utf-8", errors="replace")
        for token in secret_tokens:
            if token and token in text:
                secret_hits.append(LeakedSecretHit(secret_label=token, blob_sha=sha))
        if _EXPECTED_KEY_MARKER not in text:
            continue
        leaked_case_ids = _structural_answer_key_leaks(text, holdout_case_ids)
        for case_id in sorted(leaked_case_ids):
            answer_key_hits.append(LeakedAnswerKeyHit(case_id=case_id, blob_sha=sha))
    return tuple(secret_hits), tuple(answer_key_hits)
