# AS-OBSIDIAN-CAPTURE-001-F11 — the third failure site in each writer

**Status:** implemented, awaiting independent verification. **Not sealed.**

## The defect

An atomic note write can fail in three places: reading the prior note, creating
the note's parent directory, and `os.replace`. F6 closed the boundary for the
first and third. **The middle one was left outside the guard in both writers.**

Reproduced on current `main` (`a7adce4e`), a plain file where a path component
must be a directory:

    obsidian_projection._write_atomic  ->  NotADirectoryError escaped raw
    graph_projections._promote         ->  NotADirectoryError escaped raw

Meanwhile, in the very same function, an `os.replace` failure is correctly
contained as `unwritable-note:PermissionError:<path>`. Two of three sites
guarded, one not — a caller catching the module's own exception type did not
catch this at all, which is precisely the defect F6 exists to prevent.

Recorded in the F1-F4 residual register as "`_write_atomic`'s `mkdir` is outside
the new guard". This closes it, and finds the same defect at a second site the
register did not name.

## The fix

Both `mkdir` calls are wrapped, raising the module's own error type and naming
the **directory** rather than the note, because the directory is what the
operator has to act on:

    unwritable-note-directory:<ErrorType>:<parent path>

Four lines in each writer. No behaviour change: the same writes fail, inside the
module's boundary instead of outside it.

## Reachability

A plain file sitting where a directory must be — a stale or tampered vault, a
path component an operator created by hand, or a partially-restored backup. It
needs no malformed input and no unusual permissions, and the failure surfaces
today as an unhandled traceback rather than an Atlas diagnostic.

## Negative controls

Each guard reverted independently, under an assertion that the file changed, and
restored byte-identical afterwards:

| control | result |
|---|---|
| baseline | **5 passed** |
| projection guard removed | **3 failed** |
| graph guard removed | **3 failed** |

Both bite, which is what makes this two fixes rather than one fix and one
assertion.

One test is deliberately phrased as **"no `OSError` escapes"** rather than "a
domain error is raised". The defect was that the domain type did not cover this
path, so a test checking only for the domain type would also pass on a writer
that raised nothing at all.

## What is not claimed

- **Not a policy change.** Nothing that succeeded before is refused now; a
  positive control asserts directories are still created normally.
- **Not that every `OSError` in these modules is now contained** — only the
  three sites in the atomic write path, which is what F6 scoped and what the
  residual register named.
- **Not that `ingestion.py` is covered.** A third writer, owner-gated behind a
  frozen surface, untouched here.
