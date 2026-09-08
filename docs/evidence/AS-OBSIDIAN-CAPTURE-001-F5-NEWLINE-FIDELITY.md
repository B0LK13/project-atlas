# AS-OBSIDIAN-CAPTURE-001-F5 — HUMAN line endings are bytes, not formatting

**Status:** implemented, awaiting independent verification. **Not sealed.**

**Owner policy this serves (F3, unchanged):** raw HUMAN bytes are immutable —
no auto-escaping, no normalisation, no zero-width rewriting.

## The defect

Every generated-span-preserving writer reads the prior note, splices a fresh
generated span into it, and writes the result back. All four read with
`Path.read_text(encoding="utf-8")`, which opens in text mode with universal
newlines: `\r\n` and a lone `\r` become `\n` **before the merge ever sees the
bytes**. The operator's HUMAN region is therefore rewritten by a refresh they
did not request.

The note is a *store*, not merely a parse target — it is the file the human
edits — so a translating read is a silent write-back mutation.

## Why existing protections cannot see it

The guards on these writers check marker **presence, count and placement**.
After translation every marker is still present, still correctly counted, still
correctly placed. Only the bytes differ. The F1–F4 suites likewise assert
substring presence (`"my note" in text`), which is true both before and after
the line endings are destroyed.

This is the corruption class those checks were never able to detect.

## Reproduced on current `main` (`7a9eeb76`), all four entry points

Each was driven through its **real** entry point, comparing bytes on disk:

| # | entry point | driver | CR before → after | HUMAN block intact |
|---|---|---|---|---|
| 1 | `obsidian_capture_note.py:378` | `capture()` then `retry()` | 2 → 0 | no |
| 2 | `obsidian_projection.py:360` | `materialize_obsidian_projection()` | 2 → 0 | no |
| 3 | `graph_projections.py:644` | `write_projection_outputs()` | 2 → 0 | no |
| 4 | `ingestion.py:99` | `_generated_content()` | 2 → 0 | no — **owner-gated, see below** |

Entry point 3 is the sharpest: `write_projection_outputs`'s own docstring says
*"Preserves HUMAN protected regions byte-for-byte (AT-011 fail-closed)"*.

Entry point 4 does **not** route through `protected_regions`, which is why a
search for `merge_protected_regions` callers finds only three sites. The F3
receipt's "all three writers" undercounted for exactly this reason.

## The full corruption class

`Path.read_text` translation was measured directly:

| input | outcome |
|---|---|
| `a\r\nb\r\n` (Windows editor) | **mutated** → `a\nb\n` |
| `a\rb\r` (classic Mac) | **mutated** → `a\nb\n` |
| `literal CR \r mid-prose` | **mutated** → `\n` |
| `a\r\nb\nc\r\n` (mixed) | **mutated** → all `\n` |
| `U+2028` line separator | intact |
| form feed `\x0c` | intact |

So the class is precisely CR-bearing line endings, not "whitespace" generally.

## Pre-existing, not introduced

The behaviour reproduces identically on base `main` before this change and on
earlier bases; independent verification of #717 confirmed it is byte-for-byte
identical on `15c9a6d6`. F3 neither introduced nor changed it. F3's seal
recorded it as a residual requiring its own work package. This is that package.

## The write side is already correct

Checked, because a mirrored defect there would have made the fix incomplete:
all four writers emit with `write_bytes`, and `ingestion.py:296` already passes
`newline="\n"` explicitly. There is no write-side translation to fix, on any
platform. The defect is entirely on the read path.

## Scope split by an owner gate — three sites fixed, one gated

`src/project_atlas/ingestion.py` is a **certified surface** frozen by
`test_atlas3_demo_isolation_001.test_certified_surfaces_unmodified`. Editing it
requires an owner-approved, **sha256-pinned** exception under
`docs/atlas-3/ARCHITECTURE.md` SS9.1 — a gate this lane cannot self-grant, and
must not.

The first candidate for this package did edit it, and the guard caught it. That
is the guard working. Rather than seek a way around it, the package is split:

