# AS-OBSIDIAN-CAPTURE-001-F6 — an unreadable note is an operator condition

**Status:** integrated on `main` and **SEALED** (PR #729). See the post-merge seal at the end of this file. An earlier revision left this line reading "awaiting independent verification, not sealed" beneath a completed seal section, which asserted the opposite of the truth.

## The defect

Both projection writers read the prior note in order to splice a fresh
generated span into it. When that read fails — the file is not valid UTF-8, or
cannot be opened — the raw exception escaped the module's own error boundary,
so the operator got a raw exception instead of the module's own error.

Stated precisely, because an earlier revision of this receipt overstated it: the
two `PermissionError` cases already carried the path (`OSError.filename`). What
was wrong in all four is that the exception escaped the module's error boundary
— a caller catching `GraphProjectionError` or `ObsidianProjectionError` did not
catch these at all.

This is a **consistency** defect rather than a design question: one writer in
the same lane already does it correctly. `obsidian_capture_note.write_note`
catches `(OSError, UnicodeError)` and raises `OBSIDIAN_NOTE_CONFLICT`. The two
projection writers did not.

## Reproduced on current `main` (`91f40368`), before anything changed

Driven through the real entry points:

| writer | condition | before |
|---|---|---|
| `obsidian_projection.materialize_obsidian_projection` | note is not valid UTF-8 | raw `UnicodeDecodeError` |
| `obsidian_projection.materialize_obsidian_projection` | note unreadable (`chmod 000`) | raw `PermissionError` |
| `graph_projections.write_projection_outputs` | note is not valid UTF-8 | raw `UnicodeDecodeError` |
| `graph_projections.write_projection_outputs` | note unreadable (`chmod 000`) | raw `PermissionError` |
| `obsidian_capture_note.write_note` | both | **already correct** |

A fifth leak the first candidate closed without claiming it: the guard also
wraps `path.is_file()`, so a parent directory with mode `0o000` — where
`is_file()` itself raises `EACCES` — is caught too.

Four leaks, not the three an earlier informal probe found — `obsidian_projection`
leaks on the unreadable case too, which only surfaced when both writers were
tested against both failure modes rather than one each. That is the reason the
lane rule says verify *all* affected entry points.

## Why the existing instrument could not see it

#707's independent verification fuzzed **60,000 malformed input pairs** through
the graph adapter and reported **0 raw leaks**. That result is not contradicted
here: its corpus was *valid UTF-8* with malformed markers, so invalid bytes and
unreadable files were never in the space. The boundary had a hole the instrument
could not reach — worth stating precisely, so the earlier claim is scoped rather
than made to look wrong.

## Blast radius, and one place the no-write property does NOT hold

For **`graph_projections`** the read happens while building the write plan,
**before** `_promote`, so a failure aborts before anything is written. Verified
by execution in both orderings — corrupt the first output or the second, the
sibling is byte-identical either way and no staging residue is left.

For **`obsidian_projection` it is not true**, and an earlier revision of this
receipt claimed it was. That writer loops over projects and calls
`_write_atomic` *inside* the loop, so in a multi-project vault where an earlier
note merges cleanly and a later one fails, the earlier note **has already been
rewritten**. Independent verification proved this on head *and* on base, so it
is **pre-existing and not introduced here** — but the unqualified claim was
wrong and is corrected rather than softened. Making that writer plan-then-promote
is a separate work package; F6 does not attempt it.

F6 does not change what is written. It changes what the operator is told when a
note cannot be read or written.

## The fix, and why it needed a write-side guard too

`try/except (OSError, UnicodeError)` around each **read**, raising the module's
own domain error naming the note and the underlying exception class.
`UnicodeDecodeError` is a `UnicodeError`; `PermissionError` is an `OSError`, so
one clause per site covers both observed modes. Raised **from** the original, so
the operator gets a named note and a developer still gets the cause chain.

The read guard alone left the claim **platform-incomplete**, which only surfaced
when independent verification ran the Windows CI job on the first candidate. On
Windows `chmod` clears only the read-only bit, so an "unreadable" note still
*reads* fine and it is `os.replace` that fails with `WinError 5`. The first
candidate therefore failed Windows CI with a raw `PermissionError` escaping
`ObsidianProjectionError` — at the very failure mode this package names.

`obsidian_projection._write_atomic` now guards its `tmp.write_bytes` /
`os.replace` the same way, raising `unwritable-note:<class>:<path>`. The
existing `finally` still removes the staging file on the ordinary refused-write
path, and a test pins that no `.tmp` residue survives it. Cleanup is now
best-effort, so if the removal *itself* fails the residue can survive — see the
residual register below. An earlier revision of this paragraph said only "still
removes", contradicting that residual, which the register below records.

## Evidence

**Positive: 13 tests.** Both writers × both read-failure modes, plus the write
path, asserting the **exact domain type** rather than "raises something", that
the message names the note, and that `__cause__` is the original exception.
Plus two adversarial no-partial-write tests for the graph writer (a sibling
output and the offending note are sha256-compared across the failure, and
staging residue is checked), a `.tmp`-residue test for the refused write, a
valid-note regression, and a test that a structurally malformed note still
raises its **own** F3 diagnostic.

**Portability, learned the hard way.** The first candidate provoked the
unreadable case with `chmod(0o000)`. That is not portable — on Windows `chmod`
clears only the read-only bit, so the read succeeds and the test failed there
with `DID NOT RAISE`; it also passes vacuously as root. Windows CI was red at
that head. The tests now **inject** the failure by patching `Path.read_bytes` /
`os.replace`, which is strictly better than skipping on Windows: it exercises
the boundary on every runner and every uid, and it tests what this package
claims — that a failing read or write becomes a domain error — rather than
testing the operating system's permission semantics. One real-filesystem
`chmod` test is retained for the POSIX path, guarded per the convention already
used by `test_logging.py` (`skipif(os.name == "nt")`) and additionally skipped
as root.

**Negative controls — each load-bearing. A–D fail pairwise disjoint sets;
F ⊂ E ⊂ C, all strict**, because removing the write guard removes both the error
E proves is not masked and the warning F proves carries its payload. (An earlier
revision said E had a *single* failure. That was true before the logging test
existed; when it was added the table was re-derived and this sentence was not —
the same carry-forward this receipt keeps recording, one layer down in the prose
rather than the figures.)

| control | reverted | result |
|---|---|---|
| baseline | — | **13 passed** |
| A | `graph_projections` read guard removed | **5 failed** |
| B | `obsidian_projection` read guard removed | **2 failed** |
| C | `obsidian_projection` write guard removed | **4 failed** |
| D | read guard widened over the merge (body **and** clause) | **1 failed** |
| E | the `finally` cleanup guard removed | **2 failed** |
| F | the warning's payload un-nested from `context` | **1 failed** |

Re-derived in full at this head. Every earlier revision of this table was
patched rather than re-derived, and every one of them ended up carrying a
figure from its predecessor — which is why the whole set is now re-measured
whenever any test is added.

**Control D is the one that matters, and it took two attempts to describe
correctly.** The first candidate recorded the mutation as "widen the clause to
`except Exception`"; verification reproduced that and got 8 passed. The second
attempt said "widen the try **body**"; verification reproduced *that* and got 11
passed. Both were wrong, and the second was written without re-running it —
which is the discipline this lane exists to enforce, applied to itself and
missed.

Measured directly, at this head:

| mutation | result |
|---|---|
| body widened over the merge, clause unchanged | **13 passed** |
| clause widened to `except Exception`, body unchanged | **13 passed** |
| **body widened AND clause widened** | **1 failed** |

The mechanism is the exception hierarchy: `ProtectedRegionError` and
`GraphProjectionError` are `ValueError` subclasses, so `(OSError, UnicodeError)`
never catches them however the body is arranged, and `except Exception` catches
nothing extra unless the merge is inside the `try`. **Both** changes are needed
before `malformed-generated-markers` gets relabelled `unreadable-existing-note`.
The test is genuinely load-bearing; two successive receipts described the wrong
mutation.

**Suites:** the group set, every path written out in full — an earlier revision
abbreviated six of the nine, and two of those abbreviations expand to filenames
that do not exist (`test_as_graph_005_projections_adversarial.py`,
`test_as_coder_alpha_obsidian_001_r1_001.py`), so the list was not runnable as
written:

    tests/unit/test_as_obsidian_capture_001.py
    tests/unit/test_as_obsidian_capture_001_f3.py
    tests/unit/test_as_obsidian_capture_001_f5_newline_fidelity.py
    tests/unit/test_as_obsidian_capture_001_f6_error_boundary.py
    tests/unit/test_as_graph_005_projections.py
    tests/unit/test_as_graph_005_adversarial.py
    tests/unit/test_as_graph_005_f4_canonical_semantics.py
    tests/unit/test_as_coder_alpha_obsidian_001.py
    tests/unit/test_as_coder_alpha_obsidian_r1_001.py

= **277 passed, 4 xfailed**. Full suite **5,682 passed, 8 skipped, 4 xfailed**. Freeze guard 78
(26 higher than this package first measured: F7 merged into `main` and brought 26 tests with it,
so the figure moved with the base refresh rather than with any change here)
(neither changed file is a certified surface). `ruff check .` clean; `mypy src`
clean (405 files).

## Residuals found by verification, recorded not fixed

- **F5's sealed work-package entry still carries the abbreviated suite list** that
  P3-2 corrected everywhere else, including the two abbreviations that expand to
  filenames which do not exist. It sits in the byte-identical prefix this
  package must not touch -- editing it would break the pure-insertion property
  that proves no sealed record was rewritten -- so it is recorded here for a
  future package rather than fixed. Observed by verification in round 8.

- **A directory at the obsidian note path escapes raw.**
  `materialize_obsidian_projection` has no `canonical-target-not-file` precheck
  (the graph writer does), so `is_file()` is False, the merge proceeds, and
  `os.replace` raises `IsADirectoryError` — now caught by the new write guard,
  but as `unwritable-note`, which names the condition imprecisely.
  Pre-existing; reproduces on base.
- **Three raw `OSError`s still escape `write_projection_outputs`** from the
  unguarded `_promote`: an ancestor directory replaced by a file, a read-only
  output directory, and a file becoming unreadable between the plan read and
  `_promote`'s own read. Pre-existing and outside this package's two read sites.
- **A cleanup failure could mask the real error — found by verification, now
  fixed.** `_write_atomic`'s `finally` removed the staging file unguarded, so a
  failing `unlink` propagated *out of the finally* and **replaced** the
  `ObsidianProjectionError` raised just above — handing the caller a raw
  exception on the very path this guard covers, and leaving the `.tmp` residue
  that `test_f6_failed_write_leaves_no_tmp_residue` pins as absent. Cleanup is
  now best-effort, with control E pinning it. The residue in that narrow case
  is now a *disclosed* residual rather than a silent one: masking the real error
  is strictly worse than leaving a file behind.
- **`_write_atomic`'s `mkdir` is outside the new guard.** `path.parent.mkdir(
  parents=True, exist_ok=True)` runs before the `try`, so an unwritable parent
  chain still escapes as a raw `PermissionError` — reproduced at this head and
  identical on base, so pre-existing and not introduced, but it is a raw escape
  on the very write path this package guards and it was missing from the first
  version of this list.
- **Diagnostic path asymmetry**: the graph writer emits a vault-relative path,
  the obsidian writer an absolute filesystem path. No uniformity is claimed.
- **`obsidian_projection` writes inside its project loop**, so the no-write
  property does not hold there for multi-project vaults (above).

## Claim boundary

Claimed: a read **or write** failure at either projection writer surfaces as
that module's own error type, names the offending note, and preserves the cause
chain. For **`graph_projections`** the failure path additionally writes nothing.

**Not claimed — that `obsidian_projection` writes nothing.** It calls
`_write_atomic` inside its per-project loop, so in a multi-project vault an
earlier note that merged cleanly has already been rewritten when a later one
fails. Pre-existing, proven on base, and disclosed above. An earlier revision of
this paragraph said "either projection writer … writes nothing", contradicting
this document's own Blast-radius section far earlier in the same file.

Also **not claimed:** that this fixes any data-loss defect — it does not; that every raw exception everywhere in these modules
is now wrapped; that `ingestion.py`'s parallel raise sites are addressed (they
raise a plain `ValueError` with a different spelling and remain a separate
residual); or that the diagnostic is now uniform across all surfaces.

Implementation evidence, not certification. Independent exact-head verification
and CI are required before merge, and merge authority is not this lane's.

---

## Post-merge seal

Integrated as PR #729: merge commit `e264d599`, second parent `c5d85fe7`, base
`7b0989a7`. Merged **unrebased at the verified object** — `git diff c5d85fe7
e264d599` is empty and the merge trees (`src 8086e6f9`, `tests e6157e27`,
`docs aa0b3336`) are hash-identical to the certified object.

Nine verification rounds against nine objects (`ce771fb7` was pushed but
superseded before a round ran on it). Round 1 found the fix itself
platform-incomplete. An earlier revision of this paragraph added that "every
finding after it was in the claim record, not the code" -- **false**, and raised
by two independent reviewers: six of the nine objects changed `src`/`tests`, and
only the last three (`c995040a`, `8ec6311d`, `c5d85fe7`) were documentation-only.
R3's `finally` masking and R5's discarded log payload were engineering defects,
which is precisely why they are controls **E** and **F** below. The recurring
defect *class* was bookkeeping; the findings were not all bookkeeping. The final
round returned P0/P1/P2 = 0.

Measured on the merge object, in an isolated worktree with its own venv, after
proving both the parent process and a spawned child resolve `project_atlas`
there — the repository's primary checkout sits on another branch and would
otherwise capture subprocess tests through the editable install:

    F6 suite               13 passed
    nine-file group set    277 passed, 4 xfailed
    full suite             5,682 passed, 8 skipped, 4 xfailed
    freeze guard           78 passed
    ruff / mypy            clean, 405 files

All six negative controls reproduce **on main**, each mutation under a sha256
assertion that it changed the file, both sources restored byte-identical after:

    baseline 13 · A 5 · B 2 · C 4 · D 1 · E 2 · F 1

A–D fail pairwise disjoint sets; `F ⊊ E ⊊ C`, both strict — computed on failing
test-name sets, not counts, since equal cardinalities prove nothing about
containment.

Control D reproduces only with the merge call moved *inside* the `try` **and**
the clause widened; each half alone is a no-op at 13 passed. An earlier
reconstruction of D during this seal returned 13 passed, meaning it was not the
documented mutation — it was discarded and rebuilt rather than reported. A
control that passes is not evidence.

Two limits on this package's evidence process, both raised in verification and
neither closed here. The body generator that produces the PR description is not
in the repository, so "derived at generation time" is consistent with the
artifact but not established by it. And the figures it derives are the ledger
deltas only: the headline block and the control tables above are reproduced
faithfully from this receipt, which is typed — a generator reproduces a wrong
receipt figure just as faithfully, which is what `5,656` did in round 8. Both
are recorded in the residual register rather than fixed, being outside this
package's defect class.
