# AS-OBSIDIAN-CAPTURE-001-F11 — the mkdir failure site in each writer

**Status:** implemented, verified, corrected under verification. **Not sealed.**

## The defect

An atomic note write can fail in several places. F6 closed the boundary for the
read of the prior note and for `os.replace`. **Creating the note's parent
directory was left outside the guard in both writers.**

Reproduced on `main` (`a7adce4e`), a plain file where a path component must be a
directory:

    obsidian_projection._write_atomic  ->  NotADirectoryError escaped raw
    graph_projections._promote         ->  NotADirectoryError escaped raw

Meanwhile, in the same function, an `os.replace` failure is correctly contained
— as `unwritable-note:<ErrorType>:<path>` in the obsidian writer, and as
`promotion-failed-prior-state-intact` in the graph writer, which does not name
the path. Guarded on either side of an unguarded step, so a caller catching the
module's own exception type did not catch this at all.

## Both sites were already recorded. Retraction.

An earlier revision of this receipt, its commit message and its PR body all said
this package "finds the same defect at a second site the register did not name".
**That is false and is retracted.** `AS-OBSIDIAN-CAPTURE-001-F6-ERROR-BOUNDARY.md`
records it explicitly, thirteen lines above the bullet this package quoted:

> **Three raw `OSError`s still escape `write_projection_outputs`** from the
> unguarded `_promote`: **an ancestor directory replaced by a file**, a read-only
> output directory, and a file becoming unreadable between the plan read and
> `_promote`'s own read.

"An ancestor directory replaced by a file" is exactly this package's second site.
Verification caught the over-claim; the *fix* is new, the *finding* was not.

## The fix

Both `mkdir` calls are wrapped, raising the module's own error type and naming
the **directory** rather than the note, because the directory is what the
operator has to act on:

    unwritable-note-directory:<ErrorType>:<parent path>

Six lines of code replace one in each writer (`+11/-1` and `+10/-1` with the
comments). No behaviour change: the same writes fail, inside the module's
boundary instead of outside it.

## Reachability, corrected

A plain file sitting where a directory must be — a stale or tampered vault, a
path component an operator created by hand, or a partially-restored backup. It
needs no malformed input and no unusual permissions.

An earlier revision said the failure "surfaces today as an unhandled traceback
rather than an Atlas diagnostic". **Not true at either production surface**, and
retracted: `cli.py:4264` catches `(ObsidianProjectionError, OSError, ValueError)`
and logs `obsidian projection failed: …` with `EXIT_ERROR`; `connect.py:786`
catches `(OSError, ValueError, KeyError, TypeError)` and re-raises `ConnectError`.
Both already contained the raw error on base. The one unguarded caller is
`demo_readiness.py:162`, an internal harness. What this fix buys is therefore
**precision and type-correctness at the boundary**, not the difference between a
traceback and a diagnostic.

Reachability of the graph half is weaker still, and was omitted before:
`graph_projections.write_projection_outputs` has **no caller anywhere in
`src/`** — only seven test modules reach it. The graph guard is not reachable from
any Atlas command today.

## Negative controls

Each mutation applied under an assertion that the file changed, then restored
with `git restore --source=HEAD --staged --worktree` under a `git status
--porcelain` emptiness assertion. Sources byte-identical before and after
(`a538ab59…` / `e957a673…`).

| control | result | failing tests |
|---|---|---|
| baseline | **5 passed** | — |
| projection guard removed | **3 failed** | projection_mkdir, not_coupled, nothing_left_behind |
| graph guard removed | **3 failed** | graph_mkdir, not_coupled, nothing_left_behind |
| **both guards swallow and raise nothing** | **4 failed, 1 passed** | all but the positive control |
| **guard reports a generic `OSError`** | **3 failed** | the three that assert the class |
| fixture made inert, one fixture | **3 failed** | projection_mkdir, graph_mkdir, nothing_left_behind |
| fixture made inert, both fixtures | **4 failed** | all but the positive control |
| restored | **5 passed** | — |