* **F5 (this candidate)** fixes the three permitted sites plus the shared helper.
  `ingestion.py` is reverted to byte-identical with `main`.
* **F5-B (owner-gated successor)** is the `ingestion.py` site. It needs an owner
  decision, not more engineering.

The defect at the gated site is **not** dropped or downgraded to a note. Its
four reproduction tests stay in the suite as `xfail(strict=True)`, so they run
on every CI pass, document the defect executably, and flip to a **visible XPASS
failure** the moment the gated fix lands. A residual that self-alerts is worth
more than a residual in a paragraph.

## The fix

One helper, `protected_regions.read_note_text(path)`, used at the three
permitted sites (and ready for the fourth when F5-B is granted).

`newline=""` would be the obvious spelling, but `Path.read_text` only accepts
it from Python 3.13 and this package declares `requires-python >= 3.12`, so the
helper decodes the bytes directly. The exception surface is unchanged: `OSError`
from the read, `UnicodeDecodeError` (a `UnicodeError`) from the decode — which
is what the existing `except (OSError, UnicodeError)` handlers already catch.

A shared helper rather than four inline changes, so the invariant has one name,
one docstring stating why `read_text` is wrong here, and one place to test.

## The boundary this must NOT cross

`CORE3-014` deliberately normalises CRLF→LF **before hashing** so content
identity is stable across platforms. `canonical_content` says so explicitly:
*"The stored raw evidence is the untouched original; this function never changes
what is persisted."* Storage fidelity and identity normalisation are separate
concerns. This package changes only what is written back; a test pins that
`content_hash("a\r\nb\r\n") == content_hash("a\nb\n")` still holds.

## Evidence

**Positive:** 28 tests. Four line-ending shapes × four entry points, asserting
**bytes and digests**, never substring presence — plus repeat-refresh stability
(erosion check), an LF-only regression guard that also asserts no line endings
are *invented*, and a check that the generated span still refreshes beside
preserved CRLF human content, so preserving HUMAN bytes has not accidentally
frozen derived content.

**Negative controls — every one load-bearing, and per-site:**

| control | reverted | result |
|---|---|---|
| baseline | — | **24 passed, 4 xfailed** |
| A | helper → `read_text` (all three live sites) | **17 failed**, 7 passed |
| B | `graph_projections.py` site only | **5 failed** |
| C | `obsidian_capture_note.py` site only | **4 failed** |
| D | `obsidian_projection.py` site only | **4 failed** |

B–D each fail a *different* test, so no site is protected only by another
site's coverage. The 7 that survive control A are the ones that must: the four
`read_text`-is-the-defect controls, the LF-only guard, and identity hashing.
The 4 xfails are the gated `ingestion.py` reproductions, which stay strict.

(The pre-split candidate, which also fixed `ingestion.py`, measured 28 passed
and 21/4/5/4/4 under the same controls. Recorded because the earlier figure
appears in the first revision of this receipt and is otherwise unexplained.)

A further control pins that `Path.read_text` still translates. If it ever stops
failing, the helper has become redundant — worth learning deliberately rather
than when someone "simplifies" it away.

**Suites:** F1–F4 + capture + graph projections + Obsidian + F5 = 261 passed,
4 xfailed. The certified-surface freeze guard
(`test_atlas3_demo_isolation_001`, 78 tests) passes, confirming this candidate
touches no frozen surface. `ruff check .` clean; `mypy src` clean (405 files).

## Claim boundary

Claimed: CR-bearing line endings inside HUMAN regions survive a refresh
byte-for-byte at all four generated-span-preserving writers, and identity
hashing is unchanged.

**Not claimed:** that the fourth writer is fixed — `ingestion.py` is
unchanged here and its defect is live on `main`, owner-gated as F5-B; general
byte fidelity for every transformation; that notes already normalised by a
previous refresh are recoverable (they are not — this stops further loss, it
does not undo it); that non-newline normalisation elsewhere is absent; or that
Obsidian note corruption in general is solved.

Implementation evidence, not certification. Independent exact-head verification
and CI are required before merge, and merge authority is not this lane's.
