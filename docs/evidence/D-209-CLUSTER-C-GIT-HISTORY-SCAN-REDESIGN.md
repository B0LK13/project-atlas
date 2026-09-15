# D-209 — Cluster C: historical-leak scan redesign (security property preserved, cost eliminated)

## Origin

Directive `D-CODEX-ATLAS-OWNER-FRONTIER-RESOLUTION-CI-CONDITIONAL-INTEGRATION-AND-DAG-CONTINUATION`
§4/§5/§13, resolving Cluster C from the prior 7(8)-failure re-triage as
`READY_OWNER_INDEPENDENT` with an explicit policy resolution:
`REDESIGN_WITH_SECURITY_ASSURANCE_PRESERVED` — the security property must be
preserved or strengthened; a timeout, sample, or `xfail` is not an acceptable
fix.

`ID_NOTE`: `D-208` is already claimed by the still-open, not-yet-merged PR
#646's own evidence-doc rename (`D-206`→`D-208`, this same session); using
`D-209` here avoids a second collision with an in-flight, not-yet-integrated
ID.

## Round-1 independent verification: REJECTED, then fixed

A fresh, maximally-adversarial IV subagent (separate worktree) found a real,
reproduced false negative in the first implementation:
`_structural_answer_key_leaks` required a holdout `case_id` and an
`"expected"` field to appear in the SAME JSON dict. IV constructed
`{"case_id": "EV-HOLD-999", "scoring": {"expected": "leak"}}` — case id and
answer split across sibling dicts, an entirely ordinary way to structure a
scored-case record — and proved the same-dict check missed it, while the
OLD (pre-redesign) algorithm's ADDED-line substring check actually caught
it (the whole object lands on one diff line). Per the directive's explicit
standard, a false negative is REJECT-level regardless of speed/elegance
gains, and was not softened or argued around.

