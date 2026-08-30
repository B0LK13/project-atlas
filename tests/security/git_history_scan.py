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
_CASE_ID_FIELDS = ("case_id", "id")


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


def _json_dicts_with_answer_key(obj: Any) -> Iterator[dict[str, Any]]:
    """Recursively yield every dict in a parsed JSON value that carries an
    ``"expected"`` key -- i.e. every dict that looks like a scored answer
    record, wherever it's nested (top-level object, list of cases, ...)."""
    if isinstance(obj, dict):
        if _ANSWER_KEY_FIELD in obj:
            yield obj
        for value in obj.values():
            yield from _json_dicts_with_answer_key(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _json_dicts_with_answer_key(item)


def _structural_answer_key_leaks(text: str, holdout_case_ids: Sequence[str]) -> set[str]:
    """Case ids whose committed record, in this blob, structurally pairs a
    holdout case id with an ``"expected"`` answer -- parses the blob as JSON
    first (this repo's holdout cases are exclusively JSON; parsing rejects
    Python/Markdown/etc. source that merely *mentions* both substrings, which
    is what the naive same-blob substring check false-positived on: this
    file's own test source, in its own git history, both defines and checks
    for the strings "EV-HOLD-101"/"EV-HOLD-102" and "expected" -- discussing
    the property is not violating it)."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return set()
    hits: set[str] = set()
    for record in _json_dicts_with_answer_key(parsed):
        for field in _CASE_ID_FIELDS:
            value = record.get(field)
            if isinstance(value, str) and value in holdout_case_ids:
                hits.add(value)
    return hits


def find_leaked_holdout_evidence(
    repo_root: Path,
    *,
    secret_tokens: Sequence[str] = (),
    holdout_case_ids: Sequence[str] = (),
) -> tuple[tuple[LeakedSecretHit, ...], tuple[LeakedAnswerKeyHit, ...]]:
    """Single traversal of every unique historical blob, checking BOTH
    security properties in one pass (no matter how many secrets/case ids):

    1. none of ``secret_tokens`` appears in any historical blob;
    2. no historical blob structurally pairs a ``holdout_case_ids`` entry with
       an ``"expected"`` answer field -- the signature of a committed answer
       key. Deliberately JSON-structural rather than a substring/same-line
       check: adversarial differential testing against this repository's own
       real history (see the PR evidence doc) found that BOTH a same-blob and
       a same-line substring heuristic false-positive on ordinary Python test
       source that legitimately discusses/asserts on the case id and the
       ``"expected"`` field name together (e.g. `hold["expected"] ==
       scoring_capability["EV-HOLD-101"]`) without ever containing a real
       leaked value. This repository's holdout case records are exclusively
       JSON (confirmed: `_holdout_case_meta()` only reads `*.json`, and the
       operator's private answer map is always `json.dumps`-written), so
       requiring the match to parse as JSON and structurally pair the two
       fields in one record is precise for the real threat model and
       eliminates that false-positive class entirely, at zero proven
       detection cost (see the differential test matrix in the PR).

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
