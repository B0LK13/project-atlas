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

## A regression this fix introduced, found by verification

Reading faithfully is not enough if a *consumer* of that text was silently
relying on the translation. Independent verification of the first candidate
found exactly that, and it is the sharpest lesson of this package.

`_existing_capture_id` gated ownership on `text.startswith("---\n")`. The old
translating read masked it; the faithful read exposed it. Measured on both
trees, the trigger is precisely **the note's first line ending**:

| note shape | base `7a9eeb76` | first candidate `6788f3bc` |
|---|---|---|
| whole file CRLF | `ok`, bytes mutated | **`partial`, `OBSIDIAN_NOTE_CONFLICT`** |
| first line CRLF only | `ok`, bytes mutated | **`partial`, `OBSIDIAN_NOTE_CONFLICT`** |
| HUMAN block CRLF only | `ok`, bytes mutated | `ok`, byte-identical |
| CRLF everywhere but first line | `ok`, bytes mutated | `ok`, HUMAN bytes preserved |

That is what a Windows editor or a `core.autocrlf=true` checkout produces. It
failed **closed** — raw capture preserved, note untouched, surfaced as
`status="partial"` rather than silently — but the note would never refresh
again, and the error named the wrong cause.

Fixed by normalising **for the ownership probe only**, the same split
`canonical_content` draws for identity: interpret a normalised copy, persist
the original. Two tests pin it, and a fifth negative control (reverting the
probe to LF-naive) fails 3 tests.

**Scoped precisely:** on a whole-note CRLF rewrite the *generated* span
correctly comes back LF, because generated content is derived and re-rendered
canonically — Atlas owns those bytes. Only HUMAN bytes must survive. An earlier
revision of the locality test asserted whole-file CR parity and failed for that
correct reason; it now asserts the HUMAN block.

## Findings recorded rather than fixed here

- **Site 4's blast radius is wider than one note.** `_generated_content` is
  called from `ingestion.py:2245` (a loop over the whole rendered knowledge
  bundle) and `:2251` (`projects/<p>/project.md`), so F5-B covers a family of
  vault notes. Also `ingestion.py:478` reads the same note with a translating
  `read_text` for preflight marker validation — read-only and harmless, but it
  means preflight and splice decode differently.
- **A second splice implementation survives** at `graph_projections.py:184-230`
  for the no-HUMAN case. Fed faithful bytes today, so not a live defect, but it
  would silently inherit any future translating read.
- **Adjacent digest-fidelity defects, out of scope and pre-existing.**
  `chatgpt_bridge.py:66-74` and `openai_import_real.py:68-77` hash the
  *translated* text of an operator-supplied file and store it as
  `source_sha256` beside the path and size, so for a CRLF input the receipt's
  digest can never match the file it names; in the latter `source_sha256` and
  `source_bytes` are mutually inconsistent. `obsidian_capture.py:737` already
  does this correctly via `read_bytes().decode()`. Separate defect class,
  separate package — deliberately not folded in.

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

**Suites:** the F1–F4 + capture + projection set — enumerated, because the
figure was previously unreproducible as stated:
`test_as_obsidian_capture_001.py`, `test_as_obsidian_capture_001_f3.py`,
`test_as_graph_005_projections.py`, `test_as_graph_005_adversarial.py`,
`test_as_graph_005_f4_canonical_semantics.py`,
`test_as_coder_alpha_obsidian_001.py`, `test_as_coder_alpha_obsidian_r1_001.py`
and this package's own file — **264 passed, 4 xfailed**. The certified-surface freeze guard
(`test_atlas3_demo_isolation_001`, 78 tests) passes, confirming this candidate
touches no frozen surface. `ruff check .` clean; `mypy src` clean (405 files).

## Claim boundary

Claimed: CR-bearing line endings inside HUMAN regions survive a refresh
byte-for-byte at the **three live** generated-span-preserving writers fixed
here; note ownership no longer depends on line endings; and identity hashing is
unchanged.

(An earlier revision of this sentence said "all four writers", which
contradicted the very next paragraph and was measurably false — independent
verification recorded the fourth writer at CR 3 → 0 on this exact head. It is
corrected rather than softened, because this paragraph is the one most likely
to be cited downstream as certification.)

**Not claimed:** that the fourth writer is fixed — `ingestion.py` is
unchanged here and its defect is live on `main`, owner-gated as F5-B; general
byte fidelity for every transformation; that notes already normalised by a
previous refresh are recoverable (they are not — this stops further loss, it
does not undo it); that non-newline normalisation elsewhere is absent; or that
Obsidian note corruption in general is solved.

Implementation evidence, not certification. Independent exact-head verification
and CI are required before merge, and merge authority is not this lane's.