**Fix**: widened detection to same-*document* co-occurrence (case id
anywhere in the parsed JSON value; `"expected"` key anywhere in that same
value), rather than same-dict — see `_json_has_answer_key` /
`_json_contains_string` in `tests/security/git_history_scan.py`. This
closes the gap while preserving the JSON-parse gate that fixes the
*original* false-positive class (Python source never parses as JSON, so
it's excluded before the document-wide check is even reached). New
regression test:
`test_new_scanner_catches_case_id_and_expected_split_across_sibling_dicts`
in `tests/security/test_git_history_scan_differential.py`, pinning this
exact defect permanently. Re-verified after the fix: 13/13 differential
tests pass (was 11, +1 parametrized scenario +1 dedicated regression test),
12/12 integration-file tests pass, zero false positives against this
repo's real history (re-run), runtime unaffected (~9.8-13.5s across runs,
still >10x faster than the old algorithm's >120s non-completion). `ruff`/
`mypy` clean.

The IV's other five verification lanes (blob-scan plumbing edge cases —
empty blob, embedded newlines, header-lookalike content, large blob, binary
blob; tag-only/deleted-branch reachability; the `-S` blind-spot claim
reproduced by hand plus a `-G`-vs-`-S` characterization; a search for any
NEW false negative from the plumbing itself — none found, submodule gitlinks
noted as a pre-existing boundary shared by both old and new equally, not a
gap introduced here; independent benchmark; full test/lint/type gates; scope
confirmed test-only) all came back clean and are not repeated here — see
the IV transcript for the full detail. Round 2 IV re-verification of the fix
is tracked separately (see PR #651 comments).

## Step 1 — formalize the security property BEFORE optimizing (directive §4)

```
SECURITY_INVARIANT = No needle -- a holdout secret answer value, or a
    holdout case id co-occurring with a committed "expected" answer field --
    has ever existed in any blob object reachable from any ref in this
    repository's history: at any commit, on any branch, under any path or
    filename, including a path later renamed, deleted, or recreated, and
    including identical content re-introduced under a different pathname.

THREAT_MODEL = An adversary (an optimizing agent under evaluation, or an
    external contributor) with full read access to the repository INCLUDING
    its complete commit history (every ref reachable via `git rev-list
    --all`), attempting to recover a holdout evaluation case's secret
    expected answer via git-history search rather than the sanctioned
    scoring-broker protocol. True dangling/unreachable git objects are out
    of scope for both the OLD and NEW implementation alike -- this redesign
    neither widens nor narrows that boundary.

CURRENT_ALGORITHM (OLD, as shipped) =
    1. `git rev-list --all` -> every commit SHA reachable from any ref.
    2. For EACH secret token (one per holdout case, freshly random per test
       run): `git grep --fixed-strings <token> <every revision SHA>`.
    3. For 2 hardcoded case ids: `git log --all -p -S <case_id> --
       fixtures/eval`, then scan every diff hunk's ADDED lines for the
       literal substring `"expected"`.

CURRENT_COMPLEXITY = Step 2 is O(N_secrets * R) where R = revision count,
    because `git grep <pattern> <R revision arguments>` walks each listed
    revision's tree independently -- it does not internally deduplicate
    identical blob content the way a blob-level traversal does. Step 3
    (`git log -S -- <pathspec>`) is already well-scoped and cheap; it is NOT
    the pathological part.

CURRENT_RUNTIME = Independently reproduced against this repository's real
    history (2092 commits) TWICE this session: a direct benchmark of step 2
    alone (one token) did not complete within a 120s hard timeout; running
    the actual `test_adv_git_history_access` (2 tokens, both steps) via
    pytest likewise required SIGKILL past 120s in the prior triage pass.
    Neither run ever reached a PASS or FAIL verdict.

FALSE_NEGATIVE_BOUND (OLD) = Nonzero, empirically demonstrated (see Step 5
    below) -- `-S <case_id>` only flags a commit when the NET OCCURRENCE
    COUNT of `case_id` changes between parent and child. Editing an existing,
    already-committed case file to ADD its `"expected"` answer -- without the
    case-id substring's own occurrence count changing (still exactly one
    occurrence before and after) -- is invisible to `-S`. Step 2 (the token
    grep) has no false-negative risk of its own (exact substring match,
    exhaustive over the listed revisions) -- but note the tokens it searches
    for are fresh cryptographically-random values generated AFTER all
    existing history was authored, so by construction they can never appear
    in that history regardless of algorithm; step 2 is a defensive
    regression guard against a future change to secret derivation, not a
    proof about current history.

FALSE_POSITIVE_BOUND (OLD) = Zero for step 2 (exact match). Step 3's
    ADDED-line substring check is coarse (any added line containing
    `"expected"` in a pathspec-touched file, regardless of the line's actual
    content) but is not empirically false-positive-prone against this
    repo's real history in its current, narrow, 2-hardcoded-id, single-
    pathspec form.
```

## Step 2 — design the cheapest equivalent (directive §4, candidate techniques)

Chosen: **blob-ID deduplication + one-pass object traversal** (both
explicitly listed as directive-suggested candidates).

`git rev-list --objects --all` enumerates every object -- commit, tree, and
blob -- reachable from any ref, **exactly once each** (git's own
mark-and-sweep traversal, not re-implemented here). Filtering to blob-type
objects (`git cat-file --batch-check`) and reading each blob's content
exactly once (`git cat-file --batch`, one streamed process, no per-object
process spawn) visits the same universe of historical content the OLD
per-revision grep visits, but a file unchanged across 500 commits is ONE
blob object -- not re-read 500 times. This collapses `O(secrets * revisions)`
to `O(unique blobs)`, independent of both revision count and secret count
(every needle is checked against every blob in the SAME pass).

Blob-content identity is git's own content-addressing (SHA-1 of bytes), not
a path association -- so a renamed, deleted, or recreated path, or identical
content re-committed under an entirely different filename, is automatically
the same blob object and therefore automatically covered, with **no
path-based or rename-tracking logic required**. This is a structural
strengthening over the OLD algorithm's step 3, which was scoped to a single
hardcoded pathspec (`-- fixtures/eval`) and would not have looked anywhere
else at all.

Implementation: `tests/security/git_history_scan.py`
(`unique_historical_blob_shas`, `find_leaked_holdout_evidence`).

**Leaked-answer-key detection is JSON-structural, not substring-based** --
this was NOT the first design tried. A same-blob substring check (`case_id`
and `"expected"` anywhere in the same blob) and a same-line substring check
were both prototyped first and BOTH produced real false positives against
this repository's own history: this very test module's own historical
source (and `eval_substrate.py`, and an unrelated `AS-OPT-GATE-001` test
file) legitimately discusses/asserts on both strings together (e.g.
`assert hold["expected"] == scoring_capability["EV-HOLD-101"]`) without ever
containing a real leaked value. This repository's holdout case records are
exclusively JSON (`_holdout_case_meta()` only reads `*.json`; the operator's
private answer map is always `json.dumps`-written) -- requiring the match to
parse as JSON and structurally pair a `case_id`/`id` field with an
`expected` field in the SAME record is precise for the real threat model and
eliminates that false-positive class entirely, at zero proven detection
cost (see Step 3 below -- every real violation scenario is still caught).

## Step 3 — adversarial differential testing (directive §5)

`tests/security/test_git_history_scan_differential.py` — synthetic git
histories (`git init` scratch repos, cheap enough that the OLD algorithm
stays affordable for direct comparison) covering every position the
directive requires:

| Scenario | Expected | OLD result | NEW result |
|---|---|---|---|
| clean, no violation | no leak | no leak (correct) | no leak (correct) |
| violation at current HEAD | leak | **no leak (WRONG -- false negative)** | leak (correct) |
| violation at first commit | leak | leak (correct) | leak (correct) |
| violation at an arbitrary middle commit | leak | **no leak (WRONG -- false negative)** | leak (correct) |
| violation, then path renamed | leak | leak (correct) | leak (correct) |
| violation, then path deleted | leak | leak (correct) | leak (correct) |
| violation, path deleted then recreated clean | leak | leak (correct) | leak (correct) |
| same leaked content under a different pathname | leak | leak (correct) | leak (correct) |
| violation amid many irrelevant commits | leak | leak (correct) | leak (correct) |
| source code merely *discusses* case id + `"expected"` | no leak | no leak (correct) | no leak (correct) |

**`NEW_PROPERTY_STRONGER_THAN_OLD = YES`, not merely equivalent** — the two
"WRONG" rows above are a real, reproduced OLD-algorithm blind spot (the `-S`
occurrence-count edge case predicted analytically in Step 1, now empirically
confirmed): editing an already-committed case file to add its `"expected"`
answer, when the case-id substring's own occurrence count doesn't change,
is silently invisible to `git log -S <case_id>`. The NEW algorithm inspects
every historical blob's actual bytes directly rather than a diff of them,
so it has no such blind spot. `test_old_algorithm_is_proven_to_miss_same_occurrence_count_edits`
pins this finding as a permanent regression test.

10/10 scenarios: NEW matches ground truth in every case. OLD matches ground
truth in 8/10 and is proven wrong in 2/10.

## Step 4 — benchmark against real history

```
OLD_RUNTIME = >120s, did not complete (hard-timeout-terminated; independently
    reproduced twice this session, both as a standalone benchmark of step 2
    alone and as the full pytest test)
NEW_RUNTIME = 11.2s-13.5s (measured across 3 separate runs: standalone
    module call ~11.2-11.7s; full pytest test including fixture setup
    ~13.5s), scanning all 8548 unique blob objects across this repository's
    complete 2092-commit history in one pass
SPEEDUP = >10x lower bound (120s / 11.2s); the true speedup is materially
    larger since the OLD algorithm was still incomplete at the 120s mark,
    not merely slow
SECURITY_EQUIVALENCE_RESULT = NEW_PROPERTY_STRONGER_THAN_OLD = YES (see
    Step 3 -- proven via reproduced counter-example, not asserted)
```

## Step 5 — production change

`tests/integration/test_as_2_2_eval_broker_adversarial.py::test_adv_git_history_access`
now calls `find_leaked_holdout_evidence()` directly. No change to
non-test production code (`src/project_atlas/**` untouched). No security
property was weakened, sampled, or skipped; `xfail`/timeout-as-fixed was
never used, per the directive's explicit prohibition.

**Known related, NOT-in-scope pattern (flagged, not touched):**
`tests/unit/test_as_2_2_eval_broker_secret.py::test_generated_secret_answer_is_never_committed_or_in_history`
carries the identical OLD single-token `git grep <token> <all revisions>`
pattern and is very likely equally slow against real history (observed
hanging past 120s in this session's own verification run). This directive
scoped Cluster C narrowly to `test_adv_git_history_access`; this sibling
test is a natural, low-risk follow-up candidate for the same
`find_leaked_holdout_evidence()` helper, deliberately left untouched here to
avoid unauthorized scope expansion -- flagged as a new
`READY_OWNER_INDEPENDENT` candidate node for a future pass.

## Post-round-2 finding: two more real defects, found by Cursor's automated review

After round-2 IV (`CONFIRMED WITH MINOR NOTES`), Cursor's automated review
of PR #651 independently surfaced two further real, reproduced defects —
external review catching what two rounds of adversarial IV had not:

1. **Key-based leak detection gap** (`_json_contains_string` only walked
   dict VALUES, never KEYS). A document shaped like
   `{"EV-HOLD-999": {"expected": "..."}}` — case id as key, not value — was
   invisible, even though the same document carries an `"expected"` field.
   Independently reproduced against the unfixed code before accepting the
   fix (confirmed: zero hits on `{"EV-HOLD-999": {"expected":
   "the-secret-answer"}}`, a real leak). **Not a contrived shape**: it is
   the exact structure of this repository's own operator expected-answer
   map (`test_as_2_2_eval_broker_adversarial.py`'s `broker` fixture:
   `{cid: token for cid in meta}` — case ids as keys). Fixed: `dict.items()`
   is now walked (both key and value recursed), not just `dict.values()`.
   Two new regression tests pin both the direct form
   (`{case_id: {"expected": ...}}`) and the sibling form (`{"expected":
   {case_id: ...}}`).

2. **Test-helper environment fragility** (not a security-property gap, a
   portability bug): the differential test file's `_git()` helper passed a
   bare identity-only `env={"GIT_AUTHOR_NAME": ..., ...}` to `subprocess`,
   which *replaces* the child process's entire environment rather than
   extending it — dropping `PATH` (and, on Windows, `SYSTEMROOT`) entirely.
   This happened to still work on this session's Linux/WSL host only
   because of `execvpe`'s POSIX default-PATH fallback when `PATH` is
   completely absent from `env` — a coincidence of this one host, not a
   portable guarantee, and specifically not something Windows
   subprocess/`git.exe` can be relied on to tolerate (this repo's own CI
   matrix includes `windows-latest`). Fixed: `_ENV` now spreads
   `**os.environ` first, then overrides only the identity vars.

Re-verified after both fixes: 15/15 differential tests pass (was 13, +2).
12/12 integration-file tests pass. Zero false positives re-confirmed
against this repo's real history (~10.2s, unaffected). `ruff`/`mypy` clean.
Round-3 IV: CONFIRMED (see PR #651 comments).

## Post-round-3 finding: test-helper isolation gap (Cursor review, again)

A third Cursor-review finding, after round 3's `CONFIRMED`: spreading
`**os.environ` (the round-3 fix for the PATH-dropping bug) also forwards
`HOME` and therefore the host's global/system gitconfig, plus
`GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` if ever set by an invoking
process. Independently confirmed on this session's host **before**
accepting the fix: with the round-3 `env` and no isolation, `git config
--get commit.gpgsign` inside a freshly `git init`-ed scratch repo returned
`"true"` — inherited straight from this account's real global gitconfig.
Every synthetic commit in the differential suite had therefore been
silently GPG-signing with this account's real key the whole time; it only
ever appeared to work because this host happens to have a usable default
signing key. On a host without one (any ordinary CI runner, most fresh dev
machines) every commit in that file would fail with a GPG signing error.
`GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` were not set on this host, but
if ever set by an invoking process (e.g. a git hook), they would redirect
`init`/`add`/`commit` at the WRONG repository — a correctness/safety risk,
not just portability.

Fix: `GIT_CONFIG_NOSYSTEM=1` + `GIT_CONFIG_GLOBAL=os.devnull` to isolate
host gitconfig, plus popping the three `GIT_*` path-override vars if
present. Re-verified: `commit.gpgsign` inside a scratch repo now resolves
to empty (was `"true"`). 15/15 differential, 12/12 integration, `ruff`/
`mypy` clean, all unaffected. This is test-infrastructure-only hardening —
the detection logic (`_json_has_answer_key`/`_json_contains_string`) is
byte-for-byte unchanged from the round-3-verified version.

## PR review finding (P1, two independent reviewers): malformed-JSON blind spot

Before merge, PR #651's own GitHub review threads (`chatgpt-codex-connector`
and Cursor's Security Reviewer, independently, both P1/MEDIUM) flagged that
`_structural_answer_key_leaks` treated ANY `json.loads` failure as "no
leak," unconditionally — a malformed, truncated, or BOM-prefixed JSON blob
that still plaintext-contains a holdout case id and `"expected"` was
silently reported clean, even though the bytes remain exactly as readable
via `git rev-list --objects --all` as a well-formed blob would be. This is
a genuine regression versus the ORIGINAL `git log -p -S` / added-line
substring check, which worked on raw diff text and never required valid
JSON — the reviewers were correct that the JSON-parse gate, introduced to
fix the same-blob false-positive class, went one step too far by silently
dropping detection on the parse-failure path entirely.

Independently reproduced before accepting: an unfixed run against
`{"case_id": "EV-HOLD-999", "expected": "the-secret-answer"` (missing
closing brace, otherwise a real leak) returned zero hits.

**Fix**: `_looks_like_json_document()` — a narrow heuristic gate: does the
blob's content, after stripping a UTF-8 BOM and leading whitespace, start
with `{` or `[`? Ordinary source (Python, Markdown, ...) essentially never
does. When `json.loads` fails AND this gate is true, `_raw_fallback_answer_key_leaks()`
falls back to the original raw substring check (case id + `"expected"`
marker present in the same blob) — restoring detection for blobs clearly
attempting to be JSON, without reintroducing the broad false-positive
class the JSON gate was introduced to fix (Python source doesn't start
with `{`/`[`, so it stays excluded even on this fallback path).

3 new regression tests: truncated/missing-closing-brace, BOM-prefixed,
trailing-garbage-after-document (all now caught), plus one confirming the
fallback stays correctly gated (ordinary Python source is still not
flagged even though it also fails to parse).

## Validation

- `tests/security/test_git_history_scan_differential.py`: 19/19 pass (was
  15, +4: 3 malformed-JSON regressions + 1 fallback-gating guard).
- `tests/integration/test_as_2_2_eval_broker_adversarial.py`: 12/12 pass
  (full file, including the redesigned test at 13.48s, was >120s/SIGKILL).
- `ruff check .`: clean. `mypy` on the new module: clean.
- No production (`src/`) code touched.