**Read the table honestly.** The 3/3 rows are each carried by *one*
guard-specific test; the other two failures in each row are shared tests that
detect either guard's absence. Judged on name sets rather than counts —
`A\B = {projection_mkdir}`, `B\A = {graph_mkdir}` — neither set contains the
other, so the two guards *are* independently load-bearing. But there is one
independent witness per guard, not three.

## Two corrections verification forced

**1. The Windows failure (P0).** Two tests asserted the literal string
`"NotADirectoryError"`. The same blocked-parent condition raises
`FileExistsError` on Windows, and Windows CI was red. On Linux alone the class
depends on shape: an ancestor file gives `NotADirectoryError` (errno 20), an
immediate parent file gives `FileExistsError` (errno 17). The assertion was
platform- *and* shape-coupled from the start.

Fixed by measuring: `_mkdir_error_name` performs the same `mkdir`, catches the
`OSError`, and the test asserts the guard names *that* class. This is portable
and **stronger** — a guard reporting a generic `OSError` now fails (control
above), which the hard-coded string could not detect. Reproduced locally under a
plugin that re-raises the Windows class for this family:

    new assertion, Windows class simulated:  5 passed
    old assertion, Windows class simulated:  2 failed, 3 passed   <- the CI failure

**2. The "no `OSError` escapes" justification (P1) was inverted.** An earlier
revision asserted containment with a `try/except OSError` and justified it as
stronger than `pytest.raises`, "because a test that only checked for the domain
type would pass on a writer that raised nothing at all". Backwards.
`pytest.raises` fails with DID NOT RAISE, and re-raises non-matching exceptions,
so it rejects *both* failure modes. Demonstrated with a mutant that swallows the
`mkdir` failure and raises nothing — both writers confirmed to return normally:

    old try/except form on that mutant:  1 passed   <- did not detect it
    new pytest.raises form:              1 failed   <- detects it

That test was also redundant with the two above it, running the same fixture. It
now runs a **second, materially different** blocked shape, so it pins that
containment is not coupled to one errno.

## What this does NOT close

The F6 register named **three** raw `_promote` escapes. This package closes one.
The other two remain raw at this head, pre-existing and reproduced here:

| condition | escapes as | at |
|---|---|---|
| read-only output directory | `PermissionError` | `graph_projections.py:620` `staged.write_bytes(plan[path])` |
| existing target unreadable | `PermissionError` | `graph_projections.py:616` `path.read_bytes()` |
| `ENAMETOOLONG` filename | `OSError` | `graph_projections.py:614` `path.exists()` |

The escape table's line numbers are stated **at the merged base `06362807`**. An
earlier revision cited 609/605/603, which were correct at the pre-merge head and
went stale by 11 lines when F10 landed -- and line 609 there is now the guarded
`mkdir` itself, so those numbers pointed a reader at the fix rather than at an
escape. Verification caught it. The durable anchors are the code expressions,
which is why they are quoted alongside.

These three are filed as **#757** so they are explicitly owned, and deliberately
not folded in here: different sites, different failure modes, different guards.

## What is not claimed

- **Not a policy change.** Nothing that succeeded before is refused now.
  Verification confirmed this independently across 67 legitimate scenarios
  (deep paths, unusual directory names, symlinked vault root, 1 MB and binary
  content, multi-file plans) with byte-identical output trees on base and head,
  plus 960 concurrent writes into a shared not-yet-existing tree with zero
  errors on either side. `Path.mkdir(parents=True, exist_ok=True)` is race-safe
  and the guard is purely additive.
- **Not that every `OSError` in these modules is now contained.** The mkdir site
  in both writers only — see the table above. An earlier revision said "the
  three sites in the atomic write path", which understates `_promote`.
- **Not that the F6 property holds "at all three sites"**, as the test module's
  docstring said. Retracted.
- **Not that `ingestion.py` is covered.** A third writer, owner-gated behind a
  frozen surface, untouched here.
- **Not verified on Windows beyond CI.** No Windows machine; junctions,
  ACL-denied components and case-insensitive filesystems are untested.
